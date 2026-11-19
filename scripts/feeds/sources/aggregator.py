"""ShopStyle / Skimlinks-style aggregator stubs.

Both networks aggregate (or wrap) merchant product URLs. This adapter
normalizes their usual field names and wraps nothing until it is
enabled with credentials.

ShopStyle (env ``SHOPSTYLE_API_KEY``):
  name / brandedName, price, currency, inStock, pageUrl (canonical),
  clickUrl (affiliate), image, brand, categories, colors.

Skimlinks (env ``SKIMLINKS_API_KEY``, ``SKIMLINKS_PUBLISHER_ID``):
  typically a URL-wrapping API rather than a full product catalog.
  Expected fixture / future payload: title, price, canonical_url,
  image, brand, category, plus an optional already-wrapped ``affiliate_url``.
  A live run would call the Skimlinks link-wrapping API and store the
  result in affiliateUrl only.

No accounts are created and no URLs are submitted while disabled.
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


class AggregatorAdapter(SourceAdapter):
    name = "aggregator"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.network = (config or {}).get("network") or "shopstyle"
        if self.network == "skimlinks":
            self.env_vars = ("SKIMLINKS_API_KEY", "SKIMLINKS_PUBLISHER_ID")
        else:
            self.env_vars = ("SHOPSTYLE_API_KEY",)
        self.name = f"aggregator:{self.network}"

    def _fetch(self) -> list[dict[str, Any]]:
        return []

    def normalize_one(self, rec: dict[str, Any]) -> NormalizedProduct | None:
        name = rec.get("name") or rec.get("brandedName") or rec.get("title") or rec.get("product_name")
        brand = rec.get("brand") or rec.get("merchant") or rec.get("retailer") or ""
        if isinstance(brand, dict):
            brand = brand.get("name") or brand.get("label") or ""
        price = price_of(rec.get("price") or rec.get("salePrice") or rec.get("amount"))
        if isinstance(rec.get("price"), dict):
            price = price_of(rec["price"].get("amount") or rec["price"].get("value") or rec["price"].get("raw"))
        canonical = rec.get("pageUrl") or rec.get("page_url") or rec.get("canonical_url") or rec.get("url") or ""
        affiliate = rec.get("clickUrl") or rec.get("click_url") or rec.get("affiliate_url") or rec.get("wrapped_url") or ""
        img = rec.get("image") or rec.get("image_url") or rec.get("imageUrl") or ""
        if isinstance(img, dict):
            img = img.get("url") or img.get("sizes", {}).get("Large", {}).get("url") or img.get("src") or ""
        if not name or price is None or not (canonical or affiliate) or not img:
            return None
        cats = rec.get("categories") or rec.get("category") or ""
        if isinstance(cats, list):
            cat_hint = " ".join(c.get("name") if isinstance(c, dict) else str(c) for c in cats)
        else:
            cat_hint = str(cats)
        if is_women(str(name), None, cat_hint) or is_drop(str(name), cat_hint):
            return None
        cat, sub = categorize(str(name), cat_hint)
        if not cat:
            return None
        if rec.get("inStock") in (False, "false", 0, "0") or rec.get("in_stock") in (False, "false", 0, "0"):
            return None
        colour_val = rec.get("colors") or rec.get("color") or rec.get("colour") or ""
        if isinstance(colour_val, list):
            colour_val = " ".join(c.get("name") if isinstance(c, dict) else str(c) for c in colour_val)
        colour, hx = colour_from_text(str(colour_val), str(name))
        currency = rec.get("currency") or "USD"
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
            st="aggregator",
            sq="partner",
            source=f"aggregator:{self.network}",
            sourceId=str(rec.get("id") or rec.get("sku") or ""),
            inStock=True,
        )
