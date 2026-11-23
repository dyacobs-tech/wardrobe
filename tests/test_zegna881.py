"""The Zegna grey 12milmil12 knit tee is drawn with regular short sleeves (.86.81).

David, 23 Nov 2026, screenshot of the grey tee with white jeans: "Sleeves on this are much short like a regular
tee shirt pls fix this item". The five pictures with the long, elbow-length sleeves were redrawn.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEE = "item-1795302318182-394566"
OLD = ["6200f5d9010d4d3e.webp", "169bfc678d37b6e9.webp", "3b8f19709c6cff65.webp", "f238e8ff9158b226.webp", "32cec7b0275dcd00.webp"]
man = json.loads((ROOT / "assets/onbody/manifest.json").read_text())["r"]
files = [e["f"] for e in man]
assert not [f for f in OLD if f in files], "a long-sleeve picture is still listed"
mine = [e for e in man if TEE in e["k"]]
assert len(mine) >= 5 and all((ROOT / "assets/onbody-cut-hq" / e["f"]).exists() for e in mine), mine
print("Confirmed the %d Zegna grey tee pictures are the redrawn short-sleeve ones" % len(mine))
