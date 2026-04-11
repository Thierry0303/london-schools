"""
reset_snobe_urls.py
───────────────────
Regenerates all Snobe URLs from scratch using current correct slug logic.
Run automatically by GitHub Actions monthly, or manually:

    python3 scripts/reset_snobe_urls.py
"""

import json, re

STOP_WORDS = {"the","of","for","and","a","at","in","by","with","an"}

KNOWN = {
    "St Vincent de Paul Catholic Primary School":
        "https://snobe.co.uk/schools/st-vincent-de-paul-catholic-primary-school-0",
    "St Vincent de Paul RC Primary School":
        "https://snobe.co.uk/schools/st-vincent-de-paul-catholic-primary-school-0",
    "St Vincent's Catholic Primary School":
        "https://snobe.co.uk/schools/st-vincents-catholic-primary-school",
    "St Eugene de Mazenod Roman Catholic Primary School":
        "https://snobe.co.uk/schools/st-eugene-de-mazenod-roman-catholic-primary-school",
    "Thomas Coram Centre":
        "https://snobe.co.uk/nursery/thomas-coram-centre",
    "Ashbourne College":
        "https://snobe.co.uk/schools/ashbourne-independent-school",
    "City of London School for Girls":
        "https://snobe.co.uk/schools/city-london-school-girls",
    "The Aldgate School":
        "https://snobe.co.uk/schools/aldgate-school",
    "St Francis of Assisi Catholic Primary School":
        "https://snobe.co.uk/schools/saint-francis-assisi-catholic-primary-school",
    "St Francis of Assisi RC Primary School":
        "https://snobe.co.uk/schools/saint-francis-assisi-catholic-primary-school",
    "Parliament Hill School":
        "https://snobe.co.uk/schools/parliament-hill-school",
    "Harris Academy Battersea":
        "https://snobe.co.uk/schools/harris-academy-battersea",
}

def make_slug(name):
    words = str(name).lower()\
        .replace("\u2019","").replace("\u2018","").replace("'","")\
        .replace(",","").replace(".","").replace("(","").replace(")","").strip().split()
    slug = "-".join(w for w in words if w not in STOP_WORDS)
    return re.sub(r"-+","-",slug).strip("-")

def snobe_prefix(s):
    p = str(s.get("phase","")).lower()
    t = str(s.get("school_type","")).lower()
    n = str(s.get("name","")).lower()
    return "nursery" if "nursery" in p+t+n else "schools"

print("Loading schools.json...")
with open("schools.json", encoding="utf-8") as f:
    schools = json.load(f)
print(f"  {len(schools):,} schools loaded")

known_count = gen_count = 0

for s in schools:
    name = s.get("name","")
    if name in KNOWN:
        s["snobe_url"] = KNOWN[name]
        known_count += 1
    else:
        sl = make_slug(name)
        prefix = snobe_prefix(s)
        s["snobe_url"] = f"https://snobe.co.uk/{prefix}/{sl}" if sl else None
        gen_count += 1

with open("schools.json", "w", encoding="utf-8") as f:
    json.dump(schools, f, ensure_ascii=False, separators=(",",":"))

print(f"\nDone!")
print(f"  Known correct applied: {known_count:,}")
print(f"  Auto-generated:        {gen_count:,}")
print(f"\nNow upload schools.json to GitHub:")
print(f"  Go to github.com/Thierry0303/london-schools")
print(f"  Click schools.json → Edit → paste contents → Commit")
print(f"  OR drag and drop the file onto the repo page")

# Quick verification
with open("schools.json", encoding="utf-8") as f:
    check = json.load(f)

samples = ["Parliament Hill School", "Harris Academy Battersea",
           "The Aldgate School", "Thomas Coram Centre"]
print(f"\nVerification:")
for s in check:
    if s.get("name") in samples:
        print(f"  {s['name']} → {s.get('snobe_url')}")
