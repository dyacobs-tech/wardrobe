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

pairsWith (".pairs"): each SKU is re-paired with the closet pieces it
actually goes with (--closet <items.json>, default the live closet copy):
a different slot (a trouser pairs with tops, layers and shoes, never
another trouser), colour harmony (neutral anchors, tonal, soft
complements; saturated clashes lose), and at most two per closet
category, so ordering and suggestions differ per SKU.

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
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
SRC = Path(ARGS[0] if ARGS else "/workspace/wardrobe-audit/edit-catalog/catalog.json")
CLOSET = Path(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--closet=")), "/workspace/wardrobe-audit/build-75/fixture_live83.json"))
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


CLOSET_SLOT = {"Sweaters": "top", "Polos": "top", "Shirts": "top", "Button downs": "top", "Tees": "top", "Blazers": "layer", "Jackets": "layer", "Coats": "layer",
               "Leather jackets": "layer", "Trousers": "bottom", "Jeans": "bottom", "Shorts": "bottom", "Bathing suits": "bottom", "Shoes": "shoes", "Belts": "accessory"}
SKU_SLOT = {"knitwear": "top", "top": "top", "shirt": "top", "blazer": "layer", "suit": "layer", "outerwear": "layer", "trousers": "bottom", "jeans": "bottom",
            "shorts": "bottom", "swim": "bottom", "shoes": "shoes", "belt": "accessory", "sunglasses": "accessory", "tie": "accessory"}
NEUTRAL_WORDS = ("navy", "white", "cream", "ecru", "beige", "stone", "sand", "khaki", "tan", "camel", "brown", "chocolate", "espresso", "taupe", "grey", "gray",
                 "charcoal", "black", "olive", "ivory", "natural", "oat", "denim", "indigo", "panna")


def hex_hsl(h):
    import colorsys
    h = str(h or "").lstrip("#")
    if len(h) != 6:
        return None
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, ss, ll


def neutral(name, hx):
    n = str(name or "").lower()
    if any(w in n for w in NEUTRAL_WORDS):
        return True
    c = hex_hsl(hx)
    return bool(c and (c[1] < 0.22 or c[2] < 0.2 or c[2] > 0.88))


def harmony(a_name, a_hex, b_name, b_hex):
    """Colour score for wearing a with b: neutrals anchor anything,
    tonal pairs and soft complements work, saturated clashes don't."""
    na, nb = neutral(a_name, a_hex), neutral(b_name, b_hex)
    ca, cb = hex_hsl(a_hex), hex_hsl(b_hex)
    score = 0.0
    if na and nb:
        score += 2.0
        if ca and cb:
            score += min(abs(ca[2] - cb[2]), 0.5) * 2  # light against dark reads better than two mids
    elif na or nb:
        score += 2.5
    if ca and cb:
        dh = abs(ca[0] - cb[0]); dh = min(dh, 360 - dh)
        if not (na or nb):
            if dh < 30:
                score += 1.5  # tonal
            elif 150 <= dh <= 210:
                score += 1.0  # complement
            elif 60 <= dh <= 120 and ca[1] > 0.35 and cb[1] > 0.35:
                score -= 2.5  # clash
        if abs(ca[2] - cb[2]) < 0.06 and dh < 12 and ca[1] > 0.15:
            score -= 1.0  # same colour twice
    return score


def pair_closet(e, closet):
    slot = SKU_SLOT.get(e.get("cat"), "top")
    cands = []
    for it in closet:
        cs = CLOSET_SLOT.get(it.get("category"))
        if not cs or cs == slot or (slot == "accessory" and cs == "accessory"):
            continue
        sc = harmony(e.get("colour"), e.get("hex"), it.get("colourName"), it.get("colourHex"))
        # a layer pairs best with tops, shoes with bottoms, bottoms with tops
        if (slot, cs) in (("bottom", "top"), ("layer", "top"), ("shoes", "bottom"), ("top", "bottom"), ("accessory", "bottom"), ("accessory", "shoes")):
            sc += 0.75
        sc += (int(hashlib.md5((e["url"] + it["id"]).encode()).hexdigest()[:4], 16) / 65535) * 0.3  # stable tiebreak
        cands.append((sc, it))
    cands.sort(key=lambda x: -x[0])
    # round-robin across the other slots (a trouser gets tops, a layer
    # AND shoes), best colour match first within each slot
    by_slot = {}
    for sc, it in cands:
        if sc >= 1.0:
            by_slot.setdefault(CLOSET_SLOT.get(it.get("category")), []).append(it)
    order = sorted(by_slot, key=lambda k: -max(harmony(e.get("colour"), e.get("hex"), x.get("colourName"), x.get("colourHex")) for x in by_slot[k]))
    out, per, r = [], {}, 0
    while len(out) < 6 and any(by_slot.values()) and r < 20:
        r += 1
        for k in order:
            lst = by_slot[k]
            while lst:
                it = lst.pop(0)
                c = it.get("category")
                if per.get(c, 0) >= 2:
                    continue
                per[c] = per.get(c, 0) + 1
                out.append(it["id"])
                break
            if len(out) >= 6:
                break
    return out


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
            "sku": Path(str(img_of(p) or "")).stem if str(img_of(p) or "").startswith("img/") else (p.get("sku") or None),
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
    if CLOSET.exists():
        closet = [i for i in json.loads(CLOSET.read_text()) if isinstance(i, dict) and i.get("id")]
        for e in out:
            e["pairs"] = pair_closet(e, closet)
        print(f"paired against {len(closet)} closet pieces ({CLOSET.name})")
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
