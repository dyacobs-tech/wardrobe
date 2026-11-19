#!/usr/bin/env python3
"""Pull public Shopify products.json feeds into a local cache.

    python3 scripts/feeds/shopify_pull.py --config scripts/feeds/brands.yml
    python3 scripts/feeds/shopify_pull.py --probe          # verify products.json
    python3 scripts/feeds/shopify_pull.py --from-cache DIR # reuse dumps (no HTTP)

Read-only. Respects robots.txt, inter-page / inter-store delays, and 429
backoff. Does not write to the live catalog — run ingest.py afterwards.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
sys.path.insert(0, str(ROOT / "scripts"))

from feeds.sources.shopify import ShopifyAdapter, stores_from_config  # noqa: E402


def load_yaml(path: Path) -> dict:
    import yaml
    return yaml.safe_load(path.read_text()) or {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=ROOT / "scripts" / "feeds" / "brands.yml")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "feeds" / "shopify")
    ap.add_argument("--probe", action="store_true", help="Hit page=1 for every listed store and report.")
    ap.add_argument("--from-cache", type=Path, help="Directory of previously saved products.json dumps.")
    ap.add_argument("--store", action="append", help="Limit to one or more store ids.")
    ap.add_argument("--include-disabled", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_yaml(args.config)
    shop_cfg = cfg.get("shopify") or {}
    stores = stores_from_config(cfg)
    if args.store:
        want = set(args.store)
        stores = [s for s in stores if s.get("id") in want]
    if not args.probe and not args.include_disabled:
        stores = [s for s in stores if s.get("enabled")]

    args.out.mkdir(parents=True, exist_ok=True)
    report = []

    if args.from_cache:
        # Copy/normalize cached dumps so ingest can read a consistent tree.
        cache = args.from_cache
        for s in stores:
            sid = s["id"]
            dest = args.out / sid
            dest.mkdir(parents=True, exist_ok=True)
            adapter = ShopifyAdapter(shop_cfg, s)
            # Look for this store under the cache in a few layouts.
            candidates = [
                cache / sid,
                cache / "products" / sid,
                cache / "_probes" / f"{sid}-p1.json",
                cache / f"{sid}-p1.json",
            ]
            found = next((c for c in candidates if c.exists()), None)
            if not found:
                # also search by filename
                hits = list(cache.rglob(f"*{sid}*.json"))
                found = hits[0] if hits else None
            recs = adapter.load_cached(found) if found else []
            (dest / "all.json").write_text(json.dumps({"products": recs}))
            print(f"cache {sid}: {len(recs)} products from {found}")
            report.append({"id": sid, "ok": bool(recs), "n": len(recs), "source": str(found)})
        (args.out / "pull-report.json").write_text(json.dumps(report, indent=2))
        return 0

    store_delay = float(shop_cfg.get("store_delay_seconds") or 5.0)
    for i, s in enumerate(stores):
        sid = s["id"]
        dest = args.out / sid
        dest.mkdir(parents=True, exist_ok=True)
        adapter = ShopifyAdapter(shop_cfg, {**s, "enabled": True})
        pages = []
        total = 0
        last_code = 0
        limit = 1 if args.probe else int(shop_cfg.get("page_limit") or 8)
        for page in range(1, limit + 1):
            code, prods = adapter.fetch_page(page)
            last_code = code
            (dest / f"page-{page}.json").write_text(json.dumps({"products": prods}))
            pages.append({"page": page, "code": code, "n": len(prods)})
            total += len(prods)
            print(f"{sid} p{page}: {code} n={len(prods)}", flush=True)
            if args.probe or len(prods) < 250:
                break
            time.sleep(float(shop_cfg.get("delay_seconds") or 3.0))
        allp = []
        for p in dest.glob("page-*.json"):
            allp.extend(json.loads(p.read_text()).get("products") or [])
        # dedupe by id
        seen, uniq = set(), []
        for rec in allp:
            hid = rec.get("id") or rec.get("handle")
            if hid in seen:
                continue
            seen.add(hid)
            uniq.append(rec)
        (dest / "all.json").write_text(json.dumps({"products": uniq}))
        rec = {
            "id": sid,
            "brand": s.get("brand"),
            "base": s.get("base"),
            "ok": last_code == 200 and total > 0,
            "code": last_code,
            "n": len(uniq),
            "pages": pages,
        }
        report.append(rec)
        if i + 1 < len(stores):
            time.sleep(store_delay)

    (args.out / "pull-report.json").write_text(json.dumps(report, indent=2))
    live = [r for r in report if r.get("ok")]
    print(f"live {len(live)}/{len(report)} stores, {sum(r['n'] for r in live)} products")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
