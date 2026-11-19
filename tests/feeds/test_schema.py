from feeds.schema import (
    NormalizedProduct,
    categorize,
    colour_from_text,
    is_drop,
    is_women,
    tier_for,
    validate_row,
)


def test_tier_bands():
    assert tier_for(80, "shirt") == "affordable"
    assert tier_for(220, "shirt") == "accessible"
    assert tier_for(900, "shirt") == "luxury"
    assert tier_for(2000, "blazer") == "insensitive"


def test_colour_and_category():
    name, hx = colour_from_text("Navy Linen Trousers")
    assert name == "Navy"
    assert hx.startswith("#")
    assert categorize("Navy Linen Drawstring Trousers", "Mens Trousers") == ("trousers", "trousers")
    assert categorize("Olive Swim Shorts", "Swim") == ("swim", "swim")
    assert categorize("Tan Leather Weekender", "Bags")[0] == "bag"
    assert categorize("Beige Suede Penny Loafers", "Shoes") == ("shoes", "loafer")


def test_filters():
    assert is_women("Pleated Skirt", None, "WOMEN_TROUSERS_SS26")
    assert is_drop("Scented Candle")
    assert not is_drop("Olive Swim Trunks", "Swim")


def test_validate_and_serialize():
    p = NormalizedProduct(
        brand="Sunspel",
        name="Navy Linen Trousers",
        price=195,
        url="https://us.sunspel.com/products/navy-linen-trousers?utm=x",
        cat="trousers",
        source="shopify:sunspel",
        imgUrl="https://cdn.example.com/x.jpg",
        affiliateUrl="https://click.example/x",
    )
    row = p.to_edit_row()
    assert row["url"].endswith("/navy-linen-trousers")
    assert row["affiliateUrl"].startswith("https://click.example")
    assert row["pipeline"] is True
    assert row["tier"] == "accessible"
    assert validate_row(row) == []
    # tracking URL must not replace canonical
    assert "click.example" not in row["url"]
