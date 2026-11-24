"""Outfit pictures are renamed when they are redrawn or repaired; tests that name a picture follow the renames here."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPS = [("tests/belts8703.json", "belted"), ("tests/pictures8704.json", "renamed"), ("tests/pictures8705.json", "renamed")]


def current(stem):
    for path, key in MAPS:
        p = ROOT / path
        if p.exists():
            stem = json.loads(p.read_text()).get(key, {}).get(stem, stem)
    return stem
