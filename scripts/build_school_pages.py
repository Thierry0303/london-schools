import json, os, pathlib, re

# Always run from repo root regardless of where Vercel calls this from
os.chdir(pathlib.Path(__file__).parent.parent)

BASE_URL = "https://londonschool.directory"

SUPA_URL = "https://kwqyogicwbubzbrjwues.supabase.co"
SUPA_KEY = "sb_publishable_488SMcDgCgQx14JB6ngw7A_qay_j9cd"

FEEDBACK_WIDGET = f"""<style>
  #fb-btn{{position:fixed;bottom:24px;right:24px;z-index:9999;background:#1A1A2E;color:#D4A843;border:2px solid #D4A843;border-radius:24px;padding:10px 18px;font-family:system-ui,sans-serif;font-size:14px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:6px;box-shadow:0 4px 16px rgba(0,0,0,0.25);transition:all 0.2s;}}
  #fb-btn:hover{{background:#D4A843;color:#1A1A2E;}}
  #fb-overlay{{position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:10000;display:none;align-items:flex-end;justify-content:center;padding:0 0 80px;}}
  #fb-overlay.open{{display:flex;}}
  #fb-panel{{background:#fff;border-radius:16px 16px 0 0;width:100%;max-width:480px;padding:28px 24px 24px;font-family:system-ui,sans-serif;animation:fbSlide 0.25s ease;position:relative;}}
  @keyframes fbSlide{{from{{transform:translateY(40px);opacity:0;}}to{{transform:translateY(0);opacity:1;}}}}
  #fb-panel h3{{font-size:1.1rem;font-weight:700;margin-bottom:4px;color:#1a1a1a;}}
  #fb-panel p{{font-size:0.83rem;color:#888;margin-bottom:14px;}}
  .fb-stars{{display:flex;gap:6px;margin-bottom:14px;}}
  .fb-star{{font-size:28px;cursor:pointer;color:#ddd;transition:color 0.1s;line-height:1;}}
  .fb-star.active{{color:#D4A843;}}
  .fb-inp{{width:100%;padding:10px 12px;border:1.5px solid #ddd;border-radius:8px;font-family:system-ui,sans-serif;font-size:14px;color:#1a1a1a;background:white;margin-bottom:10px;outline:none;box-sizing:border-box;}}
  .fb-inp:focus{{border-color:#D4A843;}}
  textarea.fb-inp{{resize:vertical;min-height:80px;}}
  #fb-sub{{width:100%;padding:12px;background:#1A1A2E;color:#D4A843;border:none;border-radius:8px;font-size:1rem;font-weight:700;cursor:pointer;}}
  #fb-sub:disabled{{opacity:0.5;cursor:not-allowed;}}
  #fb-close{{position:absolute;top:14px;right:16px;background:none;border:none;font-size:20px;cursor:pointer;color:#aaa;}}
  #fb-ok{{text-align:center;padding:16px 0;display:none;}}
  @media(max-width:520px){{#fb-btn{{bottom:16px;right:16px;padding:8px 14px;font-size:13px;}}}}
</style>
<button id="fb-btn">&#128172; Feedback</button>
<div id="fb-overlay">
  <div id="fb-panel">
    <button id="fb-close">&#10005;</button>
    <div id="fb-wrap">
      <h3>Share your feedback</h3>
      <p>Help us improve London Schools Explorer.</p>
      <div class="fb-stars">
        <span class="fb-star" data-v="1">&#9733;</span>
        <span class="fb-star" data-v="2">&#9733;</span>
        <span class="fb-star" data-v="3">&#9733;</span>
        <span class="fb-star" data-v="4">&#9733;</span>
        <span class="fb-star" data-v="5">&#9733;</span>
      </div>
      <input id="fb-name" class="fb-inp" type="text" placeholder="Your name (optional)" />
      <input id="fb-email" class="fb-inp" type="email" placeholder="Email (optional)" />
      <textarea id="fb-comment" class="fb-inp" placeholder="What did you think? What's missing?"></textarea>
      <button id="fb-sub">Send feedback</button>
    </div>
    <div id="fb-ok"><div style="font-size:2.5rem">&#9989;</div><h3 style="color:#27AE60;margin:8px 0 4px">Thank you!</h3><p>Your feedback helps London parents find the right school.</p></div>
  </div>
</div>
<script>
(function(){{
  var SUPA_URL='{SUPA_URL}',SUPA_KEY='{SUPA_KEY}',rating=0;
  document.getElementById('fb-btn').onclick=function(){{document.getElementById('fb-overlay').classList.add('open');}};
  document.getElementById('fb-close').onclick=function(){{document.getElementById('fb-overlay').classList.remove('open');}};
  document.getElementById('fb-overlay').onclick=function(e){{if(e.target===document.getElementById('fb-overlay'))document.getElementById('fb-overlay').classList.remove('open');}};
  document.querySelectorAll('.fb-star').forEach(function(s){{s.onclick=function(){{rating=parseInt(s.dataset.v);document.querySelectorAll('.fb-star').forEach(function(x){{x.classList.toggle('active',parseInt(x.dataset.v)<=rating);}});}};}}); 
  document.getElementById('fb-sub').onclick=async function(){{
    var comment=document.getElementById('fb-comment').value.trim();
    if(!comment){{document.getElementById('fb-comment').focus();return;}}
    var btn=document.getElementById('fb-sub');btn.disabled=true;btn.textContent='Sending\u2026';
    try{{
      var res=await fetch(SUPA_URL+'/rest/v1/feedback',{{method:'POST',headers:{{'Content-Type':'application/json','apikey':SUPA_KEY,'Authorization':'Bearer '+SUPA_KEY,'Prefer':'return=minimal'}},body:JSON.stringify({{page_url:window.location.href,name:document.getElementById('fb-name').value.trim()||null,email:document.getElementById('fb-email').value.trim()||null,rating:rating||null,comment:document.getElementById('fb-comment').value.trim()}})}});
      if(res.ok||res.status===201){{document.getElementById('fb-wrap').style.display='none';document.getElementById('fb-ok').style.display='block';setTimeout(function(){{document.getElementById('fb-overlay').classList.remove('open');document.getElementById('fb-wrap').style.display='block';document.getElementById('fb-ok').style.display='none';document.getElementById('fb-comment').value='';document.getElementById('fb-name').value='';document.getElementById('fb-email').value='';rating=0;document.querySelectorAll('.fb-star').forEach(function(s){{s.classList.remove('active');}});btn.disabled=false;btn.textContent='Send feedback';}},3000);}}else{{throw new Error();}}
    }}catch(e){{btn.disabled=false;btn.textContent='Try again';alert('Something went wrong. Please try again.');}}
  }};
}})();
</script>"""

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
    title         = name
    title         = name
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
    # Ensure spaces between title prefix and name parts (e.g. "MrSmith" â†’ "Mr Smith")
    if head_name:
        import re as _re
        head_name = _re.sub(r'\b(Mr|Mrs|Ms|Miss|Dr|Prof|Rev|Sir)([A-Z])', r'\1 \2', head_name)
    head_title    = safe(school.get("head_job_title", "Headteacher"))
    website       = school.get("website") or ""
    telephone     = format_phone(school.get("telephone"))
    # Only use verified snobe_url from schools.json â€” set by check_snobe_slugs.py
    # Never generate slugs from name: Snobe uses -0/-1/-2 suffixes for duplicates
    # and different naming conventions to GIAS. Unverified links cause 404s.
    snobe_url = school.get("snobe_url") or ""
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
    school_name_url = name.replace(" ", "+").replace("&", "and") if name else ""

    # Rich meta description with actual data
    meta_parts = [f"{ofsted_label} {phase} school in {borough}, London"]
    if school.get("apps_per_place"):
        meta_parts.append(f"{school['apps_per_place']}Ã- oversubscribed")
    if ks4_att8:
        meta_parts.append(f"Attainment 8: {ks4_att8}")
    elif ks2_expected:
        meta_parts.append(f"KS2 expected: {ks2_expected}%")
    if pupils:
        meta_parts.append(f"{pupils} pupils")
    meta_parts.append(f"{postcode}")
    meta_desc = ". ".join(meta_parts) + ". Free admissions, Ofsted and exam data."

    schema = {
        "@context": "https://schema.org",
        "@type": "School",
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
        "isAccessibleForFree": True,
        "publicAccess": True,
    }
    if telephone:
        schema["telephone"] = telephone
    if website:
        schema["sameAs"] = f"https://{website}" if not website.startswith("http") else website
    if lat and lng:
        schema["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": lat,
            "longitude": lng
        }
    if pupils:
        try:
            schema["numberOfStudents"] = int(pupils)
        except:
            pass
    if school.get("gender") and school["gender"] != "Mixed":
        schema["gender"] = school["gender"]

    # FAQ schema â€” answers common questions parents search for
    faq_items = []
    if school.get("apps_per_place"):
        r = school["apps_per_place"]
        faq_items.append({
            "@type": "Question",
            "name": f"How oversubscribed is {name}?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"{name} received {r} first-choice applications per available place in the 2025 admissions round."
            }
        })
    if ofsted_label and ofsted_label != "Not yet rated":
        faq_items.append({
            "@type": "Question",
            "name": f"What is {name}\'s Ofsted rating?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"{name} was rated {ofsted_label} by Ofsted{(' on ' + inspection) if inspection else ''}. View the full report on the Ofsted website."
            }
        })
    if ks4_att8:
        faq_items.append({
            "@type": "Question",
            "name": f"What are {name}\'s GCSE results?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"{name} achieved an Attainment 8 score of {ks4_att8} in 2024/25. The national average is 46.4."
            }
        })
    elif ks2_expected:
        faq_items.append({
            "@type": "Question",
            "name": f"What are {name}\'s KS2 results?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"At {name}, {ks2_expected}% of pupils met the expected standard in reading, writing and maths at KS2 in 2024/25."
            }
        })
    if school.get("crime_label"):
        faq_items.append({
            "@type": "Question",
            "name": f"Is the area around {name} safe?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"The area within 500m of {name} is classified as {school['crime_label'].lower()} based on Metropolitan Police data."
            }
        })

    faq_schema = None
    if faq_items:
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_items
        }

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name}, {borough} | London Schools Explorer</title>
  <meta name="description" content="{meta_desc}">
  <link rel="canonical" href="{url}">
  <script type="application/ld+json">{{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{"@type": "ListItem", "position": 1, "name": "London Schools Explorer", "item": "https://londonschool.directory/"}},
      {{"@type": "ListItem", "position": 2, "name": "{borough}", "item": "{BASE_URL}/schools/{borough_slug}"}},
      {{"@type": "ListItem", "position": 3, "name": "{title}", "item": "{url}"}}
    ]
  }}</script>
  <meta property="og:title" content="{name} | London Schools Explorer">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:url" content="{url}">
  <meta property="og:type" content="website">
  <script type="application/ld+json">{json.dumps(schema, indent=2)}</script>
  {f'<script type="application/ld+json">{json.dumps(faq_schema, indent=2)}</script>' if faq_schema else ''}
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
    @media (max-width: 600px) {{
      .hero {{ padding: 20px 14px 16px; }}
      h1 {{ font-size: 22px; }}
      .meta {{ font-size: 13px; }}
      .actions {{ flex-direction: column; }}
      .btn {{ text-align: center; }}
      .container {{ padding: 16px 12px; gap: 12px; }}
      .grid {{ grid-template-columns: 1fr; }}
      .card {{ padding: 14px 16px; }}
      td {{ font-size: 13px; padding: 6px 0; }}
      .topbar {{ padding: 10px 12px; font-size: 13px; }}
    }}
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
      <p class="meta">{street}, {borough}, {postcode}{"&ensp;•&ensp;" + phase if phase != "N/A" else ""}{"&ensp;•&ensp;" + school_type if school_type != "N/A" else ""}</p>
    </div>
    <div class="actions">
      {"<a class='btn btn-primary' href='" + ofsted_url + "' target='_blank' rel='noopener'>View Ofsted report</a>" if ofsted_url else ""}
      {"<a class='btn' href='" + maps_link + "' target='_blank' rel='noopener'>📍 View on map</a>" if maps_link else ""}
      {"<a class='btn' href='https://www.google.com/maps/dir/?api=1&destination=" + str(lat) + "," + str(lng) + "&travelmode=walking' target='_blank' rel='noopener' style='background:#E8F5E9;color:#27AE60;border-color:#A5D6A7'>🚶 Walking route</a>" if lat and lng else ""}
      {"<a class='btn' href='https://www.google.com/maps/dir/?api=1&destination=" + str(lat) + "," + str(lng) + "&travelmode=transit' target='_blank' rel='noopener' style='background:#E3F2FD;color:#1565C0;border-color:#90CAF9'>🚌 Bus / Tube route</a>" if lat and lng else ""}
      {"<a class='btn' href='" + snobe_url + "' target='_blank' rel='noopener' style='background:#7B2FBE;color:white;border-color:#7B2FBE'>View on Snobe</a>" if snobe_url else "<a class='btn' href='https://snobe.co.uk/find-schools?search=" + school_name_url + "' target='_blank' rel='noopener' style='background:#7B2FBE;color:white;border-color:#7B2FBE'>Search on Snobe</a>"}
      <a class="btn" href="/schools/{borough_slug}">More schools in {borough}</a>
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

<!-- PiAcademy Section -->
<section class="card" style="background:linear-gradient(135deg,#fff 0%,#f0f7ff 100%);border-color:#dbeafe;">
    <h2 style="display:flex;align-items:center;gap:8px;">
      <span style="font-size:20px;">🎓</span> 11+ Exam Preparation
    </h2>
    <p style="font-size:14px;color:#555;margin-bottom:16px;line-height:1.6;">
      High-quality 11+, 13+, Pre-Tests, SATs and GCSE resources from PiAcademy. 
      Use code <strong>THIERR25</strong> at checkout for 25% off.
    </p>
    
    <a href="https://piacademy.co.uk/?aff=2849515" 
       target="_blank" rel="noopener sponsored"
       style="display:inline-flex;align-items:center;gap:10px;padding:14px 28px;background:#7e22ce;color:white;border-radius:10px;font-size:16px;font-weight:700;text-decoration:none;box-shadow:0 4px 12px rgba(126,34,206,0.3);">
      🎓 Visit PiAcademy & Get 25% OFF
    </a>
    
    <p style="font-size:12px;color:#666;margin-top:12px;">
      <strong>How it works:</strong> Add courses or papers to cart, then enter <strong>THIERR25</strong> at checkout.
    </p>
    
    <p style="font-size:11px;color:#aaa;margin-top:8px;">Sponsored — helps keep this site free.</p>
  </section>

<!-- Scholastic Books Section -->
<section class="card" style="background:linear-gradient(135deg,#fff 0%,#f0f7ff 100%);border-color:#dbeafe;">
    <h2 style="display:flex;align-items:center;gap:8px;">
      <span style="font-size:20px;">📚</span> Children's Books
    </h2>
    <p style="font-size:14px;color:#555;margin-bottom:16px;line-height:1.6;">
      Great children's books at low prices from Scholastic. Every purchase helps your child's school get free books too!
    </p>
    
    <a href="https://www.awin1.com/cread.php?awinmid=2957&awinaffid=2849515&campaign=PBBR+Starter+Packs+Reading+Roots" 
       target="_blank" rel="noopener sponsored"
       style="display:inline-flex;align-items:center;gap:10px;padding:14px 28px;background:#d97706;color:white;border-radius:10px;font-size:16px;font-weight:700;text-decoration:none;box-shadow:0 4px 12px rgba(217,119,6,0.3);">
      📚 Shop Books at Scholastic
    </a>
    
    <p style="font-size:12px;color:#666;margin-top:12px;">
      Tip: At checkout, choose your school — Scholastic donates <strong>20p for every £1 spent</strong> back to the school in free books.
    </p>
    
    <p style="font-size:11px;color:#aaa;margin-top:8px;">Sponsored — helps keep this site free.</p>
  </section>

  

</div>

<footer>
  Data sourced from Ofsted and the Department for Education. Last updated 2025.<br>
  <a href="/">London Schools Explorer</a> &mdash; helping families find the right school.
</footer>

<script defer src="/_vercel/insights/script.js"></script>
</body>
</html>""" + FEEDBACK_WIDGET.replace('</body>', '').replace('</html>', '') + """
</body>
</html>"""

    return borough_slug, school_slug, html


# â”€â”€ Build all pages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


# â”€â”€ Borough index pages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from collections import defaultdict

BOROUGH_DESCRIPTIONS = {
    "Barking and Dagenham": "Barking and Dagenham is one of East London's most affordable boroughs and has seen significant investment in its schools. The borough has a strong mix of primary and secondary provision, with several schools rated Outstanding by Ofsted. It borders Essex and offers good transport links into central London via the District and Overground lines.",
    "Barnet": "Barnet is one of London's highest-performing boroughs for education, with a large number of Outstanding and Good schools across both primary and secondary phases. The borough includes several selective grammar schools and is consistently popular with families relocating from central London. Areas such as Finchley, East Barnet and Hendon are particularly sought after for their school catchments.",
    "Bexley": "Bexley is a south-east London borough with a well-regarded school system and some of the lowest crime rates in the capital. The borough retains a selective grammar school system, making it attractive to families seeking academic pathways. Schools in areas like Bexleyheath, Sidcup and Welling consistently perform above national averages.",
    "Bromley": "Bromley is one of London's largest boroughs and benefits from a strong educational landscape with numerous Outstanding-rated schools. Like Bexley, it operates grammar schools alongside comprehensive and faith schools. The borough has a suburban feel with good green space and is popular with families seeking larger homes within commuting distance of central London.",
    "Camden": "Camden is an inner-London borough with a diverse and highly competitive school landscape. The borough is home to some of London's most oversubscribed primaries and highly regarded secondaries. Areas such as Hampstead, Primrose Hill and Gospel Oak attract families for their school catchments. Camden consistently invests in education and has a higher-than-average proportion of Outstanding schools.",
    "City of London": "The City of London is the smallest local authority in the country, with just a handful of schools serving its resident and working population. Notable institutions include The Aldgate School, an Outstanding-rated Church of England primary, alongside several prestigious independent schools such as City of London School and City of London School for Girls.",
    "Croydon": "Croydon is south London's largest borough and has one of the most varied school landscapes in the capital, ranging from Outstanding independents to schools requiring improvement. The borough is undergoing significant regeneration and has seen investment in its educational infrastructure. Selective and faith school options are available alongside a full range of comprehensive schools.",
    "Ealing": "Ealing in west London has a strong reputation for education, particularly at primary level, with a high proportion of Good and Outstanding schools. The borough is ethnically diverse and multilingual, and schools reflect this rich cultural mix. Areas such as Hanwell, Northfields and Southall are popular with families, and the Elizabeth line has improved transport links significantly.",
    "Enfield": "Enfield is a north London borough bordering Hertfordshire with a wide range of school types including grammar, faith, academy and independent schools. The borough spans leafy suburban areas in the north such as Winchmore Hill and Palmers Green, through to more urban areas in the south. Several schools consistently achieve above national average exam results.",
    "Greenwich": "Greenwich combines historic significance with a growing and improving school landscape. The borough has seen considerable investment in new school places due to population growth. Secondary schools including Thomas Tallis and Corelli College are well regarded. The borough also benefits from proximity to Blackheath and Eltham, areas popular with families.",
    "Hackney": "Hackney is one of East London's most dynamic boroughs and has transformed its educational offer over the past decade. The borough now has one of the highest proportions of Outstanding-rated schools in inner London. Highly regarded schools such as Gayhurst Community School and Queensbridge Primary make it a competitive catchment. Secondary provision includes Stoke Newington School and Mossbourne Community Academy.",
    "Hammersmith and Fulham": "Hammersmith and Fulham is a compact west London borough with a strong concentration of Good and Outstanding schools. The borough is one of the most densely populated in London, making school places highly competitive. It borders Kensington and Chelsea to the east and has a mix of state, faith and independent school options.",
    "Haringey": "Haringey spans from the affluent Muswell Hill and Crouch End in the west to the more diverse Tottenham and Wood Green in the east, and its school landscape reflects this contrast. The borough has made significant strides in improving school quality and has several Outstanding-rated primaries and secondaries. Alexandra Park School and Fortismere School are among the most popular secondaries.",
    "Harrow": "Harrow is a north-west London borough with a diverse and high-performing school system. The borough is home to the renowned independent Harrow School as well as a strong state sector. Many schools serve large South Asian communities and have a strong ethos around academic achievement. Harrow-on-the-Hill and Pinner are particularly popular areas for families.",
    "Havering": "Havering is the easternmost London borough, bordering Essex, and has a strong tradition of selective education with grammar schools including Royal Liberty and Coopers' Company and Coborn. The borough has a largely suburban character with lower house prices than inner London, making it attractive to families seeking larger homes and strong school options.",
    "Hillingdon": "Hillingdon in west London includes areas ranging from urban Hayes and Southall through to the greener suburbs of Ruislip, Northwood and Uxbridge. The borough has a wide range of school types and several schools rated Outstanding. Proximity to Heathrow and good Crossrail links make it popular with commuting families.",
    "Hounslow": "Hounslow is a diverse west London borough with a strong primary school sector and improving secondary provision. The borough spans from Chiswick in the east â€” with some of west London's most sought-after schools â€” to Feltham and Hanworth in the west. Many schools serve large South Asian and Eastern European communities.",
    "Islington": "Islington is an inner-London borough with a highly competitive school landscape and some of the most oversubscribed schools in the capital. The borough borders Camden and Hackney and is popular with young professional families. Highbury Fields School, Elizabeth Garrett Anderson and Highgate Wood School are among the most popular secondaries. Primary catchments can be extremely tight.",
    "Kensington and Chelsea": "Kensington and Chelsea is one of London's wealthiest boroughs and home to a concentration of prestigious independent schools as well as strong state provision. Holland Park School is one of the most celebrated state secondaries in the capital. The borough has some of the most competitive primary catchments in London, particularly around South Kensington and Chelsea.",
    "Kingston upon Thames": "Kingston upon Thames is a prosperous south-west London borough with consistently high-performing schools across both primary and secondary phases. The borough benefits from a strong local economy and high levels of parental engagement. Schools in areas such as Surbiton, New Malden and Kingston town centre are popular with families relocating from central London.",
    "Lambeth": "Lambeth is a vibrant south London borough stretching from the South Bank to Streatham, with a diverse and improving school landscape. The borough includes highly regarded schools such as Dunraven School and La Retraite RC Girls' School. Brixton, Clapham and Streatham are popular with young families drawn by relatively affordable housing and good transport links.",
    "Lewisham": "Lewisham is a south-east London borough with a strong community feel and an improving school landscape. The borough has invested significantly in education over the past decade and several schools are now rated Outstanding. Areas such as Blackheath, Forest Hill and Lee are particularly popular with families. Prendergast schools and Haberdashers' Boys' School are among the most sought-after secondaries.",
    "Merton": "Merton is a south London borough with a strong reputation for education, particularly in the Wimbledon and Raynes Park areas. The borough has several Outstanding-rated schools and benefits from good transport links via the District line and Thameslink. Rutlish School and Wimbledon College are popular secondary choices.",
    "Newham": "Newham in east London has undergone remarkable educational improvement over the past two decades and now has one of the highest proportions of Good and Outstanding schools among inner-London boroughs. The borough benefited significantly from Olympic investment and regeneration. Schools such as Brampton Manor Academy â€” which sends more students to Oxbridge than most independent schools â€” have national reputations.",
    "Redbridge": "Redbridge is a north-east London borough with a highly competitive school system and a large number of selective and faith school options. The borough has one of the highest proportions of grammar school places in London. Ilford County High and Woodford County High are among the most academically selective schools in the country. The borough borders Essex and has a large South Asian community.",
    "Richmond upon Thames": "Richmond upon Thames is consistently rated as one of the best boroughs in London for education and quality of life. The borough has an exceptionally high proportion of Outstanding-rated schools and benefits from low crime, extensive green space and strong community networks. Schools in Richmond, Twickenham and Ham are highly sought after and catchments can be very tight.",
    "Southwark": "Southwark is an inner-south London borough with a rapidly improving school landscape. The borough spans from London Bridge and Bermondsey through to Peckham, Dulwich and Forest Hill. Dulwich in particular is home to several prestigious independent schools. State secondaries such as Notre Dame RC Girls' School and Harris Academy Peckham are well regarded.",
    "Sutton": "Sutton is a south London borough with one of the strongest selective school systems in the capital. Grammar schools including Nonsuch High School for Girls, Wallington High School for Girls and Sutton Grammar School are among the most academically competitive in London. The borough has consistently high Ofsted ratings across both primary and secondary phases.",
    "Tower Hamlets": "Tower Hamlets is one of London's most densely populated and diverse boroughs, and has one of the most improved school systems in the country. The borough now performs significantly above national averages at both primary and secondary level, a remarkable turnaround from a decade ago. Schools such as Mulberry Academy Shoreditch and George Green's School on the Isle of Dogs are well regarded.",
    "Waltham Forest": "Waltham Forest in north-east London has seen significant improvement in its school quality over the past decade. The borough is increasingly popular with young families priced out of Hackney and Islington, attracted by its improving schools and better value housing. Areas such as Walthamstow, Leytonstone and Chingford offer a range of primary and secondary options.",
    "Wandsworth": "Wandsworth is a south London borough with one of the strongest state school systems in the capital. The borough consistently produces some of the best primary and secondary results in London. Areas such as Battersea, Tooting, Balham and Putney are highly sought after for their school catchments. Ernest Bevin College and Burntwood School are among the most popular secondaries.",
    "Westminster": "Westminster is central London's most prominent borough and home to a mix of outstanding state schools and prestigious independent institutions. The borough is one of the most diverse in London and its schools reflect this. Several primaries are among the most oversubscribed in the capital. Secondary options include Grey Coat Hospital School and The Grey Coat Hospital.",
}

by_borough = defaultdict(list)
for school in schools:
    b = school.get("local_authority", "unknown")
    by_borough[b].append(school)

for borough, borough_schools in by_borough.items():
    borough_slug = slugify(borough)
    borough_dir  = out_root / borough_slug
    borough_dir.mkdir(parents=True, exist_ok=True)

    # Count outstanding schools for the meta description
    outstanding = sum(1 for s in borough_schools if (s.get("quality_label") or s.get("score_band")) == "Outstanding")
    good        = sum(1 for s in borough_schools if (s.get("quality_label") or s.get("score_band")) == "Good")
    desc_intro  = BOROUGH_DESCRIPTIONS.get(borough, f"Browse all {len(borough_schools)} schools in {borough}, London. Find outstanding schools by Ofsted rating, phase and type.")

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
  <title>Schools in {borough}, London | Ofsted Ratings &amp; Results | London Schools Explorer</title>
  <meta name="description" content="{len(borough_schools)} schools in {borough}, London. {outstanding} Outstanding, {good} Good-rated by Ofsted. Compare admissions oversubscription, exam results and crime data. Free.">
  <script type="application/ld+json">{{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": "Schools in {borough}, London",
    "description": "{len(borough_schools)} schools in {borough}, London rated by Ofsted",
    "numberOfItems": {len(borough_schools)},
    "url": "{BASE_URL}/schools/{borough_slug}"
  }}</script>
  <script type="application/ld+json">{{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{"@type": "ListItem", "position": 1, "name": "London Schools Explorer", "item": "https://londonschool.directory/"}},
      {{"@type": "ListItem", "position": 2, "name": "Schools in {borough}", "item": "{BASE_URL}/schools/{borough_slug}"}}
    ]
  }}</script>
  <link rel="canonical" href="{BASE_URL}/schools/{borough_slug}">
  <meta property="og:title" content="Schools in {borough} | London Schools Explorer">
  <meta property="og:description" content="{len(borough_schools)} schools in {borough}. {outstanding} Outstanding-rated. Compare Ofsted ratings, exam results and admissions.">
  <meta property="og:url" content="{BASE_URL}/schools/{borough_slug}">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; color: #1a1a1a; background: #f8f9fa; line-height: 1.6; }}
    a {{ color: #1565C0; }}
    .topbar {{ background: #fff; border-bottom: 1px solid #e0e0e0; padding: 12px 20px; }}
    .topbar a {{ text-decoration: none; font-weight: 600; color: #1a1a1a; font-size: 15px; }}
    .topbar span {{ color: #888; margin: 0 8px; }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 32px 20px; }}
    h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 8px; }}
    .intro {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 10px; padding: 20px 24px; margin-bottom: 24px; font-size: 15px; color: #333; line-height: 1.7; }}
    .stats-row {{ display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }}
    .stat-box {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 14px 18px; flex: 1; min-width: 120px; }}
    .stat-num {{ font-size: 24px; font-weight: 700; color: #1a1a1a; line-height: 1; }}
    .stat-lbl {{ font-size: 12px; color: #888; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; border: 1px solid #e0e0e0; }}
    th {{ background: #f5f5f5; padding: 12px 16px; text-align: left; font-size: 13px; color: #555; font-weight: 600; border-bottom: 1px solid #e0e0e0; }}
    td {{ padding: 12px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fafafa; }}
    .back {{ display: inline-block; margin-bottom: 20px; font-size: 14px; color: #555; text-decoration: none; }}
    .back:hover {{ color: #111; }}
    footer {{ text-align: center; padding: 32px 20px; font-size: 13px; color: #888; }}
    @media (max-width: 600px) {{
      .container {{ padding: 16px 12px; }}
      h1 {{ font-size: 22px; }}
      .stats-row {{ grid-template-columns: 1fr 1fr; }}
      .intro {{ padding: 14px 16px; font-size: 14px; }}
      table {{ font-size: 13px; }}
      th, td {{ padding: 10px 10px; }}
      .topbar {{ padding: 10px 12px; font-size: 13px; }}
    }}
    @media (max-width: 600px) {{ .stats-row {{ flex-direction: column; }} }}
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
  <a class="back" href="/">&#8592; All boroughs</a>
  <h1>Schools in {borough}</h1>

  <div class="stats-row">
    <div class="stat-box"><div class="stat-num">{len(borough_schools)}</div><div class="stat-lbl">Total schools</div></div>
    <div class="stat-box"><div class="stat-num">{outstanding}</div><div class="stat-lbl">Outstanding</div></div>
    <div class="stat-box"><div class="stat-num">{sum(1 for s in borough_schools if (s.get("quality_label") or s.get("score_band")) == "Good")}</div><div class="stat-lbl">Good</div></div>
    <div class="stat-box"><div class="stat-num">{len(set(s.get("phase","") for s in borough_schools if s.get("phase") and s.get("phase") != "Not applicable"))}</div><div class="stat-lbl">School phases</div></div>
  </div>

  <div class="intro">{desc_intro}</div>

  <section class="card" style="background:linear-gradient(135deg,#fff 0%,#f0f7ff 100%);border-color:#dbeafe;">
    <h2 style="display:flex;align-items:center;gap:8px;">
      <span style="font-size:20px;">&#127891;</span> 11+ Exam Preparation
    </h2>
    <p style="font-size:14px;color:#555;margin-bottom:16px;line-height:1.6;">
      High-quality 11+, 13+, Pre-Tests, SATs and GCSE resources from PiAcademy. Use code <strong>THIERR25</strong> at checkout for 25% off.
    </p>
    <a href="https://piacademy.co.uk/?aff=2849515"
       target="_blank" rel="noopener sponsored"
       style="display:inline-flex;align-items:center;gap:10px;padding:14px 28px;background:#7e22ce;color:white;border-radius:10px;font-size:16px;font-weight:700;text-decoration:none;box-shadow:0 4px 12px rgba(126,34,206,0.3);">
      &#127891; Visit PiAcademy &amp; Get 25% OFF
    </a>
    <p style="font-size:12px;color:#666;margin-top:12px;">
      <strong>How to get the discount:</strong> Add any course or papers to your cart, then enter coupon code <strong>THIERR25</strong> at the checkout.
    </p>
    <p style="font-size:11px;color:#aaa;margin-top:8px;">Sponsored &mdash; helps keep this site free.</p>
  </section>

  <section class="card" style="background:linear-gradient(135deg,#fff 0%,#f0f7ff 100%);border-color:#dbeafe;">
    <h2 style="display:flex;align-items:center;gap:8px;">
      <span style="font-size:20px;">&#128218;</span> Children's Books
    </h2>
    <p style="font-size:14px;color:#555;margin-bottom:16px;line-height:1.6;">
      Great children's books at low prices from Scholastic. Every purchase helps your child's school get free books too!
    </p>
    <a href="https://www.awin1.com/cread.php?awinmid=2957&awinaffid=2849515&campaign=PBBR+Starter+Packs+Reading+Roots"
       target="_blank" rel="noopener sponsored"
       style="display:inline-flex;align-items:center;gap:10px;padding:14px 28px;background:#d97706;color:white;border-radius:10px;font-size:16px;font-weight:700;text-decoration:none;box-shadow:0 4px 12px rgba(217,119,6,0.3);">
      &#128218; Shop Books at Scholastic
    </a>
    <p style="font-size:12px;color:#666;margin-top:12px;">
      Tip: At checkout, choose your school &mdash; Scholastic donates <strong>20p for every &pound;1 spent</strong> back to the school in free books.
    </p>
    <p style="font-size:11px;color:#aaa;margin-top:8px;">Sponsored &mdash; helps keep this site free.</p>
  </section>

  <table>
    <thead><tr><th>School</th><th>Phase</th><th>Ofsted</th><th>Pupils</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<footer><a href="/">London Schools Explorer</a> &mdash; helping families find the right school in London.</footer>
<script defer src="/_vercel/insights/script.js"></script>
</body>
</html>"""

    borough_html = borough_html + FEEDBACK_WIDGET.replace('</body>', '').replace('</html>', '') + "\n</body>\n</html>"
    (borough_dir / "index.html").write_text(borough_html, encoding="utf-8")
    sitemap_urls.append(f"{BASE_URL}/schools/{borough_slug}")

print(f"Built {len(by_borough)} borough pages.")


# â”€â”€ School type landing pages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def build_type_page(slug, title, meta_desc, intro, filter_fn):
    matched = [s for s in schools if filter_fn(s)]
    matched.sort(key=lambda s: (s.get("ofsted_score") or 0), reverse=True)

    rows = ""
    for s in matched:
        b_slug  = slugify(s.get("local_authority", "unknown"))
        s_slug  = slugify(s.get("name", "unknown"))
        label   = s.get("quality_label") or s.get("score_band") or "Not yet rated"
        tc, bc  = ofsted_badge_color(label)
        score   = s.get("ofsted_score")
        rows += f"""<tr>
          <td><a href="/schools/{b_slug}/{s_slug}">{safe(s.get('name'))}</a></td>
          <td>{safe(s.get('local_authority'))}</td>
          <td>{safe(s.get('phase'))}</td>
          <td><span style="background:{bc};color:{tc};padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600">{label}</span></td>
          <td style="font-weight:700;color:#1a1a1a">{int(score) if score else 'â€”'}</td>
        </tr>"""

    url  = f"{BASE_URL}/schools/{slug}"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | London Schools Explorer</title>
  <meta name="description" content="{meta_desc}">
  <link rel="canonical" href="{url}">
  <script type="application/ld+json">{{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{"@type": "ListItem", "position": 1, "name": "London Schools Explorer", "item": "https://londonschool.directory/"}},
      {{"@type": "ListItem", "position": 2, "name": "{borough}", "item": "{BASE_URL}/schools/{borough_slug}"}},
      {{"@type": "ListItem", "position": 3, "name": "{title}", "item": "{url}"}}
    ]
  }}</script>
  <meta property="og:title" content="{title} | London Schools Explorer">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:url" content="{url}">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; color: #1a1a1a; background: #f8f9fa; line-height: 1.6; }}
    a {{ color: #1565C0; }}
    .topbar {{ background: #fff; border-bottom: 1px solid #e0e0e0; padding: 12px 20px; }}
    .topbar a {{ text-decoration: none; font-weight: 600; color: #1a1a1a; font-size: 15px; }}
    .topbar span {{ color: #888; margin: 0 8px; }}
    .container {{ max-width: 960px; margin: 0 auto; padding: 32px 20px; }}
    h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 8px; }}
    .intro {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 10px; padding: 20px 24px; margin-bottom: 24px; font-size: 15px; color: #333; line-height: 1.7; }}
    .count-badge {{ display: inline-block; background: #1565C0; color: #fff; font-size: 13px; font-weight: 600; padding: 4px 12px; border-radius: 20px; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; border: 1px solid #e0e0e0; }}
    th {{ background: #f5f5f5; padding: 12px 16px; text-align: left; font-size: 13px; color: #555; font-weight: 600; border-bottom: 1px solid #e0e0e0; white-space: nowrap; }}
    td {{ padding: 11px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fafafa; }}
    .back {{ display: inline-block; margin-bottom: 20px; font-size: 14px; color: #555; text-decoration: none; }}
    footer {{ text-align: center; padding: 32px 20px; font-size: 13px; color: #888; }}
    @media (max-width: 600px) {{
      .container {{ padding: 16px 12px; }}
      h1 {{ font-size: 22px; }}
      .intro {{ padding: 14px 16px; font-size: 14px; }}
      table {{ font-size: 12px; }}
      th, td {{ padding: 8px 8px; }}
      th:nth-child(3), td:nth-child(3),
      th:nth-child(5), td:nth-child(5) {{ display: none; }}
      .topbar {{ padding: 10px 12px; font-size: 13px; }}
    }}
  </style>
</head>
<body>
<div class="topbar">
  <div style="max-width:960px;margin:0 auto">
    <a href="/">London Schools Explorer</a>
    <span>/</span>
    {title}
  </div>
</div>
<div class="container">
  <a class="back" href="/">&#8592; All schools</a>
  <h1>{title}</h1>
  <span class="count-badge">{len(matched)} schools</span>
  <div class="intro">{intro}</div>

  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin:20px 0;">

    <div style="background:linear-gradient(135deg,#fdf8ff 0%,#f3e8ff 100%);border:1px solid #d8b4fe;border-radius:10px;padding:18px 20px;">
      <h3 style="font-family:inherit;font-size:0.95rem;font-weight:700;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
        <span>&#127891;</span> 11+ &amp; Exam Preparation
      </h3>
      <p style="font-size:0.82rem;color:#555;margin-bottom:12px;line-height:1.5;">
        High-quality 11+, 13+, Pre-Tests, SATs and GCSE resources from PiAcademy.
        Use code <strong>THIERR25</strong> for 25% off.
      </p>
      <a href="https://piacademy.co.uk/?aff=2849515" target="_blank" rel="noopener sponsored"
        style="display:inline-flex;align-items:center;gap:8px;padding:10px 18px;background:#7e22ce;color:white;border-radius:8px;font-size:0.85rem;font-weight:700;text-decoration:none;">
        &#127891; Visit PiAcademy &mdash; 25% OFF
      </a>
      <p style="font-size:0.72rem;color:#aaa;margin-top:10px;">Sponsored &mdash; helps keep this site free.</p>
    </div>

    <div style="background:linear-gradient(135deg,#fffbf0 0%,#fef3c7 100%);border:1px solid #fcd34d;border-radius:10px;padding:18px 20px;">
      <h3 style="font-family:inherit;font-size:0.95rem;font-weight:700;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
        <span>&#128218;</span> Children's Books
      </h3>
      <p style="font-size:0.82rem;color:#555;margin-bottom:12px;line-height:1.5;">
        Great children's books at low prices from Scholastic. Every purchase helps your child's school get free books too!
      </p>
      <a href="https://www.awin1.com/cread.php?awinmid=2957&awinaffid=2849515&campaign=PBBR+Starter+Packs+Reading+Roots"
        target="_blank" rel="noopener sponsored"
        style="display:inline-flex;align-items:center;gap:8px;padding:10px 18px;background:#d97706;color:white;border-radius:8px;font-size:0.85rem;font-weight:700;text-decoration:none;">
        &#128218; Shop Books at Scholastic
      </a>
      <p style="font-size:0.72rem;color:#aaa;margin-top:10px;">Sponsored &mdash; helps keep this site free.</p>
    </div>

  </div>
  <table>
    <thead><tr><th>School</th><th>Borough</th><th>Phase</th><th>Ofsted</th><th>Score</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<footer><a href="/">London Schools Explorer</a> &mdash; helping families find the right school in London.</footer>
<script defer src="/_vercel/insights/script.js"></script>
</body>
</html>"""

    page_dir = pathlib.Path("schools") / slug
    page_dir.mkdir(parents=True, exist_ok=True)
    html = html + FEEDBACK_WIDGET.replace('</body>', '').replace('</html>', '') + "\n</body>\n</html>"
    (page_dir / "index.html").write_text(html, encoding="utf-8")
    sitemap_urls.append(url)
    print(f"  Built /schools/{slug} ({len(matched)} schools)")


TYPE_PAGES = [
    (
        "outstanding",
        "Outstanding Schools in London",
        "Full list of all Outstanding-rated schools in London ranked by Ofsted score. Compare exam results, admissions and pupil data across all 32 boroughs.",
        "Outstanding is the highest rating awarded by Ofsted inspectors and is given only to schools that are truly exceptional across all areas: quality of education, behaviour and attitudes, personal development, and leadership and management. Less than a quarter of London schools hold an Outstanding rating. This page lists every Outstanding-rated school in London, ranked by composite score, so you can compare them across boroughs, phases and school types.",
        lambda s: (s.get("quality_label") or s.get("score_band")) == "Outstanding"
    ),
    (
        "good",
        "Good Schools in London",
        "Browse all Good-rated schools in London by Ofsted. Compare results, admissions and borough across all 32 London boroughs.",
        "Good is the second-highest Ofsted rating and represents a school that is performing well and meeting the needs of its pupils. The majority of London schools are rated Good. This page lists every Good-rated school in London, ranked by composite score. A Good school is an excellent choice for most families â€” many Good schools outperform Outstanding schools on exam results and have less oversubscribed admissions.",
        lambda s: (s.get("quality_label") or s.get("score_band")) == "Good"
    ),
    (
        "selective",
        "Selective Schools in London",
        "All selective schools in London including grammar schools and academically selective independents. Compare Ofsted ratings, exam results and admissions data.",
        "Selective schools in London admit pupils based on academic ability, typically assessed through entrance exams taken in Year 5 or 6 for secondary entry. London has fewer grammar schools than areas like Kent or Buckinghamshire, but there are selective state schools and many academically selective independent schools. Selective schools are among the most oversubscribed in the capital. This page lists every school in London with a selective admissions policy, ranked by Ofsted score.",
        lambda s: s.get("admissions") == "Selective"
    ),
    (
        "grammar",
        "Grammar Schools in London",
        "All grammar schools in London. Compare Ofsted ratings, exam results, admissions and borough location for every London grammar school.",
        "Grammar schools are state-funded secondary schools that select pupils by academic ability. London has significantly fewer grammar schools than surrounding counties â€” most are concentrated in Barnet, Bexley, Kingston, Redbridge and Sutton. Entry is typically via the 11-plus exam taken in Year 6. Places at London grammar schools are highly competitive, with many schools receiving ten or more applications per place. This page lists every grammar school in London ranked by Ofsted composite score.",
        lambda s: "grammar" in s.get("school_type", "").lower()
    ),
    (
        "faith",
        "Faith Schools in London",
        "All faith schools in London including Church of England, Catholic, Jewish, Muslim and other religious schools. Compare Ofsted ratings and admissions data.",
        "London has one of the most diverse ranges of faith schools of any city in the world, reflecting its multicultural population. Church of England and Catholic schools make up the majority, but there are also Jewish, Muslim, Hindu, Sikh and other faith schools across the capital. Many faith schools are rated Outstanding or Good by Ofsted and are highly sought after. Admissions to faith schools often prioritise regular worshippers, so it is important to understand the admissions criteria carefully before applying.",
        lambda s: s.get("religious_character") and s.get("religious_character") not in ("None", "Does not apply", "Not applicable", "N/A")
    ),
    (
        "primary",
        "Primary Schools in London",
        "Browse all primary schools in London. Compare Ofsted ratings, KS2 SATs results, admissions and pupil data across all 32 boroughs.",
        "London has over 2,000 primary schools spanning nursery, infant, junior and all-through primary phases, catering for children aged 3 to 11. Primary school places in inner London are among the most competitive in the country, with many schools receiving far more applications than they have places available. This page lists all primary schools in London ranked by Ofsted composite score. You can click any school to view its full profile including KS2 SATs results, admissions data and local area information.",
        lambda s: s.get("phase") == "Primary"
    ),
    (
        "secondary",
        "Secondary Schools in London",
        "Browse all secondary schools in London. Compare Ofsted ratings, GCSE results, sixth form provision and admissions data across all 32 boroughs.",
        "London has over 500 secondary schools offering education to pupils aged 11 to 16 or 18. Secondary school choice in London is complex, with a mix of comprehensives, academies, selective grammar schools, faith schools and independent schools. GCSE results vary widely â€” from schools where nearly every pupil achieves grade 5 or above in English and Maths, to schools with significant challenges. This page lists all secondary schools in London ranked by Ofsted composite score, with GCSE Attainment 8 scores where available.",
        lambda s: s.get("phase") in ("Secondary", "Middle deemed secondary")
    ),
    (
        "sixth-form",
        "Schools with Sixth Forms in London",
        "All London schools and colleges with sixth forms. Compare A-level provision, Ofsted ratings and admissions across all 32 boroughs.",
        "Having a sixth form means a school offers post-16 education, typically A-levels or BTECs, allowing students to continue their studies through Years 12 and 13 without changing schools. Not all London secondary schools have sixth forms â€” many pupils transfer to sixth form colleges or further education colleges at 16. This page lists every school in London that has a sixth form, ranked by Ofsted composite score.",
        lambda s: s.get("sixth_form") == "Has a sixth form"
    ),
]

print("Building school type pages...")
for args in TYPE_PAGES:
    build_type_page(*args)
print(f"Built {len(TYPE_PAGES)} type pages.")



# Written as .txt so Vercel doesn't treat it as a binary asset.
# vercel.json rewrites /sitemap.xml â†’ /sitemap_data.txt transparently.
lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
from datetime import date as _date
_today = _date.today().isoformat()
for u in sitemap_urls:
    safe_u = u.replace("&", "&amp;")
    if u == BASE_URL + "/":
        priority, changefreq = "1.0", "weekly"
    elif u == BASE_URL + "/appeals":
        priority, changefreq = "0.9", "yearly"
    elif "/schools/" in u and u.count("/") >= 5:
        priority, changefreq = "0.8", "monthly"
    elif "/schools/" in u:
        priority, changefreq = "0.7", "monthly"
    else:
        priority, changefreq = "0.5", "monthly"
    lines.append(
        f"  <url><loc>{safe_u}</loc>"
        f"<lastmod>{_today}</lastmod>"
        f"<changefreq>{changefreq}</changefreq>"
        f"<priority>{priority}</priority></url>"
    )
lines.append("</urlset>")

with open("sitemap_data.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print(f"Sitemap written with {len(sitemap_urls)} URLs.")


# â”€â”€ robots.txt â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
robots = f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n"
pathlib.Path("robots.txt").write_text(robots, encoding="utf-8")
print("robots.txt written.")

print("\nDone! Deploy to Vercel and submit sitemap.xml to Google Search Console.")

