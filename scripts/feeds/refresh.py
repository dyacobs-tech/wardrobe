#!/usr/bin/env python3
"""Nightly price/stock refresh for pipeline-managed rows.

    python3 scripts/feeds/refresh.py --catalog assets/edit-catalog.json

Rules:
  * Locked / seed rows (no pipeline flag, or locked=true) are never
    changed — not even their price.
  * Pipeline rows can have price, inStock, sizes, retrievedAt updated.
  * A 404 or sold-out product is marked ``status: inactive``. It is
    never deleted.
  * Rows that stay in stock are marked ``status: active``.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from feeds.schema import price_of  # noqa: E402


def is_locked(row: dict) -> bool:
    if row.get("locked") is True:
        return True
    # Seed catalog (the original 250) has sources like "shopify-json"
    # or "buckmason-markdown", not "shopify:<store>".
    if row.get("pipeline") is True:
        return False
    src = str(row.get("source") or "")
    if src.startswith(("shopify:", "rakuten:", "cj:", "impact:", "awin:", "partnerize:", "csvxml:", "aggregator:")):
        return False
    return True


def refresh_shopify_row(row: dict, timeout: int = 20) -> dict:
    """Re-fetch a Shopify product handle.json and return a *copy* with updates."""
    import ssl, urllib.request, urllib.error
    url = row["url"]
    # /products/<handle> → /products/<handle>.json
    if "/products/" not in url:
        return row
    handle = url.split("/products/", 1)[1].split("?")[0].strip("/")
    base = url.split("/products/", 1)[0]
    js_url = f"{base}/products/{handle}.json"
    req = urllib.request.Request(js_url, headers={"User-Agent": "DonnaCatalogBot/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            code = r.status
            data = r.read()
    except urllib.error.HTTPError as e:
        code = e.code
        data = b""
    except Exception:
        return row  # network blip: leave unchanged
    updated = dict(row)
    if code == 404:
        updated["status"] = "inactive"
        updated["inStock"] = False
        updated["retrievedAt"] = __import__("datetime").date.today().isoformat()
        return updated
    if code != 200:
        return row
    try:
        product = json.loads(data.decode("utf-8", "replace")).get("product") or {}
    except Exception:
        return row
    variants = product.get("variants") or []
    avail = [v for v in variants if v.get("available") and price_of(v.get("price")) is not None]
    updated["retrievedAt"] = __import__("datetime").date.today().isoformat()
    if not avail:
        updated["status"] = "inactive"
        updated["inStock"] = False
        return updated
    prices = [price_of(v["price"]) for v in avail]
    updated["price"] = min(p for p in prices if p is not None)
    updated["inStock"] = True
    updated["status"] = "active"
    return updated


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", type=Path, default=ROOT / "assets" / "edit-catalog.json")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    raw = json.loads(args.catalog.read_text())
    products = raw.get("products") if isinstance(raw, dict) else raw
    out_rows = []
    stats = {"locked_untouched": 0, "refreshed": 0, "inactivated": 0, "unchanged": 0}
    n = 0
    for row in products:
        if is_locked(row):
            out_rows.append(row)  # same object, untouched
            stats["locked_untouched"] += 1
            continue
        if args.limit is not None and n >= args.limit:
            out_rows.append(row)
            continue
        src = str(row.get("source") or "")
        if src.startswith("shopify:"):
            new = refresh_shopify_row(row)
            n += 1
            if new is row:
                stats["unchanged"] += 1
                out_rows.append(row)
            else:
                stats["refreshed"] += 1
                if new.get("status") == "inactive" and row.get("status") != "inactive":
                    stats["inactivated"] += 1
                out_rows.append(new)
            time.sleep(args.delay)
        else:
            # Affiliate/file sources: no live hook in this version.
            out_rows.append(row)
            stats["unchanged"] += 1
    print(json.dumps(stats, indent=2))
    if args.dry_run:
        return 0
    dest = args.out or args.catalog
    payload = {"v": 1, "source": raw.get("source") if isinstance(raw, dict) else "pipeline", "count": len(out_rows), "products": out_rows}
    dest.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
