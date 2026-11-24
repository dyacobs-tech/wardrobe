"""Every outfit picture shows both shoes (.86.81).

David, 23 Nov 2026, Home screenshot of the olive pocket tee and light blue jeans with the left shoe cut away to a
sliver of sole: "WTF!!!!". Cutting the background out of light-soled shoes on the grey floor had removed one shoe in
nine pictures. Both feet must be there: the bottom of every cut-out has about as much shoe on the left as the right.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
man = json.loads((ROOT / "assets/onbody/manifest.json").read_text())["r"]
bad = []
for f in sorted({e["f"] for e in man}):
    for d in ("onbody-cut", "onbody-cut-hq"):
        a = np.asarray(Image.open(ROOT / "assets" / d / f).convert("RGBA"))[..., 3] > 127
        h, w = a.shape
        rows = np.where(a.any(1))[0]
        band = a[rows.max() - int(h * 0.06): rows.max() + 1]
        left, right = band[:, : w // 2].sum(), band[:, w // 2:].sum()
        if min(left, right) / max(left, right, 1) < 0.55:
            bad.append((d, f))
assert not bad, ("a shoe is missing in", bad[:8])
print("Confirmed both shoes are in all %d outfit pictures" % len({e["f"] for e in man}))
