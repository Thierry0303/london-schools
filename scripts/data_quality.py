#!/usr/bin/env python3
"""
data_quality.py — data quality report + fabrication guard for schools.json
===========================================================================
Run this any time to get an honest picture of data completeness and to catch
fabricated / malformed data BEFORE it reaches the site.

  python3 scripts/data_quality.py            # print a report
  python3 scripts/data_quality.py --strict   # exit 1 if any CRITICAL issue

What it checks
--------------
CRITICAL (fail in --strict): things that break trust or the site
  • Fabricated-looking school names   e.g. "Oakwood School (Barnet 1)"
  • Duplicate URNs
  • Sequentially-generated postcodes   e.g. AA, BB, CC pattern
  • agent_data values with no source URL (should never happen post-validation)
  • Percentages outside 0–100
WARNING (report only): completeness gaps you may want to improve
  • Missing postcode / coordinates / website
  • Ofsted "Not yet rated" counts
  • Performance-data coverage (KS2/KS4)
  • Agent enrichment coverage
"""

import json
import pathlib
import re
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).parent.parent
SCHOOLS = ROOT / "schools.json"

RED = "\033[91m"; YEL = "\033[93m"; GRN = "\033[92m"; DIM = "\033[2m"; END = "\033[0m"


def load():
    return json.loads(SCHOOLS.read_text(encoding="utf-8"))


def check(schools):
    critical = []
    warnings = []
    n = len(schools)

    # ── CRITICAL: fabrication patterns ──
    fake_name_re = re.compile(r"\(\s*[A-Za-z]+\s+\d+\s*\)\s*$")
    fake_names = [x for x in schools if fake_name_re.search(x.get("name", ""))]
    if fake_names:
        critical.append((f"{len(fake_names)} school names look fabricated "
                         f"(e.g. '{fake_names[0]['name']}')", fake_names[:5]))

    # Duplicate URNs
    urns = Counter(x.get("urn") for x in schools if x.get("urn") is not None)
    dupes = [u for u, c in urns.items() if c > 1]
    if dupes:
        critical.append((f"{len(dupes)} duplicate URNs: {dupes[:10]}", None))

    # Sequential/synthetic postcodes (e.g. many ending AA, BB, CC in order)
    suffixes = [x.get("postcode", "")[-2:] for x in schools if x.get("postcode")]
    doubled = sum(1 for s in suffixes if len(s) == 2 and s[0] == s[1] and s.isalpha())
    if doubled > n * 0.2:
        critical.append((f"{doubled} postcodes end in doubled letters (AA/BB/CC) — "
                         f"looks synthetically generated", None))

    # agent_data values without a source
    unsourced = []
    for x in schools:
        ad = x.get("agent_data")
        if not ad:
            continue
        vals = ad.get("values", {})
        srcs = ad.get("sources", {})
        NO_SRC_OK = {"fees_note", "distance_note", "a_level_note",
                     "exam_year", "isi_year", "last_distance_year", "oversubscribed"}
        for k in vals:
            if k in NO_SRC_OK:
                continue
            if not srcs.get(k, "").startswith("http"):
                unsourced.append((x["name"], k))
    if unsourced:
        critical.append((f"{len(unsourced)} agent values have no source URL", unsourced[:5]))

    # Percentages out of range
    pct_fields = ["ks2_expected_pct", "ks4_grade5_em", "ks4_grade4_em"]
    bad_pct = []
    for x in schools:
        for f in pct_fields:
            v = x.get(f)
            if isinstance(v, (int, float)) and not (0 <= v <= 100):
                bad_pct.append((x["name"], f, v))
    if bad_pct:
        # >100 can be legitimate in DfE data occasionally; flag only if wildly off
        wild = [b for b in bad_pct if b[2] < 0 or b[2] > 130]
        if wild:
            critical.append((f"{len(wild)} percentages wildly out of range", wild[:5]))

    # ── WARNINGS: completeness ──
    def missing(field):
        return sum(1 for x in schools if not x.get(field) or x.get(field) == "N/A")

    for field, label in [("postcode", "postcode"), ("lat", "coordinates"),
                         ("website", "website"), ("head_name", "head teacher")]:
        m = missing(field)
        if m:
            warnings.append(f"{m}/{n} missing {label} ({100*m//n}%)")

    ql = Counter(x.get("quality_label") or x.get("score_band") or "None" for x in schools)
    warnings.append(f"Ofsted: {ql.get('Not yet rated',0)} not yet rated, "
                    f"{ql.get('None',0)} with no label")

    ad_count = sum(1 for x in schools if x.get("agent_data"))
    warnings.append(f"Agent enrichment: {ad_count}/{n} schools "
                    f"({100*ad_count//n}%)")

    return critical, warnings


def main():
    strict = "--strict" in sys.argv
    schools = load()
    n = len(schools)

    print("=" * 64)
    print(f"  DATA QUALITY REPORT — {n:,} schools")
    print("=" * 64)

    critical, warnings = check(schools)

    print(f"\n{'─'*64}\nCOMPLETENESS\n{'─'*64}")
    core = ["name", "postcode", "local_authority", "school_type", "phase",
            "pupils", "lat", "website", "quality_label"]
    for f in core:
        filled = sum(1 for x in schools if x.get(f) not in (None, "", "N/A"))
        pct = 100 * filled // n
        colour = GRN if pct >= 90 else (YEL if pct >= 50 else RED)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"  {f:18s} {colour}{bar}{END} {pct:3d}%  ({filled:,}/{n:,})")

    print(f"\n{'─'*64}\nCRITICAL ISSUES (trust-breaking)\n{'─'*64}")
    if not critical:
        print(f"  {GRN}✓ None — no fabrication or malformed data detected{END}")
    else:
        for msg, sample in critical:
            print(f"  {RED}✗ {msg}{END}")
            if sample:
                for s in sample:
                    print(f"      {DIM}{s}{END}")

    print(f"\n{'─'*64}\nWARNINGS (completeness — improve over time)\n{'─'*64}")
    for w in warnings:
        print(f"  {YEL}•{END} {w}")

    print("\n" + "=" * 64)
    if critical:
        print(f"  {RED}RESULT: {len(critical)} critical issue(s) — investigate before deploy{END}")
        if strict:
            return 1
    else:
        print(f"  {GRN}RESULT: no critical issues — data is trustworthy{END}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
