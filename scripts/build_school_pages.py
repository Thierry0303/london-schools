import json, os, pathlib

# Load your school data
with open("schools.json") as f:
    schools = json.load(f)

# Create output directory
out_dir = pathlib.Path("schools")
out_dir.mkdir(exist_ok=True)

for school in schools:
    # Create a slug from the school name
    slug = school["name"].lower().replace(" ", "-").replace("'", "").replace(",", "")
    borough_slug = school["borough"].lower().replace(" ", "-")
    
    school_dir = out_dir / borough_slug / slug
    school_dir.mkdir(parents=True, exist_ok=True)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{school['name']}, {school['borough']} | London Schools Explorer</title>
  <meta name="description" content="{school.get('ofstedRating', 'Ofsted-rated')} school in {school['borough']}. View Ofsted report, admissions info and nearby schools.">
  <link rel="canonical" href="https://london-schools.vercel.app/schools/{borough_slug}/{slug}">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "EducationalOrganization",
    "name": "{school['name']}",
    "address": {{
      "@type": "PostalAddress",
      "addressLocality": "{school['borough']}",
      "addressRegion": "London"
    }},
    "url": "https://london-schools.vercel.app/schools/{borough_slug}/{slug}"
  }}
  </script>
</head>
<body>
  <h1>{school['name']}</h1>
  <p><strong>Borough:</strong> {school['borough']}</p>
  <p><strong>Ofsted rating:</strong> {school.get('ofstedRating', 'N/A')}</p>
  <p><strong>Pupils:</strong> {school.get('pupils', 'N/A')}</p>
  <a href="/">Back to all schools</a>
</body>
</html>"""
    
    (school_dir / "index.html").write_text(html)

print(f"Built {len(schools)} school pages")
