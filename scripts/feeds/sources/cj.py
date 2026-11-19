"""CJ (Commission Junction) product adapter.

Skipped unless ``enabled: true`` and ``CJ_API_KEY`` is set. Never applies
to a programme or creates an account.

CJ Product Search (v2) fields used:
  name, advertiser-name / advertiser-id, sku, price, sale-price,
  buy-url (affiliate deep link), image-url, in-stock, brand,
  advertiser-category, description.

The canonical product URL is ``property-value`` / ``manufacturer-page`` /
``product-url`` when present. ``buy-url`` is stored only as affiliateUrl.
"""
from __future__ import annotations

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


def _g(rec: dict[str, Any], *names: str) -> Any:
    for n in names:
        if rec.get(n) not in (None, ""):
            return rec[n]
        # XML-style hyphenated aliases sometimes arrive as underscored JSON
        alt = n.replace("-", "_")
        if alt != n and rec.get(alt) not in (None, ""):
            return rec[alt]
    return None


class CJAdapter(SourceAdapter):
    name = "cj"
    env_vars = ("CJ_API_KEY",)

    def _fetch(self) -> list[dict[str, Any]]:
        return []  # no live call until explicitly enabled with a key

    def normalize_one(self, rec: dict[str, Any]) -> NormalizedProduct | None:
        name = _g(rec, "name", "product-name", "title")
        brand = _g(rec, "brand", "manufacturer-name", "advertiser-name") or ""
        price = price_of(_g(rec, "sale-price", "sale_price", "price"))
        canonical = _g(rec, "product-url", "manufacturer-page", "landing-page", "canonical-url") or ""
        affiliate = _g(rec, "buy-url", "buy_url", "click-url") or ""
        img = _g(rec, "image-url", "image_url", "image") or ""
        if not name or price is None or not (canonical or affiliate) or not img:
            return None
        # Prefer a non-tracking URL as canonical; if we only have buy-url,
        # keep it as the affiliate link and use it as url only when no other
        # landing page exists (documented exception).
        url = canonical or affiliate
        cat_hint = _g(rec, "advertiser-category", "category") or ""
        if is_women(str(name), None, str(cat_hint)) or is_drop(str(name), str(cat_hint)):
            return None
        cat, sub = categorize(str(name), str(cat_hint))
        if not cat:
            return None
        stock = _g(rec, "in-stock", "in_stock")
        if stock in (False, "false", "no", "N", "0", 0):
            return None
        colour, hx = colour_from_text(str(_g(rec, "color", "colour") or ""), str(name))
        advertiser = _g(rec, "advertiser-id", "advertiser_id") or "unknown"
        currency = _g(rec, "currency") or "USD"
        if isinstance(_g(rec, "price"), dict):
            currency = _g(rec, "price").get("currency") or currency  # type: ignore[union-attr]
        return NormalizedProduct(
            brand=str(brand),
            name=str(name).strip(),
            price=price,
            url=url if canonical else (canonical or url),
            affiliateUrl=affiliate or None,
            cat=cat,
            subcat=sub or cat,
            colour=colour,
            hex=hx,
            imgUrl=str(img),
            retailer=str(_g(rec, "advertiser-name") or brand),
            currency=str(currency).upper(),
            keys=keys_of(str(name), str(cat_hint), str(brand)),
            st="affiliate",
            sq="partner",
            source=f"cj:{advertiser}",
            sourceId=str(_g(rec, "sku", "id") or ""),
            inStock=True,
        )
