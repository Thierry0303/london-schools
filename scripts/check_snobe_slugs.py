"""
check_snobe_slugs.py
────────────────────
Checks every school in schools.json against Snobe to find wrong slugs.

USAGE:
  Test first (10 schools, ~30 seconds):
      python3 scripts/check_snobe_slugs.py --test

  Full run (3,000+ schools, ~50 minutes):
      python3 scripts/check_snobe_slugs.py

Requirements: pip install requests
"""

import json, re, sys, time, requests

SCHOOLS_FILE     = "schools.json"
CORRECTIONS_FILE = "snobe_corrections.json"
MISSING_FILE     = "snobe_missing.json"
SNOBE_BASE       = "https://snobe.co.uk/schools/"
STOP_WORDS       = {"the","of","for","and","a","at","in","by","with","an"}
HEADERS          = {"User-Agent": "Mozilla/5.0 (compatible; LondonSchoolDirectory/1.0)"}

TEST_NAMES = [
    "The Aldgate School",               # EXPECT FIX: drop 'the'
    "Ashbourne College",                # EXPECT FIX: 'ashbourne-independent-school'
    "City of London School for Girls",  # EXPECT FIX: drop 'of','for'
    "Camden School for Girls",          # EXPECT FIX: drop 'for'
    "The Archbishop Lanfranc Academy",  # EXPECT FIX: drop 'the'
    "Hackney New School",               # EXPECT OK
    "Haverstock School",                # EXPECT OK
    "St Paul's Cathedral School",       # EXPECT OK
    "St Vincent de Paul RC Primary School",  # EXPECT FIX: needs '-0' suffix
    "St Mary's CofE Primary School",    # EXPECT FIX: needs '-0' or similar suffix
]


def make_slug(name):
    words = str(name).lower()\
        .replace("\u2019","").replace("\u2018","").replace("'","")\
        .replace(",","").replace(".","").replace("(","").replace(")","").strip().split()
    slug = "-".join(w for w in words if w not in STOP_WORDS)
    return re.sub(r"-+", "-", slug).strip("-")


def check_url(slug):
    try:
        r = requests.get(SNOBE_BASE + slug, headers=HEADERS, timeout=15, allow_redirects=True)
        return r.status_code, r.url
    except Exception as e:
        return None, str(e)


def try_alternates(name):
    base = make_slug(name)
    variants = set()

    # Full name with stop words kept
    full = str(name).lower().replace("\u2019","").replace("'","").replace(",","").replace(".","").strip()
    variants.add(re.sub(r"\s+", "-", full))

    # College/Academy swaps
    variants.add(base.replace("college", "independent-school"))
    variants.add(base.replace("college", "school"))
    variants.add(base.replace("academy", "school"))
    variants.add(base.replace("school", "academy"))

    # Add -school suffix if no institution word
    if not any(w in base for w in {"school","academy","college","institute"}):
        variants.add(base + "-school")

    variants.discard(base)
    variants.discard("")

    for v in sorted(variants):
        status, url = check_url(v)
        if status == 200:
            return v, SNOBE_BASE + v

    # Try numeric suffixes — Snobe appends -0, -1, -2 when multiple
    # schools share the same name (e.g. St Vincent de Paul exists in many LAs)
    all_slugs = [base] + list(variants)
    for slug in all_slugs:
        for n in range(0, 5):
            suffixed = f"{slug}-{n}"
            status, url = check_url(suffixed)
            if status == 200:
                return suffixed, SNOBE_BASE + suffixed

    return None, None


def main():
    test_mode = "--test" in sys.argv

    print("=" * 55)
    print("Snobe Slug Checker — London Schools Explorer")
    print("=" * 55)

    with open(SCHOOLS_FILE, encoding="utf-8") as f:
        all_schools = json.load(f)
    all_schools = [s for s in all_schools if s.get("name") and s.get("urn")]

    if test_mode:
        schools = [s for s in all_schools if s.get("name") in TEST_NAMES]
        print(f"\nTEST MODE — {len(schools)} schools (~30 seconds)\n")
        print("Expected: Aldgate=fix, Ashbourne=fix, City of London Girls=fix")
        print("         Hackney New School=OK, Haverstock=OK\n")
    else:
        schools = all_schools
        print(f"\nFull run — {len(schools):,} schools (~50 minutes)\n")

    corrections, missing = [], []
    ok_count = 0

    for i, s in enumerate(schools):
        name, urn = s["name"], s["urn"]
        slug = make_slug(name)
        status, _ = check_url(slug)

        if status == 200:
            ok_count += 1
            print(f"  ✅ OK:      {name}")
        else:
            correct_slug, correct_url = try_alternates(name)
            if correct_url:
                corrections.append({"urn": urn, "name": name,
                    "wrong_slug": slug, "correct_slug": correct_slug,
                    "correct_url": correct_url})
                print(f"  🔧 FIXED:   {name}")
                print(f"             wrong:   {SNOBE_BASE + slug}")
                print(f"             correct: {correct_url}")
            else:
                missing.append({"urn": urn, "name": name, "tried_slug": slug})
                print(f"  ❌ MISSING: {name}")

        if not test_mode and (i + 1) % 100 == 0:
            print(f"\n  [{i+1}/{len(schools)}] ✅{ok_count} OK | 🔧{len(corrections)} fixed | ❌{len(missing)} missing\n")

        time.sleep(1.0)

    print(f"\n{'=' * 55}")
    print(f"Results: ✅ {ok_count} OK | 🔧 {len(corrections)} fixed | ❌ {len(missing)} missing")
    print(f"{'=' * 55}")

    if test_mode:
        print("\nIf results look right, run without --test for the full check.")
        return

    with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(corrections, f, indent=2, ensure_ascii=False)
    with open(MISSING_FILE, "w", encoding="utf-8") as f:
        json.dump(missing, f, indent=2, ensure_ascii=False)

    if corrections:
        cmap = {c["urn"]: c["correct_url"] for c in corrections}
        for s in all_schools:
            if s.get("urn") in cmap:
                s["snobe_url"] = cmap[s["urn"]]
        with open(SCHOOLS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_schools, f, ensure_ascii=False, separators=(",",":"))
        print(f"\nPatched {len(corrections)} URLs in schools.json")
        print("Next: python3 scripts/build_school_pages.py → commit → push")


if __name__ == "__main__":
    main()
