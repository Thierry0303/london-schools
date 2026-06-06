#!/usr/bin/env python3
"""
fetch_independent_ratings.py

Fetches the DfE's management information CSV for non-association independent
schools (Ofsted-inspected) and merges inspection ratings into schools.json.

The DfE publishes this CSV annually. The URL below points to the most recent
release. Update CSV_URL each year when a new release appears — check:
https://www.gov.uk/government/statistical-data-sets/non-association-independent-schools-inspections-and-outcomes-management-information

Run order: after refresh_nhs_data.py, before build_school_pages.py.

What this script does:
  1. Downloads the DfE CSV.
  2. Builds a lookup by URN → inspection data.
  3. For each school in schools.json with school_type containing "independent"
     and no existing quality_label, attempts to match by URN.
  4. If matched, sets quality_label, ofsted_score, and ofsted_url.
  5. Writes schools.json back in place.
  6. Prints a summary of matches found.
"""

import csv
import io
import json
import os
import pathlib
import urllib.request

# ── Config ────────────────────────────────────────────────────────────────────

# Update this URL when DfE publishes a new annual release (usually Feb/March).
# Find the latest at:
# https://www.gov.uk/government/statistical-data-sets/non-association-independent-schools-inspections-and-outcomes-management-information
CSV_URL = (
    "https://assets.publishing.service.gov.uk/media/679cee251d14e76535afb685/"
    "Management_information_-_non-association_independent_schools_most_recent_"
    "inspections_data_as_at_31_December_2024.csv"
)

# Ofsted numeric rating → label mapping
RATING_MAP = {
    "1": "Outstanding",
    "2": "Good",
    "3": "Requires improvement",
    "4": "Inadequate",
}

# Ofsted label → numeric score used by the site's composite scoring
SCORE_MAP = {
    "Outstanding":           100,
    "Good":                   75,
    "Requires improvement":   50,
    "Inadequate":             25,
}

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHOOLS_JSON = ROOT / "schools.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def download_csv(url: str) -> list[dict]:
    """Download the DfE CSV and return rows as a list of dicts."""
    print(f"Downloading DfE CSV from:\n  {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "LondonSchoolDirectory/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8-sig")  # strip BOM if present
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    print(f"  Downloaded {len(rows):,} rows")
    return rows


def build_lookup(rows: list[dict]) -> dict[str, dict]:
    """Build a URN → inspection data lookup from DfE CSV rows."""
    lookup = {}
    for row in rows:
        urn = row.get("URN", "").strip()
        if not urn:
            continue
        overall = row.get("Overall effectiveness", "").strip()
        label = RATING_MAP.get(overall)
        if not label:
            continue  # skip rows with no valid rating
        ofsted_url = row.get(
            "Web link to Ofsted provider page (opens in new window)", ""
        ).strip()
        inspection_date = row.get("First day of inspection", "").strip()
        lookup[urn] = {
            "quality_label": label,
            "ofsted_score":  SCORE_MAP[label],
            "ofsted_url":    ofsted_url,
            "inspection_date": inspection_date,
            "source":        "DfE non-association independent schools CSV",
        }
    print(f"  Built lookup with {len(lookup):,} rated schools")
    return lookup


def is_independent(school: dict) -> bool:
    """Return True if this school is an independent school without a rating."""
    school_type = (school.get("school_type") or "").lower()
    return "independent" in school_type or "non-maintained" in school_type


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load schools.json
    print(f"\nLoading {SCHOOLS_JSON}")
    schools = json.loads(SCHOOLS_JSON.read_text(encoding="utf-8"))
    print(f"  {len(schools):,} schools loaded")

    # Download and parse DfE CSV
    rows = download_csv(CSV_URL)
    lookup = build_lookup(rows)

    # Counters
    matched      = 0
    already_had  = 0
    no_urn       = 0
    not_in_csv   = 0
    not_indep    = 0

    for school in schools:
        if not is_independent(school):
            not_indep += 1
            continue

        # Skip if already has a rating
        if school.get("quality_label") and school["quality_label"] not in (
            "Not yet rated", "N/A", None, ""
        ):
            already_had += 1
            continue

        urn = str(school.get("urn") or school.get("URN") or "").strip()
        if not urn or urn in ("None", "nan", ""):
            no_urn += 1
            continue

        if urn not in lookup:
            not_in_csv += 1
            continue

        # Apply the rating
        data = lookup[urn]
        school["quality_label"]   = data["quality_label"]
        school["ofsted_score"]    = data["ofsted_score"]
        if data["ofsted_url"] and not school.get("ofsted_url"):
            school["ofsted_url"]  = data["ofsted_url"]
        if data["inspection_date"] and not school.get("inspection_date"):
            school["inspection_date"] = data["inspection_date"]
        matched += 1

    # Save back
    SCHOOLS_JSON.write_text(
        json.dumps(schools, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Summary
    print(f"""
── Summary ──────────────────────────────────────────
  Total schools in JSON:       {len(schools):>6,}
  Non-independent (skipped):   {not_indep:>6,}
  Already had a rating:        {already_had:>6,}
  No URN (can't match):        {no_urn:>6,}
  Independent, not in CSV:     {not_in_csv:>6,}  ← likely ISI-inspected
  ✓ Ratings applied:           {matched:>6,}
─────────────────────────────────────────────────────
schools.json updated.
""")

    if not_in_csv > 0:
        print(
            f"Note: {not_in_csv} independent schools were not found in the DfE CSV.\n"
            "These are likely ISI-inspected association schools. Their quality_label\n"
            "will remain 'Not yet rated' until ISI data is available.\n"
            "Consider adding an 'isi_inspected' flag to distinguish them from\n"
            "genuinely unrated schools.\n"
        )


if __name__ == "__main__":
    main()
