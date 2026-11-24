"""Tucked outfit pictures show the belt the app pairs with them (.87.03).

From the audit David asked to have fixed ("Just start going through ALL of these in order"), fix 6: outfit pictures
with a shirt tucked in had no belt. Blocked until he topped up FASHN ("I'm Topped do this"), then, 24 Nov 2026:
"finish belt pictures now that we are back up!". Each picture's belt was added with an image edit; only the waist
strip was laid onto the current picture, keeping today's pixels near the outer outline (the edit drew black slivers
along the sleeves there). All 149 edits were reviewed: 113 are in, 36 that went wrong (no belt, a belt over an
untucked top, a hem cut away, the wrong belt, an altered jacket) were left out and stay beltless.
Checks: each belted picture is listed under its new name with every file it needs (drawing, cut-outs, preview,
feet entry) and the old name is gone; none of the 36 left out was renamed; outside the waist strip the cut-out's
outline is unchanged.
"""
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
B = json.loads((ROOT / "tests/belts8703.json").read_text())
src = (ROOT / "src/app.html").read_text()
seed = json.loads(re.search(r"var ONBODY_SEED = (\{.*?\});\n", src).group(1))
files = {e["f"] for e in seed["r"]}
feet = json.loads((ROOT / "assets/onbody-cut/feet.json").read_text())["feet"]
lq = json.loads((ROOT / "assets/onbody-cut/lq.json").read_text())["lq"]
cman = json.loads((ROOT / "assets/onbody-cut/manifest.json").read_text())["map"]
assert len(B["belted"]) == 113 and len(B["left_out"]) == 36, (len(B["belted"]), len(B["left_out"]))
for old, new in B["belted"].items():
    assert old + ".webp" not in files and new + ".webp" in files, ("belted picture not listed", old, new)
    for d in ("assets/onbody/", "assets/onbody-cut/", "assets/onbody-cut-hq/"):
        assert (ROOT / d / (new + ".webp")).exists(), ("missing file", d, new)
        assert not (ROOT / d / (old + ".webp")).exists(), ("old file left behind", d, old)
    assert new in feet and new in lq and cman.get(new + ".webp"), ("belted picture missing from feet/lq/cut manifest", new)
    hq = Image.open(ROOT / "assets/onbody-cut-hq" / (new + ".webp"))
    assert hq.size == (386, 1280), (new, hq.size)
for old in B["left_out"]:
    assert old + ".webp" in files, ("a left-out picture was renamed or dropped", old)
# the outline (alpha) of a belted cut-out matches its small copy: nothing was cut away at the waist
for new in list(B["belted"].values())[:20]:
    a = np.asarray(Image.open(ROOT / "assets/onbody-cut-hq" / (new + ".webp")).convert("RGBA"))[..., 3] > 127
    s = np.asarray(Image.open(ROOT / "assets/onbody-cut" / (new + ".webp")).convert("RGBA").resize((386, 1280)))[..., 3] > 127
    assert (a != s).mean() < 0.02, ("cut-out and small copy disagree", new)
print("Confirmed %d tucked pictures carry their belt and %d bad edits were left out" % (len(B["belted"]), len(B["left_out"])))
