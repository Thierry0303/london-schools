"""
check_snobe_slugs.py
────────────────────
Checks every school in schools.json against Snobe to find which ones
have wrong slugs (404 on Snobe) and attempts to find the correct URL.

Run from your repo root:
    python3 scripts/check_snobe_slugs.py

Outputs:
    snobe_corrections.json  — schools with wrong slugs + correct URLs
    snobe_missing.json      — schools not on Snobe at all

Requirements: pip install requests
"""

import json
import time
import re
import requests

SCHOOLS_FILE   = "schools.json"
CORRECTIONS_FILE = "snobe_corrections.json"
MISSING_FILE     = "snobe_missing.json"

SNOBE_BASE = "https://snobe.co.uk/schools/"
SNOBE_SEARCH = "https://snobe.co.uk/best-schools/search/london?search="

STOP_WORDS = {"the", "of", "for", "and", "a", "at", "in", "by", "with", "an"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LondonSchoolDirectory/1.0)"
}


def make_slug(name):
    """Generate our current Snobe slug from a school name."""
    words = str(name).lower()\
        .replace("'", "").replace("'", "").replace("'", "")\
        .replace(",", "").replace(".", "").replace("(", "").replace(")", "")\
        .strip().split()
    filtered = [w for w in words if w not in STOP_WORDS]
    slug = "-".join(filtered)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def check_snobe_url(slug):
    """Check if a Snobe URL returns 200 or 404."""
    url = SNOBE_BASE + slug
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        return r.status_code, r.url
    except Exception as e:
        return None, str(e)


def try_alternate_slugs(name):
    """
    Try several alternate slug variations to find the correct Snobe URL.
    Snobe sometimes uses:
    - Full name including stop words
    - Different abbreviations
    - 'Independent School' instead of 'College'
    - 'Academy' instead of 'School'
    """
    variants = set()

    # Variant 1: full name, no stop word removal
    full = str(name).lower()\
        .replace("'", "").replace(",", "").replace(".", "")\
        .replace("(", "").replace(")", "").strip()
    variants.add(re.sub(r"\s+", "-", full))

    # Variant 2: replace 'college' with 'independent-school'
    v2 = make_slug(name).replace("college", "independent-school")
    variants.add(v2)

    # Variant 3: replace 'college' with 'school'
    v3 = make_slug(name).replace("college", "school")
    variants.add(v3)

    # Variant 4: add 'school' at end if not present
    base = make_slug(name)
    if not base.endswith("school") and not base.endswith("college") and not base.endswith("academy"):
        variants.add(base + "-school")

    # Variant 5: remove 'and' without stop word filter (some schools keep 'and')
    words_with_and = str(name).lower()\
        .replace("'", "").replace(",", "").replace(".", "")\
        .strip().split()
    slug_with_and = "-".join(words_with_and)
    variants.add(re.sub(r"-+", "-", slug_with_and).strip("-"))

    for slug in variants:
        if slug == make_slug(name):
            continue  # already checked this one
        status, final_url = check_snobe_url(slug)
        if status == 200:
            return slug, SNOBE_BASE + slug

    return None, None


def main():
    print("Loading schools.json...")
    with open(SCHOOLS_FILE, encoding="utf-8") as f:
        schools = json.load(f)

    # Only check schools that are in London (should all be, but just in case)
    # Skip schools without names
    schools = [s for s in schools if s.get("name") and s.get("urn")]

    print(f"Total schools to check: {len(schools):,}")
    print("This will take a while due to rate limiting. Checking 1 school/second.\n")

    corrections = []
    missing = []
    ok_count = 0
    checked = 0

    for s in schools:
        name = s["name"]
        urn  = s["urn"]
        slug = make_slug(name)

        status, final_url = check_snobe_url(slug)
        checked += 1

        if status == 200:
            ok_count += 1
            if checked % 100 == 0:
                print(f"  [{checked}/{len(schools)}] {ok_count} OK, {len(corrections)} wrong, {len(missing)} missing...")

        elif status == 404 or status is None:
            # Try alternate slugs
            correct_slug, correct_url = try_alternate_slugs(name)

            if correct_url:
                corrections.append({
                    "urn":          urn,
                    "name":         name,
                    "wrong_slug":   slug,
                    "correct_slug": correct_slug,
                    "correct_url":  correct_url,
                })
                print(f"  ✓ FIXED: {name}")
                print(f"    Wrong:   {SNOBE_BASE + slug}")
                print(f"    Correct: {correct_url}")
            else:
                missing.append({
                    "urn":  urn,
                    "name": name,
                    "tried_slug": slug,
                })
                print(f"  ✗ NOT ON SNOBE: {name}")

        # Rate limit — 1 request per second to be respectful
        time.sleep(1.0)

    # Save results
    with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(corrections, f, indent=2, ensure_ascii=False)

    with open(MISSING_FILE, "w", encoding="utf-8") as f:
        json.dump(missing, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"Done. Checked {checked:,} schools.")
    print(f"  ✅ Correct slug:  {ok_count:,}")
    print(f"  🔧 Wrong slug:    {len(corrections):,}  → saved to {CORRECTIONS_FILE}")
    print(f"  ❌ Not on Snobe:  {len(missing):,}  → saved to {MISSING_FILE}")
    print(f"{'='*50}")

    # Now apply corrections to schools.json
    if corrections:
        print(f"\nApplying {len(corrections)} corrections to schools.json...")
        correction_map = {c["urn"]: c["correct_url"] for c in corrections}

        updated = 0
        for s in schools:
            if s.get("urn") in correction_map:
                s["snobe_url"] = correction_map[s["urn"]]
                updated += 1

        with open(SCHOOLS_FILE, "w", encoding="utf-8") as f:
            json.dump(schools, f, ensure_ascii=False, separators=(",", ":"))

        print(f"Updated schools.json with {updated} corrected Snobe URLs.")
        print("Run build_school_pages.py to rebuild all pages with correct links.")


if __name__ == "__main__":
    main()
