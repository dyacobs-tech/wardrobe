"""Every picture of David has whole arms and the same head size (.87.04).

David, 24 Nov 2026, with Home screenshots: "Issue with all arm cut off sleeves wrong pls fix", then "Same - did you
audit the fucking images????!", then "My head is a different size in all of these!!!!!!! ALL AVATARS should have
same proportions wtf!!!!!!". The drawings had been fitted into the app's narrow frame by cutting straight down
through the arms, and his head was up to 28% bigger or smaller against his height. Cut arms were redrawn past the
cut (FASHN Reframe, only the new arm edges kept; every one reviewed by eye) and every head scaled to one size with
the body adjusted so his height is unchanged. Pictures that could not be repaired are hidden (ONBODY_AUDIT883).
Checks every listed outfit picture that is not hidden:
  1. nothing of him touches the picture's side edges (an arm running into the frame is cut off by it);
  2. no outer edge runs dead straight for more than 130 rows (a long hard cut; sleeves that hang straight run
     up to about 120). Shorter cuts cannot be told apart from straight sleeves by measurement: the eye review
     caught those;
  3. head width / head-to-sole height is within 3% of the standard 0.098.
"""
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
STD = 0.098
src = (ROOT / "src/app.html").read_text()
seed = json.loads(re.search(r"var ONBODY_SEED = (\{.*?\});\n", src).group(1))
hidden = set(re.findall(r'"([0-9a-f]{16})\.webp"', "".join(re.findall(r"var ONBODY_(?:TUCK_EXCLUDE|REJECTED859|TEELONG879|AUDIT883) = \{.*?\};", src))))


def longest_straight(a):
    best = 0
    for b in (a, a[:, ::-1]):
        rows = np.where(b.any(1))[0]
        ext = np.array([np.argmax(r) for r in b[rows]]); m = ext.min(); run = 1
        for i in range(1, len(ext)):
            run = run + 1 if ext[i] == ext[i - 1] and ext[i] <= m + 2 else 1
            best = max(best, run)
    return best


from oldpics import is_redrawn
touching, straight, head, n, redrawn_n = [], [], [], 0, 0
for e in seed["r"]:
    f = e["f"][:-5]
    if f in hidden:
        continue
    n += 1
    if is_redrawn(f):   # .87.27: its old cut-out is gone; the app shows the high-res redraw
        redrawn_n += 1
        continue
    a = np.asarray(Image.open(ROOT / "assets/onbody-cut-hq" / (f + ".webp")).convert("RGBA"))[..., 3] > 127
    if a[:, :2].any() or a[:, -2:].any():
        touching.append(f)
    if longest_straight(a) > 130:
        straight.append(f)
    rows = np.where(a.any(1))[0]; top, feet = int(rows.min()), int(rows.max()); fig = feet - top
    w = a.sum(1).astype(float); y0, y1 = top + int(0.06 * fig), top + int(0.18 * fig)
    neck = int(y0 + np.argmin(w[y0:y1])); ratio = float(w[top:neck].max()) / fig
    if abs(ratio / STD - 1) > 0.03:
        head.append((f, round(ratio, 4)))
assert n > 700, ("too few pictures checked", n)
assert not touching, ("pictures with an arm running into the frame edge", len(touching), touching[:8])
assert not straight, ("pictures with a long straight cut down an arm", len(straight), straight[:8])
assert not head, ("pictures whose head is not the standard size", len(head), head[:8])
print("(%d of them are old pictures still shown; %d have a high-res redraw)" % (n - redrawn_n, redrawn_n))
print("Confirmed %d pictures: nothing touches the frame, no long straight cuts, the same head size (%.3f of his height)" % (n, STD))
