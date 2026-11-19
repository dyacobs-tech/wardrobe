#!/usr/bin/env python3
"""Download remote product images, cut them out onto #F6F2EA, save webp.

    python3 scripts/feeds/process_images.py --products data/feeds/normalized.json \
        --out data/feeds/normalized-imaged.json --img-dir assets/editimg
"""
from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import sys
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from feeds.cutout import MAX_PX, QUALITY, composite_offwhite, cutter, process_image  # noqa: E402

UA = "DonnaCatalogBot/1.0 (+https://dyacobs-tech.github.io/wardrobe/; catalog research)"
CTX = ssl.create_default_context()


def fetch_bytes(url: str, timeout: int = 25) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            if r.status >= 400:
                return None
            return r.read()
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--products", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--img-dir", type=Path, default=ROOT / "assets" / "editimg")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    raw = json.loads(args.products.read_text())
    rows = raw if isinstance(raw, list) else list(raw.get("products") or [])
    if args.limit:
        rows = rows[: args.limit]
    cut = cutter()
    args.img_dir.mkdir(parents=True, exist_ok=True)
    kept, failed = [], 0
    for i, row in enumerate(rows, 1):
        if row.get("img") and str(row["img"]).startswith("assets/editimg/"):
            dest = ROOT / row["img"]
            if dest.exists():
                kept.append(row)
                continue
        src = row.get("imgUrl") or row.get("img") or ""
        if not src.startswith("http"):
            failed += 1
            continue
        data = fetch_bytes(src)
        if not data or len(data) < 1000:
            failed += 1
            print(f"  [{i}/{len(rows)}] fail download {row.get('brand')} {row.get('name','')[:40]}", flush=True)
            continue
        try:
            im = Image.open(BytesIO(data))
            cut_im = cut(im)
            out = composite_offwhite(cut_im)
            out.thumbnail((MAX_PX, MAX_PX), Image.Resampling.LANCZOS)
            buf = BytesIO()
            out.save(buf, "WEBP", quality=QUALITY, method=6)
            blob = buf.getvalue()
            h = hashlib.sha256(blob).hexdigest()[:16]
            dest = args.img_dir / f"{h}.webp"
            if not dest.exists():
                dest.write_bytes(blob)
            row = dict(row)
            row["img"] = f"assets/editimg/{h}.webp"
            kept.append(row)
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(rows)}] fail cutout {e}", flush=True)
            continue
        if i % 10 == 0 or i == len(rows):
            print(f"  [{i}/{len(rows)}] kept {len(kept)} failed {failed}", flush=True)
    payload = {"count": len(kept), "failed": failed, "products": kept}
    if isinstance(raw, dict) and "report" in raw:
        payload["report"] = raw["report"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {args.out}: {len(kept)} imaged, {failed} dropped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
