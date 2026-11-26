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


def garments_for_all_levels():
    """Formal and summer garments missing from the original synthetic closet."""
    items = []
    for name, category, colour in [
        ("Black patent Oxford shoes", "Shoes", "Black"),
        ("Black leather oxford dress shoes", "Shoes", "Black"),
        # .86.72 (David, 22 Nov 2026): "Formal loafers should be dark brown boudain lange all Belgians. Balenciaga."
        ("Belgian Shoes dark brown suede loafers", "Shoes", "Dark brown"),
        ("Tuxedo trousers", "Trousers", "Black"),
        ("White tuxedo dress shirt", "Shirts", "White"),
        ("Black shawl collar dinner jacket", "Suits", "Black"),
        ("Navy suit jacket", "Suits", "Navy"),
        ("Grey wool dress trousers", "Trousers", "Grey"),
        ("Olive tailored shorts", "Shorts", "Olive"),
        # .87.23 (David, 26 Nov 2026: "Formal looks should have TIES!!!! All formal should have ties"): Formal
        # deals nothing without a tie, so a closet that covers every level needs some
        ("Dark navy knit tie", "Ties", "Navy"),
        ("Royal blue textured knit tie", "Ties", "Royal Blue"),
        ("Burgundy silk tie", "Ties", "Burgundy"),
    ]:
        items.append(dict(id=name, name=name, category=category, colourName=colour))
    return items
