"""Striped trousers and trunks are whole: their light stripes are no longer cut out of the picture (audit, .86.85).

From the audit David asked to have fixed ("Just start going through ALL of these in order"): in four outfit
pictures the cut-out had removed the white and cream stripes of the striped trousers and swim trunks, so the
background showed through. They were re-cut from the original drawing; this checks they stay whole.
"""
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
# old picture -> repaired picture (.86.85)
FIXED = {
    "abe92b103bb3e362": "b21f9a0d50bc0b45",   # brown and cream striped trousers, grey tee
    "b237d8bf53466e47": "0331bef751936873",   # multi-stripe trunks, white linen shirt
    "758a656cc3cf89f5": "c601a0a9fc63a801",   # multi-stripe trunks, navy tee
    "8d7393fd9ab73342": "a4cb797436619038",   # multi-stripe trunks, cream tee
}


def light_holes(stem):
    """Pixels inside the figure's outline that are cut away although the drawing shows something lighter
    than the grey backdrop there (a keyed-out light stripe)."""
    raw = np.asarray(Image.open(ROOT / f"assets/onbody/{stem}.webp").convert("RGB")).astype(np.float32)
    a = np.asarray(Image.open(ROOT / f"assets/onbody-cut-hq/{stem}.webp").convert("RGBA"))[..., 3]
    edge = np.concatenate([raw[:, :12], raw[:, -12:]], axis=1)
    lighter = raw.mean(2) - np.median(edge, axis=1).mean(1)[:, None] > 22
    n = 0
    for y in range(300, a.shape[0]):
        xs = np.where(a[y] >= 128)[0]
        if xs.size >= 2:
            n += int(((a[y, xs.min():xs.max()] < 128) & lighter[y, xs.min():xs.max()]).sum())
    return n


src = (ROOT / "src/app.html").read_text()
seed = json.loads(re.search(r"var ONBODY_SEED = (\{.*?\});\n", src).group(1))
files = {e["f"] for e in seed["r"]}
for old, new in FIXED.items():
    assert old + ".webp" not in files, ("the old cut-out is still listed", old)
    assert new + ".webp" in files, ("the repaired picture is not listed", new)
    n = light_holes(new)
    assert n < 60, ("light stripes cut out of the picture", new, n)
print("Confirmed the 4 striped outfit pictures are whole")
