"""Awin product-feed adapter.

Skipped unless ``enabled: true`` and ``AWIN_API_KEY`` (plus, when
needed, ``AWIN_PUBLISHER_ID``) are set. Never applies to a programme
or creates an account.

Awin datafeed / Product API v3 fields:
  product_name, brand_name, merchant_name, search_price, store_price,
  currency, merchant_deep_link (canonical), aw_deep_link (affiliate),
  aw_image_url, merchant_image_url, category_name, colour, size,
  in_stock, merchant_product_id, ean.
"""
from __future__ import annotations

from typing import Any

from ..schema import (
    NormalizedProduct,
    Size,
    categorize,
    colour_from_text,
    is_drop,
    is_women,
    keys_of,
    price_of,
)
from .base import SourceAdapter


class AwinAdapter(SourceAdapter):
    name = "awin"
    env_vars = ("AWIN_API_KEY",)

    def missing_env(self) -> list[str]:
        # Publisher id is recommended but the key alone is the hard gate.
        missing = super().missing_env()
        return missing

    def _fetch(self) -> list[dict[str, Any]]:
        return []

    def normalize_one(self, rec: dict[str, Any]) -> NormalizedProduct | None:
        name = rec.get("product_name") or rec.get("productName") or rec.get("name")
        brand = rec.get("brand_name") or rec.get("brandName") or rec.get("brand") or rec.get("merchant_name") or ""
        price = price_of(rec.get("search_price") or rec.get("store_price") or rec.get("price"))
        canonical = rec.get("merchant_deep_link") or rec.get("merchantDeepLink") or rec.get("merchant_product_url") or ""
        affiliate = rec.get("aw_deep_link") or rec.get("awDeepLink") or rec.get("awin_url") or ""
        img = rec.get("aw_image_url") or rec.get("merchant_image_url") or rec.get("awImageUrl") or rec.get("image") or ""
        if not name or price is None or not (canonical or affiliate) or not img:
            return None
        cat_hint = rec.get("category_name") or rec.get("categoryName") or rec.get("category") or ""
        if is_women(str(name), None, str(cat_hint)) or is_drop(str(name), str(cat_hint)):
            return None
        cat, sub = categorize(str(name), str(cat_hint))
        if not cat:
            return None
        stock = rec.get("in_stock") if "in_stock" in rec else rec.get("inStock")
        if stock in (False, "false", "0", 0, "N", "no"):
            return None
        colour, hx = colour_from_text(str(rec.get("colour") or rec.get("color") or ""), str(name))
        merchant = rec.get("merchant_id") or rec.get("advertiser_id") or rec.get("merchant_name") or "unknown"
        currency = rec.get("currency") or "USD"
        sizes = []
        if rec.get("size"):
            sizes.append(Size(size=str(rec["size"]), available=True))
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
            retailer=str(rec.get("merchant_name") or brand),
            currency=str(currency).upper(),
            keys=keys_of(str(name), str(cat_hint), str(brand)),
            st="affiliate",
            sq="partner",
            source=f"awin:{merchant}",
            sourceId=str(rec.get("merchant_product_id") or rec.get("ean") or rec.get("id") or ""),
            inStock=True,
            sizes=sizes,
        )
