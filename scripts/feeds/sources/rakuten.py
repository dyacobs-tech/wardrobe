"""Rakuten Advertising product adapter.

Live fetch is disabled unless ``enabled: true`` in brands.yml *and*
``RAKUTEN_TOKEN`` is set. This module never applies to a programme or
creates an account. Field mapping is written against the public Product
Search API shape so fixtures and a future live hook share one path.

Canonical product URL: ``product_url`` / ``landing_page_url``.
Affiliate deep link:    ``buy_url`` / ``click_url`` / ``linkurl``.
"""
from __future__ import annotations

import os
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

# Documented, not called unless credentials + enabled are both present.
RAKUTEN_PRODUCT_SEARCH = "https://api.rakutenadvertising.com/productsearch/1.0"


class RakutenAdapter(SourceAdapter):
    name = "rakuten"
    env_vars = ("RAKUTEN_TOKEN",)

    def _fetch(self) -> list[dict[str, Any]]:
        # Intentionally unused until a human enables the source and
        # provides a token. The hook is here so the mapping is one path.
        _ = os.environ.get("RAKUTEN_TOKEN")
        # No live call is made in this version (Shopify is the ship path).
        return []

    def normalize_one(self, rec: dict[str, Any]) -> NormalizedProduct | None:
        name = rec.get("product_name") or rec.get("productname") or rec.get("name") or rec.get("title")
        brand = rec.get("brand") or rec.get("manufacturer") or rec.get("merchant_name") or rec.get("advertiser_name") or ""
        price = price_of(rec.get("sale_price") or rec.get("saleprice") or rec.get("price") or rec.get("retail_price"))
        canonical = rec.get("product_url") or rec.get("landing_page_url") or rec.get("producturl") or rec.get("merchant_url") or ""
        affiliate = rec.get("buy_url") or rec.get("click_url") or rec.get("linkurl") or rec.get("link_url") or ""
        # If the feed only has a tracking URL, keep it in affiliateUrl and
        # still require a canonical URL for dedupe/verification.
        if not canonical and rec.get("url") and "click" not in str(rec.get("url")):
            canonical = rec.get("url")
        img = rec.get("image_url") or rec.get("imageurl") or rec.get("image") or rec.get("imgUrl") or ""
        if not name or price is None or not canonical or not img:
            return None
        cat_hint = rec.get("category") or rec.get("advertiser_category") or rec.get("merchant_category") or ""
        if is_women(name, None, cat_hint) or is_drop(name, cat_hint):
            return None
        cat, sub = categorize(name, cat_hint)
        if not cat:
            return None
        colour, hx = colour_from_text(rec.get("color") or rec.get("colour") or "", name)
        in_stock = rec.get("in_stock")
        if in_stock in (False, "false", "False", "N", "n", "0", 0, "out of stock"):
            return None
        advertiser = rec.get("advertiser_id") or rec.get("mid") or rec.get("merchant_id") or "unknown"
        currency = rec.get("currency") or rec.get("currency_code") or "USD"
        return NormalizedProduct(
            brand=brand or rec.get("advertiser_name") or "Unknown",
            name=str(name).strip(),
            price=price,
            url=canonical,
            affiliateUrl=affiliate or None,
            cat=cat,
            subcat=sub or cat,
            colour=colour,
            hex=hx,
            imgUrl=str(img),
            retailer=rec.get("merchant_name") or rec.get("advertiser_name") or brand,
            currency=str(currency).upper(),
            keys=keys_of(name, cat_hint, brand),
            st="affiliate",
            sq="partner",
            source=f"rakuten:{advertiser}",
            sourceId=str(rec.get("sku") or rec.get("product_id") or rec.get("id") or ""),
            inStock=True,
            wasPrice=price_of(rec.get("retail_price") or rec.get("original_price")),
        )
