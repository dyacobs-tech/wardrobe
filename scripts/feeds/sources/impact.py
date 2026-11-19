"""Impact product catalog adapter.

Skipped unless ``enabled: true`` and both ``IMPACT_SID`` and
``IMPACT_TOKEN`` are set (Account SID + auth token). Never applies to a
campaign or creates an account.

Catalog item fields used (Impact Catalogs API):
  Name, Brand, CurrentPrice, OriginalPrice, Currency,
  Url or TrackingUrl (affiliate), LandingPageUrl / CanonicalUrl,
  ImageUrl, Category, StockAvailability, Id, CampaignId, Colors, Sizes.
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


def _g(rec: dict[str, Any], *names: str) -> Any:
    lower = {k.lower(): v for k, v in rec.items()}
    for n in names:
        if rec.get(n) not in (None, ""):
            return rec[n]
        if lower.get(n.lower()) not in (None, ""):
            return lower[n.lower()]
    return None


class ImpactAdapter(SourceAdapter):
    name = "impact"
    env_vars = ("IMPACT_SID", "IMPACT_TOKEN")

    def _fetch(self) -> list[dict[str, Any]]:
        return []

    def normalize_one(self, rec: dict[str, Any]) -> NormalizedProduct | None:
        name = _g(rec, "Name", "name", "title")
        brand = _g(rec, "Brand", "Manufacturer", "CampaignName") or ""
        price = price_of(_g(rec, "CurrentPrice", "Price", "current_price"))
        canonical = _g(rec, "LandingPageUrl", "CanonicalUrl", "ItemUrl", "ProductUrl") or ""
        affiliate = _g(rec, "TrackingUrl", "TrackingLink", "Url") or ""
        # If Url is clearly a landing page (no impact.com tracking host), prefer it as canonical.
        url_field = _g(rec, "Url") or ""
        if url_field and "impact" not in str(url_field).lower() and "pxf" not in str(url_field).lower():
            if not canonical:
                canonical = url_field
            if affiliate == url_field:
                affiliate = _g(rec, "TrackingUrl", "TrackingLink") or ""
        img = _g(rec, "ImageUrl", "ImageURL", "image") or ""
        if not name or price is None or not (canonical or affiliate) or not img:
            return None
        cat_hint = _g(rec, "Category", "category") or ""
        if is_women(str(name), None, str(cat_hint)) or is_drop(str(name), str(cat_hint)):
            return None
        cat, sub = categorize(str(name), str(cat_hint))
        if not cat:
            return None
        stock = str(_g(rec, "StockAvailability", "InStock") or "InStock").lower()
        if stock in ("outofstock", "out of stock", "false", "0", "unavailable"):
            return None
        colour, hx = colour_from_text(str(_g(rec, "Colors", "Color", "Colour") or ""), str(name))
        campaign = _g(rec, "CampaignId", "CatalogId") or "unknown"
        currency = _g(rec, "Currency") or "USD"
        sizes = []
        raw_sizes = _g(rec, "Sizes", "Size") or []
        if isinstance(raw_sizes, str):
            raw_sizes = [s.strip() for s in raw_sizes.split(",") if s.strip()]
        for s in raw_sizes:
            sizes.append(Size(size=str(s), available=True))
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
            retailer=str(_g(rec, "CampaignName") or brand),
            currency=str(currency).upper(),
            keys=keys_of(str(name), str(cat_hint), str(brand)),
            st="affiliate",
            sq="partner",
            source=f"impact:{campaign}",
            sourceId=str(_g(rec, "Id", "id") or ""),
            inStock=True,
            sizes=sizes,
            wasPrice=price_of(_g(rec, "OriginalPrice")),
        )
