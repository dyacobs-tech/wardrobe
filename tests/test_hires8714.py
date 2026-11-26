#!/usr/bin/env python3
"""David's quality gate for the high-res studio redraws (.87.14).

A shown picture fails if it is under the minimum size, was made from
another copy instead of its 4k original, or is noticeably softer than
that original. Phone copies (not the originals) live in
assets/onbody-hires/; provenance in the manifest records which original
each copy came from.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "assets" / "onbody-hires" / "manifest.json"
APP = ROOT / "src" / "app.html"
SW = ROOT / "sw.js"
SOFTNESS_MIN_RATIO = 0.70


def sharpness(path: Path, target_h: int = 400) -> float:
    im = Image.open(path).convert("L")
    h = target_h
    w = max(1, int(round(im.width * h / im.height)))
    g = im.resize((w, h), Image.Resampling.LANCZOS)
    lap = np.asarray(
        g.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)),
        dtype=np.float32,
    )
    return float(lap.var())


def fail(msg: str) -> None:
    print("FAIL:", msg)
    sys.exit(1)


def main() -> None:
    if not MANIFEST.is_file():
        fail("missing assets/onbody-hires/manifest.json")
    j = json.loads(MANIFEST.read_text())
    if not j.get("r"):
        fail("hires manifest has no looks")
    app = APP.read_text()
    sw = SW.read_text()
    if "2026-11-25.87.14" not in app or "2026-11-25.87.14" not in sw:
        fail("build stamp is not 2026-11-25.87.14")
    for needle in (
        "function hiresForLook",
        "function hiresForKey",
        "assets/onbody-hires/manifest.json",
        'hiresForLook(todayLook, "full")',
        'hiresForLook(look, "card")',
        "function cardPicForLook",
        "card grids prefer the cream hires JPEG",
    ):
        if needle not in app:
            fail(f"app is missing {needle!r}")

    hires_dir = ROOT / "assets" / "onbody-hires"
    for p in hires_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".json", ".jpg", ".jpeg", ".webp"}:
            fail(f"unexpected file in onbody-hires: {p}")
        if p.stat().st_size >= 2_000_000:
            fail(f"{p} is too large for a phone copy ({p.stat().st_size} bytes)")
        if p.suffix.lower() == ".json":
            data = p.read_text()
            if "data:image" in data:
                fail("closet or original image data in the public manifest")
            if "closet" in data.lower() and "No originals or closet data" not in data:
                fail("closet data in the public manifest")

    mins_full = j["min_full"]
    mins_card = j["min_card"]
    copy_shas: dict[str, str] = {}
    failures: list[str] = []
    for e in j["r"]:
        label = f"look {e.get('look_n')} {e['k'][:24]}"
        for kind, rel, mins, sha_key, from_key, sharp_key, sharp_orig_key in (
            ("full", e["full"], mins_full, "full_sha256", "full_from_original", "sharpness_full", "sharpness_original_at_full"),
            ("card", e["card"], mins_card, "card_sha256", "card_from_original", "sharpness_card", "sharpness_original_at_card"),
        ):
            path = ROOT / rel
            if not path.is_file():
                failures.append(f"{label} {kind}: missing {path}")
                continue
            st = path.stat().st_size
            w, h = Image.open(path).size
            if w < mins["w"] or h < mins["h"]:
                failures.append(f"{label} {kind}: dims {w}x{h} under minimum {mins['w']}x{mins['h']}")
            if st < mins["bytes"]:
                failures.append(f"{label} {kind}: {st} bytes under minimum {mins['bytes']}")
            if e.get(from_key) != e.get("original_sha256"):
                failures.append(f"{label} {kind}: from_original is not the original sha256 (copy of a copy)")
            hsh = hashlib.sha256(path.read_bytes()).hexdigest()
            if hsh != e.get(sha_key):
                failures.append(f"{label} {kind}: file sha does not match manifest")
            copy_shas[hsh] = f"{label} {kind}"
            measured = sharpness(path)
            recorded_orig = float(e.get(sharp_orig_key) or 0)
            recorded_copy = float(e.get(sharp_key) or 0)
            if recorded_copy and abs(measured - recorded_copy) / recorded_copy > 0.15:
                failures.append(f"{label} {kind}: live sharpness {measured:.1f} disagrees with recorded {recorded_copy:.1f}")
            if recorded_orig and measured / recorded_orig < SOFTNESS_MIN_RATIO:
                failures.append(f"{label} {kind}: sharpness {measured:.1f} is softer than original {recorded_orig:.1f}")
        if e.get("card_from_original") != e.get("full_from_original"):
            failures.append(f"{label}: card and full do not share the same original")
        if e.get("card_sha256") == e.get("original_sha256") or e.get("full_sha256") == e.get("original_sha256"):
            failures.append(f"{label}: a phone copy was stored as the original")
        if e.get("card_sha256") == e.get("full_sha256"):
            failures.append(f"{label}: card and full are the same file")

    for e in j["r"]:
        for src in (e.get("from_original"), e.get("card_from_original"), e.get("full_from_original")):
            if src in copy_shas:
                failures.append(f"look {e.get('look_n')}: from_original is a phone copy ({copy_shas[src]})")

    onbody = json.loads((ROOT / "assets" / "onbody" / "manifest.json").read_text())
    hires_keys = {e["k"] for e in j["r"]}
    kept = 0
    for row in onbody["r"]:
        if row["k"] in hires_keys:
            continue
        if (ROOT / "assets" / "onbody" / row["f"]).is_file():
            kept += 1
    if kept == 0:
        failures.append("old onbody pictures for looks not yet redrawn are missing")

    if failures:
        fail("quality gate:\n  " + "\n  ".join(failures))
    print(f"PASS  {len(j['r'])} hires looks, {kept} unre-drawn onbody pictures kept")


if __name__ == "__main__":
    main()
