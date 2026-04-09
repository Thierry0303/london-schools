import json, os, pathlib

# Ensure we're always working from the repo root
os.chdir(pathlib.Path(__file__).parent.parent)

# Load your school data
with open("schools.json") as f:
    schools = json.load(f)
