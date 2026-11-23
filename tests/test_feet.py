"""Both shoes of every on-body cut-out stay opaque.

The Home hero paints assets/onbody-cut/<id>.webp (the outfit view zooms
assets/onbody-cut-hq/). A bad matte faded the model's right foot — the
shoe on the left of the frame — to nothing, including the Black Overshirt
& Blue Jeans render c6c0fca9cf6398ed. This checks every cut-out:

  * the two soles land within 34px of each other (a missing shoe sits
    a whole shoe-height higher)
  * the body of each shoe is opaque (median alpha >= 175) when the
    other shoe is solid, so a ghosted loafer fails too

Needs ffmpeg on PATH. Never talks to the network.

Usage: python tests/test_feet.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
# The reported outfit: Black Overshirt & Blue Jeans, taupe loafers.
REPORTED = "c6c0fca9cf6398ed"


def decode_alpha(path: Path) -> np.ndarray:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    w, h = (int(x) for x in probe.stdout.strip().split(","))
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
        capture_output=True, check=True).stdout
    if len(raw) != w * h * 4:
        raise RuntimeError(f"{path.name}: decoded {len(raw)} bytes, expected {w * h * 4}")
    return np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4)[:, :, 3]


def shoe_metrics(alpha: np.ndarray) -> dict:
    h, w = alpha.shape
    mid = w // 2
    scale = h / 1280.0

    def sole(x0, x1):
        rows = np.where((alpha[:, x0:x1] > 180).any(1))[0]
        return None if len(rows) == 0 else int(rows.max())

    def body(x0, x1, sole_y):
        up0 = int(55 * scale)
        up1 = max(4, int(10 * scale))
        band = alpha[max(0, sole_y - up0):max(0, sole_y - up1), x0:x1]
        if band.size == 0:
            return None
        cols = np.where((band > 60).any(0))[0]
        if len(cols) < 4:
            return None
        span = int(cols.max() - cols.min())
        c0 = int(cols.min() + span * 0.15)
        c1 = int(cols.max() - span * 0.15)
        core = band[:, c0:c1 + 1]
        vis = core[core > 30]
        if vis.size < 15:
            return None
        return float(np.median(vis))

    left, right = sole(8, mid - 4), sole(mid + 4, w - 8)
    if left is None or right is None:
        return {"gap": 999, "Lm": None, "Rm": None}
    return {
        "gap": abs(left - right),
        "Lm": body(8, mid - 4, left),
        "Rm": body(mid + 4, w - 8, right),
    }


def fault(m: dict) -> str | None:
    if m["gap"] >= 34:
        return f"soles {m['gap']}px apart"
    lm, rm = m["Lm"], m["Rm"]
    if lm is not None and rm is not None and min(lm, rm) < 175 and max(lm, rm) > 230:
        side = "left" if lm < rm else "right"
        return f"{side} shoe median alpha {min(lm, rm):.0f}"
    return None


def hidden_files() -> set:
    """Pictures the app never shows (rejected, tuck-excluded, long-tee): .86.82, read from src/app.html."""
    import re
    src = (ROOT / "src/app.html").read_text()
    out = set()
    for var in ("ONBODY_TUCK_EXCLUDE", "ONBODY_REJECTED859", "ONBODY_TEELONG879"):
        m = re.search(r"var " + var + r" = \{(.*?)\};", src, re.S)
        if m:
            out |= set(re.findall(r'"([0-9a-f]{16})\.webp"', m.group(1)))
    return out


def main() -> int:
    fails = []
    hidden = hidden_files()
    dirs = ["assets/onbody-cut", "assets/onbody-cut-hq"]
    n = 0
    for folder in dirs:
        for path in sorted((ROOT / folder).glob("*.webp")):
            if path.stem in hidden and path.stem != REPORTED:
                continue
            n += 1
            why = fault(shoe_metrics(decode_alpha(path)))
            if why:
                fails.append(f"{folder}/{path.name}: {why}")
            if path.stem == REPORTED and why:
                fails.append(f"reported outfit {path.name} still has a cut-off foot")
    # the reported render must be in both pools
    for folder in dirs:
        if not (ROOT / folder / f"{REPORTED}.webp").exists():
            fails.append(f"missing {folder}/{REPORTED}.webp")
    print(f"checked {n} cut-outs")
    if fails:
        print(f"{len(fails)} FAIL")
        for f in fails:
            print(" ", f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileNotFoundError as e:
        print("FAIL ffmpeg/ffprobe not available:", e)
        sys.exit(1)
