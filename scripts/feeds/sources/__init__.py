"""Source adapters for The Edit catalog pipeline."""
from .base import SourceAdapter, skip_result
from .shopify import ShopifyAdapter
from .rakuten import RakutenAdapter
from .cj import CJAdapter
from .impact import ImpactAdapter
from .awin import AwinAdapter
from .csv_xml import CsvXmlAdapter
from .aggregator import AggregatorAdapter
from .partnerize import PartnerizeAdapter

ADAPTERS = {
    "shopify": ShopifyAdapter,
    "rakuten": RakutenAdapter,
    "cj": CJAdapter,
    "impact": ImpactAdapter,
    "awin": AwinAdapter,
    "csv_xml": CsvXmlAdapter,
    "aggregator": AggregatorAdapter,
    "partnerize": PartnerizeAdapter,
}


def get_adapter(name: str, **kwargs) -> SourceAdapter:
    cls = ADAPTERS[name]
    return cls(**kwargs)
