"""Every picture of David has the same build: shoulders the same width for his height (.87.07).

David, 24 Nov 2026, with a Dress me screenshot: "My proportions look absurd !!!!!" (after "My head is a different
size in all of these!!!!!!! ALL AVATARS should have same proportions wtf!!!!!!"). The head was already one size
(test_pictures8704), but 18 drawings had him up to 18% broader across the shoulders than every other picture, which
looked squat once each picture is scaled to his standard height. Those were narrowed below the neck (the head is not
touched) to the standard build.
Checks every shown outfit picture: shoulder width (the widest row just below the neck) divided by head-to-sole height
is within 6.5% of the median of all of them.
"""
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / "src/app.html").read_text()
seed = json.loads(re.search(r"var ONBODY_SEED = (\{.*?\});\n", src).group(1))
hidden = set(re.findall(r'"([0-9a-f]{16})\.webp"', "".join(re.findall(r"var ONBODY_(?:TUCK_EXCLUDE|REJECTED859|TEELONG879|AUDIT883) = \{.*?\};", src))))


def shoulders(stem):
    a = np.asarray(Image.open(ROOT / "assets/onbody-cut-hq" / (stem + ".webp")).convert("RGBA"))[..., 3] >= 128
    rows = np.where(a.any(1))[0]
    top, feet = int(rows.min()), int(rows.max())
    fig = feet - top
    w = a.sum(1).astype(float)
    y0, y1 = top + int(0.06 * fig), top + int(0.18 * fig)
    neck = int(y0 + np.argmin(w[y0:y1]))
    best = 0
    for y in range(neck + int(0.04 * fig), neck + int(0.09 * fig)):
        xs = np.where(a[y])[0]
        if xs.size:
            best = max(best, int(xs.max() - xs.min()))
    return best / fig


from oldpics import kept   # .87.27: an outfit with a high-res redraw has no old cut-out left to measure
listed = [e["f"][:-5] for e in seed["r"] if e["f"][:-5] not in hidden]
assert len(listed) > 700, len(listed)
stems = kept(listed)
ratio = {s: shoulders(s) for s in stems}
# the standard build, measured over all 790 old pictures before the redrawn ones were removed (26 Nov 2026)
med = 0.253
off = sorted(((s, round(r / med - 1, 3)) for s, r in ratio.items() if abs(r / med - 1) > 0.065), key=lambda x: -abs(x[1]))
assert not off, ("pictures whose build is not the standard one (shoulders vs height, fraction off the median)", len(off), off[:10])
print("Confirmed %d old pictures still shown share one build: shoulders %.3f of his height, all within 6.5%% (widest %+.1f%%, narrowest %+.1f%%)"
      % (len(stems), med, 100 * (max(ratio.values()) / med - 1), 100 * (min(ratio.values()) / med - 1)))
