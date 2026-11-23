"""The Theory Cream Knit Polo is long-sleeved, so it never goes with swim trunks; the linen shirt does (.86.71).

David, 22 Nov 2026: "Bathing suits looks should be with linen button down
shirts or t shirts, or casual polos", and the standing rule that long-sleeve
polos never go with swim. The Theory polo's name does not say long-sleeve,
but its closet photo shows full sleeves and ribbed cuffs.
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLOSET = [
    {"id": "item-1794965887177-185377", "name": "Theory Cream Knit Polo", "category": "Polos", "colourName": "Cream", "colourHex": "#e8e0cc"},
    {"id": "lin", "name": "Uniqlo White Linen Shirt", "category": "Shirts", "colourName": "White", "colourHex": "#f7f5ef", "notes": "Linen, one chest pocket."},
    {"id": "am", "name": "Alex Mill White Knit Polo", "category": "Polos", "colourName": "White", "colourHex": "#f4f1ea", "notes": "Short sleeves, chest pocket."},
    {"id": "sp", "name": "Sunspel Grey Piqué Polo", "category": "Polos", "colourName": "Grey", "colourHex": "#9a9a98", "notes": "Short sleeves."},
    {"id": "wt", "name": "White Cotton Tee", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "sw", "name": "Schoastal Navy Swim Trunks", "category": "Bathing suits", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "toms", "name": "TOMS Cream Canvas Slip-Ons", "category": "Shoes", "colourName": "Cream", "colourHex": "#ece3cf"},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof WardrobeComposer.build === 'function'")
    tops = page.evaluate("closet => [...new Set(WardrobeComposer.build(closet).combos.filter(c => c.b.id === 'sw').map(c => c.t.id))]", CLOSET)
    assert "lin" in tops and "item-1794965887177-185377" not in tops, tops
    # .86.73 (David, 23 Nov 2026: "Swim looks should be T Shirts Or linen button down ONLY!!!!! Or white Alex mill
    # polo pocket shirt!!!!! Otherwise NO polos")
    assert "wt" in tops and "am" in tops and "sp" not in tops, tops
    assert not errors, errors
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        print("Confirmed: swim trunks take the linen shirt, never the long-sleeved Theory polo")
        browser.close()
