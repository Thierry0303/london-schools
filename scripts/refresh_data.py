import io, re, json, time, zipfile, requests, pandas as pd, numpy as np
from datetime import datetime, timedelta

OUTPUT_FILE = "schools.json"
GIAS_URL = "https://www.data.gov.uk/api/3/action/package_search?q=GIAS&rows=1000"
GIAS_FALLBACK = "https://files.data.gov.uk/datasets/gias/GIAS_Download_20240115.zip"
OFSTED_MI_PAGE = "https://www.gov.uk/government/publications/ofsted-monthly-management-information-ofsted-mi"

GRADE_MAP = {"1": ("Outstanding", 1, 100), "2": ("Good", 2, 80), "3": ("Requires improvement", 3, 40), "4": ("Inadequate", 4, 0)}

print("=" * 80)
print("London Schools Data Refresh")
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

# Load existing schools.json to preserve fields
try:
    with open(OUTPUT_FILE) as f:
        existing_schools = {s.get("urn"): s for s in json.load(f)}
except:
    existing_schools = {}

# Step 1: Fetch GIAS
print("\nStep 1: Fetching GIAS school register...")
gias_df = None
try:
    r = requests.get(GIAS_URL, timeout=30)
    data = r.json()
    for pkg in data.get("result", {}).get("results", []):
        for res in pkg.get("resources", []):
            if "gias" in res.get("name", "").lower() and res.get("url"):
                try:
                    r = requests.get(res["url"], timeout=60)
                    gias_df = pd.read_csv(io.BytesIO(r.content), encoding="latin-1", low_memory=False)
                    break
                except:
                    pass
        if gias_df is not None:
            break
except Exception as e:
    print(f"  GIAS lookup failed: {e}")

if gias_df is None:
    try:
        r = requests.get(GIAS_FALLBACK, timeout=60)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            csv_files = [f for f in z.namelist() if f.endswith(".csv")]
            if csv_files:
                with z.open(csv_files[0]) as f:
                    gias_df = pd.read_csv(f, encoding="latin-1", low_memory=False)
    except Exception as e:
        print(f"  GIAS fallback failed: {e}")

if gias_df is None:
    print("ERROR: Could not load GIAS data")
    exit(1)

gias_df.columns = gias_df.columns.str.strip()
gias_df = gias_df[gias_df.get("EstablishmentStatus (name)") == "Open"]

london_las = ["Barking and Dagenham", "Barnet", "Bexley", "Brent", "Bromley", "Camden", "City of London", "Croydon", 
              "Ealing", "Enfield", "Greenwich", "Hackney", "Hammersmith and Fulham", "Haringey", "Harrow", "Havering",
              "Hillingdon", "Hounslow", "Islington", "Kensington and Chelsea", "Kingston upon Thames", "Lambeth",
              "Lewisham", "Merton", "Newham", "Redbridge", "Richmond upon Thames", "Southwark", "Sutton",
              "Tower Hamlets", "Waltham Forest", "Wandsworth", "Westminster"]
gias_df = gias_df[gias_df.get("LA (name)").isin(london_las)]

schools = []
for _, row in gias_df.iterrows():
    try:
        urn = int(row.get("URN", -1))
        if urn <= 0:
            continue
        # Preserve key fields from existing school
        school = {k: v for k, v in existing_schools.get(urn, {}).items() if k in ["behaviour_raw", "personal_dev_raw", "leadership_raw", "early_years_raw", "safeguarding", "inspection_date", "ofsted_url", "ks2_expected_pct", "ks2_higher_pct", "ks4_att8", "ks4_grade5_em", "ks4_grade4_em", "demand_ratio"]}
        school.update({"urn": urn, "name": row.get("EstablishmentName", ""), "street": row.get("Street", ""), "postcode": row.get("Postcode", ""), "local_authority": row.get("LA (name)", ""), "phase": row.get("PhaseOfEducation (name)", ""), "school_type": row.get("EstablishmentTypeGroup (name)", "")})
        try: school["pupils"] = int(row.get("NumberOfPupils", 0)) if int(row.get("NumberOfPupils", 0)) > 0 else None
        except: pass
        try: school["capacity"] = int(row.get("SchoolCapacity", 0)) if int(row.get("SchoolCapacity", 0)) > 0 else None
        except: pass
        schools.append(school)
    except:
        pass

print(f"  Loaded {len(schools):,} London schools")

# Step 2: Ofsted
print("\nStep 2: Fetching Ofsted ratings...")
try:
    r = requests.get(OFSTED_MI_PAGE, timeout=30)
    csv_links = re.findall(r'href="(https://[^"]+\.csv)"', r.text) or re.findall(r'href="([^"]+\.csv)"', r.text)
    if csv_links:
        csv_url = csv_links[0]
        if csv_url.startswith("/"): csv_url = "https://www.gov.uk" + csv_url
        r = requests.get(csv_url, timeout=90)
        df = pd.read_csv(io.BytesIO(r.content), encoding="latin-1", low_memory=False)
        df.columns = df.columns.str.strip()
        
        for urn in [s.get("urn") for s in schools if s.get("urn")]:
            ofsted_rows = df[df.get("URN") == urn] if "URN" in df.columns else df[df.get("school urn") == urn] if "school urn" in df.columns else pd.DataFrame()
            if ofsted_rows.empty:
                continue
            row = ofsted_rows.iloc[0]
            school = next((s for s in schools if s.get("urn") == urn), None)
            if not school:
                continue
            
            # Extract ratings - prefer Latest OEIF columns
            overall = None
            for col in [c for c in df.columns if "overall" in c.lower()][:1]:
                try:
                    val = str(row.get(col, "")).strip()
                    if val and val not in ("", "nan", "N/A"): overall = val
                except: pass
            
            quality = behaviour = personal = leadership = early = None
            for col in [c for c in df.columns if c.startswith("Latest OEIF") and "quality" in c.lower()][:1]:
                try: quality = str(row.get(col, "")).strip() if pd.notna(row.get(col)) else None
                except: pass
            for col in [c for c in df.columns if c.startswith("Latest OEIF") and "behavio" in c.lower()][:1]:
                try: behaviour = str(row.get(col, "")).strip() if pd.notna(row.get(col)) else None
                except: pass
            for col in [c for c in df.columns if c.startswith("Latest OEIF") and "personal" in c.lower()][:1]:
                try: personal = str(row.get(col, "")).strip() if pd.notna(row.get(col)) else None
                except: pass
            for col in [c for c in df.columns if c.startswith("Latest OEIF") and "leadership" in c.lower()][:1]:
                try: leadership = str(row.get(col, "")).strip() if pd.notna(row.get(col)) else None
                except: pass
            for col in [c for c in df.columns if c.startswith("Latest OEIF") and "early" in c.lower()][:1]:
                try: early = str(row.get(col, "")).strip() if pd.notna(row.get(col)) else None
                except: pass
            
            # Convert to numeric
            def to_num(val):
                if not val or val in ("N/A", "nan", ""): return None
                for num, (label, _, _) in GRADE_MAP.items():
                    if label.lower() == val.lower(): return int(num)
                try: return int(float(val)) if 1 <= int(float(val)) <= 4 else None
                except: return None
            
            overall_num = to_num(overall)
            q, b, p, l, e = to_num(quality), to_num(behaviour), to_num(personal), to_num(leadership), to_num(early)
            
            school["behaviour_raw"], school["personal_dev_raw"], school["leadership_raw"], school["early_years_raw"] = b, p, l, e
            
            if overall_num and str(overall_num) in GRADE_MAP:
                label, raw, score = GRADE_MAP[str(overall_num)]
                school.update({"quality_label": label, "quality_raw": raw, "ofsted_score": score, "score_band": label})
            elif any([q, b, p, l, e]):
                worst = max([x for x in [q, b, p, l, e] if x])
                if str(worst) in GRADE_MAP:
                    label, raw, score = GRADE_MAP[str(worst)]
                    school.update({"quality_label": label, "quality_raw": raw, "ofsted_score": score, "score_band": label})
except Exception as e:
    print(f"  Ofsted error: {e}")

# Step 3: KS2
print("\nStep 3: Loading KS2 results...")
try:
    ks2 = pd.read_csv("ks2_school_attainment_data.csv", encoding="utf-8-sig", low_memory=False)
    ks2.columns = ks2.columns.str.strip()
    for _, row in ks2.iterrows():
        try:
            urn = int(row.get("school_urn", -1))
            school = next((s for s in schools if s.get("urn") == urn), None)
            if school:
                if pd.notna(row.get("expected_standard_pupil_percent")): school["ks2_expected_pct"] = round(float(row.get("expected_standard_pupil_percent")), 1)
                if pd.notna(row.get("higher_standard_pupil_percent")): school["ks2_higher_pct"] = round(float(row.get("higher_standard_pupil_percent")), 1)
        except: pass
    print(f"  Loaded KS2 for {len([s for s in schools if 'ks2_expected_pct' in s]):,} schools")
except Exception as e:
    print(f"  KS2 error: {e}")

# Step 4: KS4
print("\nStep 4: Loading KS4 results...")
try:
    ks4 = pd.read_csv("202425_performance_tables_schools_revised.csv", encoding="utf-8-sig", low_memory=False)
    ks4.columns = ks4.columns.str.strip()
    for _, row in ks4.iterrows():
        try:
            urn = int(row.get("school_urn", -1))
            school = next((s for s in schools if s.get("urn") == urn), None)
            if school:
                if pd.notna(row.get("attainment8_average")): school["ks4_att8"] = round(float(row.get("attainment8_average")), 1)
                if pd.notna(row.get("gcse_five_engmath_percent")): school["ks4_grade5_em"] = round(float(row.get("gcse_five_engmath_percent")), 1)
        except: pass
    print(f"  Loaded KS4 for {len([s for s in schools if 'ks4_att8' in s]):,} schools")
except Exception as e:
    print(f"  KS4 error: {e}")

# Step 5: Applications/Demand
print("\nStep 5: Loading applications/demand ratio...")
try:
    apps = pd.read_csv("AppsandOffers_2025_SchoolLevel07102025.csv", encoding="utf-8-sig", low_memory=False)
    apps.columns = apps.columns.str.strip()
    for _, row in apps.iterrows():
        try:
            urn = int(row.get("school_urn", -1))
            school = next((s for s in schools if s.get("urn") == urn), None)
            if school and pd.notna(row.get("proportion_1stprefs_v_totaloffers")):
                school["demand_ratio"] = round(float(row.get("proportion_1stprefs_v_totaloffers")), 2)
        except: pass
    print(f"  Loaded demand ratio for {len([s for s in schools if 'demand_ratio' in s]):,} schools")
except Exception as e:
    print(f"  Applications error: {e}")

# Save
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(schools, f, ensure_ascii=False, separators=(",", ":"))

print(f"\n✓ Saved {len(schools):,} schools to {OUTPUT_FILE}")
print("=" * 80)
print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
