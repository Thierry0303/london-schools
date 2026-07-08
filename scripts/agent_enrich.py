#!/usr/bin/env python3
"""
agent_enrich.py — AI-agent enrichment for London Schools Directory
==================================================================

Enriches schools with data that is NOT available in any central feed, by using
the Anthropic API's built-in web_search tool to look up each school on official /
own-domain sources, extract only what is actually found, and record the source
URL + a confidence score. Nothing is written unless a value is found on a
credible source.

DESIGN PRINCIPLES (these are what prevent fabricated data):
  1. The model is instructed to return null for any field it cannot find on a
     credible source. "I don't know" is a valid, expected answer.
  2. Every extracted value carries a `source_url` and `confidence` (high/med/low).
     Low-confidence or source-less values are dropped before writing.
  3. Enrichment is written to a separate `agent_data` object and NEVER overwrites
     existing fields in schools.json.
  4. Routing by school type — the agent only asks for data that genuinely exists
     for that type:
       - Independent schools  -> fees, a_level, gcse, isi_status
       - State-funded schools -> last_distance_offered (catchment radius),
                                  oversubscribed, published_admission_number
     (Metrics that don't exist for a type are never requested, so the model is
      never tempted to invent them. E.g. independent schools have NO catchment
      distance, so it is never asked.)
  5. Incremental + cached: results are cached in data/agent_cache.json keyed by
     URN. Re-runs only process schools not seen in the last `CACHE_TTL_DAYS`
     days, and stop after `MAX_PER_RUN` to stay within a monthly budget.

USAGE
-----
  ANTHROPIC_API_KEY=...  python3 scripts/agent_enrich.py
Optional env:
  AGENT_MAX_PER_RUN   (default 40)   how many schools to process this run
  AGENT_CACHE_TTL     (default 180)  days before a school is re-checked
  AGENT_MODEL         (default claude-sonnet-4-6)
  AGENT_DRY_RUN       (default 0)    1 = don't write schools.json, just report

The monthly workflow calls this AFTER refresh_data.py and BEFORE
build_school_pages.py, so freshly-found values appear on the next build.
"""

import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone, timedelta

# ── Config ──────────────────────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).parent.parent
SCHOOLS_JSON = ROOT / "schools.json"
DATA_DIR = ROOT / "data"
CACHE_FILE = DATA_DIR / "agent_cache.json"

MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-4-6")
MAX_PER_RUN = int(os.environ.get("AGENT_MAX_PER_RUN", "40"))
CACHE_TTL_DAYS = int(os.environ.get("AGENT_CACHE_TTL", "180"))
DRY_RUN = os.environ.get("AGENT_DRY_RUN", "0") == "1"
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Confidence values we accept for writing
ACCEPT_CONFIDENCE = {"high", "medium"}


# ── School-type routing ─────────────────────────────────────────────────────────
def school_category(school):
    """Return 'independent', 'state', or None (skip) for a school."""
    t = (school.get("school_type") or "").lower()
    if "independent" in t:
        return "independent"
    # State-funded mainstream types that use distance-based admissions
    state_markers = [
        "community school", "academy converter", "academy sponsor",
        "voluntary aided", "voluntary controlled", "foundation school",
        "free schools", "city technology", "university technical", "studio schools",
    ]
    # Exclude nurseries, PRUs, special, post-16-only (no standard catchment metric)
    exclude = ["special", "nursery", "pupil referral", "16", "alternative provision",
               "sixth form centres"]
    if any(x in t for x in exclude):
        return None
    if any(x in t for x in state_markers):
        return "state"
    return None


# ── Field specs per category ─────────────────────────────────────────────────────
# Each spec tells the model exactly what to look for, where, and the exact JSON
# shape to return. The prompt forbids guessing.
INDEPENDENT_FIELDS = """
This is an INDEPENDENT (fee-paying) school. Search its OWN official website
thoroughly and try to fill EVERY field below (look at the fees page, the exam
results/results page, and the ISI/inspection page). Return null only when a
field genuinely isn't published. Return a JSON object with these keys:

- "fees_annual": integer GBP — the ANNUAL day fee for the senior/main phase
  (multiply a termly fee by 3). VAT-inclusive if the school states VAT is included.
- "fees_note": short string — clarify what the fee covers if needed, e.g.
  "senior day, VAT incl." or "reception; senior fees differ". Else null.
- "a_level_a_star_a": number or null — % of A-level entries graded A*-A.
- "a_level_a_star_b": number or null — % of A-level entries graded A*-B.
- "gcse_9_7": number or null — % of GCSE entries graded 9-7.
- "exam_year": integer — the year these exam results refer to (e.g. 2025).
- "isi_status": string — the ISI inspection outcome, NORMALIZED to EXACTLY ONE of
  these values (map the school's wording to the closest):
    "Met all standards"      (current framework: standards met / compliant)
    "Not all standards met"  (current framework: some standards not met)
    "Excellent"              (old framework rating)
    "Good"                   (old framework rating)
    "Sound"                  (old framework rating)
    "Unsatisfactory"         (old framework rating)
  If you cannot map it confidently to one of these, return null.
- "isi_year": integer — year of the ISI inspection (e.g. 2024). Else null.

Give exam figures as plain numbers (e.g. 92.0, not "92%"). Never put sentences
in numeric fields.
"""

STATE_FIELDS = """
Return a JSON object with these keys (use null if not found on a credible source):
- "last_distance_offered_km": number, the distance to the furthest pupil offered a place in the most recent normal admissions round under the school's distance/proximity criterion (the "last distance offered" / "cut-off distance"). CONVERT MILES TO KM if the source uses miles (1 mile = 1.60934 km). If the school admits by banding and publishes several band distances, use the LARGEST band distance and note the banding in "distance_note". If the school did NOT fill on distance (sources say "n/a", "no distance cut-off", or it admits by faith/aptitude/test only), return null and set "distance_note" to explain. 
- "last_distance_year": integer year the distance refers to (e.g. 2025 or 2026).
- "distance_note": short string clarifying the measure (e.g. "furthest of 4 bands; largest = Band B 0.76mi", or "no distance cut-off — admits by banding") or null.
- "oversubscribed": boolean, whether oversubscribed in the most recent round, if an official source states it; else null.
- "published_admission_number": integer, the PAN (places) for the main entry year.

WHERE TO LOOK for the distance (search these, in order):
  1. The school's OWN website, pages titled "offer distances", "admissions outcome", "how places were allocated", "cut-off distance", or "catchment".
  2. The London BOROUGH COUNCIL's "how places were offered/allocated" report (often a PDF named like "How places were offered ... [year]").
  3. Do NOT use Locrating, Mumsnet, admissionsday, or other aggregators/forums for the number — those are not credible sources. You may only cite the school or the council.
If none of those credible sources give a number, return null. Do not estimate.
"""


def build_prompt(school, category):
    name = school.get("name", "")
    borough = school.get("local_authority", "")
    postcode = school.get("postcode", "")
    website = school.get("website", "") or ""
    fields = INDEPENDENT_FIELDS if category == "independent" else STATE_FIELDS

    return f"""You are a careful data researcher. Find verified facts about a specific London school and return them as strict JSON.

SCHOOL:
  Name: {name}
  Borough: {borough}
  Postcode: {postcode}
  Website: {website}

TASK:
Use web search to find the following fields. {fields}

CRITICAL RULES:
- Only report a value if you find it on a CREDIBLE source: the school's own official website, or the relevant London borough council, or an official inspectorate (ISI/Ofsted). Do NOT use aggregator sites, tutoring blogs, or estimates.
- If you cannot find a value on such a source, return null for that field. Returning null is correct and expected — NEVER guess, estimate, or infer a number.
- For EACH non-null field, you MUST also include the exact source URL you used.
- Assign an overall "confidence" of "high", "medium", or "low" based on source quality and how directly the source stated the value.

Return ONLY a JSON object of this exact shape, nothing else:
{{
  "values": {{ ...the fields above... }},
  "sources": {{ "<field_name>": "<source url>", ... }},
  "confidence": "high" | "medium" | "low"
}}
"""


# ── API call ─────────────────────────────────────────────────────────────────────
def call_agent(school, category):
    """Call the Anthropic API with web_search enabled. Returns parsed dict or None."""
    import requests  # available in the workflow

    prompt = build_prompt(school, category)
    body = {
        "model": MODEL,
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    }
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers=headers, json=body, timeout=120)
        if r.status_code != 200:
            print(f"    API error {r.status_code}: {r.text[:200]}")
            return "API_ERROR"
        data = r.json()
    except Exception as e:
        print(f"    request failed: {e}")
        return "API_ERROR"

    # Concatenate all text blocks, then extract the JSON object
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return parse_json_blob(text)


def parse_json_blob(text):
    """Extract the last JSON object from model text."""
    if not text:
        return None
    # strip code fences
    text = text.replace("```json", "").replace("```", "")
    # find the outermost { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


# ── Validation: only keep credible, sourced values ───────────────────────────────
def _coerce_number(v):
    """Return a float if v looks numeric (strip %, £, commas), else None."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.replace("%", "").replace("£", "").replace(",", "").strip()
        try:
            return float(s)
        except ValueError:
            return None
    return None


# Fields that MUST be numeric; if the model put text there, we drop them.
NUMERIC_FIELDS = {
    "fees_annual", "a_level_a_star_a", "a_level_a_star_b", "gcse_9_7",
    "exam_year", "isi_year", "last_distance_offered_km", "last_distance_year",
    "published_admission_number",
}
# Percentage fields must be within a sane 0-100 range.
PERCENT_FIELDS = {"a_level_a_star_a", "a_level_a_star_b", "gcse_9_7"}
# ISI status must be one of these exact normalized values.
ISI_ALLOWED = {
    "Met all standards", "Not all standards met",
    "Excellent", "Good", "Sound", "Unsatisfactory",
}
# Free-text note fields we allow through (kept short at render time).
NOTE_FIELDS = {"fees_note", "distance_note"}


def _normalize_value(field, v):
    """Enforce the schema for a single field. Return normalized value or None to drop."""
    if field in NUMERIC_FIELDS:
        n = _coerce_number(v)
        if n is None:
            return None
        if field in PERCENT_FIELDS and not (0 <= n <= 100):
            return None
        # integers where appropriate
        if field in {"fees_annual", "exam_year", "isi_year",
                     "last_distance_year", "published_admission_number"}:
            return int(round(n))
        return n
    if field == "isi_status":
        return v if v in ISI_ALLOWED else None
    if field == "oversubscribed":
        return bool(v) if isinstance(v, bool) else None
    if field in NOTE_FIELDS:
        s = str(v).strip()
        return s[:120] if s else None
    # a_level_note kept for backward-compat but capped
    if field == "a_level_note":
        s = str(v).strip()
        return s[:120] if s else None
    # unknown field: pass through as string, capped
    s = str(v).strip()
    return s[:200] if s else None


def clean_result(result, category):
    """Return a clean agent_data dict, or None if nothing usable."""
    if not result or not isinstance(result, dict):
        return None
    confidence = (result.get("confidence") or "low").lower()
    if confidence not in ACCEPT_CONFIDENCE:
        return None

    values = result.get("values") or {}
    sources = result.get("sources") or {}

    # Note fields describe a nearby value and don't need their own source URL.
    NO_SOURCE_NEEDED = NOTE_FIELDS | {"a_level_note", "exam_year", "isi_year",
                                      "last_distance_year"}

    kept = {}
    kept_sources = {}
    for k, v in values.items():
        if v is None or v == "":
            continue
        norm = _normalize_value(k, v)
        if norm is None:
            continue  # failed schema validation — drop it (this is the reliability guard)
        if k in NO_SOURCE_NEEDED:
            kept[k] = norm
            continue
        src = sources.get(k)
        if not src or not str(src).startswith("http"):
            continue
        kept[k] = norm
        kept_sources[k] = src

    # Drop orphan notes whose parent value didn't survive.
    if "fees_note" in kept and "fees_annual" not in kept:
        kept.pop("fees_note")
    if "distance_note" in kept and "last_distance_offered_km" not in kept:
        # keep distance_note only if it explains WHY there's no distance
        pass  # allowed: explains "no distance cut-off"
    if "exam_year" in kept and not any(f in kept for f in ("a_level_a_star_a", "a_level_a_star_b", "gcse_9_7")):
        kept.pop("exam_year")
    if "isi_year" in kept and "isi_status" not in kept:
        kept.pop("isi_year")

    # Must have at least one substantive (non-note, non-year) value.
    substantive = [k for k in kept if k not in NOTE_FIELDS
                   and k not in {"a_level_note", "exam_year", "isi_year", "last_distance_year"}]
    if not substantive:
        return None

    return {
        "category": category,
        "values": kept,
        "sources": kept_sources,
        "confidence": confidence,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }


# ── Cache ────────────────────────────────────────────────────────────────────────
def load_cache():
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache):
    DATA_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def is_fresh(cache_entry):
    if not cache_entry:
        return False
    try:
        d = datetime.strptime(cache_entry.get("checked_at", ""), "%Y-%m-%d")
        return datetime.utcnow() - d < timedelta(days=CACHE_TTL_DAYS)
    except Exception:
        return False


# ── Main ─────────────────────────────────────────────────────────────────────────
def main():
    if not API_KEY:
        print("⚠️  ANTHROPIC_API_KEY not set — skipping agent enrichment (non-fatal).")
        return 0

    schools = json.loads(SCHOOLS_JSON.read_text(encoding="utf-8"))
    cache = load_cache()

    # Heal poisoned entries: AGENT_PURGE_EMPTY_SINCE=YYYY-MM-DD removes
    # "checked, nothing found" entries from that date onwards so those
    # schools are retried (use after runs that failed on API credits).
    purge_since = os.environ.get("AGENT_PURGE_EMPTY_SINCE")
    if purge_since:
        before = len(cache)
        cache = {u: e for u, e in cache.items()
                 if e.get("found") or (e.get("checked_at", "9999") < purge_since)}
        print(f"purged {before - len(cache)} empty cache entries since {purge_since}")

    # Candidates: schools we can enrich and haven't checked recently
    candidates = []
    for s in schools:
        cat = school_category(s)
        if not cat:
            continue
        urn = str(s.get("urn", ""))
        if not urn:
            continue
        if is_fresh(cache.get(urn)):
            continue
        candidates.append((urn, s, cat))

    # Independent schools first (fees/ISI are the site's biggest data gap),
    # largest schools first within each group so well-known names fill in
    # early. State schools follow once independents are covered.
    candidates.sort(key=lambda t: (t[2] != "independent", -(t[1].get("pupils") or 0)))

    print(f"Agent enrichment: {len(candidates)} candidates, processing up to {MAX_PER_RUN}")
    processed = 0
    written = 0
    api_errors = 0

    for urn, school, cat in candidates[:MAX_PER_RUN]:
        name = school.get("name", "?")
        print(f"  [{processed+1}] {name} ({cat})")
        result = call_agent(school, cat)
        if result == "API_ERROR":
            # Billing/auth/network problem — NOT a research result. Don't
            # cache it (the school must be retried) and bail out early if it
            # keeps happening, instead of burning through the whole batch.
            api_errors += 1
            print("       ! API failure — not cached, will retry next run")
            if api_errors >= 3 and written == 0:
                print("ABORTING RUN: repeated API failures — check the")
                print("ANTHROPIC_API_KEY secret and your API credit balance.")
                break
            processed += 1
            time.sleep(1)
            continue
        clean = clean_result(result, cat)

        # Record in cache regardless (so we don't re-hit empty ones constantly)
        cache[urn] = {
            "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "found": bool(clean),
            "data": clean,
        }
        if clean:
            written += 1
            for k, v in clean["values"].items():
                print(f"       ✓ {k}={v}  <{clean['sources'].get(k,'')[:60]}>")
        else:
            print("       — nothing verifiable found")

        processed += 1
        # Save incrementally: a canceled/timed-out run keeps everything
        # done so far (the next run resumes from the cache).
        if processed % 5 == 0:
            save_cache(cache)
        time.sleep(1)  # gentle pacing

    save_cache(cache)

    # Merge cache -> schools.json under agent_data (never overwrite existing keys)
    if not DRY_RUN:
        by_urn = {str(s.get("urn")): s for s in schools}
        merged = 0
        for urn, entry in cache.items():
            data = entry.get("data")
            if not data:
                continue
            s = by_urn.get(urn)
            if not s:
                continue
            s["agent_data"] = data  # separate namespace; build script reads this
            merged += 1
        SCHOOLS_JSON.write_text(json.dumps(schools, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"\nWrote agent_data for {merged} schools into schools.json")
    else:
        print("\nDRY RUN — schools.json not modified")

    print(f"Done. Processed {processed}, verified {written}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
