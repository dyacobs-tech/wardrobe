"""Shopify public products.json connector.

Many DTC stores expose a read-only catalog at
``https://<store>/products.json?limit=250&page=N``. This adapter paginates
politely, respects robots.txt when asked, backs off on HTTP 429, and maps
each in-stock product into the normalized Edit schema.

``source`` is always ``shopify:<store-id>``.
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

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

DEFAULT_UA = "DonnaCatalogBot/1.0 (+https://dyacobs-tech.github.io/wardrobe/; catalog research)"
CTX = ssl.create_default_context()


class ShopifyAdapter(SourceAdapter):
    name = "shopify"
    env_vars = ()  # public, no credentials

    def __init__(self, config: dict[str, Any] | None = None, store: dict[str, Any] | None = None):
        super().__init__(config)
        self.store = store or {}
        self.delay = float((config or {}).get("delay_seconds") or 3.0)
        self.ua = (config or {}).get("user_agent") or DEFAULT_UA
        self.respect_robots = bool((config or {}).get("respect_robots", True))
        self.page_limit = int((config or {}).get("page_limit") or 8)
        self._robots_ok: bool | None = None

    def is_enabled(self) -> bool:
        if self.store:
            return bool(self.store.get("enabled", True))
        return bool(self.config.get("enabled", True))

    def skip_reason(self) -> str | None:
        if not self.store and not self.is_enabled():
            return "shopify: disabled"
        if self.store and not self.store.get("enabled", True):
            return f"shopify:{self.store.get('id')}: store disabled in brands.yml"
        return None

    def _base(self) -> str:
        return (self.store.get("base") or "").rstrip("/")

    def allowed_by_robots(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        if self._robots_ok is not None:
            return self._robots_ok
        robots = urljoin(self._base() + "/", "robots.txt")
        rp = RobotFileParser()
        try:
            req = urllib.request.Request(robots, headers={"User-Agent": self.ua, "Accept": "text/plain"})
            with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
            self._robots_ok = rp.can_fetch(self.ua, url)
        except Exception:
            # If robots.txt is missing or unreadable, proceed politely.
            self._robots_ok = True
        return self._robots_ok

    def _http_get(self, url: str, timeout: int = 30) -> tuple[int, bytes, dict[str, str]]:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.ua,
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                headers = {k.lower(): v for k, v in r.headers.items()}
                return r.status, r.read(), headers
        except urllib.error.HTTPError as e:
            headers = {k.lower(): v for k, v in (e.headers.items() if e.headers else [])}
            return e.code, (e.read() if e.fp else b""), headers

    def fetch_page(self, page: int, limit: int = 250) -> tuple[int, list[dict[str, Any]]]:
        url = f"{self._base()}/products.json?limit={limit}&page={page}"
        if not self.allowed_by_robots(url):
            return 0, []
        backoff = 8.0
        for attempt in range(5):
            code, data, headers = self._http_get(url)
            if code == 429:
                try:
                    wait = float(headers.get("retry-after") or backoff)
                except ValueError:
                    wait = backoff
                time.sleep(max(wait, 1))
                backoff = min(backoff * 2, 60)
                continue
            if code != 200:
                return code, []
            try:
                js = json.loads(data.decode("utf-8", "replace"))
            except Exception:
                return code, []
            return code, list(js.get("products") or [])
        return 429, []

    def _fetch(self) -> list[dict[str, Any]]:
        allp: list[dict[str, Any]] = []
        for page in range(1, self.page_limit + 1):
            code, prods = self.fetch_page(page)
            if code == 0 and not prods:
                break
            allp.extend(prods)
            if len(prods) < 250:
                break
            time.sleep(self.delay)
        return allp

    def load_cached(self, path) -> list[dict[str, Any]]:
        """Load a products.json dump (or a list of them) from disk."""
        import pathlib
        p = pathlib.Path(path)
        files = [p] if p.is_file() else sorted(p.glob("*.json")) + sorted(p.glob("page-*.json"))
        if p.is_dir():
            files = sorted(set(p.rglob("*.json")))
        seen = set()
        out = []
        for f in files:
            if f.name in ("meta.json", "download_report.json"):
                continue
            try:
                data = json.loads(f.read_text())
            except Exception:
                continue
            prods = []
            if isinstance(data, dict) and "products" in data:
                prods = data.get("products") or []
            elif isinstance(data, dict) and "product" in data:
                prods = [data["product"]]
            elif isinstance(data, list):
                prods = data
            for rec in prods:
                if not isinstance(rec, dict):
                    continue
                hid = rec.get("id") or rec.get("handle")
                if hid in seen:
                    continue
                seen.add(hid)
                out.append(rec)
        return out

    def normalize_one(self, rec: dict[str, Any]) -> NormalizedProduct | None:
        store = self.store or {}
        title = rec.get("title") or ""
        ptype = rec.get("product_type") or ""
        tags = rec.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        handle = rec.get("handle") or ""
        if not handle or not title:
            return None
        if is_women(title, tags, ptype):
            return None
        if is_drop(title, ptype):
            return None
        variants = rec.get("variants") or []
        avail = [v for v in variants if v.get("available") and price_of(v.get("price")) is not None]
        if not avail:
            return None  # sold out — do not ingest
        prices = [price_of(v["price"]) for v in avail]
        price = min(p for p in prices if p is not None)
        if price is None or price <= 0:
            return None
        compares = [price_of(v.get("compare_at_price")) for v in avail]
        was = min((c for c in compares if c and c > price), default=None)

        colour = ""
        for opt in rec.get("options") or []:
            if (opt.get("name") or "").lower() in ("color", "colour", "col"):
                vals = opt.get("values") or []
                if vals:
                    colour = vals[0]
                    break
        cname, chex = colour_from_text(colour, title)
        cat, subcat = categorize(title, ptype)
        if not cat:
            return None

        imgs = rec.get("images") or []
        img = ""
        skip_img = ("sizechart", "size-chart", "size_chart", "sizecchart",
                    "measurements", "garment-measurement", "lookbook-copy")
        if imgs:
            usable = []
            for im in imgs:
                src = im.get("src") or ""
                alt = (im.get("alt") or "").lower()
                low = src.lower()
                if any(k in low or k in alt for k in skip_img):
                    continue
                usable.append(src)
            if usable:
                img = usable[0]
                for src in usable:
                    low = src.lower()
                    if any(k in low for k in ("_1.", "flat", "front", "product", "-1.", "cutout", "ghost")):
                        img = src
                        break
        if not img:
            return None

        base = self._base() or store.get("base") or ""
        # Some already-normalized cache rows may include a product URL.
        url = rec.get("url") or (f"{base}/products/{handle}" if base else "")
        if not url:
            return None

        sizes = []
        for v in variants:
            label = v.get("title") or v.get("option1") or ""
            if not label or label == "Default Title":
                # still record in-stock default
                label = v.get("option1") or "OS"
            sizes.append(
                Size(
                    size=str(label),
                    available=bool(v.get("available")),
                    sku=str(v.get("sku") or v.get("id") or "") or None,
                    price=price_of(v.get("price")),
                )
            )

        currency = store.get("currency") or rec.get("currency") or "USD"
        brand = store.get("brand") or rec.get("vendor") or ""
        retailer = store.get("retailer") or brand
        sid = store.get("id") or urlparse(base).netloc.replace("www.", "").split(".")[0]
        source_id = str(rec.get("id") or handle)

        return NormalizedProduct(
            brand=brand,
            name=title.strip(),
            price=price,
            url=url,
            cat=cat,
            subcat=subcat or cat,
            colour=cname,
            hex=chex,
            imgUrl=img,
            retailer=retailer,
            currency=currency,
            keys=keys_of(title, ptype, " ".join(tags[:12])),
            st="brand_direct",
            sq="elite",
            sku="",
            source=f"shopify:{sid}",
            sourceId=source_id,
            inStock=True,
            sizes=sizes,
            wasPrice=was,
            pipeline=True,
            locked=False,
        )


def stores_from_config(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    block = cfg.get("shopify") if "shopify" in cfg else cfg
    return list((block or {}).get("stores") or [])
