"""
refresh_data.py
───────────────
Rebuilds schools.json from scratch monthly using multiple official sources:

  1. GIAS — Get Information About Schools (school register)
  2. Ofsted — Monthly management information CSV (latest Ofsted ratings)
  3. KS2 — Key Stage 2 attainment data (primary school results)
  4. KS4 — GCSE performance tables (secondary school results)
  5. Applications — School applications and offers data
  6. EES — Explore Education Statistics API (KS2/KS4 exam results, FSM data)
  7. Police API — Crime data within 500m of each school

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

GIAS_URL = "https://www.data.gov.uk/api/3/action/package_search?q=GIAS&rows=1000"
GIAS_FALLBACK_URL = "https://files.data.gov.uk/datasets/gias/GIAS_Download_20240115.zip"

OFSTED_MI_PAGE = "https://www.gov.uk/government/publications/ofsted-monthly-management-information-ofsted-mi"

KS2_DATA_URL = "https://content.explore-education-statistics.service.gov.uk/api/releases/latest/data-sets/key-stage-2-attainment-school-level"

KS4_DATA_URL = "https://content.explore-education-statistics.service.gov.uk/api/releases/latest/data-sets/gcse-attainment-4-9-in-english-and-maths"

APPLICATIONS_DATA_URL = "https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/65b074b6-b6df-419b-af04-dd0f19865b59/csv"

POLICE_API_BASE = "https://data.police.uk/api/crimes-street/all-crime"

GRADE_MAP = {
    "1": ("Outstanding", 1, 100),
    "2": ("Good", 2, 80),
    "3": ("Requires improvement", 3, 40),
    "4": ("Inadequate", 4, 0),
}

PRESERVE_FIELDS = [
    "behaviour_raw", "personal_dev_raw", "leadership_raw", "early_years_raw",
    "safeguarding", "inspection_date", "ofsted_url", "ofsted_pupils",
    "ks2_expected_pct", "ks2_higher_pct", "ks2_avg_score", "ks2_progress",
    "ks4_att8", "ks4_engmath_pass", "ks4_engmath_n",
]

# ── Step 1: GIAS — School list ────────────────────────────────────────────────

def fetch_gias():
    """Download GIAS school register for open London schools."""
    print("Step 1: Fetching school list from GIAS...")
    
    df = None
    
    try:
        r = requests.get(GIAS_URL, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        if data.get("result", {}).get("results"):
            for pkg in data["result"]["results"]:
                for resource in pkg.get("resources", []):
                    if "gias" in resource.get("name", "").lower() and resource.get("url"):
                        try:
                            r = requests.get(resource["url"], timeout=60)
                            if r.status_code == 200:
                                df = pd.read_csv(io.BytesIO(r.content), encoding="latin-1", low_memory=False)
                                print(f"  Downloaded GIAS data ({len(df):,} rows)")
                                break
                        except Exception:
                            continue
                if df is not None:
                    break
    except Exception as e:
        print(f"  GIAS lookup failed: {e}")
    
    if df is None:
        try:
            r = requests.get(GIAS_FALLBACK_URL, timeout=60)
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                csv_files = [f for f in z.namelist() if f.endswith(".csv")]
                if csv_files:
                    with z.open(csv_files[0]) as f:
                        df = pd.read_csv(f, encoding="latin-1", low_memory=False)
                        print(f"  Downloaded GIAS via fallback ({len(df):,} rows)")
        except Exception as e:
            print(f"  GIAS fallback failed: {e}")
            return pd.DataFrame()
    
    if df is None:
        return pd.DataFrame()
    
    df.columns = df.columns.str.strip()
    
    if "EstablishmentStatus (name)" in df.columns:
        df = df[df["EstablishmentStatus (name)"].str.strip() == "Open"]
    
    if "LA (name)" in df.columns:
        london_las = [
            "Barking and Dagenham", "Barnet", "Bexley", "Brent", "Bromley", "Camden",
            "City of London", "Croydon", "Ealing", "Enfield", "Greenwich", "Hackney",
            "Hammersmith and Fulham", "Haringey", "Harrow", "Havering", "Hillingdon",
            "Hounslow", "Islington", "Kensington and Chelsea", "Kingston upon Thames",
            "Lambeth", "Lewisham", "Merton", "Newham", "Redbridge", "Richmond upon Thames",
            "Southwark", "Sutton", "Tower Hamlets", "Waltham Forest", "Wandsworth", "Westminster"
        ]
        df = df[df["LA (name)"].str.strip().isin(london_las)]
    
    print(f"  Filtered to {len(df):,} London schools")
    return df

# ── Step 2: Ofsted ────────────────────────────────────────────────────────────

def fetch_ofsted():
    """Download Ofsted monthly management information with support for both old and new formats."""
    print("Step 2: Fetching Ofsted ratings...")
    
    try:
        r = requests.get(OFSTED_MI_PAGE, timeout=30)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"  Could not fetch Ofsted MI page: {e}")
        return {}
    
    csv_links = re.findall(r'href="(https://[^"]+\.csv[^"]*)"', html)
    if not csv_links:
        csv_links = re.findall(r'href="([^"]+\.csv[^"]*)"', html)
    
    if not csv_links:
        print("  No CSV link found on Ofsted MI page")
        return {}
    
    csv_url = csv_links[0]
    if csv_url.startswith("/"):
        csv_url = "https://www.gov.uk" + csv_url
    
    print(f"  Downloading from: {csv_url}")
    try:
        r = requests.get(csv_url, timeout=90)
        r.raise_for_status()
        df = pd.read_csv(io.BytesIO(r.content), encoding="latin-1", low_memory=False)
    except Exception as e:
        print(f"  Could not download Ofsted CSV: {e}")
        return {}
    
    print(f"  Ofsted rows: {len(df):,}")
    df.columns = df.columns.str.strip()
    
    def find_col(patterns, prefer_latest_oeif=False):
        """Find column matching patterns, prioritizing 'Latest OEIF' for new format."""
        matches = []
        for col in df.columns:
            col_normalized = col.lower().replace(" ", "").replace("(", "").replace(")", "")
            for pattern in patterns:
                if pattern.lower().replace(" ", "") in col_normalized:
                    matches.append(col)
                    break
        
        if not matches:
            return None
        
        if prefer_latest_oeif:
            oeif_matches = [m for m in matches if m.startswith("Latest OEIF")]
            if oeif_matches:
                return oeif_matches[0]
        
        return matches[0]
    
    urn_col = find_col(["urn", "school urn"])
    overall_col = find_col(["overall", "effectiveness"])
    quality_col = find_col(["quality", "education"], prefer_latest_oeif=True)
    behaviour_col = find_col(["behaviour", "attitudes", "behavior"], prefer_latest_oeif=True)
    personal_col = find_col(["personal", "development"], prefer_latest_oeif=True)
    leadership_col = find_col(["leadership", "management"], prefer_latest_oeif=True)
    early_col = find_col(["early", "years"], prefer_latest_oeif=True)
    safeguard_col = find_col(["safeguard", "protection"])
    date_col = find_col(["inspection", "date", "inspected"])
    url_col = find_col(["web", "url", "link", "href", "report"])
    
    if not urn_col:
        print("  Could not find URN column")
        return {}
    
    mapping = {}
    
    for _, row in df.iterrows():
        try:
            urn = int(float(str(row[urn_col]).strip()))
        except (ValueError, TypeError):
            continue
        
        def safe_grade(col):
            if not col or col not in row.index:
                return None
            val = str(row[col]).strip()
            if val in ("", "nan", "N/A", "n/a", "None"):
                return None
            return val
        
        def text_to_numeric(grade):
            if not grade:
                return None
            grade_str = str(grade).strip()
            
            for num_str, (label, _, _) in GRADE_MAP.items():
                if label.lower() == grade_str.lower():
                    return int(num_str)
            
            try:
                num = int(float(grade_str))
                if 1 <= num <= 4:
                    return num
            except (ValueError, TypeError):
                pass
            
            return None
        
        overall = safe_grade(overall_col)
        quality = safe_grade(quality_col)
        behaviour = safe_grade(behaviour_col)
        personal = safe_grade(personal_col)
        leadership = safe_grade(leadership_col)
        early = safe_grade(early_col)
        
        label, raw, score = None, None, None
        
        if overall:
            grade_num = text_to_numeric(overall)
            if grade_num and str(grade_num) in GRADE_MAP:
                label, raw, score = GRADE_MAP[str(grade_num)]
        
        if not label:
            sub_grades = []
            for sub_col in [quality, behaviour, personal, leadership, early]:
                g = text_to_numeric(sub_col)
                if g:
                    sub_grades.append(g)
            
            if sub_grades:
                worst = max(sub_grades)
                if str(worst) in GRADE_MAP:
                    label, raw, score = GRADE_MAP[str(worst)]
        
        behaviour_raw = text_to_numeric(behaviour)
        personal_dev_raw = text_to_numeric(personal)
        leadership_raw = text_to_numeric(leadership)
        early_years_raw = text_to_numeric(early)
        
        mapping[urn] = {
            "quality_label": label,
            "quality_raw": raw,
            "ofsted_score": score,
            "score_band": label,
            "behaviour_raw": behaviour_raw,
            "personal_dev_raw": personal_dev_raw,
            "leadership_raw": leadership_raw,
            "early_years_raw": early_years_raw,
            "safeguarding": safe_grade(safeguard_col),
            "inspection_date": safe_grade(date_col),
            "ofsted_url": safe_grade(url_col),
        }
    
    print(f"  Ofsted ratings mapped: {len(mapping):,}")
    
    old_format_count = sum(1 for m in mapping.values() if m.get("quality_label"))
    new_format_count = sum(
        1 for m in mapping.values()
        if not m.get("quality_label") and any(
            m.get(f) for f in ["behaviour_raw", "personal_dev_raw", "leadership_raw"]
        )
    )
    
    if old_format_count > 0 or new_format_count > 0:
        print(f"  └─ {old_format_count:,} old format (overall grade), {new_format_count:,} new Report Card format (Sept 2024+)")
    
    return mapping

# ── Step 3: KS2 Data ──────────────────────────────────────────────────────────

def fetch_ks2():
    """Load KS2 attainment data from CSV."""
    print("Step 3: Fetching KS2 results...")
    
    try:
        df = pd.read_csv("ks2_school_attainment_data.csv", encoding="utf-8-sig", low_memory=False)
        print(f"  Loaded {len(df):,} KS2 records")
        
        df.columns = df.columns.str.strip()
        
        ks2_mapping = {}
        for _, row in df.iterrows():
            try:
                urn = int(row.get("school_urn", -1))
                if urn <= 0:
                    continue
                
                if urn not in ks2_mapping:
                    ks2_mapping[urn] = {
                        "ks2_expected_pct": None,
                        "ks2_higher_pct": None,
                        "ks2_avg_score": None,
                        "ks2_progress": None,
                    }
                
                if pd.notna(row.get("expected_standard_pupil_percent")):
                    ks2_mapping[urn]["ks2_expected_pct"] = round(float(row.get("expected_standard_pupil_percent")), 1)
                if pd.notna(row.get("higher_standard_pupil_percent")):
                    ks2_mapping[urn]["ks2_higher_pct"] = round(float(row.get("higher_standard_pupil_percent")), 1)
                if pd.notna(row.get("average_scaled_score")):
                    ks2_mapping[urn]["ks2_avg_score"] = round(float(row.get("average_scaled_score")), 1)
                if pd.notna(row.get("progress_measure_score")):
                    ks2_mapping[urn]["ks2_progress"] = round(float(row.get("progress_measure_score")), 2)
            
            except (ValueError, TypeError):
                continue
        
        print(f"  KS2 schools mapped: {len(ks2_mapping):,}")
        return ks2_mapping
    
    except Exception as e:
        print(f"  Could not load KS2 data: {e}")
        return {}

# ── Step 4: KS4 Data ──────────────────────────────────────────────────────────

def fetch_ks4():
    """Load KS4 GCSE performance data from CSV."""
    print("Step 4: Fetching KS4 results...")
    
    try:
        df = pd.read_csv("202425_performance_tables_schools_revised.csv", encoding="utf-8-sig", low_memory=False)
        print(f"  Loaded {len(df):,} KS4 records")
        
        df.columns = df.columns.str.strip()
        
        ks4_mapping = {}
        for _, row in df.iterrows():
            try:
                urn = int(row.get("school_urn", -1))
                if urn <= 0:
                    continue
                
                if urn not in ks4_mapping:
                    ks4_mapping[urn] = {
                        "ks4_att8": None,
                        "ks4_engmath_pass": None,
                        "ks4_engmath_n": None,
                    }
                
                if pd.notna(row.get("attainment8_average")):
                    ks4_mapping[urn]["ks4_att8"] = round(float(row.get("attainment8_average")), 1)
                if pd.notna(row.get("gcse_five_engmath_percent")):
                    ks4_mapping[urn]["ks4_engmath_pass"] = round(float(row.get("gcse_five_engmath_percent")), 1)
                if pd.notna(row.get("engmath_entering_total")):
                    ks4_mapping[urn]["ks4_engmath_n"] = int(row.get("engmath_entering_total"))
            
            except (ValueError, TypeError):
                continue
        
        print(f"  KS4 schools mapped: {len(ks4_mapping):,}")
        return ks4_mapping
    
    except Exception as e:
        print(f"  Could not load KS4 data: {e}")
        return {}

# ── Step 5: Applications Data ─────────────────────────────────────────────────

def fetch_applications():
    """Load school applications and offers data."""
    print("Step 5: Fetching applications/offers data...")
    
    try:
        df = pd.read_csv("AppsandOffers_2025_SchoolLevel07102025.csv", encoding="utf-8-sig", low_memory=False)
        print(f"  Loaded {len(df):,} application records")
        
        df.columns = df.columns.str.strip()
        
        apps_mapping = {}
        for _, row in df.iterrows():
            try:
                urn = int(row.get("school_urn", -1))
                if urn <= 0:
                    continue
                
                if urn not in apps_mapping:
                    if pd.notna(row.get("proportion_1stprefs_v_totaloffers")):
                        ratio = float(row.get("proportion_1stprefs_v_totaloffers"))
                        apps_mapping[urn] = {"demand_ratio": round(ratio, 2)}
            
            except (ValueError, TypeError):
                continue
        
        print(f"  Schools with demand ratio: {len(apps_mapping):,}")
        return apps_mapping
    
    except Exception as e:
        print(f"  Could not load applications data: {e}")
        return {}

# ── Step 6: Apply Ofsted + derive Report Card ratings ────────────────────────

def derive_report_card_composite(schools):
    """After merge, derive Report Card composite ratings from sub-grades."""
    derived = 0
    
    for s in schools:
        if s.get("quality_label") or s.get("ofsted_score"):
            continue
        
        sub_grades = [
            s.get("behaviour_raw"),
            s.get("personal_dev_raw"),
            s.get("leadership_raw"),
            s.get("early_years_raw"),
        ]
        sub_grades = [g for g in sub_grades if g is not None]
        
        if sub_grades:
            worst = max(sub_grades)
            
            if worst == 1:
                label, score = "Outstanding", 100
            elif worst == 2:
                label, score = "Good", 80
            elif worst == 3:
                label, score = "Requires improvement", 40
            elif worst == 4:
                label, score = "Inadequate", 0
            else:
                label, score = None, None
            
            if label:
                s["quality_label"] = label
                s["ofsted_score"] = score
                s["score_band"] = label
                s["quality_raw"] = worst
                derived += 1
    
    if derived:
        print(f"  └─ Derived Report Card composite ratings for {derived:,} schools (Sept 2024+ framework)")
    
    return schools

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("London Schools Data Refresh")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
    schools = []
    
    gias_df = fetch_gias()
    if gias_df.empty:
        print("ERROR: Could not load GIAS data")
        return
    
    for _, row in gias_df.iterrows():
        try:
            urn = int(row.get("URN", -1))
            if urn <= 0:
                continue
            
            school = {
                "urn": urn,
                "name": row.get("EstablishmentName", ""),
                "address": row.get("Street", ""),
                "postcode": row.get("Postcode", ""),
                "local_authority": row.get("LA (name)", ""),
                "phase": row.get("PhaseOfEducation (name)", ""),
                "type": row.get("EstablishmentTypeGroup (name)", ""),
                "pupils": None,
                "capacity": None,
            }
            
            try:
                pupils = int(row.get("NumberOfPupils", 0))
                if pupils > 0:
                    school["pupils"] = pupils
            except (ValueError, TypeError):
                pass
            
            try:
                cap = int(row.get("SchoolCapacity", 0))
                if cap > 0:
                    school["capacity"] = cap
            except (ValueError, TypeError):
                pass
            
            schools.append(school)
        
        except Exception:
            continue
    
    print(f"\nLoaded {len(schools):,} schools from GIAS\n")
    
    ofsted_map = fetch_ofsted()
    print()
    
    ks2_map = fetch_ks2()
    print()
    
    ks4_map = fetch_ks4()
    print()
    
    apps_map = fetch_applications()
    print()
    
    print("Step 6: Merging all data sources...")
    for s in schools:
        urn = s.get("urn")
        
        if urn in ofsted_map:
            s.update(ofsted_map[urn])
        
        if urn in ks2_map:
            s.update(ks2_map[urn])
        
        if urn in ks4_map:
            s.update(ks4_map[urn])
        
        if urn in apps_map:
            s.update(apps_map[urn])
    
    print(f"  Merged data from {len(ofsted_map):,} Ofsted, {len(ks2_map):,} KS2, {len(ks4_map):,} KS4, {len(apps_map):,} apps records")
    print()
    
    print("Step 7: Deriving Report Card composite ratings...")
    schools = derive_report_card_composite(schools)
    print()
    
    print("Step 8: Saving to JSON...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(schools, f, ensure_ascii=False, separators=(",", ":"))
    
    print(f"  Saved {len(schools):,} schools to {OUTPUT_FILE}")
    print()
    print("=" * 70)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    main()
