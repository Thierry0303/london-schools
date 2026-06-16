#!/usr/bin/env python3
"""
fetch_independent_school_data.py

Fetches and merges independent school enrichment data (fees, exam results, boarding).
Part of the monthly data refresh pipeline.

Usage:
  python3 scripts/fetch_independent_school_data.py

Input file:
  data/independent_school_enrichment.csv

Output:
  Modified schools.json with 'independent_data' field added to qualifying schools
"""

import json
import pathlib
import csv
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHOOLS_JSON = ROOT / "schools.json"
DATA_DIR = ROOT / "data"
INDEPENDENT_DATA_CSV = DATA_DIR / "independent_school_enrichment.csv"


def load_independent_data():
    """Load independent school data from CSV file."""
    lookup = {}
    
    if not INDEPENDENT_DATA_CSV.exists():
        print(f"⚠️  Data file not found: {INDEPENDENT_DATA_CSV}")
        print("   Create data/independent_school_enrichment.csv to enable independent school data")
        return lookup
    
    try:
        with open(INDEPENDENT_DATA_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                school_name = row.get('school_name', '').strip()
                if not school_name:
                    continue
                
                # Parse data with type conversion
                try:
                    fees = row.get('fees_annual', '').strip()
                    fees_annual = int(fees) if fees else None
                except (ValueError, TypeError):
                    fees_annual = None
                
                try:
                    a_level = row.get('a_level_a_star_b', '').strip()
                    a_level_pct = float(a_level) if a_level else None
                except (ValueError, TypeError):
                    a_level_pct = None
                
                try:
                    gcse = row.get('gcse_9_7', '').strip()
                    gcse_pct = float(gcse) if gcse else None
                except (ValueError, TypeError):
                    gcse_pct = None
                
                try:
                    year = row.get('exam_year', '').strip()
                    exam_year = int(year) if year else None
                except (ValueError, TypeError):
                    exam_year = None
                
                # Build data dict (only include non-null values)
                ind_data = {}
                if fees_annual is not None:
                    ind_data['fees_annual'] = fees_annual
                if row.get('boarding', '').strip():
                    ind_data['boarding'] = row['boarding'].strip()
                if a_level_pct is not None:
                    ind_data['a_level_a_star_b_percent'] = a_level_pct
                if gcse_pct is not None:
                    ind_data['gcse_9_7_percent'] = gcse_pct
                if exam_year is not None:
                    ind_data['exam_results_year'] = exam_year
                if row.get('isi_status', '').strip():
                    ind_data['isi_inspection_status'] = row['isi_status'].strip()
                if row.get('notes', '').strip():
                    ind_data['notes'] = row['notes'].strip()
                
                if ind_data:  # Only add if we have at least one field
                    lookup[school_name] = ind_data
        
        print(f"✓ Loaded independent school data for {len(lookup)} schools")
        return lookup
    
    except Exception as e:
        print(f"✗ Error loading CSV: {e}")
        return {}


def merge_into_schools_json(independent_data):
    """Merge independent school data into schools.json."""
    
    if not independent_data:
        print("No independent school data to merge")
        return 0
    
    # Load schools.json
    try:
        with open(SCHOOLS_JSON, 'r', encoding='utf-8') as f:
            schools = json.load(f)
    except Exception as e:
        print(f"✗ Error loading schools.json: {e}")
        return 0
    
    print(f"  Loaded {len(schools)} schools from schools.json")
    
    # Merge data
    merged = 0
    skipped = 0
    
    for school in schools:
        school_name = school.get('name', '').strip()
        school_type = school.get('school_type', '').lower()
        
        # Only process independent schools
        if 'independent' not in school_type:
            continue
        
        # Skip if already has data (don't overwrite existing enrichment)
        if school.get('independent_data'):
            skipped += 1
            continue
        
        # Find matching data
        if school_name in independent_data:
            school['independent_data'] = independent_data[school_name]
            merged += 1
    
    # Save updated schools.json
    try:
        with open(SCHOOLS_JSON, 'w', encoding='utf-8') as f:
            json.dump(schools, f, ensure_ascii=False, indent=2)
        print(f"✓ Merged independent data for {merged} schools")
        if skipped > 0:
            print(f"  (Skipped {skipped} schools that already had data)")
        return merged
    except Exception as e:
        print(f"✗ Error saving schools.json: {e}")
        return 0


def main():
    print("=" * 70)
    print("Fetching Independent School Enrichment Data")
    print("=" * 70)
    
    # Load data from CSV
    independent_data = load_independent_data()
    
    # Merge into schools.json
    merged_count = merge_into_schools_json(independent_data)
    
    # Summary
    print()
    if merged_count > 0:
        print(f"✅ Successfully enriched {merged_count} independent schools")
    else:
        print("⚠️  No schools enriched. Check data/independent_school_enrichment.csv")
    
    print(f"  Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")


if __name__ == '__main__':
    main()
