#!/usr/bin/env python3
"""
update_reception_timeline.py
Runs every October via GitHub Actions.
Updates the reception timeline guide with the correct year for the next admissions cycle.

Admissions cycle logic:
- Applications open September PREV_YEAR
- Deadline: 15 January APPLICATION_YEAR  
- Offer day: 16 April APPLICATION_YEAR
- Children start school: September ADMISSIONS_YEAR

When this runs in October CURRENT_YEAR:
  ADMISSIONS_YEAR = CURRENT_YEAR + 1  (e.g. Oct 2026 → Sep 2027 start)
  APPLICATION_YEAR = CURRENT_YEAR + 1  (deadline Jan 2027, offer Apr 2027)
  PREV_YEAR = CURRENT_YEAR             (applications open Sep 2026)

Birth year range:
  Children born 1 Sep (ADMISSIONS_YEAR - 5) to 31 Aug (ADMISSIONS_YEAR - 4)
  e.g. for Sep 2027 start: born 1 Sep 2022 to 31 Aug 2023
"""

from datetime import date
from pathlib import Path

def main():
    today = date.today()
    current_year = today.year

    # When running in October, we're preparing for the NEXT September
    admissions_year = current_year + 1
    application_year = current_year + 1
    prev_year = current_year

    # Birth year range
    birth_from = f"1 September {admissions_year - 5}"
    birth_to = f"31 August {admissions_year - 4}"

    # Today's date for last updated stamp
    last_updated = today.strftime("%-d %B %Y")

    # Schema date (use today)
    schema_date = today.strftime("%Y-%m-%d")

    template_path = Path(__file__).parent / "guides/london-reception-application-timeline/index.html"
    
    content = template_path.read_text()

    replacements = {
        "ADMISSIONS_YEAR": str(admissions_year),
        "APPLICATION_YEAR": str(application_year),
        "PREV_YEAR": str(prev_year),
        "BIRTH_FROM": birth_from,
        "BIRTH_TO": birth_to,
        "LAST_UPDATED": last_updated,
        "SCHEMA_DATE": schema_date,
    }

    for token, value in replacements.items():
        content = content.replace(token, value)

    template_path.write_text(content)
    print(f"Updated reception timeline for {admissions_year} admissions cycle")
    print(f"  Application deadline: 15 January {application_year}")
    print(f"  Offer day: 16 April {application_year}")
    print(f"  Start school: September {admissions_year}")
    print(f"  Birth range: {birth_from} – {birth_to}")

if __name__ == "__main__":
    main()
