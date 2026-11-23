"""The burgundy and white striped trousers are never tucked and never belted; only the Brunello blue and white
striped linen shirt goes under a blazer (.86.77).

David, 23 Nov 2026: "The purple white striped pants should not be worn tucked!!!!! Or with belt!!!!" and
"Yellow linen shirt is NOT to be worn under a blazer. Only linen I would consider under blazer is the blue and
white striped Brunello one. Generally"
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLOSET = [
    {"id": "item-1795296663305-695652", "name": "Burgundy & White Striped Trousers", "category": "Trousers", "colourName": "Burgundy", "colourHex": "#6a2a3a",
     "notes": "Wide burgundy and white stripe with a button waist. Wide-leg."},
    {"id": "tee", "name": "White Cotton Tee", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "ch", "name": "Stone Cotton Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#c9b896"},
    {"id": "bz", "name": "Navy Wool Blazer", "category": "Blazers", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "yl", "name": "Brunello Cucinelli Yellow Linen Shirt", "category": "Shirts", "colourName": "Yellow", "colourHex": "#efe0a0"},
    {"id": "bl", "name": "Brunello Cucinelli Blue Stripe Linen Shirt", "category": "Shirts", "colourName": "Blue Stripe", "colourHex": "#b9cde3"},
    {"id": "wl", "name": "Uniqlo White Linen Shirt", "category": "Shirts", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "lf", "name": "Dark Brown Suede Penny Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "belt", "name": "Dark Brown Suede Belt", "category": "Belts", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
]


def run(browser):
    ctx = browser.new_context(service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof WardrobeComposer.build === 'function'")
    out = page.evaluate("""closet => { const d = WardrobeComposer.build(closet); const S = 'item-1795296663305-695652';
      const striped = d.combos.filter(c => c.b.id === S);
      const belts = []; [1, 2, 3, 4, 5].forEach(lv => d.deal(30, { level: lv, temp: 76, recent: [], prefs: {}, exposure: {}, banned: {} }).forEach(o => { if (o.bottom.id === S && o.belt) belts.push(o.belt.id); }));
      return { stripedTucked: striped.filter(c => c.tuck).length, striped: striped.length, belts,
               underBlazer: [...new Set(d.combos.filter(c => c.l && c.l.id === 'bz').map(c => c.t.id))] }; }""", CLOSET)
    assert out["striped"] > 0 and out["stripedTucked"] == 0 and not out["belts"], out
    assert "yl" not in out["underBlazer"] and "wl" not in out["underBlazer"], out
    assert "bl" in out["underBlazer"], out
    ctx.close()
    return out


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        o = run(browser)
        print("Confirmed: striped trousers never tucked or belted (%d outfits); only the Brunello blue stripe linen under a blazer" % o["striped"])
        browser.close()
