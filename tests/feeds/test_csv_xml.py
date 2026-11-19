from pathlib import Path

from feeds.sources.csv_xml import CsvXmlAdapter

FIX = Path(__file__).parent / "fixtures"


def test_csv_feed():
    adapter = CsvXmlAdapter(config={"enabled": True, "feed": str(FIX / "generic_feed.csv"), "id": "demo"})
    result = adapter.run()
    assert result["skipped"] is False
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item.brand == "Faherty"
    assert item.cat == "shirt"
    assert item.subcat == "overshirt"
    assert item.url.startswith("https://fahertybrand.com/")
    assert item.affiliateUrl.startswith("https://go.example.com/")


def test_xml_feed():
    adapter = CsvXmlAdapter(config={"enabled": True, "feed": str(FIX / "generic_feed.xml"), "id": "demo"})
    result = adapter.run()
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item.brand == "Alex Mill"
    assert item.cat == "shirt"
    assert item.url.startswith("https://alexmill.com/")
    assert "go.example.com" in item.affiliateUrl


def test_csv_skips_without_feed():
    adapter = CsvXmlAdapter(config={"enabled": True})
    result = adapter.run()
    assert result["skipped"] is True
    assert result["items"] == []
