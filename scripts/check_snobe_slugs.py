"""
check_snobe_slugs.py
────────────────────
Verifies snobe_url values already written into schools.json by reset_snobe_urls.py.
Does NOT regenerate slugs — that's reset_snobe_urls.py's job. We trust its KNOWN
table and its generated slugs, and just check whether the resulting URL is live.

Three improvements over the previous version:
  1. Uses a real browser User-Agent + headers so Cloudflare/Snobe doesn't 403.
  2. Validates schools.json's snobe_url directly (not a freshly-regenerated slug).
  3. Aborts early if it detects a systematic block — no more 50-minute noise logs.

USAGE:
  Test (10 schools, ~30s):  python3 scripts/check_snobe_slugs.py --test
  Full (3k+ schools, ~30m): python3 scripts/check_snobe_slugs.py
"""

import json
import re
import sys
import time
import requests

SCHOOLS_FILE     = "schools.json"
CORRECTIONS_FILE = "snobe_corrections.json"
MISSING_FILE     = "snobe_missing.json"
SNOBE_BASE       = "https://snobe.co.uk/schools/"
SNOBE_NURSERY    = "https://snobe.co.uk/nursery/"
STOP_WORDS       = {"the", "of", "for", "and", "a", "at", "in", "by", "with", "an"}

# Real Chrome User-Agent + the headers a real browser actually sends.
# Snobe's CDN blocks vanilla python-requests; this passes through cleanly.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# After the first 20 checks, if half or more were blocked/errored, abort.
BLOCK_CHECK_AFTER  = 20
BLOCK_ABORT_RATIO  = 0.5

TEST_NAMES = [
    "The Aldgate School",
    "Ashbourne College",
    "City of London School for Girls",
    "Camden School for Girls",
    "Hackney New School",
    "Haverstock School",
    "St Paul's Cathedral School",
    "St Vincent de Paul RC Primary School",
    "Thomas Coram Centre",
    "St Francis of Assisi Catholic Primary School",
]

session = requests.Session()
session.headers.update(HEADERS)


def make_slug(name: str) -> str:
    """Mirror reset_snobe_urls.make_slug so variant search stays consistent."""
    words = (
        str(name).lower()
        .replace("’", "").replace("‘", "").replace("'", "")
        .replace(",", "").replace(".", "").replace("(", "").replace(")", "")
        .strip().split()
    )
    slug = "-".join(w for w in words if w not in STOP_WORDS)
    return re.sub(r"-+", "-", slug).strip("-")


def fetch_status(url: str) -> int:
    """Return HTTP status (or -1 on network error)."""
    try:
        r = session.get(url, timeout=15, allow_redirects=True, stream=True)
        r.close()  # Don't download the body, just want the status.
        return r.status_code
    except Exception:
        return -1


def try_variants(name: str):
    """If the stored URL 404s, try common Snobe slug variants. Return URL on hit."""
    base = make_slug(name)
    cands = [base]

    # St ↔ Saint — Snobe is inconsistent across schools
    if base.startswith("st-"):
        cands.append("saint-" + base[3:])
    elif base.startswith("saint-"):
        cands.append("st-" + base[6:])
    if "-st-" in base:
        cands.append(base.replace("-st-", "-saint-"))
    if "-saint-" in base:
        cands.append(base.replace("-saint-", "-st-"))

    # Institution-type swaps
    if "college" in base:
        cands.append(base.replace("college", "school"))
        cands.append(base.replace("college", "independent-school"))
    if "academy" in base:
        cands.append(base.replace("academy", "school"))
    if "school" in base:
        cands.append(base.replace("school", "academy"))
    if not any(w in base for w in {"school", "academy", "college", "institute", "centre"}):
        cands.append(base + "-school")

    # Deduplicate
    cands = list(dict.fromkeys(re.sub(r"-+", "-", c).strip("-") for c in cands if c))

    # Try /schools/{slug}, then /nursery/{slug}, with numeric suffixes -0..-4
    for prefix in (SNOBE_BASE, SNOBE_NURSERY):
        for slug in cands:
            for suffix in ("", "-0", "-1", "-2", "-3", "-4"):
                if fetch_status(prefix + slug + suffix) == 200:
                    return prefix + slug + suffix
                time.sleep(0.3)
    return None


def main():
    test_mode = "--test" in sys.argv
    print("=" * 55)
    print("Snobe URL validator — London Schools Explorer")
    print("=" * 55)

    with open(SCHOOLS_FILE, encoding="utf-8") as f:
        schools = json.load(f)

    # Only validate schools that actually have a URN, name, and snobe_url already set
    eligible = [s for s in schools if s.get("name") and s.get("urn") and s.get("snobe_url")]

    if test_mode:
        targets = [s for s in eligible if s.get("name") in TEST_NAMES]
        print(f"\nTEST MODE — {len(targets)} schools (~30 seconds)\n")
    else:
        targets = eligible
        print(f"\nFull run — {len(targets):,} schools (~30 minutes)\n")

    ok = 0
    blocked = 0
    corrections = []
    missing = []

    for i, s in enumerate(targets):
        name = s["name"]
        url = s["snobe_url"]
        status = fetch_status(url)

        if status == 200:
            ok += 1
            print(f"  OK     {name}")
        elif status == 404:
            # Real miss — try alternate slugs
            fixed = try_variants(name)
            if fixed:
                corrections.append({
                    "urn": s["urn"], "name": name,
                    "wrong_url": url, "correct_url": fixed,
                })
                print(f"  FIX    {name}  ->  {fixed}")
            else:
                missing.append({"urn": s["urn"], "name": name, "tried_url": url})
                print(f"  MISS   {name}")
        elif status in (403, 429, 503) or status == -1:
            blocked += 1
            print(f"  BLOCK  ({status})  {name}")
        else:
            blocked += 1
            print(f"  ERR    ({status})  {name}")

        # Early abort if we're being systematically blocked — no point in 50 more minutes of red logs
        if (i + 1) == BLOCK_CHECK_AFTER and blocked / BLOCK_CHECK_AFTER >= BLOCK_ABORT_RATIO:
            print()
            print("=" * 55)
            print(f"SYSTEMATIC BLOCK DETECTED: {blocked}/{BLOCK_CHECK_AFTER} requests blocked.")
            print("Snobe is rejecting requests from this IP/User-Agent.")
            print("Existing snobe_url values in schools.json are unchanged.")
            print("Run this script locally to actually validate; CI cannot reach Snobe today.")
            print("=" * 55)
            return

        if not test_mode and (i + 1) % 100 == 0:
            print(f"\n  [{i+1}/{len(targets)}]  OK={ok}  FIX={len(corrections)}  MISS={len(missing)}  BLOCK={blocked}\n")

        time.sleep(0.8)

    print()
    print("=" * 55)
    print(f"Results: OK={ok}  FIX={len(corrections)}  MISS={len(missing)}  BLOCK={blocked}")
    print("=" * 55)

    if test_mode:
        return

    with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(corrections, f, indent=2, ensure_ascii=False)
    with open(MISSING_FILE, "w", encoding="utf-8") as f:
        json.dump(missing, f, indent=2, ensure_ascii=False)

    if corrections:
        cmap = {c["urn"]: c["correct_url"] for c in corrections}
        for s in schools:  # write back to the full list, not just eligible
            if s.get("urn") in cmap:
                s["snobe_url"] = cmap[s["urn"]]
        with open(SCHOOLS_FILE, "w", encoding="utf-8") as f:
            json.dump(schools, f, ensure_ascii=False, separators=(",", ":"))
        print(f"\nPatched {len(corrections)} URLs in schools.json.")


if __name__ == "__main__":
    main()
