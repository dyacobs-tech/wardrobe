"""A button-down is never tucked into swim trunks or drawstring trousers (.87.34).

David, 28 Nov 2026: "Button downs should NEVER be tucked into a bathing suit or drawstring pants!!!!!!"

The outfit engine never tucks a shirt into swim trunks or into trousers with a drawstring or elastic waist,
whatever else would tuck it (a blazer over it, a closet rule). 19 high-res pictures drawn with a shirt tucked
into swim trunks or drawstring trousers are hidden until they are redrawn untucked.
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent

src = (ROOT / "src/app.html").read_text()
hidden = set(re.findall(r'"([0-9a-f]{16})"', re.search(r"var HIRES_TUCKED8734 = (\{.*?\});", src).group(1)))
man = json.loads((ROOT / "assets/onbody-hires/manifest.json").read_text())["r"]
stems = {Path(e["full"]).stem: e for e in man}
assert len(hidden) == 19 and hidden <= set(stems), ("the hidden tucked pictures must be real entries", len(hidden), sorted(hidden - set(stems)))

CLOSET = [
    {"id": "sh-linen", "name": "White Linen Shirt", "category": "Shirts", "colourName": "White", "colourHex": "#f4f2ec"},
    {"id": "sh-oxford", "name": "Light Blue Oxford Button-Down Shirt", "category": "Shirts", "colourName": "Light Blue", "colourHex": "#a8c3d1"},
    {"id": "sw-trunks", "name": "Kiton Orange Swim Trunks", "category": "Bathing suits", "colourName": "Orange", "colourHex": "#e8762c"},
    {"id": "tr-draw", "name": "Isaia Navy Drawstring Trousers", "category": "Trousers", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "tr-elastic", "name": "Malibu Linen Pants", "category": "Trousers", "colourName": "Grey", "colourHex": "#8a8a80", "notes": "elastic waist with a drawstring"},
    {"id": "tr-chino", "name": "Stone Stretch Chinos", "category": "Trousers", "colourName": "Stone", "colourHex": "#b9ad98"},
    {"id": "bz-navy", "name": "Navy Hopsack Blazer", "category": "Blazers", "colourName": "Navy", "colourHex": "#1e2846"},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and r.request.method == "GET" else r.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof WardrobeComposer.tuckOf === 'function' && typeof HIRES !== 'undefined' && HIRES.ready", timeout=30000)
    got = page.evaluate("""closet => { const C = WardrobeComposer; const p = id => C.profile(closet.find(i => i.id === id), 0);
      const out = {};
      for (const sh of ['sh-linen', 'sh-oxford']) for (const b of ['sw-trunks', 'tr-draw', 'tr-elastic', 'tr-chino']) for (const ly of [null, 'bz-navy']) {
        const layer = ly ? Object.assign({}, p(ly), { role: 'layer' }) : null;
        out[sh + '+' + b + (ly ? '+blazer' : '')] = C.tuckOf(p(sh), layer, p(b)); }
      return out; }""", CLOSET)
    for k, v in got.items():
        if "tr-chino" in k:
            continue
        assert v is False, ("a button-down is tucked into swim trunks or drawstring trousers", k, got)
    # the chinos still take a tucked shirt under a blazer, so the rule is not simply "never tuck"
    assert got["sh-oxford+tr-chino+blazer"] is True, got
    shown = page.evaluate("stems => Object.values(HIRES.map).filter(e => stems.includes(String(e.full || '').replace(/^.*\\//, '').replace(/\\.[a-z]+$/i, ''))).length", sorted(hidden))
    assert shown == 0, ("a tucked picture is still in use", shown)
    assert not errors, errors
    ctx.close()
    return got


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        b = engine.launch()
        got = run(b)
        b.close()
print("Confirmed: a button-down is never tucked into swim trunks or drawstring trousers (%d cases, blazer or not); chinos still take a tucked shirt under a blazer; the %d pictures drawn tucked are hidden" % (sum(1 for k in got if "chino" not in k), len(hidden)))
