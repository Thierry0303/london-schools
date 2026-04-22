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
    # Diagnostic: check coordinate columns
    coord_cols = [c for c in df.columns if any(k in c.lower() for k in ("lat", "lon", "lng", "geo", "east", "north", "coord", "point", "x_", "y_", "_x", "_y"))]
    if coord_cols:
        print(f"  Coordinate columns found: {coord_cols[:8]}")
    else:
        print(f"  WARNING: No coordinate columns found in GIAS data!")
        print(f"  All GIAS columns (first 60): {list(df.columns[:60])}")
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
    # "Category of concern" — populated for schools in Special Measures, Serious Weaknesses etc.
    category_col  = next((c for c in df.columns if "category" in c.lower() and "concern" in c.lower()), None)
    # Monitoring outcome — for schools with monitoring inspections after RI/Inadequate
    monitoring_col = next((c for c in df.columns if "monitoring" in c.lower() and "outcome" in c.lower()), None)

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

        # Build ungraded_outcome from category of concern and/or monitoring outcome
        category   = get_grade(category_col)
        monitoring = get_grade(monitoring_col)
        ungraded   = None
        if monitoring and monitoring.lower() not in ("", "n/a", "not applicable"):
            ungraded = monitoring
        elif category and category.lower() not in ("", "n/a", "not applicable", "none"):
            ungraded = category

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
            "ungraded_outcome": ungraded,
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
EES_KS4_URL  = "https://content.explore-education-statistics.service.gov.uk/api/releases/latest/data-sets/key-stage-4-performance"
EES_FSM_URL  = "https://content.explore-education-statistics.service.gov.uk/api/releases/latest/data-sets/school-level-underlying-data"

# Direct CSV download URLs (stable)
KS2_CSV_URL = "https://content.explore-education-statistics.service.gov.uk/api/releases/latest/files/key-stage-2-attainment-national-and-local-authority-and-school-level/school-level-ks2.csv"
KS4_CSV_URL = "https://content.explore-education-statistics.service.gov.uk/api/releases/latest/files/key-stage-4-performance-revised/school-level-ks4.csv"


def _find_urn_col(columns):
    """
    Find the URN column in a DataFrame column list, trying multiple name variants.
    EES content API files use 'urn'; EES stats API flat-format files use 'institution_id'
    or 'school_urn'. Returns the column name or None.
    """
    cols_lower = [c.lower().strip() for c in columns]
    # Exact matches first
    for exact in ("urn", "institution_id", "school_urn", "new_urn", "urn_number"):
        if exact in cols_lower:
            return columns[cols_lower.index(exact)]
    # Substring: column whose name IS just "urn" after stripping common prefixes
    for c in columns:
        cl = c.lower().strip()
        if cl.endswith("_urn") or cl.startswith("urn_"):
            return c
    # Broadest fallback: any column containing "urn"
    for c in columns:
        if "urn" in c.lower():
            return c
    return None

def _ees_content_api_download(pub_slug, file_keyword, label):
    """
    Generic helper: use EES content API to download the latest release file for a publication.
    Picks the largest file whose name contains file_keyword (or any file if keyword is None).
    Returns raw bytes or None.
    """
    api = "https://content.explore-education-statistics.service.gov.uk/api"
    try:
        pub_r = requests.get(f"{api}/publications/{pub_slug}", timeout=30)
    except Exception as e:
        print(f"  [{label}] Content API connection error: {e}")
        return None
    if not pub_r.ok:
        print(f"  [{label}] Content API /publications/{pub_slug} → HTTP {pub_r.status_code}")
        return None
    pub_data = pub_r.json()
    # Handle different field names for the latest release slug across API versions
    latest_slug = (
        pub_data.get("latestReleaseSlug")
        or pub_data.get("latestRelease", {}).get("slug")
        or (pub_data.get("releases") or [{}])[0].get("slug", "")
    )
    print(f"  [{label}] Content API pub keys: {list(pub_data.keys())[:10]}")
    if not latest_slug:
        print(f"  [{label}] Content API: could not determine latestReleaseSlug from response")
        return None
    rel_r = requests.get(f"{api}/publications/{pub_slug}/releases/{latest_slug}", timeout=30)
    if not rel_r.ok:
        print(f"  [{label}] Content API release/{latest_slug} → HTTP {rel_r.status_code}")
        return None
    rel_data  = rel_r.json()
    release_id = rel_data.get("id", "")
    dl_files  = rel_data.get("downloadFiles", [])
    print(f"  [{label}] Content API: {len(dl_files)} download files in release '{latest_slug}' (id={release_id[:8]}...)")
    if dl_files:
        print(f"    File names: {[f.get('name','?') for f in dl_files[:5]]}")
    if not dl_files:
        return None

    # Log first file object's full structure so we know what fields the API returns
    if dl_files:
        first = dl_files[0]
        print(f"  [{label}] File[0] keys: {list(first.keys())}")
        print(f"  [{label}] File[0] sample: id={str(first.get('id',''))[:24]} name={first.get('name','')} size={first.get('size',0)}")

    # Build a prioritised list of download URL candidates for a given file object.
    # Priority based on empirical evidence: releases/{releaseId}/files/{fileId} (no /download)
    # is a live EES Content API endpoint (seen in Google-indexed URLs).
    def _build_dl_urls(f):
        urls = []
        fid = str(f.get("id", ""))
        # 1) Direct URL fields (populated in some API versions)
        for field in ("url", "href", "downloadUrl", "path"):
            val = f.get(field, "")
            if val and val.startswith("http"):
                urls.append(val)
        if fid:
            # 2) Release-ID-based WITHOUT /download — confirmed live URL format
            if release_id:
                urls.append(f"{api}/releases/{release_id}/files/{fid}")
            # 3) Slug-based (alternative format)
            urls.append(f"{api}/publications/{pub_slug}/releases/{latest_slug}/files/{fid}")
            # 4) Variants with /download suffix
            if release_id:
                urls.append(f"{api}/releases/{release_id}/files/{fid}/download")
            urls.append(f"{api}/publications/{pub_slug}/releases/{latest_slug}/files/{fid}/download")
        return urls

    def _fetch_file_content(url, name, label):
        """
        Fetch a URL and return binary content.
        Handles two cases:
          a) Direct binary response (CSV or ZIP) → returned as-is
          b) JSON response with a 'url'/'href' field → follow that URL for the actual file
        """
        url_short = url.split("/api/")[-1]
        r = requests.get(url, timeout=120, allow_redirects=True)
        ct = r.headers.get("Content-Type", "")
        print(f"  [{label}] '{name}' [{url_short}] → HTTP {r.status_code}, {len(r.content):,} bytes, ct={ct[:40]}")
        if not r.ok:
            return None
        # If small JSON response — try to extract a download URL from it
        if len(r.content) < 5000 and "json" in ct.lower():
            try:
                jdata = r.json()
                for key in ("url", "href", "downloadUrl", "path", "fileUrl"):
                    redirect = jdata.get(key, "")
                    if redirect and redirect.startswith("http"):
                        print(f"  [{label}] JSON redirect → {redirect[:80]}")
                        r2 = requests.get(redirect, timeout=120, allow_redirects=True)
                        print(f"  [{label}] Redirect → HTTP {r2.status_code}, {len(r2.content):,} bytes")
                        if r2.ok and len(r2.content) > 1000:
                            return r2.content
                print(f"  [{label}] JSON keys: {list(jdata.keys())}")
            except Exception:
                pass
            return None
        if len(r.content) > 1000:
            return r.content
        return None

    # Pick best matching file(s) by keyword
    candidates = []
    for f in dl_files:
        name = f.get("name", "").lower()
        size = f.get("size", 0) or 0
        urls = _build_dl_urls(f)
        if not urls:
            continue
        if file_keyword and file_keyword not in name:
            continue
        candidates.append((size, name, f, urls))

    if not candidates and file_keyword:
        # Fall back: no keyword match — try all files
        print(f"  [{label}] No files matched keyword '{file_keyword}' — trying all {len(dl_files)} files")
        candidates = [
            (_f.get("size", 0) or 0, _f.get("name", "").lower(), _f, _build_dl_urls(_f))
            for _f in dl_files if _build_dl_urls(_f)
        ]

    if not candidates:
        print(f"  [{label}] No downloadable files found")
        return None

    # Prefer largest file (most likely school-level data)
    candidates.sort(reverse=True)
    for _, name, f, urls in candidates:
        for url in urls:
            try:
                content = _fetch_file_content(url, name, label)
                if content:
                    print(f"  {label}: downloaded '{name}' ({len(content)//1024} KB) via content API")
                    return content
            except Exception as e:
                url_short = url.split("/api/")[-1]
                print(f"  [{label}] '{name}' [{url_short}] → Exception: {e}")
                continue
    return None


def _ees_stats_api_download(search_term, file_keyword, label):
    """
    Use EES statistics API v1 to find a publication, list its data sets, and download a CSV.
    v1 API path: /publications → /publications/{id}/data-sets → /data-sets/{id}/file
    Returns raw bytes or None.
    """
    base = EES_API_BASE  # https://api.education.gov.uk/statistics/v1
    try:
        pub_r = requests.get(
            f"{base}/publications?search={requests.utils.quote(search_term)}&pageSize=5",
            timeout=30
        )
    except Exception as e:
        print(f"  [{label}] Stats API connection error: {e}")
        return None
    if not pub_r.ok:
        print(f"  [{label}] Stats API search '{search_term}' → HTTP {pub_r.status_code}")
        return None
    pubs = pub_r.json().get("results", [])
    if not pubs:
        print(f"  [{label}] Stats API search '{search_term}' → 0 results")
        return None
    print(f"  [{label}] Stats API found: {[p.get('title','?') for p in pubs[:3]]}")

    # v1 API: list data sets for the publication (v1 doesn't have a /releases endpoint)
    pub_id = pubs[0]["id"]
    ds_r = requests.get(f"{base}/publications/{pub_id}/data-sets?pageSize=20", timeout=30)
    if not ds_r.ok:
        print(f"  [{label}] /data-sets endpoint → HTTP {ds_r.status_code}")
        return None
    data_sets = ds_r.json().get("results", [])
    if not data_sets:
        print(f"  [{label}] No data sets found for publication")
        return None
    print(f"  [{label}] Data sets: {[d.get('title','?') for d in data_sets[:4]]}")

    # Rank: prefer data sets with keyword in title, then by result count (largest = most granular)
    ranked = []
    for ds in data_sets:
        title  = ds.get("title", "").lower()
        dsid   = ds.get("id", "")
        total  = (ds.get("latestVersion") or {}).get("totalResults", 0) or 0
        if not dsid:
            continue
        score  = 1 if (file_keyword and file_keyword in title) else 0
        ranked.append((-score, -total, title, dsid))
    ranked.sort()

    for _, _, title, dsid in ranked:
        # Try several possible download endpoint patterns for the v1 data-sets API
        for dl_path in [
            f"{base}/data-sets/{dsid}/file",
            f"{base}/data-sets/{dsid}/versions/latest/file",
            f"{base}/data-sets/{dsid}/csv",
        ]:
            try:
                dl = requests.get(dl_path, timeout=120, allow_redirects=True)
                print(f"  [{label}] {'/'.join(dl_path.split('/')[-2:])} → HTTP {dl.status_code}, {len(dl.content):,} bytes")
                if dl.ok and len(dl.content) > 1000:
                    print(f"  {label}: downloaded '{title}' ({len(dl.content)//1024} KB) via v1 data-sets API")
                    return dl.content
            except Exception as e:
                print(f"  [{label}] {dl_path.split('/')[-1]}: {e}")
    return None


def fetch_ks2_results():
    """
    Fetch KS2 SATs results from EES.
    Tries multiple approaches in order. Returns URN → {ks2_expected_pct, ks2_higher_pct}.
    """
    print("Step 3a: Fetching KS2 SATs results from EES...")

    # Approach 1: EES content API — discovers latest release automatically
    try:
        content = _ees_content_api_download("key-stage-2-attainment", "school", "KS2")
        if content:
            result = parse_ks2_csv(content)
            if result:
                return result
    except Exception as e:
        print(f"  KS2 content API failed: {e}")

    # Approach 2: EES statistics API — search for publication then download
    try:
        content = _ees_stats_api_download("key stage 2 attainment", "school", "KS2")
        if content:
            result = parse_ks2_csv(content)
            if result:
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

    # Filter to institution-level rows only (EES flat format has multiple geographic levels)
    if "geographic_level" in df.columns:
        df = df[df["geographic_level"].str.lower().isin({"institution", "school"})]

    urn_col = _find_urn_col(df.columns.tolist())
    if not urn_col:
        print(f"  KS2 parse: no URN column found. Columns: {list(df.columns[:20])}")
        return {}

    expected_col = (
        next((c for c in df.columns if "expected" in c and "rwm" in c), None)
        or next((c for c in df.columns if "expected" in c and "rw" in c), None)
        or next((c for c in df.columns if "expected" in c and "reading" in c), None)
        or next((c for c in df.columns if "expected" in c and "standard" in c), None)
        or next((c for c in df.columns if "pt_met_expected" in c or "pct_expected" in c), None)
    )
    higher_col = (
        next((c for c in df.columns if "higher" in c and "rwm" in c), None)
        or next((c for c in df.columns if "higher" in c and "rw" in c), None)
        or next((c for c in df.columns if "higher" in c and "reading" in c), None)
        or next((c for c in df.columns if "higher" in c and "standard" in c), None)
        or next((c for c in df.columns if "pt_achieved_higher" in c or "pct_higher" in c), None)
    )
    print(f"  KS2 parse: urn={urn_col} expected={expected_col} higher={higher_col} rows={len(df)}")

    mapping = {}
    for _, row in df.iterrows():
        try:
            urn = int(float(str(row[urn_col])))
        except (ValueError, TypeError):
            continue
        if urn <= 0:
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

    # Approach 1: EES content API
    try:
        content = _ees_content_api_download("key-stage-4-performance", "school", "KS4")
        if content:
            result = parse_ks4_csv(content)
            if result:
                return result
    except Exception as e:
        print(f"  KS4 content API failed: {e}")

    # Approach 2: EES statistics API — try keywords most likely to have school-level att8
    for ks4_kw in ("performance tables", "attainment 8", "school performance", "school"):
        try:
            content = _ees_stats_api_download("key stage 4 performance", ks4_kw, "KS4")
            if content:
                result = parse_ks4_csv(content)
                if result and any(s.get("ks4_att8") for s in [{"ks4_att8": v} for v in result.values()]):
                    return result
                elif result:
                    # Got schools but att8=None — keep trying other keywords
                    print(f"  KS4 stats API ({ks4_kw}): {len(result)} schools but att8=None, trying next keyword")
                    continue
        except Exception as e:
            print(f"  KS4 statistics API ({ks4_kw}) failed: {e}")

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

    # Filter to institution-level rows only (EES flat format has multiple geographic levels)
    if "geographic_level" in df.columns:
        df = df[df["geographic_level"].str.lower().isin({"institution", "school"})]

    # Filter to the overall "All pupils" row per school — EES data has multiple rows per school
    # (breakdowns by sex, disadvantage, prior attainment, etc.).  We only want the whole-cohort row.
    if "breakdown" in df.columns:
        all_pupils = df[df["breakdown"].str.lower().isin({"all pupils", "total", "all", "overall"})]
        if len(all_pupils) > 0:
            df = all_pupils
            print(f"  KS4: filtered to 'All pupils' breakdown rows — {len(df):,} rows remain")
    # Fallback: if breakdown column absent but sex/disadvantage are present, pick Total rows
    elif "sex" in df.columns and "disadvantage_status" in df.columns:
        mask = (
            df["sex"].str.lower().isin({"total", "all", ""}) &
            df["disadvantage_status"].str.lower().isin({"total", "all", ""})
        )
        if mask.sum() > 0:
            df = df[mask]
            print(f"  KS4: filtered to sex=Total / disadvantage=Total rows — {len(df):,} rows remain")

    urn_col    = _find_urn_col(df.columns.tolist())
    if not urn_col:
        print(f"  KS4 parse: no URN column found. Columns: {list(df.columns[:20])}")
        return {}

    # att8: prefer _average over _sum (sum is a cohort total, not a per-pupil score)
    att8_col   = (
        next((c for c in df.columns if c == "attainment8_average"), None)
        or next((c for c in df.columns if "attainment8_average" in c or "attainment_8_average" in c), None)
        or next((c for c in df.columns if "att8_average" in c or "a8_average" in c), None)
        or next((c for c in df.columns if "average_attainment" in c), None)
        or next((c for c in df.columns if "att8" in c or "attainment_8" in c or "attainment8" in c), None)
        or next((c for c in df.columns if "a8" in c and ("score" in c or "avg" in c or "mean" in c)), None)
    )
    # grade5 = strong pass (grade 5+) in English & Maths — EES column: engmath_95_percent
    grade5_col = (
        next((c for c in df.columns if c == "engmath_95_percent"), None)
        or next((c for c in df.columns if "engmath" in c and "95" in c and "percent" in c), None)
        or next((c for c in df.columns if "engmath_95" in c), None)
        or next((c for c in df.columns if ("grade_5" in c or "grade5" in c or "l2basics_5" in c) and "english" in c), None)
        or next((c for c in df.columns if "grade_5" in c or "grade5" in c or "l2basics_5" in c), None)
        or next((c for c in df.columns if "5_or_above" in c and "english" in c), None)
        or next((c for c in df.columns if "5_or_above" in c), None)
        or next((c for c in df.columns if "basics_94" in c or "strong_pass" in c), None)
    )
    # grade4 = standard pass (grade 4+) in English & Maths — EES column: engmath_94_percent
    grade4_col = (
        next((c for c in df.columns if c == "engmath_94_percent"), None)
        or next((c for c in df.columns if "engmath" in c and "94" in c and "percent" in c), None)
        or next((c for c in df.columns if "engmath_94" in c), None)
        or next((c for c in df.columns if ("grade_4" in c or "grade4" in c or "l2basics_4" in c) and "english" in c), None)
        or next((c for c in df.columns if "grade_4" in c or "grade4" in c or "l2basics_4" in c), None)
        or next((c for c in df.columns if "4_or_above" in c and "english" in c), None)
        or next((c for c in df.columns if "4_or_above" in c), None)
        or next((c for c in df.columns if "basics_93" in c or "standard_pass" in c), None)
    )
    pupils_col = (
        next((c for c in df.columns if c == "pupil_count"), None)
        or next((c for c in df.columns if "pupil_count" in c or "pupil_number" in c), None)
        or next((c for c in df.columns if "pupil" in c and ("number" in c or "count" in c or "total" in c)), None)
        or next((c for c in df.columns if "number_of_pupils" in c or "total_pupils" in c or "cohort_size" in c), None)
    )
    print(f"  KS4 parse: urn={urn_col} att8={att8_col} g5={grade5_col} g4={grade4_col} rows={len(df)}")
    # Always log columns so we can tune detection if needed
    print(f"  KS4 columns sample: {list(df.columns[:30])}")

    mapping = {}
    for _, row in df.iterrows():
        try:
            urn = int(float(str(row[urn_col])))
        except (ValueError, TypeError):
            continue
        if urn <= 0:
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

EES_API_BASE       = "https://api.education.gov.uk/statistics/v1"
EES_CONTENT_API    = "https://content.explore-education-statistics.service.gov.uk/api"

# DfE publishes primary + secondary admissions in ONE combined publication.
# The publication slug changed name between releases — try both variants.
ADM_PUB_SLUGS = [
    "primary-and-secondary-school-applications-and-offers",
    "secondary-and-primary-school-applications-and-offers",
]

# Fallback search terms for the EES statistics API
ADM_SEARCH_TERMS = [
    "primary and secondary school applications and offers",
    "secondary and primary school applications",
    "applications and offers primary secondary",
    "school applications offers admissions",
]


def _find_admissions_release_id():
    """
    Auto-discover the latest combined primary+secondary admissions release ID.

    Strategy:
    1. Try stable EES content API with known publication slugs (fastest, most reliable)
    2. Fall back to EES statistics API keyword search
    """
    # Method 1: Direct content API using stable publication slugs
    for slug in ADM_PUB_SLUGS:
        try:
            r = requests.get(
                f"{EES_CONTENT_API}/publications/{slug}/releases/latest",
                timeout=30
            )
            if r.ok:
                release_id = r.json().get("id")
                if release_id:
                    print(f"  Found admissions release via slug '{slug}'")
                    return release_id
        except Exception:
            continue

    # Method 2: Keyword search via statistics API
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
                if "application" in title and "offer" in title and (
                    "primary" in title or "secondary" in title
                ):
                    pub_id = pub.get("id")
                    r2 = requests.get(
                        f"{EES_API_BASE}/releases?publicationId={pub_id}&pageSize=1",
                        timeout=30
                    )
                    if r2.ok:
                        results = r2.json().get("results", [])
                        if results:
                            print(f"  Found admissions release via search: '{pub.get('title')}'")
                            return results[0]["id"]
        except Exception:
            continue

    return None


def _parse_admissions_df(df, source_label):
    """
    Parse a DfE admissions DataFrame into a URN → metrics mapping.
    Handles varying column names across releases.
    """
    df.columns = df.columns.str.strip().str.lower()

    # Filter to institution-level rows if EES flat format (stats API returns multi-level data)
    if "geographic_level" in df.columns:
        df = df[df["geographic_level"].str.lower().isin({"institution", "school"})]

    # Filter to London — case-insensitive comparison
    la_col = next((c for c in df.columns if "la" in c and "name" in c), None)
    if la_col:
        df = df[df[la_col].astype(str).str.strip().str.lower().isin({la.lower() for la in LONDON_LAS})]

    urn_col = _find_urn_col(df.columns.tolist())
    if not urn_col:
        print(f"  [{source_label}] No URN column found. Columns: {list(df.columns[:25])}")
        return {}
    print(f"  [{source_label}] Using URN column: '{urn_col}' | rows: {len(df)}")

    # 1st-preference applications (first-choice apps received)
    app_col = (
        next((c for c in df.columns if "1st" in c and "preference" in c and "applic" in c), None)
        or next((c for c in df.columns if "times_put_as_1st" in c), None)
        or next((c for c in df.columns if "1st_preference" in c and "times" in c), None)
        or next((c for c in df.columns if "first_preference" in c and ("applic" in c or "express" in c)), None)
        or next((c for c in df.columns if "preference_1" in c and ("applic" in c or "express" in c)), None)
    )

    # Published Admission Number (PAN) — the school's annual intake limit
    # Try exact name first, then progressively looser patterns
    # IMPORTANT: exclude "offer" columns — offers made ≠ PAN for oversubscribed schools
    pan_col = (
        next((c for c in df.columns if c == "pan"), None)
        or next((c for c in df.columns if c in ("planned_admission_number", "published_admission_number")), None)
        or next((c for c in df.columns if "planned_admission" in c), None)
        or next((c for c in df.columns if "published_admission" in c), None)
        or next((c for c in df.columns if "admission_number" in c and "offer" not in c), None)
        or next((c for c in df.columns if "places" in c and "pan" in c), None)
        or next((c for c in df.columns if "places" in c and "number" in c
                 and "offer" not in c and "total" not in c and "applic" not in c), None)
        # Last resort: places_offered (approximately equal to PAN for oversubscribed schools)
        or next((c for c in df.columns if "places" in c and "offer" in c), None)
    )

    # 1st-preference offers made
    off_col = next((c for c in df.columns if "1st" in c and "offer" in c), None) or \
              next((c for c in df.columns if "first_preference" in c and "offer" in c), None)

    # Total applications (any preference)
    tot_col = (
        next((c for c in df.columns if "total" in c and "applic" in c), None)
        or next((c for c in df.columns if "times_put_as_any" in c), None)
        or next((c for c in df.columns if "any_preferred" in c and "times" in c), None)
        or next((c for c in df.columns if "total_preference" in c), None)
    )

    print(f"  [{source_label}] Columns found — app:{app_col} | pan:{pan_col} | off:{off_col} | tot:{tot_col}")

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

        # Do not overwrite an existing entry with a worse one
        # (some schools appear twice — e.g. different preference rounds)
        if urn in mapping and mapping[urn].get("apps_per_place") is not None and apps_per_place is None:
            continue

        mapping[urn] = {
            "places":                  places,
            "first_pref_applications": apps,
            "total_applications":      total,
            "first_pref_offers":       offers,
            "apps_per_place":          apps_per_place,
            "first_pref_success_pct":  success_pct,
        }

    return mapping


def _load_df_from_content(content):
    """Parse bytes into a DataFrame, handling zip or raw CSV."""
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            csv_names = [n for n in z.namelist() if n.endswith(".csv")]
            csv_names.sort(key=lambda n: z.getinfo(n).file_size, reverse=True)
            with z.open(csv_names[0]) as f:
                return pd.read_csv(f, low_memory=False, encoding="latin-1")
    return pd.read_csv(io.BytesIO(content), low_memory=False, encoding="latin-1")


def fetch_admissions():
    """
    Fetch combined primary + secondary school admissions from EES.
    The DfE publishes both phases in ONE publication:
    'Primary and secondary school applications and offers'

    Two strategies tried in order — each uses ONE API consistently:
      A) EES content API: publication slug → latestReleaseSlug → downloadFiles → direct URL
      B) EES statistics API: keyword search → pub_id → release_id → file download
    """
    print("Step 4: Fetching admissions data from EES (combined primary + secondary)...")

    # ── Strategy A: Content API (slug → downloadFiles → direct URL) ──────────
    for slug in ADM_PUB_SLUGS:
        try:
            pub_r = requests.get(
                f"{EES_CONTENT_API}/publications/{slug}", timeout=30
            )
            if not pub_r.ok:
                print(f"  [Admissions] Content API slug '{slug}' → HTTP {pub_r.status_code}")
                continue
            pub_data = pub_r.json()
            # Handle both old and new EES content API field names for latest release
            latest_slug = (
                pub_data.get("latestReleaseSlug")
                or pub_data.get("latestRelease", {}).get("slug")
                or (pub_data.get("releases") or [{}])[0].get("slug", "")
            )
            print(f"  [Admissions] Slug '{slug}' OK, latest release: '{latest_slug}'")
            if not latest_slug:
                print(f"  [Admissions] Could not find release slug in: {list(pub_data.keys())}")
                continue

            rel_r = requests.get(
                f"{EES_CONTENT_API}/publications/{slug}/releases/{latest_slug}",
                timeout=30,
            )
            if not rel_r.ok:
                print(f"  [Admissions] Release request → HTTP {rel_r.status_code}")
                continue

            rel_data   = rel_r.json()
            adm_rel_id = rel_data.get("id", "")
            dl_files   = rel_data.get("downloadFiles", [])
            print(f"  [Admissions] {len(dl_files)} download files (release id={adm_rel_id[:8]}...); names: {[f.get('name','?') for f in dl_files[:5]]}")

            def _adm_dl_urls(f):
                """Return list of download URLs to try, in priority order."""
                urls = []
                for field in ("url", "href", "downloadUrl", "path"):
                    val = f.get(field, "")
                    if val and val.startswith("http"):
                        urls.append(val)
                fid = f.get("id", "")
                if fid:
                    # Release-ID-based first — same pattern that returns 200 for KS2/KS4
                    if adm_rel_id:
                        urls.append(f"{EES_CONTENT_API}/releases/{adm_rel_id}/files/{fid}")
                    # Slug-based alternatives
                    urls.append(f"{EES_CONTENT_API}/publications/{slug}/releases/{latest_slug}/files/{fid}")
                    urls.append(f"{EES_CONTENT_API}/publications/{slug}/releases/{latest_slug}/files/{fid}/download")
                    if adm_rel_id:
                        urls.append(f"{EES_CONTENT_API}/releases/{adm_rel_id}/files/{fid}/download")
                return urls

            # Sort largest first — school-level file is usually the biggest
            for ds in sorted(dl_files, key=lambda x: x.get("size", 0), reverse=True):
                name = ds.get("name", "").lower()
                urls = _adm_dl_urls(ds)
                if not urls:
                    continue
                # Skip clearly non-school files (LA-level, national, metadata)
                if any(skip in name for skip in ("national", "metadata", "glossary")):
                    continue
                for url in urls:
                    url_short = url.split("/api/")[-1]
                    try:
                        print(f"  [Admissions] '{ds.get('name','?')}' [{url_short}] → ", end="", flush=True)
                        r3 = requests.get(url, timeout=120, allow_redirects=True)
                        print(f"HTTP {r3.status_code}, {len(r3.content):,} bytes")
                        if not r3.ok:
                            continue
                        df = _load_df_from_content(r3.content)
                        result = _parse_admissions_df(df, f"ContentAPI/{slug}")
                        if result:
                            print(f"  Admissions data: {len(result):,} schools")
                            return result
                        break  # parsed but no results — move to next file
                    except Exception as exc:
                        print(f"Exception: {exc}")
                        continue

        except Exception as e:
            print(f"  Content API slug '{slug}' failed: {e}")
            continue

    # ── Strategy B: Statistics API (data-sets endpoint — same approach as KS2/KS4) ─
    # Uses /publications/{pub_id}/data-sets → /data-sets/{dsid}/csv (proven working pattern)
    for term in ADM_SEARCH_TERMS:
        for kw in ("school level", "school"):
            try:
                content = _ees_stats_api_download(term, kw, "Admissions")
                if content:
                    try:
                        df = _load_df_from_content(content)
                        result = _parse_admissions_df(df, f"StatsAPI/{term[:30]}")
                        if result:
                            print(f"  Admissions data: {len(result):,} schools")
                            return result
                    except Exception as e:
                        print(f"  [Admissions] Stats API parse failed: {e}")
            except Exception as e:
                print(f"  [Admissions] Stats API ({term[:30]}) failed: {e}")

    print("  Could not fetch admissions data — preserved data will be used")
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
    Validates the date actually has data before returning it.
    """
    candidate = None
    try:
        r = requests.get("https://data.police.uk/api/crime-last-updated", timeout=10)
        if r.ok:
            date_str = r.json().get("date", "")
            if date_str:
                candidate = date_str[:7]  # YYYY-MM
    except Exception:
        pass

    # Try candidate date then fall back month by month (up to 3 months back)
    # Validate with a test call to a known London coordinate
    test_poly = "51.515,-0.120:51.515,-0.118:51.513,-0.118:51.513,-0.120"
    for months_back in range(4):
        if months_back == 0 and candidate:
            date = candidate
        else:
            d = datetime.now()
            for _ in range(months_back + (2 if not candidate else months_back)):
                d = (d.replace(day=1) - timedelta(days=1))
            date = d.strftime("%Y-%m")

        try:
            test_r = requests.get(
                "https://data.police.uk/api/crimes-street/all-crime",
                params={"poly": test_poly, "date": date},
                timeout=15
            )
            if test_r.ok and test_r.content:
                print(f"  Crime date validated: {date}")
                return date
        except Exception:
            pass

    # Final fallback: 3 months ago
    d = datetime.now()
    for _ in range(3):
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

    # Diagnostic: check how many schools have valid coordinates
    schools_with_coords = sum(1 for s in schools if s.get("lat") and s.get("lng"))
    print(f"  Schools with lat/lng: {schools_with_coords:,} / {len(schools):,}")
    if schools_with_coords == 0:
        print("  No schools have coordinates — skipping crime fetch (check GIAS lat/lng columns)")
        return

    counts = []
    school_indices = []
    consecutive_failures = 0
    fetched = 0
    # Hard cap: crime step must finish within 8 minutes to avoid job cancellation
    CRIME_MAX_SECONDS = 480
    crime_start = time.time()

    for i, s in enumerate(schools):
        # Time-box the entire crime step
        if time.time() - crime_start > CRIME_MAX_SECONDS:
            print(f"  Crime step time limit reached ({CRIME_MAX_SECONDS}s) — stopping at school {i} (fetched {fetched})")
            break

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
        # Rate limiting — 1 req/s sustained is safe and keeps total time under 1 hour
        # With 8-min cap this processes ~450 schools max per run
        time.sleep(0.1)
        if i % 100 == 0 and i > 0:
            elapsed = int(time.time() - crime_start)
            print(f"  Crime data: {i}/{len(schools)} schools processed ({elapsed}s elapsed)...")

    # Score all schools relative to each other
    for i, s in enumerate(schools):
        count = s.get("crime_count")
        if count is not None:
            score, label = score_crime(count, counts)
            s["crime_score"] = score
            s["crime_label"] = label

    print(f"  Crime data fetched for {len(counts):,} schools")
    return schools


# ── Step 6: FSM data + deprivation scoring ───────────────────────────────────

def _parse_fsm_content(content):
    """
    Parse raw bytes (CSV or ZIP) looking for FSM% by URN.
    Returns URN → pct_fsm mapping, or empty dict if not parseable.
    """
    try:
        df = _load_df_from_content(content)
    except Exception as e:
        print(f"  FSM CSV parse failed: {e}")
        return {}

    df.columns = df.columns.str.strip().str.lower()
    # Filter to institution-level rows if EES flat format
    if "geographic_level" in df.columns:
        df = df[df["geographic_level"].str.lower().isin({"institution", "school"})]
    urn_col = _find_urn_col(df.columns.tolist())
    if not urn_col:
        print(f"  FSM parse: no URN column. Columns: {list(df.columns[:20])}")
        return {}

    # FSM percentage column — column name varies between releases
    fsm_col = (
        next((c for c in df.columns if "fsm" in c and "pct" in c), None)
        or next((c for c in df.columns if "fsm" in c and "percent" in c), None)
        or next((c for c in df.columns if "free_school_meal" in c and "percent" in c), None)
        or next((c for c in df.columns if "free school meal" in c and "percent" in c), None)
        or next((c for c in df.columns if "fsm" in c and ("eligible" in c or "proportion" in c)), None)
        or next((c for c in df.columns if "fsm" in c), None)
        or next((c for c in df.columns if "free_school_meal" in c), None)
    )

    if not fsm_col:
        print(f"  FSM: could not find FSM column in {list(df.columns[:10])}")
        return {}

    print(f"  FSM column found: '{fsm_col}'")
    mapping = {}
    for _, row in df.iterrows():
        try:
            urn = int(float(str(row[urn_col])))
        except (ValueError, TypeError):
            continue
        pct = _safe_float(row.get(fsm_col))
        if pct is not None:
            mapping[urn] = pct

    print(f"  FSM data: {len(mapping):,} schools")
    return mapping


def fetch_fsm():
    """
    Fetch free school meals (FSM) percentages from EES.
    Uses 'Schools, pupils and their characteristics' publication.
    Returns URN → pct_fsm (float, e.g. 12.5 means 12.5%).
    """
    print("Step 6a: Fetching FSM/deprivation data from EES...")

    # Approach 1: EES content API — "school-pupils-and-their-characteristics" publication
    # Use "underlying" keyword to target "school level underlying data 2025" file
    # NOT "school arranged alternative provision" which also matches "school"
    fsm_pub_slugs = [
        "school-pupils-and-their-characteristics",
        "schools-pupils-and-their-characteristics",
    ]
    for slug in fsm_pub_slugs:
        for kw in ("underlying", "school level", "school"):
            try:
                content = _ees_content_api_download(slug, kw, "FSM")
                if content:
                    result = _parse_fsm_content(content)
                    if result:
                        return result
            except Exception as e:
                print(f"  FSM content API ({slug}, kw={kw}) failed: {e}")

    # Approach 2: EES statistics API
    search_terms = [
        "free school meals",
        "schools pupils characteristics",
        "pupil characteristics school level",
    ]
    for term in search_terms:
        try:
            content = _ees_stats_api_download(term, "school", "FSM")
            if content:
                result = _parse_fsm_content(content)
                if result:
                    return result
        except Exception as e:
            print(f"  FSM stats API ('{term}') failed: {e}")

    print("  FSM data unavailable — preserved deprivation labels will be used")
    return {}


def apply_fsm_pct(schools, fsm_map):
    """Merge pct_fsm values from EES into school records."""
    updated = 0
    for s in schools:
        urn = s.get("urn")
        if urn and int(urn) in fsm_map:
            s["pct_fsm"] = fsm_map[int(urn)]
            updated += 1
    print(f"  Applied FSM % to {updated:,} schools")
    return schools


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


def _fill_coords_from_postcodes(schools):
    """
    Look up decimal lat/lng for schools that have no coordinates.
    Uses postcodes.io batch API (free, no auth required, up to 100 per request).
    """
    POSTCODES_IO = "https://api.postcodes.io/postcodes"
    # Build postcode → [school indices] map
    pc_map = {}
    for i, s in enumerate(schools):
        pc = (s.get("postcode") or "").strip().replace(" ", "").upper()
        if pc:
            pc_map.setdefault(pc, []).append(i)

    if not pc_map:
        return

    # Batch in groups of 100
    postcodes = list(pc_map.keys())
    found = 0
    for batch_start in range(0, len(postcodes), 100):
        batch = postcodes[batch_start:batch_start + 100]
        try:
            resp = requests.post(POSTCODES_IO, json={"postcodes": batch}, timeout=30)
            if not resp.ok:
                continue
            for item in resp.json().get("result", []):
                if not item or not item.get("result"):
                    continue
                pc = (item.get("query") or "").replace(" ", "").upper()
                r  = item["result"]
                lat, lng = r.get("latitude"), r.get("longitude")
                if lat and lng and pc in pc_map:
                    for idx in pc_map[pc]:
                        schools[idx]["lat"] = lat
                        schools[idx]["lng"] = lng
                        found += 1
        except Exception as e:
            print(f"    postcodes.io batch error: {e}")
            continue

    print(f"  Found coordinates for {found} schools via postcodes.io")


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

    # 1b. Pre-seed lat/lng from existing schools.json
    # GIAS CSV uses Easting/Northing (OS grid refs), not decimal lat/lng.
    # Carry over decimal coordinates from the previous run for schools we already know.
    existing_coords = load_existing()
    coords_seeded = 0
    for s in schools:
        if not s.get("lat") or not s.get("lng"):
            urn = str(s.get("urn", ""))
            old = existing_coords.get(urn, {})
            if old.get("lat") and old.get("lng"):
                s["lat"] = old["lat"]
                s["lng"] = old["lng"]
                coords_seeded += 1
    if coords_seeded:
        print(f"  Pre-seeded lat/lng for {coords_seeded:,} schools from previous data")

    # 1c. For any remaining schools without coordinates, look up via postcodes.io
    missing_coords = [s for s in schools if not s.get("lat") or not s.get("lng")]
    if missing_coords:
        print(f"  Looking up coordinates for {len(missing_coords)} schools via postcodes.io...")
        _fill_coords_from_postcodes(missing_coords)
    print()

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

    # 6. FSM deprivation (fetch + score)
    fsm_map = fetch_fsm()
    if fsm_map:
        schools = apply_fsm_pct(schools, fsm_map)
    apply_fsm_deprivation(schools)
    print()

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
