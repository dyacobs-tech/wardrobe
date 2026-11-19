#!/usr/bin/env python3
"""Append-only ingest of normalized products into The Edit catalog.

    python3 scripts/feeds/ingest.py --products data/feeds/normalized.json --batch 250

Rules:
  * Every existing SKU and all of its fields are left untouched.
  * New items are deduped against existing rows by canonical URL, then
    by brand+name.
  * Sold-out or invalid rows are dropped from the *incoming* batch only.
  * Existing rows are never deleted. Nightly retirement is refresh.py
    (marks pipeline rows inactive).
  * Seed / pre-pipeline rows have no ``pipeline: true`` flag and are
    treated as locked.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from feeds.schema import NormalizedProduct, price_of, validate_row  # noqa: E402

# Closet fixture used to tag pairsWith on *new* rows only.
DEFAULT_CLOSET = Path("/workspace/wardrobe-audit/build-75/fixture_live83.json")


def load_catalog(path: Path) -> dict:
    if not path.exists():
        return {"v": 1, "source": "pipeline", "count": 0, "products": []}
    raw = json.loads(path.read_text())
    if isinstance(raw, list):
        return {"v": 1, "source": "pipeline", "count": len(raw), "products": raw}
    raw.setdefault("products", raw.get("items") or raw.get("skus") or [])
    return raw


def index_existing(rows: list[dict]) -> tuple[set[str], set[tuple[str, str]]]:
    urls, names = set(), set()
    for r in rows:
        u = (r.get("url") or r.get("link") or "").split("#")[0]
        if u:
            urls.add(u)
        b = (r.get("brand") or "").strip().lower()
        n = (r.get("name") or r.get("title") or "").strip().lower()
        if b and n:
            names.add((b, n))
    return urls, names


def incoming_to_rows(items: list) -> list[dict]:
    out = []
    for it in items:
        if isinstance(it, NormalizedProduct):
            row = it.to_edit_row()
        elif isinstance(it, dict):
            if "cat" in it and "url" in it and "price" in it:
                # already a normalized/edit row
                row = dict(it)
            else:
                continue
        else:
            continue
        errs = validate_row(row)
        if errs:
            continue
        if row.get("status") == "inactive" or row.get("inStock") is False:
            continue
        # pipeline rows default
        row.setdefault("pipeline", True)
        row.setdefault("locked", False)
        row.setdefault("status", "active")
        out.append(row)
    return out


def pair_new_rows(rows: list[dict], closet_path: Path) -> None:
    """Fill pairs on new rows only, using the existing colour-harmony helper."""
    if not closet_path.exists():
        return
    # Reuse the production ingest helper if present; otherwise skip quietly.
    helper = ROOT / "scripts" / "ingest_edit_catalog.py"
    if not helper.exists():
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("ingest_edit_catalog", helper)
    if not spec or not spec.loader:
        return
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return
    closet = [i for i in json.loads(closet_path.read_text()) if isinstance(i, dict) and i.get("id")]
    for e in rows:
        try:
            e["pairs"] = mod.pair_closet(e, closet)
        except Exception:
            pass


def merge(existing: list[dict], incoming: list[dict], limit: int | None = None) -> tuple[list[dict], dict]:
    urls, names = index_existing(existing)
    added, skipped_url, skipped_name, skipped_other = [], 0, 0, 0
    for row in incoming:
        if limit is not None and len(added) >= limit:
            break
        url = row.get("url") or ""
        key = ((row.get("brand") or "").strip().lower(), (row.get("name") or "").strip().lower())
        if url and url in urls:
            skipped_url += 1
            continue
        if key in names and key != ("", ""):
            skipped_name += 1
            continue
        # never mutate an existing dict; append a new one
        added.append(row)
        if url:
            urls.add(url)
        if key != ("", ""):
            names.add(key)
    # Preserve existing rows verbatim (same objects, same order), then append.
    merged = list(existing) + added
    stats = {
        "existing": len(existing),
        "incoming": len(incoming),
        "added": len(added),
        "skipped_url": skipped_url,
        "skipped_brand_name": skipped_name,
        "skipped_other": skipped_other,
        "total": len(merged),
    }
    return merged, stats


def write_catalog(path: Path, products: list[dict], source: str = "pipeline") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"v": 1, "source": source, "count": len(products), "products": products}
    path.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", type=Path, default=ROOT / "assets" / "edit-catalog.json")
    ap.add_argument("--products", type=Path, required=True, help="JSON list or {products:[...]} of normalized rows")
    ap.add_argument("--batch", type=int, default=None, help="Max new items to append this run")
    ap.add_argument("--out", type=Path, help="Write to this path (default: --catalog, in place)")
    ap.add_argument("--closet", type=Path, default=DEFAULT_CLOSET)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    cat = load_catalog(args.catalog)
    existing = list(cat.get("products") or [])
    raw = json.loads(Path(args.products).read_text())
    incoming_raw = raw if isinstance(raw, list) else (raw.get("products") or raw.get("items") or [])
    incoming = incoming_to_rows(incoming_raw)
    pair_new_rows(incoming, args.closet)
    merged, stats = merge(existing, incoming, limit=args.batch)
    print(json.dumps(stats, indent=2))
    print("by source (new):", dict(Counter((r.get("source") or "?") for r in merged[len(existing):])))
    print("by cat (new):", dict(Counter((r.get("cat") or "?") for r in merged[len(existing):])))
    print("by brand (new):", dict(Counter((r.get("brand") or "?") for r in merged[len(existing):])))
    if args.dry_run:
        return 0
    dest = args.out or args.catalog
    write_catalog(dest, merged, source=cat.get("source") or "pipeline")
    print(f"wrote {dest} ({stats['total']} products, {stats['existing']} preserved, {stats['added']} added)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
