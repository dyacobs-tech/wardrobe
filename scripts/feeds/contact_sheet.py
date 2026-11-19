#!/usr/bin/env python3
"""Build a contact sheet of catalog images.

    python3 scripts/feeds/contact_sheet.py \
        --products data/feeds/batch1-imaged.json \
        --out catalog-sheet-batch.jpg
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OFFWHITE = (0xF6, 0xF2, 0xEA)
ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--products", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--cell", type=int, default=160)
    ap.add_argument("--cols", type=int, default=16)
    args = ap.parse_args(argv)

    raw = json.loads(args.products.read_text())
    rows = raw if isinstance(raw, list) else raw.get("products") or []
    cell, cols = args.cell, args.cols
    n = len(rows)
    grid_rows = max(1, math.ceil(n / cols))
    pad = 8
    W = cols * cell + pad * 2
    H = grid_rows * cell + pad * 2
    sheet = Image.new("RGB", (W, H), OFFWHITE)
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except Exception:
        font = ImageFont.load_default()
    for i, row in enumerate(rows):
        img_path = args.root / (row.get("img") or "")
        # also accept a flat img dir next to the json
        if not img_path.exists():
            alt = Path(row.get("img") or "")
            if alt.exists():
                img_path = alt
            else:
                # try just the filename under --root
                name = Path(row.get("img") or "").name
                cand = args.root / "assets" / "editimg" / name
                if cand.exists():
                    img_path = cand
        x = pad + (i % cols) * cell
        y = pad + (i // cols) * cell
        if img_path.exists():
            im = Image.open(img_path).convert("RGB")
            im.thumbnail((cell - 4, cell - 18), Image.Resampling.LANCZOS)
            ox = x + (cell - im.size[0]) // 2
            oy = y + 2
            sheet.paste(im, (ox, oy))
        label = f"{row.get('brand','')[:12]}"
        draw.text((x + 2, y + cell - 14), label, fill=(80, 70, 60), font=font)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out, "JPEG", quality=85)
    print(f"wrote {args.out} ({n} tiles, {W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
