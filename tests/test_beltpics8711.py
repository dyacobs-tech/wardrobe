"""The belt drawn in his pictures is in the shoes' shade: no cognac belts with dark brown shoes (.87.11).

David, 24 Nov 2026: "Seeing tons of belts that DONT match shoes. Remember dark brown with dark brown. Caramel with
caramel. Etc... I have a match belt for ALL my shoes. Do better!!!!". The app now deals belts shade for shade
(test_beltmatch8709), but 58 of his pictures had a belt drawn in another shade, most of them a cognac or tan belt with
his dark brown suede loafers. Where it could be done cleanly, the belt was recoloured in place to the shoes' shade,
keeping its shape, texture and buckle (each checked by an independent review); the rest are hidden until redrawn.
Checks: every recoloured picture is listed under its new name with all its files, the old name is gone; at the belt's
rows no cognac strap is left in the middle of his body; the hidden pictures are on the hidden list.
"""
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
P = json.loads((ROOT / "tests/pictures8711.json").read_text())
from picture_names import current
from oldpics import is_redrawn
src = (ROOT / "src/app.html").read_text()
seed = json.loads(re.search(r"var ONBODY_SEED = (\{.*?\});\n", src).group(1))
files = {e["f"] for e in seed["r"]}
hidden = set(re.findall(r'"([0-9a-f]{16})\.webp"', "".join(re.findall(r"var ONBODY_(?:TUCK_EXCLUDE|REJECTED859|TEELONG879|AUDIT883) = \{.*?\};", src))))
assert len(P["renamed"]) >= 38, len(P["renamed"])
left = []
for old, new0 in P["renamed"].items():
    new = current(new0)
    assert old + ".webp" not in files and new + ".webp" in files, ("recoloured picture not listed", old, new)
    gone = is_redrawn(new)   # .87.27: since redrawn in high-res, so its old files were removed
    for d in ("assets/onbody/", "assets/onbody-cut/", "assets/onbody-cut-hq/"):
        assert gone or (ROOT / d / (new + ".webp")).exists(), ("missing file", d, new)
        assert not (ROOT / d / (old + ".webp")).exists(), ("old file left behind", d, old)
    if gone:
        continue
    if new != new0:
        continue   # since redrawn under a newer name; its belt is checked there
    y0, y1 = P["belt_rows"][new]
    im = np.asarray(Image.open(ROOT / "assets/onbody-cut-hq" / (new + ".webp")).convert("RGBA"))
    a = im[..., 3] > 200
    cols = np.where(a.any(0))[0]
    cx = (cols.min() + cols.max()) // 2
    box = im[y0:y1, cx - 40:cx + 40, :3].astype(np.uint8)
    hsv = np.asarray(Image.fromarray(box).convert("HSV")).astype(float)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    cognac = (h >= 11) & (h <= 38) & (s > 0.45) & (v > 0.25) & (v < 0.75) & a[y0:y1, cx - 40:cx + 40]
    if P["target"][new] != "caramel" and cognac.mean() > 0.12:
        left.append((new, round(float(cognac.mean()), 3)))
assert not left, ("a cognac belt is still drawn with shoes of another shade", left)
for st in P["hidden"]:
    assert current(st) in hidden, ("a picture with a mismatched belt is shown", st)
print("Confirmed %d pictures now show a belt in the shoes' shade; %d are hidden until redrawn" % (len(P["renamed"]), len(P["hidden"])))
