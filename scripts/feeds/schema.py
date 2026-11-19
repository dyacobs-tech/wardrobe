#!/usr/bin/env python3
"""Normalized Edit catalog schema.

Every source adapter (Shopify, Rakuten Advertising, CJ, Impact, Awin,
generic CSV/XML, ShopStyle/Skimlinks-style aggregators) maps into this
shape. The live app reads a compatible subset via
``window.editNormalizeCatalog`` (brand, name, price, url, img, cat, …).
Extra fields stay in ``assets/edit-catalog.json`` and are ignored by
older clients.

Canonical product URL lives in ``url`` and is the dedupe key (with
brand+name as a fallback). Affiliate tracking URLs, when present, live
only in ``affiliateUrl`` — never replace ``url``.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Iterable

TODAY = date.today().isoformat()

# Price bands used by The Edit (`tier`).
def tier_for(price: float, cat: str = "") -> str:
    p = float(price or 0)
    if cat in ("blazer", "outerwear", "shoes", "bag"):
        if p < 250:
            return "affordable"
        if p < 700:
            return "accessible"
        if p < 1800:
            return "luxury"
        return "insensitive"
    if p < 150:
        return "affordable"
    if p < 400:
        return "accessible"
    if p < 1500:
        return "luxury"
    return "insensitive"


FAMILY_HEX = {
    "navy": "#1f2a44", "blue": "#3d5a80", "light blue": "#9aa7b2", "sky": "#8aa0b0",
    "dusty blue": "#7a8b99", "slate blue": "#5a6a7a", "grey": "#8a8680", "gray": "#8a8680",
    "light grey": "#c4c0b8", "light gray": "#c4c0b8", "charcoal": "#4a4a4a", "slate": "#6a6b6e",
    "heather": "#9a9590", "black": "#2a2a2a", "white": "#f4f1ea", "off white": "#f2eee6",
    "off-white": "#f2eee6", "ivory": "#f3eee3", "cream": "#efe6d6", "ecru": "#e8e0d0",
    "oatmeal": "#d8cbb8", "natural": "#d9cbb6", "beige": "#d8c6a5", "sand": "#cbb89a",
    "stone": "#c4b8a5", "camel": "#c4a574", "tan": "#c4a06a", "khaki": "#c2b280",
    "taupe": "#8d7b6b", "brown": "#6b4a32", "dark brown": "#4e2e22", "cognac": "#8a4e2a",
    "burgundy": "#6b2e2e", "red": "#8b3a3a", "green": "#3f4f3a", "olive": "#5c5a3a",
    "dark olive": "#444F35", "forest": "#3a4a3a", "military": "#5a5e45", "militare": "#5a5e45",
    "mint": "#8a9a88", "teal": "#4a6a6a", "pink": "#c9a3a3", "purple": "#5a4a5a",
    "yellow": "#c4a45a", "orange": "#c47a3a", "gold": "#c4a464", "silver": "#b0b0b0",
    "panna": "#f1e7cf", "hazelwood": "#b89a72", "mid grey": "#8a8680", "indigo": "#3a4a6a",
    "denim": "#3d5a80", "bark": "#5a4638", "barley": "#c4b68a", "espresso": "#3c2a22",
    "chocolate": "#5a3a28", "tobacco": "#7a4e2a", "rust": "#8a4a2a", "wine": "#6b2e2e",
    "bone": "#e8e0d0", "putty": "#c4b8a5", "sage": "#8a9a7a", "petrol": "#2a3a44",
    "ink": "#1a2430", "chalk": "#efece4", "snow": "#f6f4ef", "midnight": "#1a2430",
    "marine": "#1f2a44", "adobe": "#b07a5a", "rose": "#c9a3a3", "blush": "#d4b8b0",
}

WOMEN_RE = re.compile(
    r"\b(women|woman|womens|ladies|donna|girl|female|kids|child|youth|maternity)\b",
    re.I,
)
# Drop junk / loud pieces. Swim trunks and bags are allowed separately.
DROP_RE = re.compile(
    r"\b(gift card|fragrance|perfume|candle|underwear|boxer brief|sock|hosiery|"
    r"beanie|baseball cap|hat\b|scarf|glove|phone|airpod|umbrella|"
    r"shoe tree|shoetree|insole|laces\b|hoodie|sweatpants|joggers|track pant|"
    r"performance|athletic|running shoe|gym |nfl-|graphic tee|logo hoodie|"
    r"blanket|candle)\b",
    re.I,
)
LOUD_RE = re.compile(
    r"\b(camouflage|camo print|paint-splatter|logo-embroidered|graphic print|neon|"
    r"no ball games|reindeer|snowflake)\b",
    re.I,
)
SWIM_RE = re.compile(r"\b(swim|swimsuit|swim short|swim trunk|boarding short|board short|swim brief)\b", re.I)
BAG_RE = re.compile(r"\b(weekender|duffel|duffle|holdall|briefcase|messenger|tote|backpack|travel bag|garment bag)\b", re.I)

CAT_MAP = {
    "chinos": "trousers", "chino": "trousers", "polo": "knitwear",
    "pants": "trousers", "sunglass": "sunglasses",
}

GAP_CATS = {"trousers", "chinos", "jeans", "shorts", "belt", "sunglasses", "outerwear", "swim", "bag"}


def sha_sku(*parts: str) -> str:
    blob = "|".join(p or "" for p in parts)
    return "db-" + hashlib.sha1(blob.encode()).hexdigest()[:12]


def clean_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip().split("#")[0]
    if "?" in url:
        base, qs = url.split("?", 1)
        keep = [p for p in qs.split("&") if p.split("=", 1)[0].lower() == "variant"]
        url = base + (("?" + "&".join(keep)) if keep else "")
    return url


def price_of(v: Any) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    m = re.sub(r"[^0-9.]", "", str(v or ""))
    try:
        return float(m) if m else None
    except ValueError:
        return None


def price_display(price: float, currency: str = "USD") -> str:
    cur = (currency or "USD").upper()
    n = int(price) if float(price).is_integer() else float(price)
    whole = float(price).is_integer()
    if cur == "USD":
        return f"${n:,.0f}" if whole else f"${price:,.2f}"
    if cur == "GBP":
        return f"£{n:,.0f}" if whole else f"£{price:,.2f}"
    if cur == "EUR":
        return f"€{n:,.0f}" if whole else f"€{price:,.2f}"
    return f"{cur} {price}"


def colour_from_text(*parts: str) -> tuple[str, str]:
    text = " ".join(p or "" for p in parts).lower()
    for name in sorted(FAMILY_HEX, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", text):
            pretty = name.title()
            if name in ("militare", "panna"):
                pretty = name.title()
            return pretty, FAMILY_HEX[name]
    return "Neutral", "#c4b8a5"


def categorize(text: str, product_type: str = "") -> tuple[str | None, str | None]:
    t = f"{text} {product_type}".lower()
    if SWIM_RE.search(t) and "short sleeve" not in t:
        return "swim", "swim"
    if BAG_RE.search(t):
        return "bag", "bag"
    if any(k in t for k in ("sunglass", "eyewear", "eye glass")):
        return "sunglasses", "sunglasses"
    if re.search(r"\bbelt\b", t):
        return "belt", "belt"
    if re.search(r"\b(tie|necktie|bow tie)\b", t) and "tipped" in t or re.search(r"\b(silk tie|wool tie|necktie|bow tie)\b", t):
        return "tie", "tie"
    if "tie" in (product_type or "").lower() and "shirt" not in t:
        return "tie", "tie"
    if any(k in t for k in ("loafer", "penny", "tassel loafer", "venetian", "sagan", "slipper", "espadrille", "mule")):
        return "shoes", "loafer"
    if any(k in t for k in ("sneaker", "runner", "trainer", "tennis shoe")):
        return "shoes", "sneaker"
    # "oxford" alone is also a shirt cloth — only treat it as a shoe
    # when it's clearly footwear (oxford shoe / no "shirt").
    if "bootcut" in t or "boot cut" in t or "boot-cut" in t:
        pass  # jeans, not boots — fall through
    elif any(k in t for k in ("boat shoe", "driving shoe", "moccasin", "monk", "derby")) or (
        "oxford" in t and "shirt" not in t
    ) or (re.search(r"\bboots?\b", t) and "bootcut" not in t) or (re.search(r"\bshoes?\b", t) and "shirt" not in t and "sweatshirt" not in t):
        if re.search(r"\bboots?\b", t) or any(k in t for k in ("shoe", "moccasin", "derby", "boat")) or ("oxford" in t and "shirt" not in t):
            return "shoes", "shoe"
    if re.search(r"\bjeans?\b", t) or ("denim" in t and any(k in t for k in ("jean", "5-pocket", "five pocket", "selvedge"))):
        return "jeans", "jeans"
    if "chino" in t or "officer pant" in t or "officer trouser" in t:
        return "trousers", "chinos"
    if re.search(r"\bshorts\b", t) or re.search(r"\b(board|deck|chino|carry-on|cruiser)\s+short\b", t):
        if not any(k in t for k in ("short sleeve", "short-sleeve", "sweater", "crew neck", "jacket", "blazer", "coat")):
            return "shorts", "shorts"
    if any(k in t for k in ("trouser", "dress pant", "pantalon")) or re.search(r"\bpants\b", t) or product_type.lower() in ("pants", "trousers", "mens trousers"):
        if "sweatpant" in t or "jogger" in t:
            return None, None
        if any(k in t for k in ("tuxedo", "dinner jacket", "suit set")):
            return None, None
        return "trousers", "trousers"
    if any(k in t for k in ("blazer", "sport coat", "sportcoat", "suit jacket")):
        return "blazer", "blazer"
    if any(k in t for k in ("overshirt", "shirt jacket", "shacket", "chore jacket")):
        return "shirt", "overshirt"
    if any(k in t for k in ("overcoat", "topcoat", "peacoat", "field jacket", "field coat", "bomber", "harrington", "windbreaker", "raincoat", "anorak", "parka", "outerwear", "car coat", "raglan coat")):
        return "outerwear", "outerwear"
    if re.search(r"\b(jacket|coat)\b", t) and "blazer" not in t and "suit" not in t:
        return "outerwear", "outerwear"
    if "polo" in t or "rugby" in t:
        return "knitwear", "polo"
    if any(k in t for k in ("sweater", "jumper", "cardigan", "crewneck", "crew neck", "rollneck", "turtleneck", "cashmere knit", "knitwear")):
        return "knitwear", "knitwear"
    if any(k in t for k in ("shirt", "overshirt", "oxford", "camp collar", "popover")):
        return "shirt", "shirt"
    return None, None


def is_women(text: str, tags: Iterable[str] | None = None, product_type: str = "") -> bool:
    blob = f"{text} {product_type} {' '.join(tags or [])}"
    if re.search(r"WOMEN_|WOMENS|Women's|Womens", blob):
        return True
    return bool(WOMEN_RE.search(blob))


def is_drop(text: str, product_type: str = "") -> bool:
    blob = f"{text} {product_type}"
    # allow swim trunks / swim briefs
    if SWIM_RE.search(blob):
        return bool(LOUD_RE.search(blob))
    if DROP_RE.search(blob) or LOUD_RE.search(blob):
        return True
    return False


def keys_of(*parts: str, extra: Iterable[str] = ()) -> list[str]:
    keys: list[str] = []
    blob = " ".join(p or "" for p in parts)
    for piece in re.findall(r"[a-z0-9]+", blob.lower()):
        if len(piece) > 2 and piece not in keys:
            keys.append(piece)
        if len(keys) >= 8:
            break
    for e in extra:
        if e and e not in keys:
            keys.append(e)
    return keys


def occasion_for(cat: str, subcat: str, name: str) -> str:
    t = name.lower()
    if cat == "swim" or "linen" in t or cat == "sunglasses":
        return "palm-beach"
    if cat == "shorts" or subcat == "chinos":
        return "weekend" if "linen" not in t else "palm-beach"
    if cat in ("trousers", "blazer") and any(k in t for k in ("wool", "flannel", "fresco", "suit")):
        return "work"
    if cat == "shoes" and subcat == "loafer":
        return "smart-casual"
    if cat in ("belt", "bag", "tie"):
        return "smart-casual"
    if cat == "jeans" or subcat == "sneaker":
        return "weekend"
    if cat == "outerwear":
        return "travel"
    return "smart-casual"


@dataclass
class Size:
    size: str
    available: bool = True
    sku: str | None = None
    price: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"size": self.size, "available": self.available}
        if self.sku:
            d["sku"] = self.sku
        if self.price is not None:
            d["price"] = self.price
        return d


@dataclass
class NormalizedProduct:
    """Source-agnostic product row used by ingest and refresh."""

    brand: str
    name: str
    price: float
    url: str
    cat: str
    source: str
    imgUrl: str = ""
    img: str = ""
    retailer: str = ""
    subcat: str = ""
    colour: str = "Neutral"
    hex: str = "#c4b8a5"
    currency: str = "USD"
    priceDisplay: str = ""
    keys: list[str] = field(default_factory=list)
    tier: str = ""
    st: str = "brand_direct"
    sq: str = "elite"
    sku: str = ""
    sourceId: str = ""
    inStock: bool = True
    sizes: list[Size] = field(default_factory=list)
    wasPrice: float | None = None
    affiliateUrl: str | None = None
    status: str = "active"
    locked: bool = False
    pipeline: bool = True
    occasion: str = ""
    gap: int | None = None
    pairs: list[str] = field(default_factory=list)
    verified: str = TODAY
    retrievedAt: str = TODAY

    def __post_init__(self) -> None:
        self.url = clean_url(self.url)
        if self.affiliateUrl:
            self.affiliateUrl = self.affiliateUrl.strip()
        if not self.sku:
            self.sku = sha_sku(self.url or "", self.sourceId or self.name)
        if not self.priceDisplay:
            self.priceDisplay = price_display(self.price, self.currency)
        if not self.tier:
            self.tier = tier_for(self.price, self.cat)
        if not self.retailer:
            self.retailer = self.brand
        if not self.subcat:
            self.subcat = self.cat
        extras = [self.colour.lower(), self.cat, self.subcat]
        self.keys = keys_of(*self.keys, extra=extras) if not self.keys else keys_of(" ".join(self.keys), extra=extras)
        if not self.occasion:
            self.occasion = occasion_for(self.cat, self.subcat, self.name)
        if self.gap is None and (self.cat in GAP_CATS or self.subcat in GAP_CATS):
            self.gap = 1

    def identity_key(self) -> str:
        return self.url or ""

    def brand_name_key(self) -> tuple[str, str]:
        return (self.brand or "").strip().lower(), (self.name or "").strip().lower()

    def to_edit_row(self) -> dict[str, Any]:
        """Serialize for assets/edit-catalog.json (app-compatible + extras)."""
        row: dict[str, Any] = {
            "sku": self.sku,
            "brand": self.brand,
            "name": self.name,
            "price": int(self.price) if float(self.price).is_integer() else round(float(self.price), 2),
            "url": self.url,
            "img": self.img,
            "retailer": self.retailer,
            "cat": self.cat,
            "subcat": self.subcat,
            "colour": self.colour,
            "hex": self.hex,
            "keys": self.keys,
            "tier": self.tier,
            "st": self.st,
            "sq": self.sq,
            "currency": self.currency,
            "priceDisplay": self.priceDisplay,
            "inStock": self.inStock,
            "source": self.source,
            "sourceId": self.sourceId or None,
            "status": self.status,
            "locked": self.locked,
            "pipeline": self.pipeline,
            "verified": self.verified,
            "retrievedAt": self.retrievedAt,
            "occasion": self.occasion,
        }
        if self.imgUrl:
            row["imgUrl"] = self.imgUrl
        if self.wasPrice:
            row["wasPrice"] = self.wasPrice
        if self.affiliateUrl:
            row["affiliateUrl"] = self.affiliateUrl
        if self.sizes:
            row["sizes"] = [s.to_dict() if isinstance(s, Size) else s for s in self.sizes]
        if self.gap:
            row["gap"] = self.gap
        if self.pairs:
            row["pairs"] = self.pairs
        if self.currency == "USD":
            # keep currency/priceDisplay for pipeline rows; app hides USD display
            pass
        return {k: v for k, v in row.items() if v not in (None, "", [])}


def validate_row(row: dict[str, Any]) -> list[str]:
    """Return a list of problems; empty means the row can be ingested."""
    errs = []
    if not row.get("url"):
        errs.append("missing url")
    if not row.get("name"):
        errs.append("missing name")
    if price_of(row.get("price")) is None:
        errs.append("missing price")
    if not (row.get("img") or row.get("imgUrl") or row.get("image")):
        errs.append("missing image")
    if not row.get("brand"):
        errs.append("missing brand")
    if not row.get("cat"):
        errs.append("missing category")
    if row.get("status") not in (None, "active", "inactive"):
        errs.append("bad status")
    return errs
