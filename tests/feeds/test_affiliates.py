import json
import os
from pathlib import Path

from feeds.sources.aggregator import AggregatorAdapter
from feeds.sources.awin import AwinAdapter
from feeds.sources.cj import CJAdapter
from feeds.sources.impact import ImpactAdapter
from feeds.sources.partnerize import PartnerizeAdapter
from feeds.sources.rakuten import RakutenAdapter

FIX = Path(__file__).parent / "fixtures"


def _no_creds(monkeypatch, *keys):
    for k in keys:
        monkeypatch.delenv(k, raising=False)


def test_adapters_skip_without_credentials(monkeypatch):
    _no_creds(monkeypatch, "RAKUTEN_TOKEN", "CJ_API_KEY", "IMPACT_SID", "IMPACT_TOKEN", "AWIN_API_KEY", "PARTNERIZE_USER_KEY", "PARTNERIZE_API_KEY")
    cases = [
        (RakutenAdapter, {"enabled": True, "env": ["RAKUTEN_TOKEN"]}, "RAKUTEN_TOKEN"),
        (CJAdapter, {"enabled": True, "env": ["CJ_API_KEY"]}, "CJ_API_KEY"),
        (ImpactAdapter, {"enabled": True, "env": ["IMPACT_SID", "IMPACT_TOKEN"]}, "IMPACT_SID"),
        (AwinAdapter, {"enabled": True, "env": ["AWIN_API_KEY"]}, "AWIN_API_KEY"),
        (PartnerizeAdapter, {"enabled": True, "env": ["PARTNERIZE_USER_KEY", "PARTNERIZE_API_KEY"]}, "PARTNERIZE_USER_KEY"),
        (AggregatorAdapter, {"enabled": True, "network": "shopstyle", "env": ["SHOPSTYLE_API_KEY"]}, "SHOPSTYLE_API_KEY"),
        (AggregatorAdapter, {"enabled": True, "network": "skimlinks", "env": ["SKIMLINKS_API_KEY", "SKIMLINKS_PUBLISHER_ID"]}, "SKIMLINKS_API_KEY"),
    ]
    for cls, cfg, needle in cases:
        adapter = cls(config=cfg)
        result = adapter.run()
        assert result["skipped"] is True, cls
        assert result["items"] == []
        assert needle in result["reason"]
        assert "account" in result["reason"].lower() or "credentials" in result["reason"].lower()


def test_adapters_skip_when_disabled_even_with_creds(monkeypatch):
    monkeypatch.setenv("RAKUTEN_TOKEN", "dummy")
    adapter = RakutenAdapter(config={"enabled": False, "env": ["RAKUTEN_TOKEN"]})
    result = adapter.run()
    assert result["skipped"] is True
    assert "disabled" in result["reason"]


def test_rakuten_splits_canonical_and_tracking():
    rec = json.loads((FIX / "rakuten_item.json").read_text())
    item = RakutenAdapter(config={"enabled": False}).normalize_one(rec)
    assert item.url.startswith("https://www.baudoinlange.com/")
    assert "linksynergy.com" in item.affiliateUrl
    assert item.source.startswith("rakuten:")
    assert item.cat == "shoes"
    assert item.price == 390
    assert item.currency == "GBP"


def test_cj_swim_maps_and_splits_urls():
    rec = json.loads((FIX / "cj_item.json").read_text())
    item = CJAdapter(config={"enabled": False}).normalize_one(rec)
    assert item.cat == "swim"
    assert item.url.startswith("https://www.orlebarbrown.com/")
    assert "anrdoezrs.net" in item.affiliateUrl
    assert item.source.startswith("cj:")


def test_impact_belt_and_sizes():
    rec = json.loads((FIX / "impact_item.json").read_text())
    item = ImpactAdapter(config={"enabled": False}).normalize_one(rec)
    assert item.cat == "belt"
    assert item.url.startswith("https://www.andersons.it/")
    assert "sjv.io" in item.affiliateUrl
    assert [s.size for s in item.sizes] == ["90", "95", "100"]


def test_awin_jumper_splits_deep_links():
    rec = json.loads((FIX / "awin_item.json").read_text())
    item = AwinAdapter(config={"enabled": False}).normalize_one(rec)
    assert item.cat == "knitwear"
    assert item.url.startswith("https://www.johnsmedley.com/")
    assert "awin1.com" in item.affiliateUrl
    assert item.currency == "GBP"


def test_shopstyle_aggregator_fixture():
    rec = json.loads((FIX / "shopstyle_item.json").read_text())
    item = AggregatorAdapter(config={"network": "shopstyle", "enabled": False}).normalize_one(rec)
    assert item.cat == "sunglasses"
    assert item.url.startswith("https://www.garrettleight.com/")
    assert "shopstyle.com" in item.affiliateUrl
    assert item.brand == "Garrett Leight"
    assert item.source == "aggregator:shopstyle"


def test_partnerize_splits_canonical_and_tracking():
    rec = json.loads((FIX / "partnerize_item.json").read_text())
    item = PartnerizeAdapter(config={"enabled": False}).normalize_one(rec)
    assert item.cat == "trousers"
    assert item.url.startswith("https://www.mrporter.com/")
    assert "prf.hn" in item.affiliateUrl
    assert "camref" in item.affiliateUrl
    assert item.source.startswith("partnerize:")
    assert item.brand == "Brunello Cucinelli"
    assert item.price == 1290
    # tracking must not replace canonical
    assert "prf.hn" not in item.url

