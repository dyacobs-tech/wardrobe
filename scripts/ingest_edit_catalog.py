#!/usr/bin/env python3
"""Ingest the verified Edit catalogue into the app.

    python scripts/ingest_edit_catalog.py [/workspace/wardrobe-audit/edit-catalog/catalog.json]

Input: catalog.json — a list (or {"products"|"items"|"skus": [...]}) of
SHOP_CATALOGUE-shaped rows with extras (subcat, currency, priceDisplay,
colourName, hex, tags.gapFiller / pairsWith / occasion, verified).
Tolerant of name|title, url|link, img|image|images, store|retailer.

Output:
  assets/edit-catalog.json   the Edit's catalogue (window.editNormalizeCatalog)
  assets/editimg/<sha16>.webp  local images, max 640px, webp q80
  assets/shop-db.json        verified rows merged in by URL (existing URLs
                             are kept as they are; sunglasses stay Edit-only
                             because the shop matchers have no such slot)

Category mapping: subcat chinos -> trousers, polo -> knitwear,
sunglasses kept as its own Edit category. Rows without url, name,
numeric price or an image are dropped and counted.
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
SHOPDB = ROOT / "assets" / "shop-db.json"
MAX_PX, QUALITY = 640, 80
CAT_MAP = {"chinos": "trousers", "chino": "trousers", "polo": "knitwear", "pants": "trousers", "sunglass": "sunglasses"}
SHOP_CATS = {"top", "shirt", "knitwear", "outerwear", "trousers", "shoes", "blazer", "shorts", "suit", "jeans", "belt", "swim", "tie"}


def price_of(v):
    if isinstance(v, (int, float)):
        return float(v)
    m = re.sub(r"[^0-9.]", "", str(v or ""))
    try:
        return float(m) if m else None
    except ValueError:
        return None


def img_of(p):
    v = p.get("img") or p.get("image") or p.get("image_url") or p.get("local_img") or p.get("file")
    if not v and isinstance(p.get("images"), list) and p["images"]:
        f = p["images"][0]
        v = f if isinstance(f, str) else (f.get("src") or f.get("url"))
    return v or p.get("imageUrl") or p.get("imgUrl")


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
        im = Image.open(path)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        im.thumbnail((MAX_PX, MAX_PX), Image.Resampling.LANCZOS)
        im.save(dest, "WEBP", quality=QUALITY, method=6)
    return f"assets/editimg/{h}.webp"


def cat_of(p):
    sub = str(p.get("subcat") or "").lower()
    cat = str(p.get("cat") or p.get("category") or p.get("type") or "").lower()
    if cat in CAT_MAP:
        cat = CAT_MAP[cat]
    if not cat and sub:
        cat = CAT_MAP.get(sub, sub)
    return cat, sub


def yes(v):
    return v is True or str(v).lower() in ("yes", "true", "1")


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
        cat, sub = cat_of(p)
        tags = p.get("tags") or {}
        cur = p.get("currency") or "USD"
        out.append({k: v for k, v in {
            "brand": p.get("brand") or p.get("vendor") or "",
            "name": name, "price": price, "url": url, "img": img,
            "retailer": p.get("retailer") or p.get("store") or p.get("seller") or "",
            "cat": cat, "subcat": sub,
            "colour": p.get("colourName") or p.get("colour") or p.get("color") or "",
            "hex": p.get("hex") or "",
            "keys": p.get("keys") or [],
            "tier": p.get("tier"), "st": p.get("st"), "sq": p.get("sq"),
            "currency": cur if cur != "USD" else None,
            "priceDisplay": p.get("priceDisplay") if cur != "USD" else None,
            "wasPrice": price_of(p.get("wasPrice") or p.get("compare_at_price")),
            "gap": 1 if yes(tags.get("gapFiller")) else None,
            "pairs": tags.get("pairsWith") or None,
            "occasion": tags.get("occasion") or None,
            "verified": p.get("verified") or True,
        }.items() if v not in (None, "", [])})
    out.sort(key=lambda e: (0 if e.get("gap") else 1, 0 if e.get("cat") == "trousers" else 1))
    OUT.write_text(json.dumps({"v": 1, "source": SRC.name, "count": len(out), "products": out}, separators=(",", ":"), ensure_ascii=False))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} products, {dropped} dropped")

    if SHOPDB.exists():
        db = json.loads(SHOPDB.read_text())
        have = {r.get("url") for r in db}
        add = []
        for e in out:
            if e["url"] in have or e.get("cat") not in SHOP_CATS or e.get("currency"):
                continue
            add.append({k: e[k] for k in ("brand", "cat", "img", "keys", "name", "price", "retailer", "tier", "url", "st", "sq") if k in e})
            if e.get("hex"):
                add[-1]["hex"] = e["hex"]
            if e.get("colour"):
                add[-1]["colourName"] = e["colour"]
        if add:
            SHOPDB.write_text(json.dumps(add + db, separators=(",", ":"), ensure_ascii=False))
        print(f"merged {len(add)} new rows into {SHOPDB.relative_to(ROOT)} ({len(db) + len(add)} total)")


if __name__ == "__main__":
    main()
