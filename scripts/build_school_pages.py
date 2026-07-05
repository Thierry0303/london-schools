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
    is_special = "special" in (school.get("school_type")
