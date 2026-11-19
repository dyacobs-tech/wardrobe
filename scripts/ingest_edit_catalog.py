#!/usr/bin/env python3
"""Drop the verified Edit catalogue into the app.

    python scripts/ingest_edit_catalog.py [/workspace/wardrobe-audit/edit-catalog/catalog.json]

Reads catalog.json (a list, or {"products"|"items"|"skus": [...]}) with
per-product brand, name|title, price, url|link, img|image|image_url|images,
store|retailer, cat|category, colour|color. Local images (paths relative
to the catalogue folder) are re-encoded to assets/editimg/<hash>.webp
(max 900px, q82); https images are kept as URLs. Writes
assets/edit-catalog.json in the shape the app reads
(window.editNormalizeCatalog). Products without a url, name, numeric
price or image are dropped and counted.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/wardrobe-audit/edit-catalog/catalog.json")
OUT = ROOT / "assets" / "edit-catalog.json"
IMG = ROOT / "assets" / "editimg"


def price_of(v):
    if isinstance(v, (int, float)):
        return float(v)
    m = re.sub(r"[^0-9.]", "", str(v or ""))
    try:
        return float(m) if m else None
    except ValueError:
        return None


def img_of(p):
    v = p.get("img") or p.get("image") or p.get("image_url") or p.get("imageUrl") or p.get("local_img") or p.get("file")
    if not v and isinstance(p.get("images"), list) and p["images"]:
        f = p["images"][0]
        v = f if isinstance(f, str) else (f.get("src") or f.get("url"))
    return v


def localize(v: str) -> str | None:
    if re.match(r"^https://", v):
        return v
    path = Path(v)
    if not path.is_absolute():
        path = SRC.parent / v
    if not path.exists():
        return None
    from PIL import Image
    h = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    IMG.mkdir(parents=True, exist_ok=True)
    dest = IMG / f"{h}.webp"
    if not dest.exists():
        im = Image.open(path).convert("RGB")
        im.thumbnail((900, 900))
        im.save(dest, "WEBP", quality=82, method=6)
    return f"assets/editimg/{h}.webp"


def main():
    raw = json.loads(SRC.read_text())
    arr = raw if isinstance(raw, list) else (raw.get("products") or raw.get("items") or raw.get("skus") or [])
    out, seen, dropped = [], set(), 0
    for p in arr:
        if not isinstance(p, dict):
            dropped += 1
            continue
        url = p.get("url") or p.get("link") or p.get("pdp") or p.get("href")
        name = p.get("name") or p.get("title")
        price = price_of(p.get("price", p.get("price_usd")))
        img = img_of(p)
        img = localize(img) if img else None
        if not url or not name or price is None or not img or url in seen:
            dropped += 1
            continue
        seen.add(url)
        out.append({k: v for k, v in {
            "brand": p.get("brand") or p.get("vendor") or "",
            "name": name, "price": price, "url": url, "img": img,
            "store": p.get("store") or p.get("retailer") or p.get("seller") or "",
            "category": p.get("cat") or p.get("category") or p.get("type") or "",
            "colour": p.get("colour") or p.get("color") or "",
            "wasPrice": price_of(p.get("wasPrice") or p.get("compare_at_price")),
            "verified": p.get("verified", True),
        }.items() if v not in (None, "")})
    OUT.write_text(json.dumps({"v": 1, "source": str(SRC.name), "count": len(out), "products": out}, separators=(",", ":")))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} products, {dropped} dropped")


if __name__ == "__main__":
    main()
