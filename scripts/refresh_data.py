"""
refresh_data.py
───────────────
Rebuilds schools.json from scratch every month using four official sources:

  1. GIAS  — Get Information About Schools (school register, all London schools)
  2. Ofsted — Monthly management information CSV (latest Ofsted ratings)
  3. EES   — Explore Education Statistics API (KS2/KS4 exam results, FSM data)
  4. Police API — Crime data within 500m of each school

Run manually or via GitHub Actions on the 15th of each month.

Requirements: pip install requests pandas numpy pyyaml
"""

import io
import re
import json
import time
import zipfile
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_FILE = "schools.json"

# Fields to preserve from the existing schools.json that don't come from official sources
# These are carried over when the API fetch returns None/empty
PRESERVE_FIELDS = [
    # School profile
    "website", "ofsted_url", "mat_name", "lsoa_code",
    "imd_rank", "imd_decile", "imd_score",
    "num_boys", "num_girls", "snobe_url",
    # Coordinates — preserved if GIAS fetch returns None
    "lat", "lng",
    # Exam results — preserved when EES API is unavailable
    "ks2_expected_pct", "ks2_higher_pct",
    "ks4_att8", "ks4_pupils", "ks4_grade5_em", "ks4_grade4_em",
    # Admissions — preserved when DfE data unavailable
    "places", "first_pref_applications", "first_pref_offers",
    "total_applications", "apps_per_place", "first_pref_success_pct",
    # Crime — preserved when Police API is unavailable
    "crime_count", "crime_score", "crime_label",
    # Ofsted ratings — preserved for schools not in monthly MI (independents + awaiting inspection)
    # Fresh Ofsted data from MI always overwrites these — merge_existing only fills gaps
    "quality_label", "quality_raw", "ofsted_score", "score_band",
    "behaviour_raw", "personal_dev_raw", "leadership_raw", "safeguarding",
    "inspection_date", "ungraded_outcome",
    "rc_curriculum", "rc_achievement", "rc_attendance", "rc_leadership", "rc_safeguarding",
    # Deprivation
    "idaci_quintile", "fsm_label",
]

LONDON_LAS = {
    "Barking and Dagenham", "Barnet", "Bexley", "Brent", "Bromley",
    "Camden", "City of London", "Croydon", "Ealing", "Enfield",
    "Greenwich", "Hackney", "Hammersmith and Fulham", "Haringey",
    "Harrow", "Havering", "Hillingdon", "Hounslow", "Islington",
    "Kensington and Chelsea", "Kingston upon Thames", "Lambeth",
    "Lewisham", "Merton", "Newham", "Redbridge", "Richmond upon Thames",
    "Southwark", "Sutton", "Tower Hamlets", "Waltham Forest",
    "Wandsworth", "Westminster",
}

# School phases to include (exclude further education, nursery-only etc.)
VALID_PHASES = {
    "Primary", "Secondary", "Middle deemed primary", "Middle deemed secondary",
    "All-through", "16 plus", "Not applicable", "Nursery",
}

# Establishment types to exclude (not schools)
EXCLUDE_TYPES = {
    "Higher education institutions", "Further education",
    "Online provider", "British schools overseas",
}

# ── Step 1: GIAS — Get Information About Schools ──────────────────────────────

GIAS_URL = "https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public/edubasealldata{date}.csv"
GIAS_FALLBACK_URL = "https://get-information-schools.service.gov.uk/api/download?datasetId=all-current-open-establishments"

def fetch_gias():
    """
    Download the full GIAS dataset and filter to open London schools.
    Returns a DataFrame with one row per school.
    """
    print("Step 1: Fetching GIAS school register...")

    # Try today's dated URL first, then fall back to previous days
    df = None
    for days_ago in range(0, 7):
        date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")
        url = GIAS_URL.format(date=date_str)
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                df = pd.read_csv(
                    io.BytesIO(r.content),
                    encoding="latin-1",
                    low_memory=False,
                )
                print(f"  Downloaded GIAS data from {date_str} ({len(df):,} rows)")
                break
        except Exception:
            continue

    if df is None:
        # Try fallback URL
        try:
            r = requests.get(GIAS_FALLBACK_URL, timeout=60)
            r.raise_for_status()
            df = pd.read_csv(io.BytesIO(r.content), encoding="latin-1", low_memory=False)
            print(f"  Downloaded GIAS via fallback ({len(df):,} rows)")
        except Exception as e:
            print(f"  GIAS download failed: {e}")
            return pd.DataFrame()

    # Filter to open London schools
    df.columns = df.columns.str.strip()

    # Status filter — only open schools
    if "EstablishmentStatus (name)" in df.columns:
        df = df[df["EstablishmentStatus (name)"].str.strip() == "Open"]

    # LA filter — London only
    la_col = next((c for c in df.columns if "la" in c.lower() and "name" in c.lower()), None)
    if la_col:
        df[la_col] = df[la_col].astype(str).str.strip()
        df = df[df[la_col].isin(LONDON_LAS)]

    # Phase filter
    phase_col = next((c for c in df.columns if "phase" in c.lower() and "education" in c.lower()), None)

    # Remove non-school establishment types
    type_col = next((c for c in df.columns if "typeofestablishment" in c.lower().replace(" ", "") and "name" in c.lower()), None)
    if type_col:
        df = df[~df[type_col].isin(EXCLUDE_TYPES)]

    print(f"  London open schools: {len(df):,}")
    return df


def parse_gias(df):
    """
    Map GIAS columns to our schools.json field names.
    Returns list of school dicts.
    """
    col = {}
    for c in df.columns:
        cl = c.lower().replace(" ", "").replace("(name)", "").replace("(", "").replace(")", "")
        col[cl] = c

    def g(key, default=None):
        """Get value safely from a row using fuzzy column name."""
        return col.get(key, default)

    schools = []
    for _, row in df.iterrows():
        def v(key, fallback=None):
            c = g(key)
            if c and c in row.index:
                val = row[c]
                if pd.isna(val):
                    return fallback
                if isinstance(val, float) and val == int(val):
                    return int(val)
                return val
            return fallback

        # Build head name
        head_title_prefix = v("headtitlename", "") or v("headtitle", "") or v("headtitlename", "") or ""
        head_first = v("headfirstname", "")
        head_last  = v("headlastname", "")
        # Build full name with title prefix, ensuring spaces between each part
        parts = [p.strip() for p in [head_title_prefix, head_first, head_last] if p and str(p).strip()]
        head_name = " ".join(parts) or None

        school = {
            "urn":               v("urn"),
            "name":              v("establishmentname"),
            "local_authority":   v("la"),
            "postcode":          v("postcode"),
            "phase":             v("phaseofeducation"),
            "school_type":       v("typeofestablishment"),
            "age_from":          v("statutorylowage"),
            "age_to":            v("statutoryhighage"),
            "sixth_form":        v("officialsixthform"),
            "gender":            v("gender"),
            "admissions":        v("admissionspolicy"),
            "pupils":            v("numberofpupils"),
            "capacity":          v("schoolcapacity"),
            "religious_character": v("religiouscharacter"),
            "diocese":           v("diocese"),
            "trust_name":        v("trusts"),
            "website":           v("schoolwebsite"),
            "telephone":         v("telephonenum"),
            "head_job_title":    v("headpreferredjobtitle", "Headteacher"),
            "head_name":         head_name,
            "street":            v("street"),
            "town":              v("town"),
            "lat":               v("latitude"),
            "lng":               v("longitude"),
            "lsoa_code":         v("lsoa"),
            "constituency":      v("constituencyparliamentary"),
            # Ofsted fields — filled in later
            "quality_label":     None,
            "quality_raw":       None,
            "ofsted_score":      None,
            "score_band":        None,
            "behaviour_raw":     None,
            "personal_dev_raw":  None,
            "leadership_raw":    None,
            "safeguarding":      None,
            "inspection_date":   None,
            "ofsted_url":        None,
            "ofsted_pupils":     None,
            "ungraded_outcome":  None,
            "rc_curriculum":     None,
            "rc_achievement":    None,
            "rc_attendance":     None,
            "rc_leadership":     None,
            "rc_safeguarding":   None,
            # Exam results — filled in later
            "ks2_higher_pct":    None,
            "ks2_expected_pct":  None,
            "ks4_pupils":        None,
            "ks4_att8":          None,
            "ks4_grade5_em":     None,
            "ks4_grade4_em":     None,
            # Admissions — filled in later
            "places":            None,
            "first_pref_applications": None,
            "total_applications":      None,
            "first_pref_offers":       None,
            "apps_per_place":          None,
            "first_pref_success_pct":  None,
            # Crime — filled in later
            "crime_count":       None,
            "crime_score":       None,
            "crime_label":       None,
            # FSM/deprivation — filled in later
            "pct_fsm":           None,
            "imd_rank":          None,
            "imd_decile":        None,
            "imd_score":         None,
            "fsm_quintile":      None,
            "fsm_label":         None,
            "fsm_color":         None,
            "fsm_bg":            None,
            # Boys/girls
            "num_boys":          v("numberofboys"),
            "num_girls":         v("numberofgirls"),
            "mat_name":          None,
        }

        # Normalise sixth form field
        sf = str(school.get("sixth_form", "")).strip().lower()
        if sf in ("1", "true", "yes"):
            school["sixth_form"] = "Has a sixth form"
        elif sf in ("0", "false", "no"):
            school["sixth_form"] = "Does not have a sixth form"

        # Normalise lat/lng to float
        for coord in ("lat", "lng"):
            try:
                school[coord] = float(school[coord]) if school[coord] is not None else None
            except (ValueError, TypeError):
                school[coord] = None
        # Generate Snobe URL — matches Snobe slug format
        # Snobe uses /nursery/ prefix for nurseries, /schools/ for everything else
        # Stop words are removed from slugs
        SNOBE_STOP_WORDS = {"the", "of", "for", "and", "a", "at", "in", "by", "with", "an"}
        name_val  = school.get("name", "")
        phase_val = str(school.get("phase", "")).lower()
        type_val  = str(school.get("school_type", "")).lower()

        is_nursery = (
            phase_val == "nursery" or
            "nursery" in type_val or
            "nursery" in str(name_val).lower()
        )
        snobe_prefix = "nursery" if is_nursery else "schools"

        if name_val:
            words = str(name_val).lower()                .replace("’", "").replace("‘", "").replace("'", "")                .replace(",", "").replace(".", "").replace("(", "").replace(")", "")                .strip().split()
            filtered = [w for w in words if w not in SNOBE_STOP_WORDS]
            snobe_slug = "-".join(filtered)
            snobe_slug = re.sub(r"-+", "-", snobe_slug).strip("-")
            school["snobe_url"] = f"https://snobe.co.uk/{snobe_prefix}/{snobe_slug}"
        else:
            school["snobe_url"] = None

        if school["urn"] and school["name"]:
            schools.append(school)

    print(f"  Parsed {len(schools):,} schools from GIAS")
    return schools


# ── Step 2: Ofsted monthly management information ─────────────────────────────

OFSTED_MI_PAGE = (
    "https://www.gov.uk/government/statistical-data-sets/"
    "monthly-management-information-ofsteds-school-inspections-outcomes"
)

GRADE_MAP = {
    "1": ("Outstanding",            1, 100),
    "2": ("Good",                   2, 80),
    "3": ("Requires improvement",   3, 40),
    "4": ("Inadequate",             4, 0),
}

FSM_QUINTILE_MAP = {
    1: ("Low pupil deprivation",    "#2E7D32", "#E8F5E9"),
    2: ("Below average deprivation","#558B2F", "#F1F8E9"),
    3: ("Average pupil deprivation","#F9A825", "#FFFDE7"),
    4: ("Above average deprivation","#E65100", "#FFF3E0"),
    5: ("High pupil deprivation",   "#B71C1C", "#FFEBEE"),
}

def fetch_ofsted():
    """
    Download Ofsted monthly management information and return
    URN → dict of Ofsted fields.
    """
    print("Step 2: Fetching Ofsted monthly management information...")

    try:
        r = requests.get(OFSTED_MI_PAGE, timeout=30)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"  Could not fetch Ofsted MI page: {e}")
        return {}

    # Find the most recent CSV download link
    csv_links = re.findall(r'href="(https://[^"]+\.csv[^"]*)"', html)
    if not csv_links:
        # Try without https requirement
        csv_links = re.findall(r'href="([^"]+\.csv[^"]*)"', html)

    if not csv_links:
        print("  No CSV link found on Ofsted MI page")
        return {}

    csv_url = csv_links[0]
    if csv_url.startswith("/"):
        csv_url = "https://www.gov.uk" + csv_url

    print(f"  Downloading: {csv_url}")
    try:
        r2 = requests.get(csv_url, timeout=90)
        r2.raise_for_status()
        df = pd.read_csv(io.BytesIO(r2.content), encoding="latin-1", low_memory=False)
    except Exception as e:
        print(f"  Could not download Ofsted CSV: {e}")
        return {}

    print(f"  Ofsted rows: {len(df):,}")
    df.columns = df.columns.str.strip()

    # Find column names — they vary between releases
    urn_col       = next((c for c in df.columns if c.strip().lower() in ("urn", "school urn")), None)
    overall_col   = next((c for c in df.columns if "overall" in c.lower() and "effectiveness" in c.lower()), None)
    quality_col   = next((c for c in df.columns if "quality" in c.lower() and "education" in c.lower()), None)
    behaviour_col = next((c for c in df.columns if "behaviour" in c.lower()), None)
    personal_col  = next((c for c in df.columns if "personal" in c.lower() and "development" in c.lower()), None)
    leadership_col= next((c for c in df.columns if "leadership" in c.lower() and "management" in c.lower()), None)
    safeguard_col = next((c for c in df.columns if "safeguard" in c.lower()), None)
    date_col      = next((c for c in df.columns if "inspection" in c.lower() and "date" in c.lower()), None)
    url_col       = next((c for c in df.columns if "web" in c.lower() or "url" in c.lower() or "link" in c.lower()), None)
    pupils_col    = next((c for c in df.columns if "pupil" in c.lower() and ("number" in c.lower() or "roll" in c.lower())), None)

    if not urn_col:
        print("  Could not find URN column in Ofsted data")
        return {}

    mapping = {}
    for _, row in df.iterrows():
        try:
            urn = int(float(str(row[urn_col]).strip()))
        except (ValueError, TypeError):
            continue

        def get_grade(col):
            if not col:
                return None
            val = str(row.get(col, "")).strip()
            if val in ("", "nan", "N/A"):
                return None
            return val

        overall   = get_grade(overall_col)
        quality   = get_grade(quality_col)
        behaviour = get_grade(behaviour_col)
        personal  = get_grade(personal_col)
        leadership= get_grade(leadership_col)

        # Map numeric grade to label
        label, raw, score = None, None, None
        if overall and overall in GRADE_MAP:
            label, raw, score = GRADE_MAP[overall]
        elif overall:
            # Try text match
            for text in ("Outstanding", "Good", "Requires improvement", "Inadequate"):
                if text.lower() in overall.lower():
                    label = text
                    raw = list(GRADE_MAP.keys())[[v[0] for v in GRADE_MAP.values()].index(text)]
                    _, raw_int, score = GRADE_MAP[raw]
                    raw = raw_int
                    break

        def grade_to_int(g):
            if g and g in GRADE_MAP:
                return GRADE_MAP[g][1]
            return None

        mapping[urn] = {
            "quality_label":    label,
            "quality_raw":      raw,
            "ofsted_score":     score,
            "score_band":       label,
            "behaviour_raw":    grade_to_int(behaviour),
            "personal_dev_raw": grade_to_int(personal),
            "leadership_raw":   grade_to_int(leadership),
            "safeguarding":     get_grade(safeguard_col),
            "inspection_date":  get_grade(date_col),
            "ofsted_url":       get_grade(url_col),
            "ofsted_pupils":    row.get(pupils_col) if pupils_col else None,
        }

    print(f"  Ofsted ratings mapped: {len(mapping):,}")
    return mapping


def apply_ofsted(schools, ofsted_map):
    """Merge Ofsted data into school records.

    For schools inspected under the new Sept 2024+ Report Card framework,
    Ofsted no longer gives an overall effectiveness grade.
    We derive a display label from the sub-grades instead.
    """
    updated = 0
    report_card = 0
    for s in schools:
        urn = s.get("urn")
        if urn and int(urn) in ofsted_map:
            s.update(ofsted_map[int(urn)])
            updated += 1
            # Handle new Report Card framework (Sept 2024+)
            # No overall grade — derive from sub-grades
            if not s.get("quality_label") and not s.get("ofsted_score"):
                sub_grades = [
                    s.get("behaviour_raw"),
                    s.get("personal_dev_raw"),
                    s.get("leadership_raw"),
                ]
                sub_grades = [g for g in sub_grades if g is not None]
                if sub_grades:
                    worst = max(sub_grades)
                    if worst == 1:
                        label, score = "Outstanding", 100
                    elif worst == 2:
                        label, score = "Good", 75
                    elif worst == 3:
                        label, score = "Requires improvement", 35
                    else:
                        label, score = "Inadequate", 0
                    s["quality_label"] = label
                    s["ofsted_score"] = score
                    s["score_band"] = label
                    s["quality_raw"] = worst
                    report_card += 1
    print(f"  Applied Ofsted data to {updated:,} schools")
    if report_card:
        print(f"  Derived Report Card ratings for {report_card:,} schools (new 2024+ framework)")
    return schools


# ── Step 3: EES — Exam results and FSM data ───────────────────────────────────

EES_KS2_URL  = "https://content.explore-education-statistics.service.gov.uk/api/releases/latest/data-sets/key-stage-2-attainment-school-level"
EES_KS4_URL  = "https://content.explore-education-statistics.service.gov.uk/api/releases/latest/data-sets/key-stage-4-performance-revised"
EES_FSM_URL  = "https://content.explore-education-statistics.service.gov.uk/api/releases/latest/data-sets/school-level-underlying-data"

# Direct CSV download URLs (stable)
KS2_CSV_URL = "https://content.explore-education-statistics.service.gov.uk/api/releases/latest/files/key-stage-2-attainment-national-and-local-authority-and-school-level/school-level-ks2.csv"
KS4_CSV_URL = "https://content.explore-education-statistics.service.gov.uk/api/releases/latest/files/key-stage-4-performance-revised/school-level-ks4.csv"

def fetch_ks2_results():
    """
    Fetch KS2 SATs results from EES.
    Tries multiple approaches in order. Returns URN → {ks2_expected_pct, ks2_higher_pct}.
    """
    print("Step 3a: Fetching KS2 SATs results from EES...")

    # Approach 1: EES content API — discovers latest release automatically
    try:
        api = "https://content.explore-education-statistics.service.gov.uk/api"
        pub = requests.get(f"{api}/publications/key-stage-2-attainment", timeout=30)
        if pub.ok:
            latest_slug = pub.json().get("latestReleaseSlug", "")
            if latest_slug:
                rel = requests.get(f"{api}/publications/key-stage-2-attainment/releases/{latest_slug}", timeout=30)
                if rel.ok:
                    data_sets = rel.json().get("downloadFiles", [])
                    for ds in data_sets:
                        name = ds.get("name", "").lower()
                        if "school" in name and ("level" in name or "underlying" in name):
                            dl_url = ds.get("url", "")
                            if dl_url:
                                r = requests.get(dl_url, timeout=120)
                                if r.ok:
                                    result = parse_ks2_csv(r.content)
                                    if result:
                                        print(f"  KS2 fetched via EES content API")
                                        return result
    except Exception as e:
        print(f"  KS2 content API failed: {e}")

    # Approach 2: EES statistics API — search for publication then download
    try:
        pub_url = "https://api.education.gov.uk/statistics/publications?search=key+stage+2+attainment&pageSize=5"
        r = requests.get(pub_url, timeout=30)
        if r.ok:
            pubs = r.json().get("results", [])
            for pub in pubs:
                if "key stage 2" in pub.get("title", "").lower() and "attainment" in pub.get("title", "").lower():
                    pub_id = pub.get("id")
                    rel_r = requests.get(
                        f"https://api.education.gov.uk/statistics/releases?publicationId={pub_id}&pageSize=1",
                        timeout=30
                    )
                    if rel_r.ok:
                        releases = rel_r.json().get("results", [])
                        if releases:
                            release_id = releases[0]["id"]
                            files_r = requests.get(
                                f"https://api.education.gov.uk/statistics/releases/{release_id}/files",
                                timeout=30
                            )
                            if files_r.ok:
                                for f in files_r.json().get("results", []):
                                    name = f.get("name", "").lower()
                                    if "school" in name and ("level" in name or "underlying" in name):
                                        dl = requests.get(
                                            f"https://api.education.gov.uk/statistics/releases/{release_id}/files/{f['id']}/download",
                                            timeout=120
                                        )
                                        if dl.ok:
                                            result = parse_ks2_csv(dl.content)
                                            if result:
                                                print(f"  KS2 fetched via statistics API")
                                                return result
    except Exception as e:
        print(f"  KS2 statistics API failed: {e}")

    print("  KS2 data unavailable — preserved fields will be used from existing data")
    return {}


def parse_ks2_csv(content):
    """Parse KS2 CSV and return URN mapping."""
    try:
        if content[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                with z.open(csv_names[0]) as f:
                    df = pd.read_csv(f, low_memory=False)
        else:
            df = pd.read_csv(io.BytesIO(content), encoding="latin-1", low_memory=False)
    except Exception as e:
        print(f"  Could not parse KS2 CSV: {e}")
        return {}

    df.columns = df.columns.str.strip().str.lower()

    urn_col      = next((c for c in df.columns if c == "urn"), None)
    expected_col = next((c for c in df.columns if "expected" in c and ("reading" in c or "rw" in c or "rwm" in c)), None)
    higher_col   = next((c for c in df.columns if "higher" in c and ("reading" in c or "rw" in c or "rwm" in c)), None)

    if not urn_col:
        return {}

    mapping = {}
    for _, row in df.iterrows():
        try:
            urn = int(float(str(row[urn_col])))
        except (ValueError, TypeError):
            continue
        mapping[urn] = {
            "ks2_expected_pct": _safe_float(row.get(expected_col)),
            "ks2_higher_pct":   _safe_float(row.get(higher_col)),
        }

    print(f"  KS2 results: {len(mapping):,} schools")
    return mapping


def fetch_ks4_results():
    """
    Fetch KS4 GCSE results from EES.
    Returns URN → {ks4_att8, ks4_grade5_em, ks4_grade4_em, ks4_pupils} mapping.
    """
    print("Step 3b: Fetching KS4 GCSE results from EES...")
    try:
        page = requests.get(
            "https://explore-education-statistics.service.gov.uk/find-statistics/key-stage-4-performance-revised",
            timeout=30
        )
        csv_links = re.findall(r'href="([^"]+school[^"]*\.csv[^"]*)"', page.text, re.IGNORECASE)
        for link in csv_links[:3]:
            if not link.startswith("http"):
                link = "https://explore-education-statistics.service.gov.uk" + link
            try:
                r = requests.get(link, timeout=90)
                if r.ok:
                    result = parse_ks4_csv(r.content)
                    if result:
                        return result
            except Exception:
                continue
    except Exception as e:
        print(f"  KS4 fetch failed: {e}")

    print("  KS4 data unavailable — skipping")
    return {}


def parse_ks4_csv(content):
    """Parse KS4 CSV and return URN mapping."""
    try:
        if content[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                with z.open(csv_names[0]) as f:
                    df = pd.read_csv(f, low_memory=False)
        else:
            df = pd.read_csv(io.BytesIO(content), encoding="latin-1", low_memory=False)
    except Exception as e:
        print(f"  Could not parse KS4 CSV: {e}")
        return {}

    df.columns = df.columns.str.strip().str.lower()

    urn_col    = next((c for c in df.columns if c == "urn"), None)
    att8_col   = next((c for c in df.columns if "att8" in c or "attainment8" in c or "attainment_8" in c), None)
    grade5_col = next((c for c in df.columns if "grade5" in c or "grade_5" in c or "5+" in c), None)
    grade4_col = next((c for c in df.columns if "grade4" in c or "grade_4" in c or "4+" in c), None)
    pupils_col = next((c for c in df.columns if "pupil" in c and ("number" in c or "count" in c or "total" in c)), None)

    if not urn_col:
        return {}

    mapping = {}
    for _, row in df.iterrows():
        try:
            urn = int(float(str(row[urn_col])))
        except (ValueError, TypeError):
            continue
        mapping[urn] = {
            "ks4_att8":       _safe_float(row.get(att8_col)),
            "ks4_grade5_em":  _safe_float(row.get(grade5_col)),
            "ks4_grade4_em":  _safe_float(row.get(grade4_col)),
            "ks4_pupils":     _safe_int(row.get(pupils_col)),
        }

    print(f"  KS4 results: {len(mapping):,} schools")
    return mapping


def apply_exam_results(schools, ks2_map, ks4_map):
    """Merge exam results into school records."""
    ks2_updated = ks4_updated = 0
    for s in schools:
        urn = s.get("urn")
        if not urn:
            continue
        if int(urn) in ks2_map:
            s.update(ks2_map[int(urn)])
            ks2_updated += 1
        if int(urn) in ks4_map:
            s.update(ks4_map[int(urn)])
            ks4_updated += 1
    print(f"  Applied KS2 to {ks2_updated:,} schools, KS4 to {ks4_updated:,} schools")
    return schools


# ── Step 4: Admissions data from EES ─────────────────────────────────────────

EES_API_BASE = "https://api.education.gov.uk/statistics"
ADM_SEARCH_TERMS = ["secondary school applications", "applications offers", "admissions"]

def _find_admissions_release_id():
    """Auto-discover the latest admissions release ID — never hardcodes a publication ID."""
    for term in ADM_SEARCH_TERMS:
        try:
            r = requests.get(
                f"{EES_API_BASE}/publications?search={requests.utils.quote(term)}&pageSize=5",
                timeout=30
            )
            if not r.ok:
                continue
            for pub in r.json().get("results", []):
                title = pub.get("title", "").lower()
                if "application" in title and ("offer" in title or "admission" in title):
                    pub_id = pub.get("id")
                    r2 = requests.get(
                        f"{EES_API_BASE}/releases?publicationId={pub_id}&pageSize=1",
                        timeout=30
                    )
                    if r2.ok:
                        results = r2.json().get("results", [])
                        if results:
                            return results[0]["id"]
        except Exception:
            continue
    return None

def fetch_admissions():
    """
    Fetch secondary school applications & offers from EES.
    Auto-discovers the latest release — no hardcoded publication IDs.
    Returns URN → {places, first_pref_applications, total_applications,
                    first_pref_offers, apps_per_place, first_pref_success_pct}
    """
    print("Step 4: Fetching admissions data from EES...")
    try:
        release_id = _find_admissions_release_id()
        if not release_id:
            print("  Could not discover admissions release — preserved data will be used")
            return {}

        r2 = requests.get(f"{EES_API_BASE}/releases/{release_id}/files", timeout=30)
        r2.raise_for_status()
        files = r2.json().get("results", [])

        # Pick the school-level file
        target = None
        for f in files:
            if "school" in f.get("name", "").lower():
                target = f
                break
        if not target and files:
            target = sorted(files, key=lambda x: x.get("size", 0), reverse=True)[0]
        if not target:
            return {}

        dl_url = f"{EES_API_BASE}/releases/{release_id}/files/{target['id']}/download"
        r3 = requests.get(dl_url, timeout=120)
        r3.raise_for_status()
        content = r3.content

        if content[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                csv_names.sort(key=lambda n: z.getinfo(n).file_size, reverse=True)
                with z.open(csv_names[0]) as f:
                    df = pd.read_csv(f, low_memory=False)
        else:
            df = pd.read_csv(io.BytesIO(content), low_memory=False)

        df.columns = df.columns.str.strip().str.lower()

        # Filter London
        la_col = next((c for c in df.columns if "la" in c and "name" in c), None)
        if la_col:
            df[la_col] = df[la_col].astype(str).str.strip()
            df = df[df[la_col].isin({la.lower() for la in LONDON_LAS})]

        urn_col  = next((c for c in df.columns if c == "urn"), None)
        # 1st-preference applications — column name changed across DfE releases
        app_col  = (next((c for c in df.columns if "1st" in c and "preference" in c and "applic" in c), None)
                    or next((c for c in df.columns if "times_put_as_1st" in c), None)
                    or next((c for c in df.columns if "1st_preference" in c and "times" in c), None))
        pan_col  = next((c for c in df.columns if "places" in c and ("offer" in c or "pan" in c or "number" in c)), None)
        off_col  = next((c for c in df.columns if "1st" in c and "offer" in c), None)
        # Total applications — column name changed across DfE releases
        tot_col  = (next((c for c in df.columns if "total" in c and "applic" in c), None)
                    or next((c for c in df.columns if "times_put_as_any" in c), None)
                    or next((c for c in df.columns if "any_preferred" in c and "times" in c), None))

        if not urn_col:
            print("  Could not find URN in admissions data")
            return {}

        mapping = {}
        for _, row in df.iterrows():
            try:
                urn = int(float(str(row[urn_col])))
            except (ValueError, TypeError):
                continue

            apps   = _safe_int(row.get(app_col))
            places = _safe_int(row.get(pan_col))
            offers = _safe_int(row.get(off_col))
            total  = _safe_int(row.get(tot_col))

            apps_per_place = None
            success_pct    = None
            if apps and places and places > 0:
                apps_per_place = round(apps / places, 1)
            if offers and apps and apps > 0:
                success_pct = round(offers / apps * 100, 1)

            mapping[urn] = {
                "places":                    places,
                "first_pref_applications":   apps,
                "total_applications":         total,
                "first_pref_offers":         offers,
                "apps_per_place":            apps_per_place,
                "first_pref_success_pct":    success_pct,
            }

        print(f"  Admissions data: {len(mapping):,} schools")
        return mapping

    except Exception as e:
        print(f"  Admissions fetch failed: {e}")
        return {}


def apply_admissions(schools, adm_map):
    """Merge admissions data into school records."""
    updated = 0
    for s in schools:
        urn = s.get("urn")
        if urn and int(urn) in adm_map:
            s.update(adm_map[int(urn)])
            updated += 1
    print(f"  Applied admissions data to {updated:,} schools")
    return schools


# ── Step 5: Police API — crime data ──────────────────────────────────────────

POLICE_API = "https://data.police.uk/api/crimes-street/all-crime"

def get_crime_date():
    """
    Get the most recent available month from the Police API.
    The API publishes data ~2 months in arrears.
    """
    try:
        r = requests.get("https://data.police.uk/api/crime-last-updated", timeout=10)
        if r.ok:
            date_str = r.json().get("date", "")
            if date_str:
                return date_str[:7]  # YYYY-MM
    except Exception:
        pass
    # Fallback: 2 months ago
    d = datetime.now()
    for _ in range(2):
        d = (d.replace(day=1) - timedelta(days=1))
    return d.strftime("%Y-%m")


def fetch_crime_for_school(lat, lng, date, radius_m=500):
    """Fetch crime count within radius_m of a lat/lng point."""
    if not lat or not lng:
        return None
    try:
        # Build polygon approximating a circle
        import math
        deg = radius_m / 111320
        poly = []
        for i in range(8):
            angle = math.pi * 2 * i / 8
            poly.append(f"{lat + deg * math.sin(angle)},{lng + deg * math.cos(angle)}")
        poly_str = ":".join(poly)

        r = requests.get(
            POLICE_API,
            params={"poly": poly_str, "date": date},
            timeout=20
        )
        if r.ok:
            return len(r.json())
    except Exception:
        pass
    return None


def score_crime(count, all_counts):
    """
    Score crime 0-100 (100 = lowest crime).
    Uses percentile rank within London schools.
    """
    if count is None or not all_counts:
        return None, None
    counts_sorted = sorted(all_counts)
    rank = counts_sorted.index(min(counts_sorted, key=lambda x: abs(x - count)))
    pct = 100 - round(rank / len(counts_sorted) * 100, 1)

    if pct >= 80:
        label = "Low crime area"
    elif pct >= 60:
        label = "Below average crime"
    elif pct >= 40:
        label = "Average crime"
    elif pct >= 20:
        label = "Above average crime"
    else:
        label = "High crime area"

    return round(pct, 1), label


def apply_crime(schools):
    """
    Fetch crime data for all schools and add crime_count, crime_score, crime_label.
    Batches requests to avoid rate limiting. Skips if API is unavailable.
    """
    print("Step 5: Fetching crime data from Police API...")
    
    # First check if Police API is reachable at all
    try:
        test = requests.get("https://data.police.uk/api/crime-last-updated", timeout=10)
        if not test.ok:
            print("  Police API unavailable — skipping crime data (will use preserved values)")
            return
    except Exception as e:
        print(f"  Police API unreachable ({e}) — skipping crime data")
        return

    crime_date = get_crime_date()
    print(f"  Using crime data month: {crime_date}")

    counts = []
    school_indices = []
    consecutive_failures = 0
    fetched = 0

    for i, s in enumerate(schools):
        lat, lng = s.get("lat"), s.get("lng")
        if lat and lng:
            count = fetch_crime_for_school(lat, lng, crime_date)
            if count is None:
                consecutive_failures += 1
            else:
                consecutive_failures = 0
                fetched += 1
            s["crime_count"] = count
            if count is not None:
                counts.append(count)
                school_indices.append(i)
            # Bail out after 20 consecutive failures — API is down
            if consecutive_failures >= 20:
                print(f"  Crime API failing consistently — stopping at {i} (fetched {fetched})")
                break
            # Early check: if first 100 schools with coords all return 0, date may be unavailable
            if i == 100 and fetched == 0 and sum(1 for x in schools[:100] if x.get("lat")) > 20:
                print(f"  Crime API returning no data after 100 schools — {crime_date} may be unavailable")
                print(f"  Skipping crime fetch — preserved data will be used")
                break
        # Rate limiting — Police API allows ~15 req/s
        if i % 10 == 0:
            time.sleep(0.5)
        if i % 100 == 0 and i > 0:
            print(f"  Crime data: {i}/{len(schools)} schools processed...")

    # Score all schools relative to each other
    for i, s in enumerate(schools):
        count = s.get("crime_count")
        if count is not None:
            score, label = score_crime(count, counts)
            s["crime_score"] = score
            s["crime_label"] = label

    print(f"  Crime data fetched for {len(counts):,} schools")
    return schools


# ── Step 6: FSM deprivation scoring ──────────────────────────────────────────

def apply_fsm_deprivation(schools):
    """
    Calculate FSM quintile and labels from pct_fsm.
    Quintile 1 = lowest FSM (least deprived), 5 = highest FSM (most deprived).
    """
    fsm_schools = [s for s in schools if s.get("pct_fsm") is not None]
    if not fsm_schools:
        return schools

    fsm_vals = sorted([s["pct_fsm"] for s in fsm_schools])
    n = len(fsm_vals)
    quintile_bounds = [fsm_vals[int(n * q / 5)] for q in range(1, 5)]

    for s in schools:
        pct = s.get("pct_fsm")
        if pct is None:
            continue
        q = 1
        for bound in quintile_bounds:
            if pct > bound:
                q += 1
        label, color, bg = FSM_QUINTILE_MAP[q]
        s["fsm_quintile"] = q
        s["fsm_label"]    = label
        s["fsm_color"]    = color
        s["fsm_bg"]       = bg

    return schools


# ── Helper functions ──────────────────────────────────────────────────────────

def _safe_float(val, decimals=1):
    try:
        f = float(str(val).replace("%", "").strip())
        if np.isnan(f):
            return None
        return round(f, decimals)
    except (ValueError, TypeError):
        return None


def _safe_int(val):
    try:
        f = float(str(val).strip())
        if np.isnan(f):
            return None
        return int(f)
    except (ValueError, TypeError):
        return None


def clean_school(s):
    """Final clean-up of a school dict before JSON serialisation."""
    cleaned = {}
    for k, v in s.items():
        if isinstance(v, float) and np.isnan(v):
            cleaned[k] = None
        elif isinstance(v, (np.integer,)):
            cleaned[k] = int(v)
        elif isinstance(v, (np.floating,)):
            cleaned[k] = None if np.isnan(v) else float(v)
        elif isinstance(v, str) and v.strip() in ("", "nan", "NaN", "N/A", "Not applicable"):
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


# ── Preserve existing enriched data ──────────────────────────────────────────

def load_existing(path="schools.json"):
    """
    Load the current schools.json and index by URN.
    Used to carry over fields that aren't available from official sources.
    """
    try:
        with open(path, encoding="utf-8") as f:
            existing = json.load(f)
        index = {int(s["urn"]): s for s in existing if s.get("urn")}
        print(f"  Loaded {len(index):,} existing schools from {path}")
        return index
    except FileNotFoundError:
        print(f"  No existing {path} found — starting fresh")
        return {}
    except Exception as e:
        print(f"  Could not load existing {path}: {e}")
        return {}


def merge_existing(schools, existing_map):
    """
    Merge preserved fields from the previous schools.json into fresh data.

    Rules:
    - Fresh official data (from APIs) always wins — never overwritten
    - If a field is None/missing in fresh data but exists in old data → carry over
    - This ensures crime, exam, admissions data survive when APIs are temporarily down
    - Schools that no longer exist in GIAS are dropped (not carried over)
    """
    carried = 0
    for s in schools:
        urn = s.get("urn")
        if not urn:
            continue
        old = existing_map.get(int(urn))
        if not old:
            continue
        changed = False
        for field in PRESERVE_FIELDS:
            new_val = s.get(field)
            old_val = old.get(field)
            # Only carry over if fresh data has nothing
            if new_val is None and old_val is not None:
                s[field] = old_val
                changed = True
        if changed:
            carried += 1
    print(f"  Carried over preserved fields for {carried:,} schools")
    return schools


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("refresh_data.py — London Schools Explorer")
    print(f"Running at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)
    print()

    # 1. GIAS — base school list
    gias_df = fetch_gias()
    if gias_df.empty:
        print("FATAL: Could not fetch GIAS data. Aborting.")
        return
    schools = parse_gias(gias_df)
    print(f"Base school list: {len(schools):,} schools\n")

    # 2. Ofsted ratings
    ofsted_map = fetch_ofsted()
    schools = apply_ofsted(schools, ofsted_map)
    print()

    # 3. Exam results
    ks2_map = fetch_ks2_results()
    ks4_map = fetch_ks4_results()
    schools = apply_exam_results(schools, ks2_map, ks4_map)
    print()

    # 4. Admissions
    adm_map = fetch_admissions()
    schools = apply_admissions(schools, adm_map)
    print()

    # 5. Crime data
    apply_crime(schools)
    print()

    # 6. FSM deprivation
    apply_fsm_deprivation(schools)

    # 7. Preserve fields from existing schools.json
    print("\nMerging preserved fields from existing data...")
    existing_map = load_existing()
    schools = merge_existing(schools, existing_map)

    # 8. Final clean and save
    schools = [clean_school(s) for s in schools]
    schools = [s for s in schools if s.get("name") and s.get("local_authority")]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(schools, f, ensure_ascii=False, separators=(",", ":"))

    print()
    print("=" * 60)
    print(f"Done. Saved {len(schools):,} schools to {OUTPUT_FILE}")
    print(
        f"  Ofsted rated:   {sum(1 for s in schools if s.get('quality_label')):,}\n"
        f"  With KS2 data:  {sum(1 for s in schools if s.get('ks2_expected_pct')):,}\n"
        f"  With KS4 data:  {sum(1 for s in schools if s.get('ks4_att8')):,}\n"
        f"  With crime data:{sum(1 for s in schools if s.get('crime_count') is not None):,}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
