"""A local closet whose item IDs match the checked-in outfit photo library."""
import json
from pathlib import Path


def photographed_closet():
    items = json.loads(Path(__file__).with_name("fixture_closet_live.json").read_text())
    return [
        # The exported photo fields contain redacted or expired blob references.
        dict(item, addedISO=item.get("addedISO") or "2026-11-17", photo="assets/icon-192.png")
        for item in items if not str(item.get("id", "")).startswith("seed-")
    ]
