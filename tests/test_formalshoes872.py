"""Formal takes only the dark brown Baudoin & Lange, any Belgian Shoes, or the Balenciaga loafers; and what is
worn underneath is lighter than the layer over it, or the same colour (.86.72).

David, 22 Nov 2026:
  "Formal loafers should be dark brown boudain lange all Belgians. Balenciaga."
  "I don't like wearing darker colors under lighter colors generally. Prefer the
   colors to either be monochromatic or lighter goes under darker."
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLOSET = [
    {"id": "bzB", "name": "Burgundy Wool Blazer", "category": "Blazers", "colourName": "Burgundy", "colourHex": "#5a2a33"},
    {"id": "bzC", "name": "Cream Wool Blazer", "category": "Blazers", "colourName": "Cream", "colourHex": "#ece3cf"},
    {"id": "bzN", "name": "Navy Knit Blazer", "category": "Blazers", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "sh", "name": "Light Blue Poplin Shirt", "category": "Shirts", "colourName": "Light Blue", "colourHex": "#a9c2de"},
    {"id": "wt", "name": "White Cotton Tee", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "nt", "name": "Navy Knit Tee", "category": "Tees", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "ch", "name": "Navy Cotton Chinos", "category": "Trousers", "colourName": "Navy", "colourHex": "#1e2846"},
    {"id": "st", "name": "Stone Cotton Chinos", "category": "Trousers", "colourName": "Stone", "colourHex": "#c9b896"},
    {"id": "eg", "name": "Edward Green Dark Brown Suede Penny Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "bl", "name": "Baudoin & Lange Dark Brown Leather Tassel Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#3e2618"},
    {"id": "blr", "name": "Baudoin & Lange Rust Suede Tassel Loafers", "category": "Shoes", "colourName": "Rust", "colourHex": "#8a4a2a"},
    {"id": "be", "name": "Belgian Shoes Brown Lizard Loafers", "category": "Shoes", "colourName": "Brown", "colourHex": "#7a4a2c"},
    {"id": "ba", "name": "Balenciaga Black Leather Penny Loafers", "category": "Shoes", "colourName": "Black", "colourHex": "#111111"},
    {"id": "tie", "name": "Dark Navy Knit Tie", "category": "Ties", "colourName": "Navy", "colourHex": "#1f2a44"},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof WardrobeComposer.build === 'function'")
    out = page.evaluate("""closet => { const d = WardrobeComposer.build(closet);
      return { formal: [...new Set(d.combos.filter(c => c.mask & (1 << 6)).map(c => c.s.id))],
               layered: [...new Set(d.combos.filter(c => c.l).map(c => c.l.id + '+' + c.t.id))] }; }""", CLOSET)
    assert set(out["formal"]) == {"bl", "be", "ba"}, out["formal"]
    lay = out["layered"]
    assert "bzC+sh" not in lay and "bzC+nt" not in lay, lay          # darker under lighter
    assert "bzB+sh" in lay and "bzN+wt" in lay, lay                    # lighter under darker
    assert "bzN+nt" in lay, lay                                        # one colour head to toe
    assert "bzC+wt" in lay, lay                                        # white under cream: the light one-colour look
    assert not errors, errors
    ctx.close()
    return out


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        o = run(browser)
        print("Confirmed: Formal shoes %s; never darker under lighter" % sorted(o["formal"]))
        browser.close()
