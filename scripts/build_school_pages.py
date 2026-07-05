import json, os, pathlib, re
from datetime import datetime

os.chdir(pathlib.Path(__file__).parent.parent)

DATA_YEAR = "2024/25"
BUILT_DATE = datetime.utcnow().strftime("%-d %B %Y")
BASE_URL = "https://londonschool.directory"

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

def derive_phase(school, fallback="N/A"):
    af = school.get("age_from")
    at = school.get("age_to")
    try:
        af = int(af) if af not in (None, "") else None
        at = int(at) if at not in (None, "") else None
    except (TypeError, ValueError):
        af = at = None
    if af is not None and at is not None:
        if at <= 5: return "Nursery"
        if af >= 16: return "Sixth form"
        is_p = af <= 7 and at >= 11
        is_s = at >= 14 and af <= 14
        if is_p and is_s: return "All-through"
        if is_p: return "Primary"
        if is_s: return "Secondary"
    raw = school.get("phase")
    if raw and str(raw).strip().lower() not in ("none", "null", "", "n/a"):
        return str(raw).strip()
    return fallback

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

def render_independent_school_section(school):
    school_type = school.get('school_type', '').lower()
    if 'independent' not in school_type:
        return ''
    
    ind_data = school.get('independent_data')
    if not ind_data:
        return ''
    
    html = []
    html.append('<section class="card" style="background:#F9F7F4;border-left:4px solid #D4A843;">')
    html.append('<h2>Independent School Information</h2>')
    html.append('<table>')
    
    if ind_data.get('fees_annual'):
        fees = ind_data['fees_annual']
        html.append(f'<tr><td>Annual Fees</td><td><strong>£{fees:,}</strong></td></tr>')
    
    if ind_data.get('boarding'):
        boarding = ind_data['boarding']
        html.append(f'<tr><td>Boarding</td><td><strong>{boarding}</strong></td></tr>')
    
    if ind_data.get('a_level_a_star_b_percent'):
        a_level = ind_data['a_level_a_star_b_percent']
        html.append(f'<tr><td>A-Level Results (A*/A)</td><td><strong>{a_level}%</strong></td></tr>')
    
    if ind_data.get('gcse_9_7_percent'):
        gcse = ind_data['gcse_9_7_percent']
        html.append(f'<tr><td>GCSE Results (9-7)</td><td><strong>{gcse}%</strong></td></tr>')
    
    if ind_data.get('exam_results_year'):
        year = ind_data['exam_results_year']
        html.append(f'<tr><td>Exam Results Year</td><td><strong>{year}</strong></td></tr>')
    
    if ind_data.get('isi_inspection_status'):
        status = ind_data['isi_inspection_status']
        html.append(f'<tr><td>ISI Inspection Status</td><td><strong>{status}</strong></td></tr>')
    
    html.append('</table>')
    html.append('</section>')
    return '\n'.join(html)

def build_school_page(school):
    borough_slug  = slugify(school.get("local_authority", "unknown"))
    school_slug   = slugify(school.get("name", "unknown"))
    url           = f"{BASE_URL}/schools/{borough_slug}/{school_slug}"
    name          = safe(school.get("name"))
    borough       = safe(school.get("local_authority"))
    postcode      = safe(school.get("postcode"))
    street        = safe(school.get("street"))
    phase         = derive_phase(school)
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
    if head_name:
        import re as _re
        head_name = _re.sub(r'\b(Mr|Mrs|Ms|Miss|Dr|Prof|Rev|Sir)([A-Z])', r'\1 \2', head_name)
    head_title    = safe(school.get("head_job_title", "Headteacher"))
    website       = school.get("website") or ""
    telephone     = format_phone(school.get("telephone"))
    snobe_url = school.get("snobe_url") or ""
    ofsted_label  = safe(school.get("quality_label") or school.get("score_band"), "Not yet rated")
    ofsted_url    = school.get("ofsted_url") or ""
    inspection    = safe(school.get("inspection_date"), "")
    fsm_label     = safe(school.get("fsm_label"), "")
    crime_label   = safe(school.get("crime_label"), "")
    lat           = school.get("lat", "")
    lng           = school.get("lng", "")

    ofsted_text_color, ofsted_bg_color = ofsted_badge_color(ofsted_label)

    ks2_expected  = school.get("ks2_expected_pct")
    ks2_higher    = school.get("ks2_higher_pct")
    ks4_att8      = school.get("ks4_att8")
    ks4_grade5    = school.get("ks4_grade5_em")
    ks4_grade4    = school.get("ks4_grade4_em")

    phase_lc = phase.lower()
    is_primary_phase = phase_lc == "primary"
    is_secondary_phase = phase_lc in ("secondary", "middle deemed secondary", "16 plus")
    is_all_through = phase_lc == "all-through"
    is_special = "special" in (school.get("school_type") or "").lower()

    results_rows = ""
    if ks2_expected is not None and is_primary_phase and not is_special:
        results_rows += f"<tr><td>KS2 expected standard</td><td><strong>{ks2_expected}%</strong></td></tr>"
    if ks2_higher is not None and is_primary_phase and not is_special:
        results_rows += f"<tr><td>KS2 higher standard</td><td><strong>{ks2_higher}%</strong></td></tr>"
    if ks4_att8 is not None and (is_secondary_phase or is_all_through) and not is_special:
        results_rows += f"<tr><td>Attainment 8 score</td><td><strong>{ks4_att8}</strong></td></tr>"
    if ks4_grade5 is not None and (is_secondary_phase or is_all_through) and not is_special:
        ks4_grade5_display = min(ks4_grade5, 100.0)
        results_rows += f"<tr><td>Grade 5+ English &amp; Maths</td><td><strong>{ks4_grade5_display}%</strong></td></tr>"
    if ks4_grade4 is not None and (is_secondary_phase or is_all_through) and not is_special:
        results_rows += f"<tr><td>Grade 4+ English &amp; Maths</td><td><strong>{ks4_grade4}%</strong></td></tr>"

    results_note = ""
    if ks4_att8 or ks4_grade5:
        results_note = f"<p style=\"font-size:12px;color:#888;margin-top:12px;line-height:1.5;\">KS4 data from DfE {DATA_YEAR} school performance tables. Attainment 8 measures average grade across 8 GCSE subjects (national average: 46.4). Grade 5+ is a strong pass in both English and Maths. Figures may occasionally exceed 100% due to mid-year cohort changes in DfE reporting.</p>"
    elif ks2_expected or ks2_higher:
        results_note = f"<p style=\"font-size:12px;color:#888;margin-top:12px;line-height:1.5;\">KS2 data from DfE {DATA_YEAR} performance tables. Figures show the percentage of pupils meeting the expected or higher standard in reading, writing and maths combined.</p>"

    apps_per_place = school.get("apps_per_place")
    if apps_per_place:
        apps_row = f'<tr><td>Applications per place</td><td><strong>{apps_per_place}</strong></td></tr>'
        apps_note = ('<p style="font-size:12px;color:#888;margin-top:12px;line-height:1.5;">'
                     'Applications per place = number of first-choice applications received per available place '
                     f'in the {DATA_YEAR} admissions round (DfE data). A figure above 1.0 means the school was '
                     'oversubscribed. For example, 2.0 means twice as many families listed this school as their '
                     'first choice as there were places available.</p>')
    else:
        apps_row = ""
        apps_note = ""

    results_section = ""
    if results_rows:
        results_section = f"""
    <section class="card">
      <h2>Exam results</h2>
      <table>{results_rows}</table>
      {results_note}
    </section>"""

    website_link = f'<a href="{"https://" + website if not website.startswith("http") else website}" target="_blank" rel="noopener">{website}</a>' if website else "N/A"
    ofsted_link  = f'<a href="{ofsted_url}" target="_blank" rel="noopener">View Ofsted report</a>' if ofsted_url else ""
    phone_link   = f'<a href="tel:{telephone}">{telephone}</a>' if telephone else "N/A"
    maps_link    = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}" if lat and lng else ""
    school_name_url = name.replace(" ", "+").replace("&", "and") if name else ""

    meta_parts = [f"{ofsted_label} {phase} school in {borough}, London"]
    if school.get("apps_per_place"):
        meta_parts.append(f"{school['apps_per_place']}x oversubscribed")
    if ks4_att8:
        meta_parts.append(f"Attainment 8: {ks4_att8}")
    elif ks2_expected:
        meta_parts.append(f"KS2 expected: {ks2_expected}%")
    if pupils:
        meta_parts.append(f"{pupils} pupils")
    meta_parts.append(f"{postcode}")
    meta_desc = ". ".join(meta_parts) + ". Free admissions, Ofsted and exam data."

    independent_section = render_independent_school_section(school)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name}, {borough} | London Schools Explorer</title>
  <meta name="description" content="{meta_desc}">
  <link rel="canonical" href="{url}">
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
    footer {{ text-align: center; padding: 32px 20px; font-size: 13px; color: #888; }}
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
      <p class="meta">{street}, {borough}, {postcode}</p>
    </div>
    <div class="actions">
      {"<a class='btn btn-primary' href='" + ofsted_url + "' target='_blank'>View Ofsted report</a>" if ofsted_url else ""}
      <a class="btn" href="/">All London schools</a>
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
    </table>
  </section>

  {results_section}

  {independent_section}

  <section class="card">
    <h2>Contact</h2>
    <table>
      <tr><td>Phone</td><td>{phone_link}</td></tr>
      <tr><td>Website</td><td>{website_link}</td></tr>
    </table>
  </section>
</div>

<footer>
  Data sourced from Ofsted and the Department for Education. Last updated {BUILT_DATE}.
</footer>
</body>
</html>"""

    return borough_slug, school_slug, html


print(f"Building {len(schools)} school pages...")
out_root = pathlib.Path("schools")
built = 0

for school in schools:
    try:
        borough_slug, school_slug, html = build_school_page(school)
        school_dir = out_root / borough_slug / school_slug
        school_dir.mkdir(parents=True, exist_ok=True)
        (school_dir / "index.html").write_text(html, encoding="utf-8")
        built += 1
    except Exception as e:
        print(f"  SKIP {school.get('name','?')}: {e}")

print(f"Built {built} pages successfully.")
print("Done!")
