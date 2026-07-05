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
Return a JSON object with these keys (use null if not found on a credible source):
- "fees_annual": integer GBP, the ANNUAL day fee for the senior/main phase, VAT-inclusive if stated. From the school's OWN website fees page only.
- "a_level_a_star_b": number, percentage of A-level grades at A*-B (if the school reports A*-A only, use that and set a_level_note accordingly). From the school's OWN results/exam page.
- "a_level_note": short string clarifying which measure (e.g. "A*-B" or "A*-A") or null.
- "gcse_9_7": number, percentage of GCSE grades at 9-7. From the school's OWN results page.
- "exam_year": integer year the exam results refer to (e.g. 2025).
- "isi_status": string, the latest ISI inspection outcome, ONLY if using current ISI wording; null if unsure.
"""

STATE_FIELDS = """
Return a JSON object with these keys (use null if not found on a credible source):
- "last_distance_offered_km": number, the distance (in km) to the furthest pupil offered a place in the most recent normal admissions round, under the school's distance/proximity oversubscription criterion. ONLY from the relevant London BOROUGH COUNCIL admissions data or the school's own admissions page. This is the "cut-off distance" / "last distance offered". If the school did not fill on distance (e.g. faith/banding/aptitude), return null.
- "last_distance_year": integer year the distance refers to (e.g. 2025).
- "oversubscribed": boolean, whether the school was oversubscribed in the most recent round (more applications than places), if stated by an official source; else null.
- "published_admission_number": integer, the PAN (number of places) for the main entry year, from the borough or school admissions page.
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
            return None
        data = r.json()
    except Exception as e:
        print(f"    request failed: {e}")
        return None

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
def clean_result(result, category):
    """Return a clean agent_data dict, or None if nothing usable."""
    if not result or not isinstance(result, dict):
        return None
    confidence = (result.get("confidence") or "low").lower()
    if confidence not in ACCEPT_CONFIDENCE:
        return None

    values = result.get("values") or {}
    sources = result.get("sources") or {}

    kept = {}
    kept_sources = {}
    for k, v in values.items():
        if v is None or v == "":
            continue
        src = sources.get(k)
        # require a source URL that looks like a real URL
        if not src or not str(src).startswith("http"):
            continue
        kept[k] = v
        kept_sources[k] = src

    if not kept:
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

    print(f"Agent enrichment: {len(candidates)} candidates, processing up to {MAX_PER_RUN}")
    processed = 0
    written = 0

    for urn, school, cat in candidates[:MAX_PER_RUN]:
        name = school.get("name", "?")
        print(f"  [{processed+1}] {name} ({cat})")
        result = call_agent(school, cat)
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
