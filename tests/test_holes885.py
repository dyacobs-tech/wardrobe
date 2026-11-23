"""Striped trousers, trunks and shoes are whole: light stripes and shoe panels are no longer cut out (audit, .86.85).

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


# .86.85: shoes and ankles re-cut from the original drawing (see-through shoe panels, washed-out shoes,
# floor shadow round the feet, white blobs at the ankle); old picture -> repaired picture
SHOES = {
    "5b2be978dd3d5249": "a209a2521074bf09",
    "90f8be4833662e86": "d2f9ac9c11fa8742",
    "1ba9d7aa17f7a14c": "feee2caae3b043c1",
    "10f8c030b01aeea6": "935ea1052794c290",
    "7b80965d416bec79": "b48524d060ea8549",
    "e817acde055c2c8f": "4864d1979c93ca81",
    "27ef24b4d48ae89c": "9e6454f40dfb0084",
    "92e321b4db67391b": "319762b968ed250e",
    "c8f0f2ec151163de": "38221feb2e6d3763",
    "76dce7c840001dff": "e065afe3060b98ac",
    "adc700dd952bc53f": "1fbfe7fbc411c624",
    "e652a1803a42e7c4": "9dc05235ab611bb1",
    "4e8b8f659c95e7dc": "e977f3a709c0b12a",
    "9c864a18553cbb83": "6e7894d7a8750c92",
    "0c6b3ed2ebc1a3a6": "300819dd0a9a3446",
    "952f390791bc3d83": "6e443fa812a995aa"
}
# the light grey sneaker whose toe panels are the floor's colour could not be cut cleanly: hidden until redrawn
SHOES_HIDDEN = ["8004b7f7e6517a4f"]

src = (ROOT / "src/app.html").read_text()
seed = json.loads(re.search(r"var ONBODY_SEED = (\{.*?\});\n", src).group(1))
files = {e["f"] for e in seed["r"]}
for old, new in FIXED.items():
    assert old + ".webp" not in files, ("the old cut-out is still listed", old)
    assert new + ".webp" in files, ("the repaired picture is not listed", new)
    n = light_holes(new)
    assert n < 60, ("light stripes cut out of the picture", new, n)
for old, new in SHOES.items():
    assert old + ".webp" not in files and new + ".webp" in files, ("shoe repair not listed", old, new)
    a = np.asarray(Image.open(ROOT / f"assets/onbody-cut-hq/{new}.webp").convert("RGBA"))[..., 3]
    assert (a[1050:, :6] > 127).sum() == 0 and (a[1050:, -6:] > 127).sum() == 0, ("stray strip at the frame edge", new)
hidden = re.search(r"var ONBODY_AUDIT883 = (\{.*?\});", src).group(1)
for f in SHOES_HIDDEN:
    assert f + ".webp" in hidden, ("picture with a broken shoe is not hidden", f)
print("Confirmed the 4 striped outfit pictures are whole and %d shoe pictures are re-cut" % len(SHOES))
