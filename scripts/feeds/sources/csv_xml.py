"""Generic CSV / XML product-feed adapter.

No credentials. Enable in brands.yml and point ``feed`` at a local path
or https URL. Column names are mapped through a set of aliases so a
Rakuten/CJ/Awin/Google-style file can be dropped in later without a
new parser.

Affiliate / tracking columns (click_url, aw_deep_link, buy_url, …) are
copied to ``affiliateUrl`` only. ``url`` / ``link`` / ``merchant_deep_link``
remain the canonical product page.
"""
from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..schema import (
    NormalizedProduct,
    categorize,
    colour_from_text,
    is_drop,
    is_women,
    keys_of,
    price_of,
)
from .base import SourceAdapter

CANONICAL_ALIASES = (
    "url", "link", "product_url", "producturl", "canonical_url", "landing_page",
    "merchant_deep_link", "page_url", "product_link",
)
AFFILIATE_ALIASES = (
    "affiliate_url", "affiliateurl", "click_url", "clickurl", "buy_url",
    "aw_deep_link", "tracking_url", "trackingurl", "linkurl",
)
IMAGE_ALIASES = ("image", "image_url", "imageurl", "img", "aw_image_url", "imgurl")
NAME_ALIASES = ("name", "title", "product_name", "productname")
BRAND_ALIASES = ("brand", "brand_name", "manufacturer", "vendor")
PRICE_ALIASES = ("price", "sale_price", "search_price", "current_price", "saleprice")
CAT_ALIASES = ("category", "cat", "product_type", "category_name", "advertiser_category")
COLOUR_ALIASES = ("colour", "color", "colour_name", "color_name")
CURRENCY_ALIASES = ("currency", "currency_code")
STOCK_ALIASES = ("in_stock", "instock", "availability", "stock")
SKU_ALIASES = ("sku", "id", "product_id", "merchant_product_id", "ean")


def _lower(rec: dict[str, Any]) -> dict[str, Any]:
    return {str(k).strip().lower(): v for k, v in rec.items()}


def _pick(rec: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    low = _lower(rec)
    for a in aliases:
        if low.get(a) not in (None, ""):
            return low[a]
    return None


def parse_csv(text: str) -> list[dict[str, Any]]:
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t|;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    return [dict(row) for row in reader]


def _elem_text(el: ET.Element) -> str | None:
    if el.text and el.text.strip():
        return el.text.strip()
    return None


def parse_xml(text: str) -> list[dict[str, Any]]:
    """Very small product XML reader (Google RSS, generic <product> lists)."""
    root = ET.fromstring(text)
    # unwrap rss/channel or products
    items = []
    for tag in ("item", "product", "entry", "Product"):
        found = root.findall(f".//{tag}")
        if found:
            items = found
            break
    if not items and list(root):
        # maybe the root is a list of children already
        if all(ch.tag in ("item", "product", "entry") or ch.tag.endswith("}item") for ch in list(root)[:3]):
            items = list(root)
    rows = []
    for el in items:
        rec: dict[str, Any] = {}
        for ch in el:
            tag = ch.tag.split("}")[-1]
            rec[tag] = _elem_text(ch) or (ch.get("src") or ch.get("url") or rec.get(tag))
            # common RSS enclosure / g:image_link
            if tag in ("image_link", "additional_image_link") and _elem_text(ch):
                rec.setdefault("image", _elem_text(ch))
        if rec:
            rows.append(rec)
    return rows


class CsvXmlAdapter(SourceAdapter):
    name = "csv_xml"
    env_vars = ()

    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled")) and bool(self.config.get("feed"))

    def skip_reason(self) -> str | None:
        if not self.config.get("enabled"):
            return "csv_xml: disabled (default)."
        if not self.config.get("feed"):
            return "csv_xml: skipped, no feed path/URL configured."
        return None

    def _fetch(self) -> list[dict[str, Any]]:
        feed = self.config["feed"]
        path = Path(feed)
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
        else:
            # Remote feeds are only fetched when explicitly enabled.
            import urllib.request
            req = urllib.request.Request(feed, headers={"User-Agent": "DonnaCatalogBot/1.0", "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=30) as r:
                text = r.read().decode("utf-8", "replace")
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            data = json.loads(text)
            return data if isinstance(data, list) else (data.get("products") or data.get("items") or [data])
        if stripped.startswith("<"):
            return parse_xml(text)
        return parse_csv(text)

    def normalize_one(self, rec: dict[str, Any]) -> NormalizedProduct | None:
        name = _pick(rec, NAME_ALIASES)
        brand = _pick(rec, BRAND_ALIASES) or ""
        price = price_of(_pick(rec, PRICE_ALIASES))
        canonical = _pick(rec, CANONICAL_ALIASES) or ""
        affiliate = _pick(rec, AFFILIATE_ALIASES) or ""
        img = _pick(rec, IMAGE_ALIASES) or ""
        if not name or price is None or not (canonical or affiliate) or not img:
            return None
        cat_hint = str(_pick(rec, CAT_ALIASES) or "")
        if is_women(str(name), None, cat_hint) or is_drop(str(name), cat_hint):
            return None
        cat, sub = categorize(str(name), cat_hint)
        if not cat:
            return None
        stock = _pick(rec, STOCK_ALIASES)
        if stock is not None and str(stock).strip().lower() in ("false", "0", "no", "n", "out of stock", "outofstock"):
            return None
        colour, hx = colour_from_text(str(_pick(rec, COLOUR_ALIASES) or ""), str(name))
        currency = _pick(rec, CURRENCY_ALIASES) or "USD"
        label = self.config.get("id") or "file"
        return NormalizedProduct(
            brand=str(brand),
            name=str(name).strip(),
            price=price,
            url=canonical or affiliate,
            affiliateUrl=affiliate or None,
            cat=cat,
            subcat=sub or cat,
            colour=colour,
            hex=hx,
            imgUrl=str(img),
            retailer=str(brand),
            currency=str(currency).upper(),
            keys=keys_of(str(name), cat_hint, str(brand)),
            st="feed",
            sq="partner",
            source=f"csvxml:{label}",
            sourceId=str(_pick(rec, SKU_ALIASES) or ""),
            inStock=True,
        )
