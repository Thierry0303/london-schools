"""
fix_snobe_urls.py
─────────────────
Quick fix for known wrong Snobe URLs in schools.json.

Does two things:
1. Applies known correct URLs for specific schools
2. Validates all stored snobe_url values — removes any that return 404
   so check_snobe_slugs.py can find the correct ones

Run from repo root:
    python3 scripts/fix_snobe_urls.py

Requirements: pip install requests
"""

import json
import re
import time
import requests

SCHOOLS_FILE = "schools.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LondonSchoolDirectory/1.0)"
}

# Known correct URLs — add any you discover here
# Format: school name as it appears in schools.json → correct Snobe URL
KNOWN_CORRECT = {
    "St Vincent de Paul Catholic Primary School":
        "https://snobe.co.uk/schools/st-vincent-de-paul-catholic-primary-school-0",
    "St Vincent de Paul RC Primary School":
        "https://snobe.co.uk/schools/st-vincent-de-paul-catholic-primary-school-0",
    "St Vincent's Catholic Primary School":
        "https://snobe.co.uk/schools/st-vincents-catholic-primary-school",
    "St Eugene de Mazenod Roman Catholic Primary School":
        "https://snobe.co.uk/schools/st-eugene-de-mazenod-roman-catholic-primary-school",
    "Thomas Coram Centre":
        "https://snobe.co.uk/nursery/thomas-coram-centre",
    "Ashbourne College":
        "https://snobe.co.uk/schools/ashbourne-independent-school",
    "City of London School for Girls":
        "https://snobe.co.uk/schools/city-london-school-girls",
    "The Aldgate School":
        "https://snobe.co.uk/schools/aldgate-school",
    # Saint vs St — Snobe uses full "saint" for some Catholic schools
    "St Francis of Assisi Catholic Primary School":
        "https://snobe.co.uk/schools/saint-francis-assisi-catholic-primary-school",
    "St Francis of Assisi RC Primary School":
        "https://snobe.co.uk/schools/saint-francis-assisi-catholic-primary-school",
}

def check_url(url):
    """Return True if URL gives 200."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False


def main():
    print("Loading schools.json...")
    with open(SCHOOLS_FILE, encoding="utf-8") as f:
        schools = json.load(f)
    print(f"  {len(schools):,} schools loaded\n")

    applied = 0
    cleared = 0
    checked = 0

    for s in schools:
        name = s.get("name", "")
        current_url = s.get("snobe_url", "")

        # 1. Apply known corrections
        if name in KNOWN_CORRECT:
            correct = KNOWN_CORRECT[name]
            if s.get("snobe_url") != correct:
                print(f"  ✅ CORRECTING: {name}")
                print(f"     Old: {s.get('snobe_url', 'none')}")
                print(f"     New: {correct}")
                s["snobe_url"] = correct
                applied += 1

        # 2. Validate stored URLs — check they actually work
        # Only check schools that have a snobe_url and it hasn't just been corrected
        elif current_url and name not in KNOWN_CORRECT:
            status = check_url(current_url)
            checked += 1
            if not status:
                print(f"  ❌ CLEARING 404: {name}")
                print(f"     Bad URL: {current_url}")
                s["snobe_url"] = None
                cleared += 1
            time.sleep(0.3)  # gentle rate limiting

            if checked % 50 == 0:
                print(f"  [{checked} validated, {cleared} cleared so far...]")

    # Save
    with open(SCHOOLS_FILE, "w", encoding="utf-8") as f:
        json.dump(schools, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n{'='*50}")
    print(f"Done.")
    print(f"  ✅ Known corrections applied: {applied}")
    print(f"  ❌ Bad URLs cleared:          {cleared}")
    print(f"  🔍 URLs validated:            {checked}")
    print(f"\nNext steps:")
    print(f"  1. python3 scripts/check_snobe_slugs.py  (finds correct URLs for cleared ones)")
    print(f"  2. python3 scripts/build_school_pages.py")
    print(f"  3. git add schools.json schools/ && git commit -m 'fix: snobe urls' && git push")


if __name__ == "__main__":
    main()
