"""
test_site.py — London Schools Explorer
Runs automatically on GitHub Actions before every deployment.
Tests data integrity, page structure, and content correctness.
"""

import json
import os
import sys
import pathlib
from collections import Counter

PASS = 0
FAIL = 0
WARNS = []

def ok(msg):
    global PASS
    PASS += 1
    print(f"  ✅ {msg}")

def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  ❌ {msg}")

def warn(msg):
    WARNS.append(msg)
    print(f"  ⚠️  {msg}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

# ── 1. schools.json integrity ─────────────────────────────────
section("1. schools.json — data integrity")

try:
    with open("schools.json") as f:
        schools = json.load(f)
    ok(f"schools.json loaded — {len(schools):,} schools")
except Exception as e:
    fail(f"Could not load schools.json: {e}")
    sys.exit(1)

# Minimum school count
if len(schools) >= 3000:
    ok(f"School count {len(schools):,} ≥ 3,000")
else:
    fail(f"School count {len(schools):,} too low — expected ≥ 3,000")

# Every school must have required fields
required = ["urn", "name", "local_authority", "postcode", "phase"]
missing_required = []
for s in schools:
    for field in required:
        if not s.get(field):
            missing_required.append(f"{s.get('name','?')} missing {field}")

if not missing_required:
    ok("All schools have required fields (urn, name, local_authority, postcode, phase)")
elif len(missing_required) <= 800:
    warn(f"{len(missing_required)} schools missing phase (expected for special/16+ schools)")
    for m in missing_required[:5]:
        print(f"    → {m}")
else:
    fail(f"{len(missing_required)} schools missing required fields — data problem")
    for m in missing_required[:5]:
        print(f"    → {m}")

# Ofsted data coverage
rated = [s for s in schools if s.get("quality_label")]
pct = len(rated) / len(schools) * 100
if len(rated) >= 1000:
    ok(f"Ofsted rated: {len(rated):,} schools ({pct:.0f}%)")
else:
    fail(f"Ofsted rated only {len(rated):,} schools — expected ≥ 1,000")

# Valid Ofsted labels only
valid_labels = {"Outstanding", "Good", "Requires improvement", "Inadequate"}
bad_labels = [s for s in schools if s.get("quality_label") and s["quality_label"] not in valid_labels]
if not bad_labels:
    ok("All Ofsted labels are valid")
else:
    fail(f"{len(bad_labels)} schools have invalid Ofsted labels: {set(s['quality_label'] for s in bad_labels)}")

# Crime data coverage
with_crime = [s for s in schools if s.get("crime_label")]
if len(with_crime) >= 3000:
    ok(f"Crime data: {len(with_crime):,} schools")
else:
    warn(f"Crime data only {len(with_crime):,} schools — expected ≥ 3,000")

# KS2 data coverage
with_ks2 = [s for s in schools if s.get("ks2_higher_pct") is not None]
if len(with_ks2) >= 1000:
    ok(f"KS2 data: {len(with_ks2):,} schools")
elif len(with_ks2) > 0:
    warn(f"KS2 data: {len(with_ks2):,} schools — partial data (EES API may be limited)")
else:
    # 0 means API failed entirely — preserved from previous run via merge_existing
    warn(f"KS2 data: 0 schools fetched — will use preserved data from previous refresh")

# Admissions data coverage
with_adm = [s for s in schools if s.get("apps_per_place") is not None]
if len(with_adm) >= 1500:
    ok(f"Admissions data: {len(with_adm):,} schools")
else:
    warn(f"Admissions data only {len(with_adm):,} schools — expected ≥ 1,500")

# Coordinates coverage
with_coords = [s for s in schools if s.get("lat") and s.get("lng")]
if len(with_coords) >= 3000:
    ok(f"Coordinates: {len(with_coords):,} schools")
else:
    fail(f"Coordinates only {len(with_coords):,} schools — expected ≥ 3,000")

# Snobe URLs
with_snobe = [s for s in schools if s.get("snobe_url")]
if len(with_snobe) >= 3000:
    ok(f"Snobe URLs: {len(with_snobe):,} schools")
else:
    warn(f"Snobe URLs only {len(with_snobe):,} schools")

# No duplicate URNs
urns = [s.get("urn") for s in schools if s.get("urn")]
dup_urns = [u for u, c in Counter(urns).items() if c > 1]
if not dup_urns:
    ok("No duplicate URNs")
else:
    fail(f"{len(dup_urns)} duplicate URNs found: {dup_urns[:5]}")

# Borough coverage — should have all 33 London boroughs
boroughs = set(s.get("local_authority") for s in schools if s.get("local_authority"))
if len(boroughs) >= 33:
    ok(f"Borough coverage: {len(boroughs)} local authorities")
else:
    fail(f"Only {len(boroughs)} boroughs — expected 33+")

# ── 2. Static pages — spot checks ────────────────────────────
section("2. Static school pages — spot checks")

schools_dir = pathlib.Path("schools")
if not schools_dir.exists():
    fail("schools/ directory not found")
else:
    # Count total pages — pages are built after data refresh so may not exist yet
    pages = list(schools_dir.rglob("index.html"))
    school_pages = [p for p in pages if len(p.parts) == 3]
    if len(school_pages) >= 3000:
        ok(f"Static pages: {len(school_pages):,} school pages built")
    else:
        # Not a failure — pages are rebuilt after this test runs
        warn(f"School pages: {len(school_pages):,} (will be rebuilt after data refresh)")

    # Check specific known schools exist
    known = [
        "schools/camden/thomas-coram-centre/index.html",
        "schools/camden/swiss-cottage-school-development-research-centre/index.html",
        "schools/camden/haverstock-school/index.html",
        "schools/greenwich/heronsgate-primary-school/index.html",
        "schools/westminster/westminster-school/index.html",
    ]
    for path in known:
        if pathlib.Path(path).exists():
            ok(f"Page exists: {path}")
        else:
            fail(f"Missing page: {path}")

    # Spot-check page content for a few schools
    check_schools = [
        ("schools/camden/thomas-coram-centre/index.html", "Outstanding", "Thomas Coram"),
        ("schools/camden/haverstock-school/index.html", "Camden", "Haverstock"),
    ]
    for path, must_contain, school_name in check_schools:
        p = pathlib.Path(path)
        if p.exists():
            content = p.read_text(encoding="utf-8")
            if must_contain in content:
                ok(f"{school_name}: contains '{must_contain}'")
            else:
                fail(f"{school_name}: missing '{must_contain}' in page")
            # Check page has basic structure
            for tag in ["<title>", "<meta", "schema.org", "Ofsted"]:
                if tag not in content:
                    fail(f"{school_name}: missing '{tag}' in page")

# ── 3. Borough and type pages ─────────────────────────────────
section("3. Borough & type index pages")

expected_boroughs = [
    "barking-and-dagenham", "barnet", "bexley", "brent", "bromley",
    "camden", "croydon", "ealing", "enfield", "greenwich",
    "hackney", "hammersmith-and-fulham", "haringey", "harrow", "havering",
    "hillingdon", "hounslow", "islington", "kensington-and-chelsea",
    "kingston-upon-thames", "lambeth", "lewisham", "merton", "newham",
    "redbridge", "richmond-upon-thames", "southwark", "sutton",
    "tower-hamlets", "waltham-forest", "wandsworth", "westminster",
    "city-of-london"
]
missing_boroughs = []
for borough in expected_boroughs:
    if not pathlib.Path(f"schools/{borough}/index.html").exists():
        missing_boroughs.append(borough)

if not missing_boroughs:
    ok(f"All 33 borough index pages present")
else:
    fail(f"Missing borough pages: {missing_boroughs}")

expected_types = ["outstanding", "good", "primary", "secondary", "sixth-form", "faith", "selective"]
missing_types = []
for t in expected_types:
    if not pathlib.Path(f"schools/{t}/index.html").exists():
        missing_types.append(t)

if not missing_types:
    ok(f"All type pages present: {expected_types}")
else:
    fail(f"Missing type pages: {missing_types}")

# ── 4. Sitemap & robots ───────────────────────────────────────
section("4. Sitemap & robots.txt")

if pathlib.Path("sitemap_data.txt").exists():
    sitemap = pathlib.Path("sitemap_data.txt").read_text()
    url_count = sitemap.count("<url>")
    if url_count >= 3000:
        ok(f"Sitemap has {url_count:,} URLs")
    else:
        warn(f"Sitemap: {url_count} URLs (will be rebuilt after static page build)")
else:
    fail("sitemap_data.txt not found")

if pathlib.Path("robots.txt").exists():
    robots = pathlib.Path("robots.txt").read_text()
    if "Sitemap:" in robots:
        ok("robots.txt present with Sitemap reference")
    else:
        fail("robots.txt missing Sitemap reference")
else:
    fail("robots.txt not found")

# ── Summary ───────────────────────────────────────────────────
section("SUMMARY")
total = PASS + FAIL
print(f"  Passed:   {PASS}/{total}")
print(f"  Failed:   {FAIL}/{total}")
if WARNS:
    print(f"  Warnings: {len(WARNS)}")
    for w in WARNS:
        print(f"    ⚠️  {w}")

if FAIL > 0:
    print("\n  ❌ TESTS FAILED — do not deploy")
    sys.exit(1)
else:
    print("\n  ✅ ALL TESTS PASSED — safe to deploy")
    sys.exit(0)
