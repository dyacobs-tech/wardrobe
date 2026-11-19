"""Partnerize (formerly Performance Horizon) product adapter.

Mr Porter, SSENSE and Farfetch — together a large share of The Edit's
luxury retail links — run their US publisher programmes on Partnerize,
not Rakuten/CJ/Impact/Awin.

Skipped unless ``enabled: true`` and both ``PARTNERIZE_USER_KEY`` and
``PARTNERIZE_API_KEY`` are set. Never applies to a campaign or creates
an account.

Typical catalog / feed fields used:
  name / title, brand, price, currency,
  destination_url / product_url / dest_url (canonical PDP),
  tracking_url / click_url / deep_link (Partnerize camref / prf.hn),
  image_url / image, category, in_stock, sku, campaign_id / advertiser_id.
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

PARTNERIZE_HOSTS = ("prf.hn", "partnerize.com", "performancehorizon.com", "pxf.io")


def _g(rec: dict[str, Any], *names: str) -> Any:
    lower = {str(k).lower(): v for k, v in rec.items()}
    for n in names:
        if rec.get(n) not in (None, ""):
            return rec[n]
        if lower.get(n.lower()) not in (None, ""):
            return lower[n.lower()]
    return None


def _is_tracking(url: str) -> bool:
    u = (url or "").lower()
    return any(h in u for h in PARTNERIZE_HOSTS) or "camref" in u


class PartnerizeAdapter(SourceAdapter):
    name = "partnerize"
    env_vars = ("PARTNERIZE_USER_KEY", "PARTNERIZE_API_KEY")

    def _fetch(self) -> list[dict[str, Any]]:
        return []  # no live call until explicitly enabled with keys

    def normalize_one(self, rec: dict[str, Any]) -> NormalizedProduct | None:
        name = _g(rec, "name", "title", "product_name", "productName")
        brand = _g(rec, "brand", "manufacturer", "advertiser_name", "merchant") or ""
        price = price_of(_g(rec, "price", "sale_price", "current_price", "search_price"))
        canonical = _g(rec, "destination_url", "dest_url", "product_url", "landing_page_url", "canonical_url") or ""
        affiliate = _g(rec, "tracking_url", "click_url", "deep_link", "camref_url", "prf_url") or ""
        url_field = _g(rec, "url") or ""
        if url_field:
            if _is_tracking(str(url_field)):
                affiliate = affiliate or url_field
            elif not canonical:
                canonical = url_field
        img = _g(rec, "image_url", "image", "imageUrl", "img") or ""
        if not name or price is None or not (canonical or affiliate) or not img:
            return None
        cat_hint = str(_g(rec, "category", "product_type", "advertiser_category") or "")
        if is_women(str(name), None, cat_hint) or is_drop(str(name), cat_hint):
            return None
        cat, sub = categorize(str(name), cat_hint)
        if not cat:
            return None
        stock = _g(rec, "in_stock", "inStock", "availability")
        if stock in (False, "false", "0", 0, "N", "no", "out of stock", "outofstock"):
            return None
        colour, hx = colour_from_text(str(_g(rec, "colour", "color") or ""), str(name))
        campaign = _g(rec, "campaign_id", "advertiser_id", "campaign", "publisher_id") or "unknown"
        currency = _g(rec, "currency") or "USD"
        retailer = _g(rec, "advertiser_name", "merchant", "retailer") or brand
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
            retailer=str(retailer),
            currency=str(currency).upper(),
            keys=keys_of(str(name), cat_hint, str(brand)),
            st="affiliate",
            sq="partner",
            source=f"partnerize:{campaign}",
            sourceId=str(_g(rec, "sku", "id", "product_id") or ""),
            inStock=True,
            wasPrice=price_of(_g(rec, "was_price", "original_price", "retail_price")),
        )
