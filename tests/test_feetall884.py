"""Every outfit picture has a height entry, so Home stands him at the same height in all of them (audit, .86.84).

David, 23 Nov 2026: "My height isn't consistent throughout these!!!!!!!" Home scales each picture by its
entry in assets/onbody-cut/feet.json; the audit found 26 pictures with no entry, which Home could not scale.
Then: "Just start going through ALL of these in order".
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
feet = json.load(open(ROOT / "assets/onbody-cut/feet.json"))["feet"]
cut = json.load(open(ROOT / "assets/onbody-cut/manifest.json"))["map"]

missing = [f for f in cut if f.endswith(".webp") and f[:-5] not in feet]
assert not missing, ("pictures with no height entry", len(missing), missing[:10])
bad = {k: v for k, v in feet.items() if not (isinstance(v, list) and len(v) == 3 and 600 < 1200 - v[0] - v[2] <= 1200)}
assert not bad, ("height entries that are not [bottom, centre, top] with a sensible height", list(bad.items())[:5])
print("Confirmed all %d outfit pictures have a height entry" % len(cut))
