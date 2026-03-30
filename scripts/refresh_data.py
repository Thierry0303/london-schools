"""
scripts/refresh_data.py

Fetches the latest month of crime data from the Police API and updates
schools.json with fresh crime counts. Designed to run in GitHub Actions.

Run manually:
    python3 scripts/refresh_data.py
"""

import requests
import json
import time
import os
import numpy as np
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2

# ── Config ───────────────────────────────────────────────────────────────────
SCHOOLS_JSON = "schools.json"
RADIUS_KM    = 0.5
PAUSE_SEC    = 0.12   # ~8 requests/sec — well under the API limit
# ─────────────────────────────────────────────────────────────────────────────


def get_best_available_month():
    """
    Police API publishes data ~2 months behind.
    Try the most recent likely month, fall back if not available yet.
    """
    for months_back in [2, 3, 4]:
        d = datetime.now() - timedelta(days=30 * months_back)
        candidate = d.strftime("%Y-%m")
        # Quick availability check
        r = requests.get(
            "https://data.police.uk/api/crimes-street/all-crime",
            params={"lat": 51.5074, "lng": -0.1278, "date": candidate},
            timeout=15
        )
        if r.status_code == 200:
            print(f"Using crime data for: {candidate}")
            return candidate
        print(f"  {candidate} not available yet, trying earlier...")
    raise RuntimeError("Could not find available crime data month")


def fetch_crimes_for_location(lat, lng, date):
    """Fetch all crimes within ~1km of a point for a given month."""
    url = "https://data.police.uk/api/crimes-street/all-crime"
    try:
        r = requests.get(url, params={"lat": lat, "lng": lng, "date": date}, timeout=20)
        if r.status_code == 200:
            return r.json()
        return []
    except Exception as e:
        print(f"    API error: {e}")
        return []


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def count_crimes_near(lat, lng, crimes):
    """Count crimes within RADIUS_KM of a point."""
    return sum(
        1 for c in crimes
        if c.get('location', {}).get('latitude') and c.get('location', {}).get('longitude')
        and haversine_km(
            lat, lng,
            float(c['location']['latitude']),
            float(c['location']['longitude'])
        ) <= RADIUS_KM
    )


def crime_score(count, p95):
    capped = min(count, p95)
    return round((1 - capped / p95) * 100, 1)


def crime_label(score):
    if score >= 80: return 'Low crime area'
    if score >= 60: return 'Below average crime'
    if score >= 40: return 'Average crime'
    if score >= 20: return 'Above average crime'
    return 'High crime area'


def main():
    print("=== Monthly Crime Data Refresh ===\n")

    # Load schools
    with open(SCHOOLS_JSON) as f:
        schools = json.load(f)

    with_coords = [s for s in schools if s.get('lat') and s.get('lng')]
    print(f"Schools to update: {len(with_coords)}")

    # Find available month
    date = get_best_available_month()

    # Fetch crime counts
    print(f"\nFetching crime data for {date}...")
    crime_counts = {}
    errors = 0

    for i, school in enumerate(with_coords):
        urn  = school['urn']
        lat  = school['lat']
        lng  = school['lng']

        crimes = fetch_crimes_for_location(lat, lng, date)
        count  = count_crimes_near(lat, lng, crimes)
        crime_counts[urn] = count

        if (i + 1) % 200 == 0:
            pct = (i + 1) / len(with_coords) * 100
            print(f"  [{i+1}/{len(with_coords)}] {pct:.0f}% complete")

        time.sleep(PAUSE_SEC)

    print(f"\nFetched {len(crime_counts)} schools, {errors} errors")

    # Calculate scores
    counts = list(crime_counts.values())
    p95 = float(np.percentile(counts, 95))
    print(f"Crime stats: min={min(counts)}, max={max(counts)}, mean={sum(counts)/len(counts):.0f}, p95={p95:.0f}")

    # Update schools.json
    for s in schools:
        urn = s.get('urn')
        if urn in crime_counts:
            count = crime_counts[urn]
            s['crime_count']    = count
            s['crime_score']    = crime_score(count, p95)
            s['crime_label']    = crime_label(s['crime_score'])
            s['crime_date']     = date

    with open(SCHOOLS_JSON, 'w') as f:
        json.dump(schools, f, indent=2)

    print(f"\n✅ schools.json updated with crime data for {date}")


if __name__ == "__main__":
    main()
