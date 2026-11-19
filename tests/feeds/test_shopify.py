import json
from pathlib import Path

from feeds.sources.shopify import ShopifyAdapter

FIX = Path(__file__).parent / "fixtures"
STORE = {
    "id": "sunspel",
    "brand": "Sunspel",
    "retailer": "Sunspel US",
    "base": "https://us.sunspel.com",
    "currency": "USD",
    "enabled": True,
}


def test_in_stock_product_maps_schema():
    rec = json.loads((FIX / "shopify_product.json").read_text())
    item = ShopifyAdapter(store=STORE).normalize_one(rec)
    assert item is not None
    assert item.source == "shopify:sunspel"
    assert item.url == "https://us.sunspel.com/products/navy-linen-drawstring-trousers"
    assert item.affiliateUrl is None
    assert item.price == 195
    assert item.cat == "trousers"
    assert item.colour == "Navy"
    assert item.inStock is True
    assert [s.size for s in item.sizes] == ["30", "32", "34"]
    assert item.sizes[2].available is False
    assert item.wasPrice == 220
    row = item.to_edit_row()
    assert row["currency"] == "USD"


def test_sold_out_is_dropped():
    rec = json.loads((FIX / "shopify_sold_out.json").read_text())
    assert ShopifyAdapter(store=STORE).normalize_one(rec) is None


def test_disabled_store_skips_cleanly():
    adapter = ShopifyAdapter(store={**STORE, "enabled": False})
    result = adapter.run()
    assert result["skipped"] is True
    assert result["items"] == []
    assert "disabled" in result["reason"]
