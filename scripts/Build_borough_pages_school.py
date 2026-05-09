#!/usr/bin/env python3
"""
Build one borough hub page per London borough for londonschool.directory.

Drop this in `scripts/build_borough_pages.py` and run from the repo root:

    python3 scripts/build_borough_pages.py

It reads schools.json, groups by borough, writes one self-contained static
HTML page per borough at `schools/{borough-slug}/index.html`, and appends
the new URLs to sitemap_data.txt.

Why this matters
----------------
Top GSC queries for the site are borough-level ("westminster schools",
"chelsea schools", "schools in kensington"). Without a borough hub page
Google has no good result to surface for those queries — only individual
school profiles, which lose to council pages and listicles.

Field names
-----------
The script tries several common field names for each piece of data
(borough/name/ofsted/etc.) and reports what it found on first run. If
something doesn't match your schema, edit the FIELD constants below.
"""

import json, re, sys, html
from pathlib import Path
from datetime import datetime
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
SCHOOLS_JSON = ROOT / "schools.json"
OUT_DIR = ROOT / "schools"
SITEMAP_DATA = ROOT / "sitemap_data.txt"

SITE_URL = "https://londonschool.directory"
SITE_NAME = "London Schools Directory"

# ---- Field-name candidates (script picks whichever exists) ----
F_NAME      = ("name", "school_name", "establishment_name", "EstablishmentName")
F_BOROUGH   = ("borough", "la_name", "local_authority", "LA_Name", "district")
F_PHASE     = ("phase", "phase_of_education", "PhaseOfEducation")
F_TYPE      = ("type", "school_type", "TypeOfEstablishment")
F_OFSTED    = ("ofsted_rating", "ofsted", "rating", "OfstedRating")
F_POSTCODE  = ("postcode", "Postcode", "post_code")
F_URL       = ("url", "page_url", "slug")
F_KS4       = ("attainment_8", "ks4_attainment_8", "att8")
F_KS2       = ("ks2_pct_expected", "ks2", "ks2_attainment")
F_OVERSUB   = ("oversubscription", "apps_per_place", "applications_per_place")

# ---- helpers --------------------------------------------------------

def slug(s):
    s = (s or "").lower()
    s = re.sub(r"&", "and", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unknown"

def first(d, keys, default=None):
    """Return the first matching key value from dict d."""
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default

def school_url(school, borough):
    """Try to use existing url field; otherwise mirror build_school_pages.py path."""
    u = first(school, F_URL)
    if u:
        return u if u.startswith("/") or u.startswith("http") else "/" + u
    name = first(school, F_NAME, "")
    return f"/schools/{slug(borough)}/{slug(name)}/"

def rating_class(r):
    return {
        "Outstanding": "rating-outstanding",
        "Good": "rating-good",
        "Requires improvement": "rating-ri",
        "Inadequate": "rating-inadequate",
    }.get(r, "rating-none")

# ---- HTML template --------------------------------------------------

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',-apple-system,sans-serif;background:#F5F0E8;color:#1A1A2E;line-height:1.55}
a{color:inherit;text-decoration:none}
.hdr{background:#1A1A2E;color:#F5F0E8;padding:18px 32px;border-bottom:3px solid #D4A843;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.hdr a{font-family:'Playfair Display',Georgia,serif;font-weight:700;font-size:1.25rem}
.hdr a span{color:#D4A843}
.hdr nav{display:flex;gap:14px;font-size:.9rem;opacity:.85}
.crumbs{padding:14px 32px;font-size:.85rem;color:#6b6e7a;background:#FDFAF4;border-bottom:1px solid #E5DFD0}
.crumbs a{color:#1A1A2E;font-weight:500}
.hero{background:#1A1A2E;color:#F5F0E8;padding:48px 32px 36px;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:-100px;right:-80px;width:380px;height:380px;background:radial-gradient(circle,rgba(212,168,67,.2) 0%,transparent 70%);pointer-events:none}
.hero-inner{max-width:1200px;margin:0 auto;position:relative}
.eyebrow{font-size:.75rem;letter-spacing:.15em;text-transform:uppercase;color:#D4A843;font-weight:600;margin-bottom:12px}
h1{font-family:'Playfair Display',Georgia,serif;font-size:clamp(2.2rem,5vw,3.4rem);font-weight:900;line-height:1.05;max-width:760px;margin-bottom:14px}
h1 em{color:#D4A843;font-style:italic}
.hero-sub{font-size:1.05rem;color:rgba(245,240,232,.78);max-width:640px;margin-bottom:28px}
.hero-stats{display:flex;gap:36px;flex-wrap:wrap}
.hero-stat-num{font-family:'Playfair Display',Georgia,serif;font-size:2rem;font-weight:700;color:#D4A843;line-height:1}
.hero-stat-label{font-size:.75rem;color:rgba(245,240,232,.6);text-transform:uppercase;letter-spacing:.06em;margin-top:4px}
main{max-width:1200px;margin:0 auto;padding:36px 32px 64px}
.intro{font-size:1rem;color:#3d3f4d;max-width:760px;margin-bottom:32px;line-height:1.65}
h2{font-family:'Playfair Display',Georgia,serif;font-size:1.6rem;font-weight:700;margin:36px 0 16px}
.school-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.card{background:#FDFAF4;border:1px solid #E5DFD0;border-radius:8px;padding:18px;transition:border-color .15s,box-shadow .15s;display:flex;flex-direction:column}
.card:hover{border-color:#D4A843;box-shadow:0 3px 14px rgba(26,26,46,.08)}
.card-name{font-family:'Playfair Display',Georgia,serif;font-weight:700;font-size:1.05rem;color:#1A1A2E;margin-bottom:6px;line-height:1.25}
.card-meta{font-size:.78rem;color:#6b6e7a;margin-bottom:10px}
.card-rating{display:inline-block;font-size:.7rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:3px 8px;border-radius:99px;margin-bottom:10px;align-self:flex-start}
.rating-outstanding{background:#27AE60;color:#fff}
.rating-good{background:#D4A843;color:#1A1A2E}
.rating-ri{background:#F39C12;color:#fff}
.rating-inadequate{background:#C0392B;color:#fff}
.rating-none{background:#E5DFD0;color:#6b6e7a}
.card-stats{display:flex;gap:16px;margin-top:auto;padding-top:10px;border-top:1px solid #E5DFD0;font-size:.78rem;color:#6b6e7a}
.card-stat strong{display:block;font-size:.95rem;color:#1A1A2E;font-weight:600}
.empty{color:#6b6e7a;padding:24px 0}
footer{background:#1A1A2E;color:rgba(245,240,232,.55);padding:24px 32px;text-align:center;font-size:.85rem}
footer a{color:rgba(245,240,232,.85)}
@media(max-width:600px){.hero{padding:32px 20px 24px}main{padding:24px 20px 48px}.hdr,.crumbs,footer{padding-left:20px;padding-right:20px}}
"""

def render_card(s, borough):
    name      = html.escape(str(first(s, F_NAME, "Unnamed school")))
    phase     = html.escape(str(first(s, F_PHASE, "")))
    typ       = html.escape(str(first(s, F_TYPE, "")))
    rating    = first(s, F_OFSTED, "")
    pc        = html.escape(str(first(s, F_POSTCODE, "")))
    url       = html.escape(school_url(s, borough))
    ks4       = first(s, F_KS4)
    ks2       = first(s, F_KS2)
    over      = first(s, F_OVERSUB)

    rating_html = f'<span class="card-rating {rating_class(rating)}">{html.escape(str(rating))}</span>' if rating else ''
    meta_bits = " · ".join(b for b in (phase, typ, pc) if b)

    stats = []
    if ks4 not in (None, ""):
        stats.append(f'<div class="card-stat">KS4 A8<strong>{ks4}</strong></div>')
    if ks2 not in (None, ""):
        stats.append(f'<div class="card-stat">KS2 %<strong>{ks2}</strong></div>')
    if over not in (None, ""):
        stats.append(f'<div class="card-stat">Apps/place<strong>{over}</strong></div>')
    stats_html = f'<div class="card-stats">{"".join(stats)}</div>' if stats else ''

    return f'''<a class="card" href="{url}">
  <div class="card-name">{name}</div>
  {rating_html}
  <div class="card-meta">{meta_bits}</div>
  {stats_html}
</a>'''

def render_page(borough, schools, total_london):
    n = len(schools)
    rating_order = {"Outstanding": 0, "Good": 1, "Requires improvement": 2, "Inadequate": 3, "": 9, None: 9}
    schools_sorted = sorted(
        schools,
        key=lambda s: (rating_order.get(first(s, F_OFSTED), 9), str(first(s, F_NAME, "")).lower())
    )

    rating_counts = defaultdict(int)
    for s in schools:
        rating_counts[first(s, F_OFSTED) or "Not rated"] += 1
    outstanding = rating_counts.get("Outstanding", 0)
    good = rating_counts.get("Good", 0)

    title = f"Schools in {borough} — Compare {n} Schools by Ofsted Rating"
    desc  = (f"Free directory of all {n} schools in {borough}, London. "
             f"{outstanding} Outstanding and {good} Good schools. Compare by Ofsted rating, "
             f"KS2/KS4 results and admissions data. Updated monthly.")
    canonical = f"{SITE_URL}/schools/{slug(borough)}/"

    items = []
    for i, s in enumerate(schools_sorted, 1):
        items.append({
            "@type": "ListItem",
            "position": i,
            "url": SITE_URL + school_url(s, borough),
            "name": str(first(s, F_NAME, ""))
        })
    json_ld_collection = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "url": canonical,
        "description": desc,
        "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": SITE_URL + "/"},
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": n,
            "itemListElement": items[:200]  # keep payload sensible
        }
    }
    json_ld_breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": borough, "item": canonical}
        ]
    }

    cards = "\n".join(render_card(s, borough) for s in schools_sorted)
    if not cards:
        cards = '<p class="empty">No schools found in this borough.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#1A1A2E">
<link rel="canonical" href="{canonical}">

<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="en_GB">
<meta property="og:image" content="{SITE_URL}/og-image.png">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{html.escape(desc)}">
<meta name="twitter:image" content="{SITE_URL}/og-image.png">

<script type="application/ld+json">{json.dumps(json_ld_collection, separators=(",",":"))}</script>
<script type="application/ld+json">{json.dumps(json_ld_breadcrumb, separators=(",",":"))}</script>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>

<header class="hdr">
  <a href="/"><span>+</span> {SITE_NAME}</a>
  <nav>
    <a href="/">Home</a>
    <a href="/appeals.html">Appeals</a>
  </nav>
</header>

<div class="crumbs">
  <a href="/">{SITE_NAME}</a> &rsaquo; {html.escape(borough)}
</div>

<section class="hero">
  <div class="hero-inner">
    <div class="eyebrow">London Borough</div>
    <h1>Schools in <em>{html.escape(borough)}</em></h1>
    <p class="hero-sub">Compare every school in {html.escape(borough)} by Ofsted rating, KS2/KS4 results and admissions data — drawn from official open data and refreshed monthly.</p>
    <div class="hero-stats">
      <div><div class="hero-stat-num">{n}</div><div class="hero-stat-label">Schools</div></div>
      <div><div class="hero-stat-num">{outstanding}</div><div class="hero-stat-label">Outstanding</div></div>
      <div><div class="hero-stat-num">{good}</div><div class="hero-stat-label">Good</div></div>
    </div>
  </div>
</section>

<main>
  <p class="intro">Showing all {n} schools in {html.escape(borough)}, sorted by Ofsted rating then alphabetically. Click any school for the full profile, including catchment, exam history and inspection reports.</p>

  <h2>All schools in {html.escape(borough)}</h2>
  <div class="school-grid">
    {cards}
  </div>
</main>

<footer>
  Data: GIAS &middot; Ofsted &middot; DfE &middot; updated {datetime.utcnow().strftime("%B %Y")}<br>
  <a href="/">{SITE_NAME}</a>
</footer>

</body>
</html>
"""

# ---- main -----------------------------------------------------------

def main():
    if not SCHOOLS_JSON.exists():
        sys.exit(f"schools.json not found at {SCHOOLS_JSON}")
    data = json.loads(SCHOOLS_JSON.read_text())
    if not isinstance(data, list):
        sys.exit("schools.json must be a list of school objects")

    # Detect which fields are present on first run
    sample = data[0] if data else {}
    detected = {
        "name":     next((k for k in F_NAME if k in sample), None),
        "borough":  next((k for k in F_BOROUGH if k in sample), None),
        "phase":    next((k for k in F_PHASE if k in sample), None),
        "ofsted":   next((k for k in F_OFSTED if k in sample), None),
        "postcode": next((k for k in F_POSTCODE if k in sample), None),
        "url":      next((k for k in F_URL if k in sample), None),
    }
    print("Detected fields:", detected)
    if not detected["name"] or not detected["borough"]:
        sys.exit("Could not find name or borough field. Edit the F_* constants at the top of this script.")

    by_borough = defaultdict(list)
    for s in data:
        b = first(s, F_BOROUGH)
        if not b:
            continue
        by_borough[str(b).strip()].append(s)

    print(f"Loaded {len(data)} schools across {len(by_borough)} boroughs")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for borough, schools in sorted(by_borough.items()):
        out = OUT_DIR / slug(borough) / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_page(borough, schools, len(data)))
        written.append((borough, len(schools), out.relative_to(ROOT)))

    for borough, count, path in written:
        print(f"  wrote {path}  ({count} schools)")

    # Append URLs to sitemap_data.txt (idempotent — dedupe)
    if SITEMAP_DATA.exists():
        existing = set(SITEMAP_DATA.read_text().splitlines())
    else:
        existing = set()
    new_lines = sorted(existing | {f"{SITE_URL}/schools/{slug(b)}/" for b, _, _ in written})
    SITEMAP_DATA.write_text("\n".join(new_lines) + "\n")
    print(f"\nSitemap: {SITEMAP_DATA.name} now has {len(new_lines)} URLs.")
    print(f"Done. {len(written)} borough pages.")

if __name__ == "__main__":
    main()
