#!/usr/bin/env python3
"""
fetch_isi_reports.py

Scrapes the Independent Schools Inspectorate (isi.net) public reports listing
and merges each matched London school's latest inspection report into
schools.json.

Why: ~330 of the site's 511 independent schools are ISI-inspected (association
schools), so they never appear in Ofsted data and currently show "Not yet
rated". ISI publishes no bulk CSV — but its listing pages ARE server-rendered,
so we crawl them politely once a month.

What it does:
  1. Crawls https://www.isi.net/reports/?p=1..N listing pages and extracts
     every institution URL + postcode (postcodes appear in the address blob).
  2. Keeps only institutions whose postcode matches an independent school in
     schools.json (fallback: normalised name match).
  3. Fetches each matched institution page and extracts the reports list.
     Report PDF filenames encode type + date, e.g. ROU6408_20250318.pdf
     = Routine inspection, 2025-03-18.
  4. Caches everything in data/isi_reports.json (re-crawl only after TTL).
  5. Writes into schools.json for each matched school:
        "isi_url":            institution page on isi.net
        "isi_latest_report":  {"type", "date", "url"}
        "inspectorate":       "ISI"

Note on outcomes: since September 2023 ISI reports carry NO single-word grade
(the framework reports whether standards are met, with possible commendation).
So we surface the latest report type + date + link, which is the honest,
verifiable signal. Narrative outcomes (e.g. "met all standards") can be
layered on via agent_enrich.py.

Run order (monthly_refresh.yml):
  refresh_data.py -> fetch_independent_ratings.py -> fetch_isi_reports.py
  -> fetch_independent_school_data.py -> agent_enrich.py -> build_school_pages.py

Usage:
  python3 scripts/fetch_isi_reports.py            # normal run (uses cache)
  ISI_FORCE=1 python3 scripts/fetch_isi_reports.py  # ignore cache TTL
  ISI_DRY_RUN=1 ...                                 # don't write schools.json
"""

import json
import os
import pathlib
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHOOLS_JSON = ROOT / "schools.json"
CACHE_FILE = ROOT / "data" / "isi_reports.json"

BASE = "https://www.isi.net"
LIST_URL = BASE + "/reports/?p={page}"
USER_AGENT = "LondonSchoolDirectory/1.0 (londonschool.directory; open-data school directory)"
CRAWL_DELAY = 1.0          # seconds between requests — be polite
CACHE_TTL_DAYS = int(os.environ.get("ISI_CACHE_TTL", "27"))  # < monthly cadence
FORCE = os.environ.get("ISI_FORCE", "0") == "1"
DRY_RUN = os.environ.get("ISI_DRY_RUN", "0") == "1"

# UK postcode (tolerant)
POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b")
# institution links on listing pages
INST_LINK_RE = re.compile(r'href="(?:https?://www\.isi\.net)?(/institutions/school/[a-z0-9\-]+-(\d+))"', re.I)
# report links on institution pages: r=<TYPE><id>_<yyyymmdd>.pdf
REPORT_RE = re.compile(
    r'href="(https?://reports\.isi\.net/DownloadReport\.aspx\?[^"]*?r=([A-Z]+)\d+_(\d{8})\.pdf[^"]*)"', re.I)

REPORT_TYPE_LABELS = {
    "ROU": "Routine inspection",
    "EQI": "Educational quality inspection",
    "FCI": "Focused compliance inspection",
    "RCI": "Regulatory compliance inspection",
    "ADD": "Regulatory compliance inspection",
    "GRT": "Integrated inspection",
    "FLW": "Follow-up / material change visit",
    "FLWMC": "Material change inspection",
    "MC": "Material change inspection",
    "PRO": "Progress monitoring visit",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")


def norm_name(name: str) -> str:
    """Normalise a school name for fuzzy matching."""
    n = name.lower()
    n = re.sub(r"\b(the|school|college|preparatory|prep|junior|senior|and|&|of|st|saint)\b", " ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return " ".join(n.split())


def norm_pc(pc: str) -> str:
    return re.sub(r"\s+", "", (pc or "").upper())


def crawl_listing() -> list[dict]:
    """Crawl all listing pages; return [{url, id, postcode, name}]."""
    institutions, seen = [], set()
    page, empty_streak = 1, 0
    while page <= 200 and empty_streak < 2:
        html = fetch(LIST_URL.format(page=page))
        links = INST_LINK_RE.findall(html)
        if not links:
            empty_streak += 1
            page += 1
            continue
        empty_streak = 0
        # Split page into per-institution chunks so each postcode is paired
        # with the right link (links appear before their address blobs).
        new = 0
        chunks = re.split(r'(?=href="(?:https?://www\.isi\.net)?/institutions/school/)', html)
        for chunk in chunks:
            m = INST_LINK_RE.search(chunk)
            if not m:
                continue
            path, inst_id = m.group(1), m.group(2)
            if inst_id in seen:
                continue
            seen.add(inst_id)
            pm = POSTCODE_RE.search(chunk)
            nm = re.search(r'/institutions/school/([a-z0-9\-]+)-\d+', path)
            institutions.append({
                "url": BASE + path,
                "id": inst_id,
                "postcode": (pm.group(1) + pm.group(2)) if pm else None,
                "slug": nm.group(1) if nm else "",
            })
            new += 1
        print(f"  page {page}: +{new} institutions (total {len(institutions)})")
        page += 1
        time.sleep(CRAWL_DELAY)
    return institutions


def extract_reports(html: str) -> list[dict]:
    """Extract report list from an institution page, newest first."""
    reports = []
    for url, rtype, ymd in REPORT_RE.findall(html):
        rtype = rtype.upper()
        # Longest-prefix match against known type codes
        label = None
        for code in sorted(REPORT_TYPE_LABELS, key=len, reverse=True):
            if rtype.startswith(code):
                label = REPORT_TYPE_LABELS[code]
                break
        try:
            date = datetime.strptime(ymd, "%Y%m%d").date().isoformat()
        except ValueError:
            continue
        reports.append({"type": label or f"Inspection ({rtype})",
                        "date": date, "url": url.replace("&amp;", "&")})
    reports.sort(key=lambda r: r["date"], reverse=True)
    # de-dup by url
    out, seen = [], set()
    for r in reports:
        if r["url"] not in seen:
            seen.add(r["url"])
            out.append(r)
    return out


def main():
    schools = json.loads(SCHOOLS_JSON.read_text(encoding="utf-8"))
    independents = [s for s in schools if "independent" in (s.get("school_type") or "").lower()]
    print(f"{len(independents)} independent schools in schools.json")

    # postcode + name lookups
    by_pc, by_name = {}, {}
    for s in independents:
        if s.get("postcode"):
            by_pc.setdefault(norm_pc(s["postcode"]), []).append(s)
        by_name.setdefault(norm_name(s.get("name", "")), []).append(s)

    # ── load or build cache ────────────────────────────────────────────────
    cache = {}
    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    fetched_at = cache.get("fetched_at")
    stale = True
    if fetched_at and not FORCE:
        age = (datetime.now(timezone.utc)
               - datetime.fromisoformat(fetched_at)).days
        stale = age >= CACHE_TTL_DAYS
        print(f"cache age: {age}d (ttl {CACHE_TTL_DAYS}d) -> {'stale' if stale else 'fresh'}")

    if stale:
        print("Crawling ISI listing pages…")
        institutions = crawl_listing()

        # match to our schools
        matched = []
        for inst in institutions:
            target = None
            if inst["postcode"] and norm_pc(inst["postcode"]) in by_pc:
                cands = by_pc[norm_pc(inst["postcode"])]
                if len(cands) == 1:
                    target = cands[0]
                else:  # same postcode, disambiguate by name
                    slug_name = norm_name(inst["slug"].replace("-", " "))
                    for c in cands:
                        if norm_name(c["name"]) == slug_name:
                            target = c
                            break
            if target is None:
                slug_name = norm_name(inst["slug"].replace("-", " "))
                cands = by_name.get(slug_name, [])
                if len(cands) == 1:
                    target = cands[0]
            if target is not None:
                matched.append((inst, target))
        print(f"matched {len(matched)} ISI institutions to London schools")

        # fetch each matched institution page for its reports
        results = {}
        for i, (inst, school) in enumerate(matched, 1):
            try:
                html = fetch(inst["url"])
                reports = extract_reports(html)
            except Exception as e:
                print(f"  ! {inst['url']}: {e}")
                continue
            results[str(school["urn"])] = {
                "isi_url": inst["url"],
                "reports": reports,
            }
            if i % 25 == 0:
                print(f"  fetched {i}/{len(matched)} institution pages")
            time.sleep(CRAWL_DELAY)

        cache = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "schools": results,
        }
        CACHE_FILE.parent.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        print(f"cached {len(results)} schools -> {CACHE_FILE.name}")

    # ── merge into schools.json ────────────────────────────────────────────
    results = cache.get("schools", {})
    merged = 0
    for s in schools:
        rec = results.get(str(s.get("urn")))
        if not rec:
            continue
        s["isi_url"] = rec["isi_url"]
        s["inspectorate"] = "ISI"
        if rec["reports"]:
            s["isi_latest_report"] = rec["reports"][0]
        merged += 1

    if DRY_RUN:
        print(f"[dry-run] would merge ISI data into {merged} schools")
        return
    SCHOOLS_JSON.write_text(
        json.dumps(schools, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ merged ISI data into {merged} schools")


if __name__ == "__main__":
    main()
