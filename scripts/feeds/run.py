#!/usr/bin/env python3
"""Orchestrate The Edit catalog pipeline.

    python3 scripts/feeds/run.py sources   # show adapters + skip reasons
    python3 scripts/feeds/run.py pull
    python3 scripts/feeds/run.py normalize --from-cache DIR
    python3 scripts/feeds/run.py ingest --products ... --batch 250
    python3 scripts/feeds/run.py refresh

Affiliate adapters are disabled by default and skip cleanly without
credentials. Shopify is the source that ships inventory today.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import yaml  # noqa: E402
from feeds.sources import get_adapter  # noqa: E402
from feeds.sources.shopify import ShopifyAdapter, stores_from_config  # noqa: E402


def load_cfg(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def cmd_sources(cfg: dict) -> int:
    shop_cfg = cfg.get("shopify") or {}
    print("Shopify stores:")
    for s in stores_from_config(cfg):
        flag = "on " if s.get("enabled") else "off"
        print(f"  [{flag}] shopify:{s['id']:16} {s.get('base')}  verified={s.get('verified')}")
    print("\nOther sources:")
    for block in cfg.get("affiliates") or []:
        adapter = get_adapter(block["adapter"], config=block)
        reason = adapter.skip_reason() or "ready"
        print(f"  {adapter.name:24} {reason}")
    return 0


def cmd_normalize(cfg: dict, cache: Path, out: Path) -> int:
    shop_cfg = cfg.get("shopify") or {}
    items = []
    per_store = {}
    for s in stores_from_config(cfg):
        if not s.get("enabled"):
            continue
        adapter = ShopifyAdapter(shop_cfg, s)
        candidates = [
            cache / "products" / s["id"],
            cache / "_probes" / f"{s['id']}-p1.json",
            cache / s["id"] / "all.json",
            cache / s["id"],
        ]
        hits = [c for c in candidates if c.exists()]
        # also any probe/dump named after the store, anywhere under cache
        hits.extend(c for c in cache.rglob(f"*{s['id']}*.json") if c not in hits)
        raw = []
        for found in hits:
            raw.extend(adapter.load_cached(found))
        # load_cached already dedupes within a path; dedupe across paths
        seen, uniq = set(), []
        for rec in raw:
            hid = rec.get("id") or rec.get("handle")
            if hid in seen:
                continue
            seen.add(hid)
            uniq.append(rec)
        raw = uniq
        found = hits[0] if hits else None
        norm = adapter.normalize(raw)
        # optional per-store cap from brands.yml
        cap = None if getattr(cmd_normalize, "_no_cap", False) else s.get("cap")
        if cap and len(norm) > int(cap):
            # keep a spread of categories, then price
            norm = _spread(norm, int(cap))
        per_store[s["id"]] = {"raw": len(raw), "normalized": len(norm), "from": str(found)}
        items.extend(norm)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"products": [i.to_edit_row() for i in items], "report": per_store, "count": len(items)}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps(per_store, indent=2))
    print(f"wrote {out} ({len(items)} normalized in-stock items)")
    return 0


def _spread(items, cap: int):
    from collections import defaultdict
    buckets = defaultdict(list)
    for it in items:
        buckets[it.cat].append(it)
    for v in buckets.values():
        v.sort(key=lambda x: x.price)
    out = []
    while len(out) < cap and any(buckets.values()):
        for cat in list(buckets):
            if buckets[cat]:
                out.append(buckets[cat].pop(0))
            if len(out) >= cap:
                break
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["sources", "pull", "normalize", "ingest", "refresh"])
    ap.add_argument("--config", type=Path, default=ROOT / "scripts" / "feeds" / "brands.yml")
    ap.add_argument("--from-cache", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "feeds" / "normalized.json")
    ap.add_argument("--products", type=Path)
    ap.add_argument("--catalog", type=Path, default=ROOT / "assets" / "edit-catalog.json")
    ap.add_argument("--batch", type=int, default=250)
    ap.add_argument("--dry-run", action="store_true")
    args, rest = ap.parse_known_args(argv)

    cfg = load_cfg(args.config)
    if args.command == "sources":
        return cmd_sources(cfg)
    if args.command == "pull":
        from feeds.shopify_pull import main as pull_main
        cmd = ["--config", str(args.config)]
        if args.from_cache:
            cmd += ["--from-cache", str(args.from_cache)]
        return pull_main(cmd)
    if args.command == "normalize":
        if not args.from_cache:
            print("--from-cache is required for normalize (or run pull first)", file=sys.stderr)
            return 2
        return cmd_normalize(cfg, args.from_cache, args.out)
    if args.command == "ingest":
        from feeds.ingest import main as ingest_main
        products = args.products or args.out
        cmd = ["--products", str(products), "--catalog", str(args.catalog), "--batch", str(args.batch)]
        if args.dry_run:
            cmd.append("--dry-run")
        return ingest_main(cmd)
    if args.command == "refresh":
        from feeds.refresh import main as refresh_main
        cmd = ["--catalog", str(args.catalog)]
        if args.dry_run:
            cmd.append("--dry-run")
        return refresh_main(cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
