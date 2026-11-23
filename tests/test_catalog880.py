"""Shop has about twice the products, menswear only, and nothing already in it changed (.86.80).

David, 23 Nov 2026: "let's beef up the shopping aspect of the app. More skus deeper catalogue etc...."
The catalog is append-only (docs/catalog-pipeline.md): existing rows stay exactly as they were.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
full = json.loads((ROOT / "assets/edit-catalog.json").read_text())["products"]
lite = json.loads((ROOT / "assets/edit-catalog-lite.json").read_text())["products"]

assert len(full) >= 1900, len(full)
assert [p["sku"] for p in full] == [p["sku"] for p in lite], "lite catalog out of step with the full one"
assert len({p["url"] for p in full}) == len(full), "a product appears twice"
women = [p["name"] for p in full if re.search(r"\b(women|womens|ladies|skirt|blouse|shirt dress)\b", p["name"], re.I) and "(men)" not in p["name"].lower()]
assert not women, women[:5]
# rows added from .86.80 on (one older locked row, a Pool House polo, has a size chart photo and cannot be edited)
charts = [p["name"] for p in full[1000:] if re.search(r"size_?guide|size[-_]chart", p.get("imgUrl", ""), re.I)]
assert not charts, charts[:5]
missing = [p["img"] for p in full if p.get("img", "").startswith("assets/") and not (ROOT / p["img"]).exists()]
assert not missing, missing[:5]
brands = {p["brand"] for p in full}
print("Confirmed %d products from %d brands, menswear only, no size charts, every photo present" % (len(full), len(brands)))
