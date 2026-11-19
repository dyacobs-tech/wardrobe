import json
from copy import deepcopy
from pathlib import Path

from feeds.ingest import incoming_to_rows, merge
from feeds.refresh import is_locked

FIX = Path(__file__).parent / "fixtures"


def _load():
    return json.loads((FIX / "existing_catalog.json").read_text())


def test_append_only_preserves_existing_bytes():
    cat = _load()
    existing = cat["products"]
    snapshot = deepcopy(existing)
    incoming = incoming_to_rows([
        {
            "brand": "Drake's",
            "name": "Grey Merino Wool Knitted Polo",
            "price": 295,
            "url": "https://www.drakes.com/products/grey-merino-wool-knitted-polo",
            "img": "assets/editimg/new1.webp",
            "cat": "knitwear",
            "source": "shopify:drakes",
            "pipeline": True,
        }
    ])
    merged, stats = merge(existing, incoming, limit=250)
    assert stats["existing"] == 2
    assert stats["added"] == 1
    assert stats["total"] == 3
    # existing rows are the same objects with identical contents
    assert merged[0] is existing[0]
    assert merged[1] is existing[1]
    assert merged[0] == snapshot[0]
    assert merged[1] == snapshot[1]
    assert merged[2]["brand"] == "Drake's"


def test_dedupe_by_url_and_brand_name():
    existing = _load()["products"]
    incoming = incoming_to_rows([
        # same URL as seed 1
        {**existing[0], "price": 1, "img": existing[0]["img"], "pipeline": True},
        # same brand+name, different URL
        {
            "brand": "Buck Mason",
            "name": "Natural Holdfast Web Belt",
            "price": 68,
            "url": "https://www.buckmason.com/products/a-different-slug",
            "img": "assets/editimg/x.webp",
            "cat": "belt",
            "source": "shopify:other",
        },
        # genuinely new
        {
            "brand": "Stoffa",
            "name": "Taupe Suede Loafer",
            "price": 890,
            "url": "https://stoffa.co/products/taupe-suede-loafer",
            "img": "assets/editimg/y.webp",
            "cat": "shoes",
            "source": "shopify:stoffa",
        },
    ])
    merged, stats = merge(existing, incoming)
    assert stats["added"] == 1
    assert stats["skipped_url"] == 1
    assert stats["skipped_brand_name"] == 1
    assert merged[-1]["brand"] == "Stoffa"
    # seed prices untouched
    assert merged[0]["price"] == 145


def test_batch_cap_and_sold_out_incoming_dropped():
    existing = _load()["products"]
    rows = [
        {
            "brand": "X",
            "name": f"Item {i}",
            "price": 100 + i,
            "url": f"https://example.com/products/item-{i}",
            "img": "assets/editimg/z.webp",
            "cat": "shirt",
            "source": "shopify:x",
        }
        for i in range(5)
    ]
    rows.append({
        "brand": "X", "name": "Gone", "price": 10,
        "url": "https://example.com/products/gone",
        "img": "assets/editimg/z.webp", "cat": "shirt",
        "inStock": False, "source": "shopify:x",
    })
    incoming = incoming_to_rows(rows)
    merged, stats = merge(existing, incoming, limit=3)
    assert stats["added"] == 3
    assert all(r.get("inStock") is not False for r in merged)


def test_seed_rows_are_locked_for_refresh():
    existing = _load()["products"]
    assert is_locked(existing[0]) is True
    assert is_locked(existing[1]) is True
    pipeline_row = {"source": "shopify:sunspel", "pipeline": True, "locked": False, "url": "https://x"}
    assert is_locked(pipeline_row) is False
    locked_pipeline = {"source": "shopify:sunspel", "pipeline": True, "locked": True}
    assert is_locked(locked_pipeline) is True
