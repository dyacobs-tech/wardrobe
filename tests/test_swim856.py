"""Bathing suits go with a tee, a linen shirt or a casual polo, and pool slides, TOMS or raffia espadrilles (.86.56).

David, 22 Nov 2026: "Bathing suits looks should be with linen button down
shirts or t shirts, or casual polos. Should Be with pool slides, my toms slip
ons, or my baudoin lange with raffia trim."
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLOSET = [
    {"id": "sw1", "name": "Yellow & Navy Chevron Swim Trunks", "category": "Bathing suits", "colourName": "Yellow", "colourHex": "#c4ab63"},
    {"id": "tee", "name": "White Tee", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "linen", "name": "Blue Linen Shirt", "category": "Shirts", "colourName": "Blue", "colourHex": "#6f86a8"},
    {"id": "noted", "name": "Slate Blue Shirt", "category": "Shirts", "colourName": "Slate Blue", "colourHex": "#716c61", "notes": "Chambray linen."},
    {"id": "oxford", "name": "White Oxford Shirt", "category": "Shirts", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "polo", "name": "Navy Knit Polo", "category": "Polos", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "lspolo", "name": "White Long-Sleeve Polo", "category": "Polos", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "knit", "name": "Navy Crewneck Sweater", "category": "Sweaters", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "slides", "name": "Navy Pool Slides", "category": "Shoes", "colourName": "Navy", "colourHex": "#26304a"},
    {"id": "toms", "name": "TOMS Cream Canvas Slip-Ons", "category": "Shoes", "colourName": "Cream", "colourHex": "#d4cab9"},
    {"id": "bl", "name": "Baudoin & Lange Tan Suede Penny Espadrilles", "category": "Shoes", "colourName": "Tan", "colourHex": "#795936"},
    {"id": "loafer", "name": "Dark Brown Suede Penny Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "sneaker", "name": "White Leather Sneakers", "category": "Shoes", "colourName": "White", "colourHex": "#f5f5f0"},
    {"id": "vans", "name": "Vans Checkerboard Slip-On Sneakers", "category": "Shoes", "colourName": "Black", "colourHex": "#171617"},
    {"id": "chino", "name": "Stone Stretch Cotton Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#b9ad98"},
    {"id": "blazer", "name": "Navy Linen Blazer", "category": "Blazers", "colourName": "Navy", "colourHex": "#1f2a44"},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof WardrobeComposer.build === 'function'")
    out = page.evaluate("""closet => { const deck = WardrobeComposer.build(closet);
      const swim = deck.combos.filter(c => c.b.id === 'sw1').map(c => ({ top: c.t.id, shoes: c.s.id, layer: c.l ? c.l.id : null }));
      const chino = deck.combos.filter(c => c.b.id === 'chino').map(c => c.t.id + '+' + c.s.id);
      return { swim, chino }; }""", CLOSET)
    swim = out["swim"]
    assert swim, "no outfit was built with the swim trunks"
    tops = {o["top"] for o in swim}
    shoes = {o["shoes"] for o in swim}
    assert not any(o["layer"] for o in swim), swim
    assert tops == {"tee", "linen", "noted", "polo"}, tops          # never the oxford, the long-sleeve polo or a sweater
    assert shoes == {"slides", "toms", "bl"}, shoes                  # never loafers, sneakers or the Vans
    # the rule is about bathing suits only: chinos still take the other tops and shoes
    assert any(c.startswith("oxford+") for c in out["chino"]) and any(c.endswith("+loafer") for c in out["chino"]), out["chino"][:8]
    assert not errors, errors
    print("Confirmed: swim trunks are dealt only with %s and %s (%d outfits)" % (sorted(tops), sorted(shoes), len(swim)))
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        browser.close()
