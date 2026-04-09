import json, os, pathlib, re

# Always run from repo root regardless of where Vercel calls this from
os.chdir(pathlib.Path(__file__).parent.parent)

BASE_URL = "https://london-schools.vercel.app"

# Load school data
with open("schools.json") as f:
    schools = json.load(f)

def slugify(text):
    if not text:
        return "unknown"
    text = str(text).lower().strip()
    text = re.sub(r"[''']", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

def safe(val, fallback="N/A"):
    if val is None or (isinstance(val, float) and str(val) == "nan"):
        return fallback
    if isinstance(val, float) and val == int(val):
        return str(int(val))
    return str(val)

def format_phone(tel):
    if not tel or tel == "N/A":
        return None
    try:
        digits = str(int(float(tel)))
        if len(digits) == 10:
            return f"0{digits}"
        return digits
    except:
        return None

def ofsted_badge_color(label):
    colors = {
        "Outstanding":   ("#1B5E20", "#E8F5E9"),
        "Good":          ("#1565C0", "#E3F2FD"),
        "Requires improvement": ("#E65100", "#FFF3E0"),
        "Inadequate":    ("#B71C1C", "#FFEBEE"),
    }
    return colors.get(label, ("#424242", "#F5F5F5"))

def build_school_page(school):
    borough_slug  = slugify(school.get("local_authority", "unknown"))
    school_slug   = slugify(school.get("name", "unknown"))
    url           = f"{BASE_URL}/schools/{borough_slug}/{school_slug}"

    name          = safe(school.get("name"))
    borough       = safe(school.get("local_authority"))
    postcode      = safe(school.get("postcode"))
    street        = safe(school.get("street"))
    phase         = safe(school.get("phase"))
    school_type   = safe(school.get("school_type"))
    gender        = safe(school.get("gender"))
    age_from      = safe(school.get("age_from", ""), "")
    age_to        = safe(school.get("age_to", ""), "")
    age_range     = f"{age_from}–{age_to}" if age_from and age_to else "N/A"
    sixth_form    = safe(school.get("sixth_form"))
    admissions    = safe(school.get("admissions"))
    pupils        = safe(school.get("pupils"))
    capacity      = safe(school.get("capacity"))
    religion      = safe(school.get("religious_character"))
    head_name     = safe(school.get("head_name"))
    head_title    = safe(school.get("head_job_title", "Headteacher"))
    website       = school.get("website") or ""
    telephone     = format_phone(school.get("telephone"))
    ofsted_label  = safe(school.get("quality_label") or school.get("score_band"), "Not yet rated")
    ofsted_url    = school.get("ofsted_url") or ""
    inspection    = safe(school.get("inspection_date"), "")
    fsm_label     = safe(school.get("fsm_label"), "")
    crime_label   = safe(school.get("crime_label"), "")
    lat           = school.get("lat", "")
    lng           = school.get("lng", "")

    ofsted_text_color, ofsted_bg_color = ofsted_badge_color(ofsted_label)

    # KS2 / KS4 results
    ks2_expected  = school.get("ks2_expected_pct")
    ks2_higher    = school.get("ks2_higher_pct")
    ks4_att8      = school.get("ks4_att8")
    ks4_grade5    = school.get("ks4_grade5_em")
    ks4_grade4    = school.get("ks4_grade4_em")

    results_rows = ""
    if ks2_expected is not None:
        results_rows += f"<tr><td>KS2 expected standard</td><td><strong>{ks2_expected}%</strong></td></tr>"
    if ks2_higher is not None:
        results_rows += f"<tr><td>KS2 higher standard</td><td><strong>{ks2_higher}%</strong></td></tr>"
    if ks4_att8 is not None:
        results_rows += f"<tr><td>Attainment 8 score</td><td><strong>{ks4_att8}</strong></td></tr>"
    if ks4_grade5 is not None:
        results_rows += f"<tr><td>Grade 5+ English &amp; Maths</td><td><strong>{ks4_grade5}%</strong></td></tr>"
    if ks4_grade4 is not None:
        results_rows += f"<tr><td>Grade 4+ English &amp; Maths</td><td><strong>{ks4_grade4}%</strong></td></tr>"

    results_section = ""
    if results_rows:
        results_section = f"""
    <section class="card">
      <h2>Exam results</h2>
      <table>{results_rows}</table>
    </section>"""

    website_link = f'<a href="{"https://" + website if not website.startswith("http") else website}" target="_blank" rel="noopener">{website}</a>' if website else "N/A"
    ofsted_link  = f'<a href="{ofsted_url}" target="_blank" rel="noopener">View Ofsted report</a>' if ofsted_url else ""
    phone_link   = f'<a href="tel:{telephone}">{telephone}</a>' if telephone else "N/A"
    maps_link    = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}" if lat and lng else ""

    meta_desc = f"{ofsted_label} {phase} school in {borough}, London. {pupils} pupils. {street}, {postcode}. View Ofsted report and admissions info."

    schema = {
        "@context": "https://schema.org",
        "@type": "EducationalOrganization",
        "name": name,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": street,
            "addressLocality": borough,
            "addressRegion": "London",
            "postalCode": postcode,
            "addressCountry": "GB"
        },
        "url": url,
        "description": meta_desc,
    }
    if telephone:
        schema["telephone"] = telephone
    if website:
        schema["sameAs"] = f"https://{website}" if not website.startswith("http") else website

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name}, {borough} | London Schools Explorer</title>
  <meta name="description" content="{meta_desc}">
  <link rel="canonical" href="{url}">
  <meta property="og:title" content="{name} | London Schools Explorer">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:url" content="{url}">
  <meta property="og:type" content="website">
  <script type="application/ld+json">{json.dumps(schema, indent=2)}</script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; color: #1a1a1a; background: #f8f9fa; line-height: 1.6; }}
    a {{ color: #1565C0; }}
    .topbar {{ background: #fff; border-bottom: 1px solid #e0e0e0; padding: 12px 20px; }}
    .topbar a {{ text-decoration: none; font-weight: 600; color: #1a1a1a; font-size: 15px; }}
    .topbar span {{ color: #888; margin: 0 8px; }}
    .hero {{ background: #fff; border-bottom: 1px solid #e0e0e0; padding: 28px 20px 24px; }}
    .container {{ max-width: 780px; margin: 0 auto; padding: 24px 20px; display: flex; flex-direction: column; gap: 16px; }}
    .hero .container {{ padding: 0; }}
    .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-bottom: 10px; }}
    h1 {{ font-size: clamp(22px, 5vw, 30px); font-weight: 700; line-height: 1.2; margin-bottom: 6px; }}
    .meta {{ color: #555; font-size: 14px; margin-top: 4px; }}
    .card {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 10px; padding: 20px 24px; }}
    .card h2 {{ font-size: 16px; font-weight: 600; margin-bottom: 14px; color: #111; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    td {{ padding: 8px 0; border-bottom: 1px solid #f0f0f0; vertical-align: top; }}
    td:first-child {{ color: #555; width: 48%; }}
    tr:last-child td {{ border-bottom: none; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .stat {{ background: #f8f9fa; border-radius: 8px; padding: 14px 16px; }}
    .stat-label {{ font-size: 12px; color: #666; margin-bottom: 4px; }}
    .stat-value {{ font-size: 22px; font-weight: 700; color: #111; }}
    .actions {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 4px; }}
    .btn {{ display: inline-block; padding: 10px 18px; border-radius: 8px; font-size: 14px; font-weight: 500; text-decoration: none; border: 1px solid #ccc; color: #1a1a1a; background: #fff; }}
    .btn-primary {{ background: #1565C0; color: #fff; border-color: #1565C0; }}
    .back-link {{ font-size: 14px; color: #555; text-decoration: none; }}
    .back-link:hover {{ color: #111; }}
    footer {{ text-align: center; padding: 32px 20px; font-size: 13px; color: #888; }}
    @media (max-width: 520px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>

<div class="topbar">
  <div style="max-width:780px;margin:0 auto">
    <a href="/">London Schools Explorer</a>
    <span>/</span>
    <a href="/schools/{borough_slug}">{borough}</a>
    <span>/</span>
    {name}
  </div>
</div>

<div class="hero">
  <div class="container">
    <div>
      <span class="badge" style="background:{ofsted_bg_color};color:{ofsted_text_color}">{ofsted_label}</span>
      <h1>{name}</h1>
      <p class="meta">{street}, {borough}, {postcode}{"&ensp;·&ensp;" + phase if phase != "N/A" else ""}{"&ensp;·&ensp;" + school_type if school_type != "N/A" else ""}</p>
    </div>
    <div class="actions">
      {"<a class='btn btn-primary' href='" + ofsted_url + "' target='_blank' rel='noopener'>View Ofsted report</a>" if ofsted_url else ""}
      {"<a class='btn' href='" + maps_link + "' target='_blank' rel='noopener'>View on map</a>" if maps_link else ""}
      <a class="btn" href="/">Browse all schools</a>
    </div>
  </div>
</div>

<div class="container">

  <div class="grid">
    <div class="stat"><div class="stat-label">Pupils</div><div class="stat-value">{pupils}</div></div>
    <div class="stat"><div class="stat-label">Capacity</div><div class="stat-value">{capacity}</div></div>
  </div>

  <section class="card">
    <h2>School details</h2>
    <table>
      <tr><td>Borough</td><td><strong>{borough}</strong></td></tr>
      <tr><td>Postcode</td><td><strong>{postcode}</strong></td></tr>
      <tr><td>Phase</td><td><strong>{phase}</strong></td></tr>
      <tr><td>School type</td><td><strong>{school_type}</strong></td></tr>
      <tr><td>Gender</td><td><strong>{gender}</strong></td></tr>
      <tr><td>Age range</td><td><strong>{age_range}</strong></td></tr>
      <tr><td>Sixth form</td><td><strong>{sixth_form}</strong></td></tr>
      <tr><td>Admissions</td><td><strong>{admissions}</strong></td></tr>
      <tr><td>Religious character</td><td><strong>{religion}</strong></td></tr>
    </table>
  </section>

  <section class="card">
    <h2>Ofsted inspection</h2>
    <table>
      <tr><td>Overall rating</td><td><span class="badge" style="background:{ofsted_bg_color};color:{ofsted_text_color}">{ofsted_label}</span></td></tr>
      {"<tr><td>Last inspected</td><td><strong>" + inspection + "</strong></td></tr>" if inspection else ""}
      {"<tr><td>Report</td><td>" + ofsted_link + "</td></tr>" if ofsted_link else ""}
    </table>
  </section>

  {results_section}

  <section class="card">
    <h2>Contact & leadership</h2>
    <table>
      <tr><td>{head_title}</td><td><strong>{head_name}</strong></td></tr>
      <tr><td>Phone</td><td>{phone_link}</td></tr>
      <tr><td>Website</td><td>{website_link}</td></tr>
    </table>
  </section>

  <section class="card">
    <h2>Local area</h2>
    <table>
      {"<tr><td>Pupil deprivation</td><td><strong>" + fsm_label + "</strong></td></tr>" if fsm_label else ""}
      {"<tr><td>Crime level</td><td><strong>" + crime_label + "</strong></td></tr>" if crime_label else ""}
    </table>
  </section>

</div>

<footer>
  Data sourced from Ofsted and the Department for Education. Last updated 2025.<br>
  <a href="/">London Schools Explorer</a> &mdash; helping families find the right school.
</footer>

</body>
</html>"""

    return borough_slug, school_slug, html


# ── Build all pages ──────────────────────────────────────────────────────────
print(f"Building {len(schools)} school pages...")
out_root = pathlib.Path("schools")
sitemap_urls = [BASE_URL + "/"]
built = 0

for school in schools:
    try:
        borough_slug, school_slug, html = build_school_page(school)
        school_dir = out_root / borough_slug / school_slug
        school_dir.mkdir(parents=True, exist_ok=True)
        (school_dir / "index.html").write_text(html, encoding="utf-8")
        sitemap_urls.append(f"{BASE_URL}/schools/{borough_slug}/{school_slug}")
        built += 1
    except Exception as e:
        print(f"  SKIP {school.get('name','?')}: {e}")

print(f"Built {built} pages successfully.")


# ── Borough index pages ───────────────────────────────────────────────────────
from collections import defaultdict
by_borough = defaultdict(list)
for school in schools:
    b = school.get("local_authority", "unknown")
    by_borough[b].append(school)

for borough, borough_schools in by_borough.items():
    borough_slug = slugify(borough)
    borough_dir  = out_root / borough_slug
    borough_dir.mkdir(parents=True, exist_ok=True)

    rows = ""
    for s in sorted(borough_schools, key=lambda x: x.get("name", "")):
        s_slug  = slugify(s.get("name","unknown"))
        label   = s.get("quality_label") or s.get("score_band") or "Not yet rated"
        tc, bc  = ofsted_badge_color(label)
        rows += f"""<tr>
          <td><a href="/schools/{borough_slug}/{s_slug}">{safe(s.get('name'))}</a></td>
          <td>{safe(s.get('phase'))}</td>
          <td><span style="background:{bc};color:{tc};padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600">{label}</span></td>
          <td>{safe(s.get('pupils'))}</td>
        </tr>"""

    borough_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Schools in {borough} | London Schools Explorer</title>
  <meta name="description" content="Browse all {len(borough_schools)} schools in {borough}, London. Filter by Ofsted rating, phase, and type. Find outstanding schools near you.">
  <link rel="canonical" href="{BASE_URL}/schools/{borough_slug}">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; color: #1a1a1a; background: #f8f9fa; line-height: 1.6; }}
    a {{ color: #1565C0; }}
    .topbar {{ background: #fff; border-bottom: 1px solid #e0e0e0; padding: 12px 20px; }}
    .topbar a {{ text-decoration: none; font-weight: 600; color: #1a1a1a; font-size: 15px; }}
    .topbar span {{ color: #888; margin: 0 8px; }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 32px 20px; }}
    h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 8px; }}
    .subtitle {{ color: #555; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; border: 1px solid #e0e0e0; }}
    th {{ background: #f5f5f5; padding: 12px 16px; text-align: left; font-size: 13px; color: #555; font-weight: 600; border-bottom: 1px solid #e0e0e0; }}
    td {{ padding: 12px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fafafa; }}
    footer {{ text-align: center; padding: 32px 20px; font-size: 13px; color: #888; }}
  </style>
</head>
<body>
<div class="topbar">
  <div style="max-width:900px;margin:0 auto">
    <a href="/">London Schools Explorer</a>
    <span>/</span>
    {borough}
  </div>
</div>
<div class="container">
  <h1>Schools in {borough}</h1>
  <p class="subtitle">{len(borough_schools)} schools &mdash; browse by name, phase or Ofsted rating</p>
  <table>
    <thead><tr><th>School</th><th>Phase</th><th>Ofsted</th><th>Pupils</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<footer><a href="/">London Schools Explorer</a> &mdash; helping families find the right school.</footer>
</body>
</html>"""

    (borough_dir / "index.html").write_text(borough_html, encoding="utf-8")
    sitemap_urls.append(f"{BASE_URL}/schools/{borough_slug}")

print(f"Built {len(by_borough)} borough pages.")


# ── Sitemap ───────────────────────────────────────────────────────────────────
lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u in sitemap_urls:
    safe_u = u.replace("&", "&amp;")
    lines.append(f"  <url><loc>{safe_u}</loc></url>")
lines.append("</urlset>")

with open("sitemap.xml", "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print(f"Sitemap written with {len(sitemap_urls)} URLs.")


# ── robots.txt ────────────────────────────────────────────────────────────────
robots = f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n"
pathlib.Path("robots.txt").write_text(robots, encoding="utf-8")
print("robots.txt written.")

print("\nDone! Deploy to Vercel and submit sitemap.xml to Google Search Console.")
