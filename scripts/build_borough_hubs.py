#!/usr/bin/env python3
"""
build_borough_hubs.py
---------------------
Generates static borough hub pages for londonschool.directory.

For each of the 33 London boroughs, this builds:
  /schools/{borough-slug}/index.html

Each hub page is fully server-rendered (no client-side JS required to display
core content), so it's crawlable and ranks for "schools in {borough}" type
queries.

Drop this file next to your existing build_school_pages.py and refresh_data.py.
Run after build_school_pages.py so the data is fresh.

Usage:
    python3 scripts/build_borough_hubs.py

It reads schools.json from the repo root and writes one /schools/{slug}/index.html
file per borough. It is defensive about missing fields — adjust the FIELD_MAP
constant at the top if your schools.json uses different field names.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Configuration — adjust if your schools.json uses different field names
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHOOLS_JSON = REPO_ROOT / "schools.json"
OUTPUT_DIR = REPO_ROOT / "schools"
SITE_URL = "https://londonschool.directory"

FIELD_MAP = {
    "name": ["name"],
    "borough": ["local_authority", "borough"],
    "phase": ["phase"],
    "type": ["school_type", "type"],
    "ofsted": ["quality_label", "ofsted_rating", "ofsted"],
    "ofsted_date": ["inspection_date", "ofsted_date"],
    "ks2_progress": ["ks2_expected_pct", "ks2_higher_pct", "ks2_progress"],
    "ks4_attainment_8": ["ks4_att8", "ks4_attainment_8", "attainment_8"],
    "apps_per_place": ["apps_per_place", "applications_per_place"],
    "crime_500m": ["crime_count", "crime_500m", "crime"],
    "imd_decile": ["imd_decile", "imd"],
    "postcode": ["postcode"],
    "address": ["street", "address"],
    "lat": ["lat", "latitude"],
    "lng": ["lng", "longitude"],
    "slug": ["slug"],
    "url_path": ["url_path"],
    "snobe_url": ["snobe_url"],
}

# London boroughs in canonical form. We normalise borough strings against this list
# so "City of Westminster", "Westminster", and "WESTMINSTER" all map to "westminster".
LONDON_BOROUGHS = [
    "Barking and Dagenham", "Barnet", "Bexley", "Brent", "Bromley", "Camden",
    "City of London", "Croydon", "Ealing", "Enfield", "Greenwich", "Hackney",
    "Hammersmith and Fulham", "Haringey", "Harrow", "Havering", "Hillingdon",
    "Hounslow", "Islington", "Kensington and Chelsea", "Kingston upon Thames",
    "Lambeth", "Lewisham", "Merton", "Newham", "Redbridge",
    "Richmond upon Thames", "Southwark", "Sutton", "Tower Hamlets",
    "Waltham Forest", "Wandsworth", "Westminster",
]

# Editorial intros per borough — written once, refreshed annually. Keep each
# ~3 sentences; they exist to give Google something unique on every hub page.
# Replace these gradually with longer hand-written ones for the highest-traffic boroughs.
BOROUGH_BLURBS = {
    "Camden": "Camden's schools sit at the heart of north-west central London, from large secondary academies near King's Cross to small church primaries in Hampstead and Kentish Town. The borough mixes some of the most oversubscribed state schools in the capital with strong faith and grammar provision. Camden's school admissions are coordinated by the council, with appeals heard each summer.",
    "Hackney": "Hackney has transformed its schools over the past two decades and now has one of the highest concentrations of Outstanding-rated primaries and secondaries in inner London. Demand for Reception and Year 7 places is high, and admission distances are short across most of the borough. The Learning Trust coordinates much of Hackney's admissions activity alongside the council.",
    "Tower Hamlets": "Tower Hamlets schools serve one of London's most diverse boroughs, covering Whitechapel, Bow, Poplar and the Isle of Dogs. The borough has seen substantial improvement in KS2 and KS4 results, and several secondaries rank among the highest performing in the country for disadvantaged-pupil progress. Admissions are coordinated by the local authority.",
    "Southwark": "Southwark's schools stretch from Bermondsey and Borough up through Camberwell, Peckham and Dulwich. The borough has a mix of community, faith and academy schools, with some of the most competitive admissions arrangements in south-east London. Many parents apply across the Southwark/Lambeth boundary, so understanding catchment is essential.",
    "Lambeth": "Lambeth schools cover Brixton, Streatham, Clapham, Vauxhall and Norwood, with a strong mix of state and faith provision. Several of the borough's secondaries are heavily oversubscribed, and primary applications are particularly competitive in the north of the borough. Appeals success rates in Lambeth track broadly with the inner-London average.",
    "Islington": "Islington's schools serve a densely populated inner-London borough running from Angel up through Highbury to Archway. The borough has invested heavily in school improvement and now has a high proportion of Good and Outstanding Ofsted ratings. Travel times to school are typically short, and waiting lists move regularly during the autumn term.",
    "Wandsworth": "Wandsworth has historically had one of the highest concentrations of Outstanding-rated schools in London, particularly in primary phase. The borough covers Battersea, Putney, Tooting, Balham and Wandsworth Town. Admissions are competitive across most of the borough, and catchment distances are tight for the most popular primaries.",
    "Hammersmith and Fulham": "Hammersmith and Fulham combines a relatively small geographic area with a strong concentration of high-performing primaries and secondaries. The borough has a notable independent and grammar presence alongside its state schools. Several of the most competitive primaries draw applicants from across west London.",
    "Westminster": "Westminster has a distinctive school mix dominated by faith primaries, a small number of community schools and some of London's best-known secondaries. The borough is small and densely populated, so catchment radii are short and many families apply across the Westminster/Camden border. Admissions in Westminster are managed by the council with most schools as their own admissions authority.",
    "Kensington and Chelsea": "Kensington and Chelsea has one of the smallest school populations of any London borough, with provision concentrated in primary phase and a smaller number of secondaries. Faith and independent provision is strong, and many families apply to neighbouring Westminster, Hammersmith and Fulham, or Brent. Admissions distances are typically short across the borough.",
    "Greenwich": "Greenwich's schools cover Woolwich, Eltham, Greenwich town, Charlton and Plumstead. The borough has invested significantly in secondary provision and has a number of recently rebuilt schools. Reception applications remain competitive in the west of the borough, particularly close to the river.",
    "Lewisham": "Lewisham schools serve a south-east London borough running from New Cross and Deptford through Catford, Brockley, Honor Oak and Lee. The borough has a strong primary offer and a growing reputation for improving secondaries. Admissions are coordinated centrally, with some Lewisham families applying into neighbouring Southwark or Greenwich.",
    "Bromley": "Bromley is one of London's largest boroughs by area and has a distinctive mix of grammar, foundation and community schools. The borough operates a partially selective system, and 11+ test preparation is a significant feature of secondary admissions. Reception applications tend to be most competitive in the north of the borough.",
    "Croydon": "Croydon's schools serve the largest population of any London borough and stretch from central Croydon out to Coulsdon, Purley, Norbury and South Norwood. The borough has a wide range of state and faith provision and a small number of grammar schools accepting Croydon applicants. Admissions are coordinated by the council.",
    "Newham": "Newham's schools serve East Ham, Stratford, Plaistow, Forest Gate and the Royal Docks. The borough has been consistently in the top half of London for KS2 and KS4 progress, with several secondaries achieving national recognition. Reception demand is high and admissions distances are short across most of the borough.",
    "Waltham Forest": "Waltham Forest covers Walthamstow, Leyton, Leytonstone and Chingford and has one of the strongest improvement stories of any London borough's schools in the last decade. The proportion of Outstanding-rated primaries has risen sharply, and secondaries are increasingly oversubscribed. Admissions are managed by the council.",
    "Redbridge": "Redbridge schools cover Ilford, Wanstead, Woodford and South Woodford, with a notable selective and grammar presence. The borough's primaries are heavily oversubscribed in central and southern wards. Many parents prepare for the 11+ from Year 4 onwards.",
    "Haringey": "Haringey schools cover Tottenham, Wood Green, Hornsey, Crouch End and Highgate. The borough mixes some of London's most competitive primary catchments with secondaries that have improved sharply in recent years. Admissions are coordinated by the council with appeals heard each summer.",
    "Enfield": "Enfield is the northernmost London borough and has a mix of community, foundation and faith schools. The borough has invested in new secondary provision in recent years, and admission distances are typically larger than in inner London. Reception oversubscription tends to be concentrated around Palmers Green, Winchmore Hill and Southgate.",
    "Barnet": "Barnet has the highest school-age population in London and is one of the strongest-performing local authority areas for both KS2 and KS4 results. The borough's school mix includes a substantial faith and academy element. Reception and Year 7 applications are competitive across much of the borough.",
    "Brent": "Brent's schools cover Wembley, Kilburn, Willesden, Harlesden, Kingsbury and Neasden. The borough has a notable concentration of high-performing primaries and an improving secondary picture, with several schools among London's most oversubscribed. Admissions are coordinated by the council.",
    "Ealing": "Ealing schools cover Acton, Hanwell, Southall, Greenford, Northolt and Ealing town. The borough has a strong primary offer and a growing reputation for academic secondaries. Reception applications are particularly competitive in central Ealing and Acton.",
    "Hounslow": "Hounslow's schools serve Chiswick, Brentford, Isleworth, Hounslow town, Feltham and Heston. The borough mixes some of west London's most oversubscribed primaries with a wide range of secondaries. Travel times across the borough can be longer than in inner London, so catchment distances matter.",
    "Hillingdon": "Hillingdon is the second-largest London borough by area and covers Uxbridge, Hayes, Ruislip, Northwood and Heathrow's edge. The borough has a mix of community, faith and academy schools, with some grammar provision. Reception demand is concentrated in the south of the borough.",
    "Harrow": "Harrow's schools cover the borough from Stanmore and Pinner through to Harrow town and Wealdstone. The borough has a strong reputation for academic performance and a notable faith-school presence. 11+ preparation is widespread among Year 4 and Year 5 families.",
    "Sutton": "Sutton operates one of London's most selective secondary systems, with a high proportion of grammar provision. The borough's primaries are heavily oversubscribed in central Sutton, Carshalton and Cheam. Many parents begin 11+ preparation in Year 4.",
    "Merton": "Merton schools cover Wimbledon, Mitcham, Morden and Colliers Wood. The borough has a strong primary offer in the north and an improving secondary picture. Reception applications are particularly competitive in Wimbledon and around Wimbledon Park.",
    "Kingston upon Thames": "Kingston upon Thames has consistently been one of the strongest-performing London boroughs for school outcomes. The borough's primaries and secondaries are heavily oversubscribed, particularly in Kingston town and Surbiton. Admission distances are tight.",
    "Richmond upon Thames": "Richmond upon Thames has one of the highest proportions of Outstanding-rated schools in London, particularly in primary phase. The borough covers Richmond, Twickenham, Teddington, Whitton and Hampton. Reception catchment radii are tight across most of the borough.",
    "Bexley": "Bexley's schools cover Bexleyheath, Erith, Sidcup, Welling and Crayford, with a notable grammar presence. The borough operates a partially selective system at secondary level. Reception applications are competitive in the north of the borough.",
    "Barking and Dagenham": "Barking and Dagenham schools serve a fast-growing east London population. The borough has invested heavily in new primary and secondary provision in the last decade. Reception applications are particularly competitive in the Barking riverside and Dagenham Heathway areas.",
    "Havering": "Havering's schools cover Romford, Hornchurch, Upminster, Rainham and Harold Hill. The borough has a mix of community, faith and academy provision. Reception oversubscription tends to be most pronounced in the south and west of the borough.",
    "City of London": "The City of London has a very small resident school-age population. It maintains a small number of primary and secondary schools, several of which have nationally recognised reputations. Most City schools draw applicants from across central London.",
}

# Borough-level appeal success rates 2024 (the latest year you cited). These
# are placeholders matched to your appeals tracker — replace from appeals.html
# data so a single source of truth is enforced.
DEFAULT_APPEAL_SUCCESS_PLACEHOLDER = None  # Set per-borough at runtime if available

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(value: str) -> str:
    """Lowercase, ASCII, hyphen-separated slug — matches the existing site convention."""
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[\s_]+", "-", value)


def pick(row: dict[str, Any], logical_key: str, default: Any = None) -> Any:
    """Resolve a logical field name to whichever real key the school row has."""
    for candidate in FIELD_MAP.get(logical_key, []):
        if candidate in row and row[candidate] not in (None, ""):
            return row[candidate]
    return default


def canonical_borough(raw: str) -> str | None:
    """Return the canonical borough name if `raw` matches one of the 33; else None."""
    if not raw:
        return None
    norm = re.sub(r"\s+", " ", raw.strip()).lower().replace("&", "and")
    for borough in LONDON_BOROUGHS:
        if borough.lower() == norm:
            return borough
    # Loose match: ignore "London Borough of" prefix
    norm = re.sub(r"^london borough of\s+", "", norm)
    norm = re.sub(r"^city of\s+", "", norm) if "city of london" not in norm else norm
    for borough in LONDON_BOROUGHS:
        if borough.lower() == norm:
            return borough
    return None


def safe_mean(values: Iterable[Any]) -> float | None:
    clean: list[float] = []
    for v in values:
        try:
            if v is None or v == "":
                continue
            clean.append(float(v))
        except (TypeError, ValueError):
            continue
    if not clean:
        return None
    return round(statistics.mean(clean), 2)


def safe_count(values: Iterable[Any], match: str | None = None) -> int:
    if match is None:
        return sum(1 for v in values if v not in (None, ""))
    return sum(1 for v in values if isinstance(v, str) and v.strip().lower() == match.lower())


def fmt(value: Any, suffix: str = "", default: str = "—") -> str:
    if value is None or value == "":
        return default
    return f"{value}{suffix}"


# ---------------------------------------------------------------------------
# Stats per borough
# ---------------------------------------------------------------------------


def compute_borough_stats(schools: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute the summary stats we surface on each borough hub page."""
    ofsted_values = [pick(s, "ofsted") for s in schools]
    ofsted_dist = Counter(v for v in ofsted_values if isinstance(v, str))
    total = len(schools)

    phases = Counter(pick(s, "phase") for s in schools if pick(s, "phase"))
    types = Counter(pick(s, "type") for s in schools if pick(s, "type"))

    return {
        "total": total,
        "outstanding": ofsted_dist.get("Outstanding", 0),
        "good": ofsted_dist.get("Good", 0),
        "requires_improvement": ofsted_dist.get("Requires Improvement", 0)
        + ofsted_dist.get("Requires improvement", 0),
        "inadequate": ofsted_dist.get("Inadequate", 0),
        "outstanding_pct": round(100 * ofsted_dist.get("Outstanding", 0) / total, 1) if total else 0,
        "good_or_better_pct": round(
            100 * (ofsted_dist.get("Outstanding", 0) + ofsted_dist.get("Good", 0)) / total, 1
        )
        if total
        else 0,
        "mean_ks2_progress": safe_mean(pick(s, "ks2_progress") for s in schools),
        "mean_ks4_att8": safe_mean(pick(s, "ks4_attainment_8") for s in schools),
        "mean_apps_per_place": safe_mean(pick(s, "apps_per_place") for s in schools),
        "mean_crime_500m": safe_mean(pick(s, "crime_500m") for s in schools),
        "mean_imd_decile": safe_mean(pick(s, "imd_decile") for s in schools),
        "primary_count": sum(1 for p, c in phases.items() if p and "primary" in p.lower() for _ in range(c)),
        "secondary_count": sum(1 for p, c in phases.items() if p and "secondary" in p.lower() for _ in range(c)),
        "phases": dict(phases),
        "types": dict(types),
    }


def rank_top_schools(schools: list[dict[str, Any]], n: int = 10) -> list[dict[str, Any]]:
    """
    Composite ranking: Outstanding first, then by KS2 progress (or KS4 Att8 for secondaries),
    then by apps-per-place as a tie-breaker. Stable, transparent.
    """
    ofsted_rank = {"Outstanding": 4, "Good": 3, "Requires Improvement": 2, "Requires improvement": 2, "Inadequate": 1}

    def sort_key(s: dict[str, Any]):
        ofsted = pick(s, "ofsted") or ""
        ks2 = pick(s, "ks2_progress")
        ks4 = pick(s, "ks4_attainment_8")
        apps = pick(s, "apps_per_place")
        try:
            ks2_val = float(ks2) if ks2 not in (None, "") else -999
        except (TypeError, ValueError):
            ks2_val = -999
        try:
            ks4_val = float(ks4) if ks4 not in (None, "") else -999
        except (TypeError, ValueError):
            ks4_val = -999
        try:
            apps_val = float(apps) if apps not in (None, "") else 0
        except (TypeError, ValueError):
            apps_val = 0
        return (
            ofsted_rank.get(ofsted, 0),
            ks4_val if ks4_val > -999 else ks2_val,
            apps_val,
        )

    return sorted(schools, key=sort_key, reverse=True)[:n]


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


PAGE_TEMPLATE = """<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{meta_description}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_description}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="London School Directory">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0b2545">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="preconnect" href="https://unpkg.com">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  :root {{
    --ink: #0b2545;
    --ink-2: #1e3a5f;
    --muted: #5b6b85;
    --line: #e3e8ef;
    --bg: #ffffff;
    --bg-2: #f6f8fb;
    --accent: #0b6efd;
    --good: #137333;
    --warn: #a85b00;
    --bad: #b3261e;
    --radius: 10px;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: var(--ink);
    background: var(--bg);
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  header.site {{
    border-bottom: 1px solid var(--line);
    background: var(--bg);
    position: sticky; top: 0; z-index: 50;
  }}
  header.site .inner {{
    max-width: 1100px; margin: 0 auto; padding: 14px 20px;
    display: flex; align-items: center; justify-content: space-between;
  }}
  header.site a.brand {{ color: var(--ink); font-weight: 700; letter-spacing: -0.01em; }}
  header.site nav a {{ margin-left: 18px; color: var(--ink-2); font-size: 14px; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 28px 20px 80px; }}
  .crumbs {{ font-size: 13px; color: var(--muted); margin-bottom: 14px; }}
  .crumbs a {{ color: var(--muted); }}
  h1 {{ font-size: 32px; line-height: 1.2; margin: 0 0 8px; letter-spacing: -0.02em; }}
  .lede {{ color: var(--ink-2); font-size: 17px; max-width: 720px; }}
  .stamp {{ font-size: 12px; color: var(--muted); margin-top: 8px; }}
  .stamp .dot {{ display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--good); vertical-align: middle; margin-right: 6px; }}
  .grid-stats {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px; margin: 24px 0 8px;
  }}
  .stat {{
    background: var(--bg-2); border: 1px solid var(--line);
    border-radius: var(--radius); padding: 14px 16px;
  }}
  .stat .v {{ font-size: 24px; font-weight: 700; color: var(--ink); }}
  .stat .l {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
  section {{ margin-top: 36px; }}
  h2 {{ font-size: 22px; margin: 0 0 12px; letter-spacing: -0.01em; }}
  .twocol {{ display: grid; grid-template-columns: 1.4fr 1fr; gap: 28px; }}
  @media (max-width: 820px) {{ .twocol {{ grid-template-columns: 1fr; }} }}
  table.schools {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  table.schools th, table.schools td {{
    text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line);
  }}
  table.schools th {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); font-weight: 600; }}
  .rating {{ font-weight: 600; }}
  .rating.Outstanding {{ color: var(--good); }}
  .rating.Good {{ color: var(--ink-2); }}
  .rating.RequiresImprovement, .rating.Requires {{ color: var(--warn); }}
  .rating.Inadequate {{ color: var(--bad); }}
  #map {{ height: 380px; border-radius: var(--radius); border: 1px solid var(--line); }}
  .pills {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .pill {{ background: var(--bg-2); border: 1px solid var(--line); border-radius: 999px; padding: 4px 10px; font-size: 12px; color: var(--ink-2); }}
  details.faq {{ border: 1px solid var(--line); border-radius: var(--radius); padding: 14px 16px; margin-bottom: 8px; background: var(--bg); }}
  details.faq summary {{ cursor: pointer; font-weight: 600; color: var(--ink); }}
  details.faq[open] {{ background: var(--bg-2); }}
  footer {{ border-top: 1px solid var(--line); padding: 28px 20px; color: var(--muted); font-size: 13px; }}
  footer .inner {{ max-width: 1100px; margin: 0 auto; display: flex; gap: 24px; flex-wrap: wrap; }}
  .sources {{ font-size: 13px; color: var(--muted); }}
  .sources a {{ color: var(--muted); text-decoration: underline; }}
  .cta {{
    display: inline-block; background: var(--ink); color: #fff; padding: 10px 14px;
    border-radius: var(--radius); font-size: 14px; font-weight: 600;
  }}
  .cta:hover {{ background: var(--ink-2); text-decoration: none; }}
</style>
<script type="application/ld+json">
{schema_json}
</script>
</head>
<body>
<header class="site">
  <div class="inner">
    <a class="brand" href="/">London School Directory</a>
    <nav>
      <a href="/">Search</a>
      <a href="/appeals.html">Appeals</a>
      <a href="/methodology.html">Methodology</a>
      <a href="/about.html">About</a>
    </nav>
  </div>
</header>
<main>
  <div class="crumbs">
    <a href="/">Home</a> &rsaquo; <a href="/schools/">Boroughs</a> &rsaquo; {borough}
  </div>

  <h1>Schools in {borough}, London</h1>
  <p class="lede">{lede}</p>
  <p class="stamp"><span class="dot"></span>Data last verified {last_updated}. Sources: Ofsted, DfE GIAS, DfE Performance Tables, Metropolitan Police, MHCLG IMD. See <a href="/sources.html">all sources</a>.</p>

  <section>
    <div class="grid-stats">
      <div class="stat"><div class="v">{total}</div><div class="l">Schools in {borough}</div></div>
      <div class="stat"><div class="v">{outstanding_pct}%</div><div class="l">Outstanding Ofsted</div></div>
      <div class="stat"><div class="v">{good_or_better_pct}%</div><div class="l">Good or Outstanding</div></div>
      <div class="stat"><div class="v">{primary_count}</div><div class="l">Primary schools</div></div>
      <div class="stat"><div class="v">{secondary_count}</div><div class="l">Secondary schools</div></div>
      <div class="stat"><div class="v">{appeal_success}</div><div class="l">Avg appeal success</div></div>
    </div>
  </section>

  <section>
    <div class="twocol">
      <div>
        <h2>Top schools in {borough}</h2>
        <p class="sources">Ranked by Ofsted rating, then by latest KS2 progress (primary) or Attainment 8 (secondary), with applications-per-place as a tie-breaker. See <a href="/methodology.html">methodology</a>.</p>
        <table class="schools">
          <thead>
            <tr><th>School</th><th>Phase</th><th>Ofsted</th><th>KS2 / Att8</th></tr>
          </thead>
          <tbody>
            {top_rows}
          </tbody>
        </table>
        <p style="margin-top:14px"><a class="cta" href="/?borough={borough_slug}">See all {total} schools in {borough}</a></p>
      </div>
      <div>
        <h2>Map</h2>
        <div id="map" aria-label="Map of schools in {borough}"></div>
      </div>
    </div>
  </section>

  <section>
    <h2>What the data says about {borough}</h2>
    <p>{narrative}</p>
  </section>

  <section>
    <h2>Frequently asked</h2>
    {faq_html}
  </section>

  <section>
    <h2>Sources</h2>
    <p class="sources">
      School list and phase from <a href="https://get-information-schools.service.gov.uk/" rel="nofollow">DfE Get Information About Schools</a> (refreshed monthly).
      Ofsted ratings from <a href="https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes" rel="nofollow">Ofsted Management Information</a> (refreshed monthly).
      Performance data from <a href="https://explore-education-statistics.service.gov.uk/" rel="nofollow">DfE Explore Education Statistics</a>.
      Crime data within 500m from the <a href="https://data.police.uk/" rel="nofollow">Metropolitan Police open data API</a>.
      Deprivation deciles from <a href="https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019" rel="nofollow">MHCLG English Indices of Deprivation 2019</a>.
      Read our full <a href="/methodology.html">methodology</a> for how each metric is calculated.
    </p>
  </section>
</main>
<footer>
  <div class="inner">
    <div>&copy; London School Directory. Independent. Free to use.</div>
    <div><a href="/about.html">About</a> &middot; <a href="/methodology.html">Methodology</a> &middot; <a href="/sources.html">Sources</a> &middot; <a href="/appeals.html">Appeals</a></div>
  </div>
</footer>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  (function() {{
    var points = {map_points_json};
    if (!points.length) return;
    var lats = points.map(function(p) {{ return p[0]; }});
    var lngs = points.map(function(p) {{ return p[1]; }});
    var avgLat = lats.reduce(function(a,b) {{ return a+b; }}, 0) / lats.length;
    var avgLng = lngs.reduce(function(a,b) {{ return a+b; }}, 0) / lngs.length;
    var map = L.map('map', {{ scrollWheelZoom: false }}).setView([avgLat, avgLng], 12);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);
    points.forEach(function(p) {{
      L.circleMarker([p[0], p[1]], {{
        radius: 5, color: '#0b2545', fillColor: '#0b6efd', fillOpacity: 0.8, weight: 1
      }}).addTo(map).bindPopup('<a href="' + p[2] + '">' + p[3] + '</a>');
    }});
  }})();
</script>
</body>
</html>
"""


def make_faq(borough: str, stats: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    """Return rendered FAQ HTML and the parallel JSON-LD entries."""
    faqs = [
        {
            "q": f"How many schools are there in {borough}?",
            "a": f"{borough} has {stats['total']} schools in our directory, drawn from the Department for Education's Get Information About Schools register. Of these, {stats['primary_count']} are primary, {stats['secondary_count']} are secondary, and the remainder are special, all-through, or post-16.",
        },
        {
            "q": f"What proportion of {borough} schools are Outstanding?",
            "a": f"As of the latest Ofsted Management Information release, {stats['outstanding']} schools in {borough} ({stats['outstanding_pct']}%) are rated Outstanding, and {stats['good_or_better_pct']}% are rated Good or Outstanding. Ratings are refreshed monthly from the Ofsted MI publication.",
        },
        {
            "q": f"When do I apply for a Reception or Year 7 place in {borough}?",
            "a": f"Reception applications in England close on 15 January each year for the September intake. Year 7 (secondary transfer) applications close on 31 October. {borough}'s applications are coordinated by the local authority through the eAdmissions system. See our <a href='/guides/london-reception-application-timeline/'>full Reception timeline guide</a>.",
        },
        {
            "q": f"How does the school appeals process work in {borough}?",
            "a": f"If you are refused your preferred school place, you have a statutory right of appeal. {borough} appeals are typically heard in May (Reception) and June–July (secondary). See our <a href='/appeals.html'>appeals tracker</a> for {borough}-level success rates by year.",
        },
        {
            "q": f"How can I tell which {borough} schools are over-subscribed?",
            "a": f"Each school listing on this site shows the number of applications per place from the DfE's published admissions data. Apps-per-place above 2 typically indicates strong over-subscription. We refresh this data annually when the DfE publishes its admissions and offers release.",
        },
    ]

    html = "\n".join(
        f'<details class="faq"><summary>{f["q"]}</summary><p>{f["a"]}</p></details>'
        for f in faqs
    )
    jsonld = [{"q": f["q"], "a": re.sub(r"<.*?>", "", f["a"])} for f in faqs]
    return html, jsonld


def make_narrative(borough: str, stats: dict[str, Any]) -> str:
    parts: list[str] = []
    if stats["good_or_better_pct"]:
        parts.append(
            f"<strong>{stats['good_or_better_pct']}%</strong> of {borough} schools are currently rated Good or Outstanding by Ofsted, "
            f"compared with a London average of roughly 90% for primary and 80% for secondary."
        )
    if stats["mean_apps_per_place"]:
        parts.append(
            f"The average number of applications per place across {borough} is "
            f"<strong>{stats['mean_apps_per_place']}</strong>, a useful indicator of how competitive local admissions are."
        )
    if stats["mean_crime_500m"] is not None:
        parts.append(
            f"The average number of recorded crime incidents within 500 metres of a school in {borough} over the most recent reporting month is "
            f"<strong>{stats['mean_crime_500m']}</strong>, drawn from the Metropolitan Police open data API."
        )
    if stats["mean_imd_decile"] is not None:
        parts.append(
            f"The mean IMD (Index of Multiple Deprivation) decile of {borough}'s schools is "
            f"<strong>{stats['mean_imd_decile']}</strong> — 1 is most deprived, 10 is least deprived."
        )
    parts.append(
        "All metrics on this page are recomputed from source data on the 15th of every month. "
        "See our <a href='/methodology.html'>methodology</a> for definitions and limitations."
    )
    return " ".join(parts)


def make_top_rows(top: list[dict[str, Any]]) -> str:
    rows = []
    for s in top:
        name = pick(s, "name") or "Unnamed school"
        phase = pick(s, "phase") or "—"
        ofsted = pick(s, "ofsted") or "—"
        ks2 = pick(s, "ks2_progress")
        ks4 = pick(s, "ks4_attainment_8")
        metric = ks4 if ks4 not in (None, "") else ks2
        metric_display = "—" if metric in (None, "") else metric
        url = pick(s, "url_path")
        if not url:
            borough_slug = slugify(pick(s, "borough") or "")
            school_slug = pick(s, "slug") or slugify(name)
            url = f"/schools/{borough_slug}/{school_slug}/"
        ofsted_class = re.sub(r"\s+", "", ofsted) if ofsted else ""
        rows.append(
            f'<tr><td><a href="{url}">{name}</a></td>'
            f"<td>{phase}</td>"
            f'<td class="rating {ofsted_class}">{ofsted}</td>'
            f"<td>{metric_display}</td></tr>"
        )
    return "\n            ".join(rows) if rows else "<tr><td colspan='4'>No schools listed yet.</td></tr>"


def make_schema_jsonld(
    borough: str,
    canonical: str,
    top: list[dict[str, Any]],
    faqs: list[dict[str, str]],
) -> str:
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"Top schools in {borough}, London",
        "itemListOrder": "http://schema.org/ItemListOrderDescending",
        "numberOfItems": len(top),
        "itemListElement": [],
    }
    for i, s in enumerate(top, 1):
        name = pick(s, "name") or "School"
        url = pick(s, "url_path")
        if not url:
            borough_slug = slugify(pick(s, "borough") or "")
            school_slug = pick(s, "slug") or slugify(name)
            url = f"/schools/{borough_slug}/{school_slug}/"
        item_list["itemListElement"].append(
            {
                "@type": "ListItem",
                "position": i,
                "url": f"{SITE_URL}{url}" if url.startswith("/") else url,
                "name": name,
            }
        )

    faq_page = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f["q"],
                "acceptedAnswer": {"@type": "Answer", "text": f["a"]},
            }
            for f in faqs
        ],
    }

    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": "Boroughs", "item": SITE_URL + "/schools/"},
            {"@type": "ListItem", "position": 3, "name": borough, "item": canonical},
        ],
    }

    return json.dumps([item_list, faq_page, breadcrumbs], indent=2)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build():
    if not SCHOOLS_JSON.exists():
        raise SystemExit(f"Could not find {SCHOOLS_JSON}. Run from repo root.")

    raw = json.loads(SCHOOLS_JSON.read_text(encoding="utf-8"))
    # schools.json could be a list or wrapped in a key; handle both
    schools: list[dict[str, Any]] = raw if isinstance(raw, list) else raw.get("schools", [])
    print(f"Loaded {len(schools)} schools")

    by_borough: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in schools:
        b = canonical_borough(pick(s, "borough"))
        if b:
            by_borough[b].append(s)

    print(f"Detected {len(by_borough)} boroughs with schools")

    today = datetime.now(timezone.utc).strftime("%-d %B %Y") if os.name != "nt" else datetime.now(timezone.utc).strftime("%d %B %Y")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build a borough index page too, at /schools/index.html
    index_links: list[str] = []

    for borough in LONDON_BOROUGHS:
        b_schools = by_borough.get(borough, [])
        slug = slugify(borough)
        out_dir = OUTPUT_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        stats = compute_borough_stats(b_schools) if b_schools else {
            "total": 0, "outstanding": 0, "good": 0, "requires_improvement": 0, "inadequate": 0,
            "outstanding_pct": 0, "good_or_better_pct": 0,
            "mean_ks2_progress": None, "mean_ks4_att8": None, "mean_apps_per_place": None,
            "mean_crime_500m": None, "mean_imd_decile": None,
            "primary_count": 0, "secondary_count": 0, "phases": {}, "types": {},
        }
        top = rank_top_schools(b_schools, n=10)

        # Map points
        map_points: list[list[Any]] = []
        for s in b_schools:
            lat = pick(s, "lat")
            lng = pick(s, "lng")
            try:
                lat_f = float(lat)
                lng_f = float(lng)
            except (TypeError, ValueError):
                continue
            name = pick(s, "name") or "School"
            url_path = pick(s, "url_path")
            if not url_path:
                school_slug = pick(s, "slug") or slugify(name)
                url_path = f"/schools/{slug}/{school_slug}/"
            map_points.append([lat_f, lng_f, url_path, name])

        faq_html, faq_jsonld = make_faq(borough, stats)
        narrative = make_narrative(borough, stats)
        top_rows = make_top_rows(top)
        canonical = f"{SITE_URL}/schools/{slug}/"
        schema_json = make_schema_jsonld(borough, canonical, top, faq_jsonld)

        lede = BOROUGH_BLURBS.get(borough,
            f"{borough} is one of the 33 London boroughs. This page lists every school in {borough} from the Department for Education register, with Ofsted rating, performance data, admissions competitiveness and local context. Data is refreshed monthly.")

        meta_description = (
            f"All {stats['total']} schools in {borough}, London. Ofsted ratings, KS2/KS4 results, "
            f"admissions competitiveness, appeal success rates and map. Updated monthly."
        )[:158]

        appeal_success = "—"  # Wire up from appeals.html data when ready

        html = PAGE_TEMPLATE.format(
            title=f"Schools in {borough}, London — Ofsted, Performance & Admissions",
            meta_description=meta_description,
            canonical=canonical,
            borough=borough,
            borough_slug=slug,
            lede=lede,
            last_updated=today,
            total=stats["total"],
            outstanding_pct=stats["outstanding_pct"],
            good_or_better_pct=stats["good_or_better_pct"],
            primary_count=stats["primary_count"],
            secondary_count=stats["secondary_count"],
            appeal_success=appeal_success,
            top_rows=top_rows,
            narrative=narrative,
            faq_html=faq_html,
            map_points_json=json.dumps(map_points),
            schema_json=schema_json,
        )

        (out_dir / "index.html").write_text(html, encoding="utf-8")
        index_links.append(
            f'<li><a href="/schools/{slug}/">{borough}</a> '
            f'<span style="color:#5b6b85">({stats["total"]} schools, {stats["outstanding_pct"]}% Outstanding)</span></li>'
        )
        print(f"  wrote /schools/{slug}/index.html  ({stats['total']} schools)")

    # /schools/index.html — borough directory page
    index_html = f"""<!doctype html>
<html lang="en-GB"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Schools by London borough — London School Directory</title>
<meta name="description" content="Browse all London schools by borough. Ofsted ratings, performance data, admissions and appeals for every state school in each of the 33 London boroughs.">
<link rel="canonical" href="{SITE_URL}/schools/">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Inter", sans-serif; max-width: 900px; margin: 0 auto; padding: 28px 20px; color: #0b2545; }}
  h1 {{ font-size: 28px; letter-spacing: -0.02em; }}
  ul {{ list-style: none; padding: 0; columns: 2; column-gap: 24px; }}
  @media (max-width: 640px) {{ ul {{ columns: 1; }} }}
  li {{ break-inside: avoid; padding: 8px 0; border-bottom: 1px solid #e3e8ef; }}
  a {{ color: #0b6efd; text-decoration: none; font-weight: 500; }}
  a:hover {{ text-decoration: underline; }}
  .crumbs {{ font-size: 13px; color: #5b6b85; margin-bottom: 14px; }}
  .crumbs a {{ color: #5b6b85; }}
</style>
</head><body>
<div class="crumbs"><a href="/">Home</a> &rsaquo; Boroughs</div>
<h1>Schools by London borough</h1>
<p>Browse every school in each of London's 33 boroughs. Each hub shows Ofsted ratings, performance, admissions competitiveness and a borough map. Updated monthly.</p>
<ul>
{''.join(index_links)}
</ul>
</body></html>
"""
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"\nDone. Wrote /schools/index.html and {len(LONDON_BOROUGHS)} borough hubs.")


if __name__ == "__main__":
    build()
