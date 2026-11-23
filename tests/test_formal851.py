"""Formal is a blazer, a shirt and tie, and dressier chinos; no suit needed (.86.51).

David, 22 Nov 2026, looking at Home saying "No Formal looks in your closet yet":
  "Showing NO looks"
  "Doesn't need to be suits tie dressier chinoos and blazer. Do that.
   Seersucker is more casual."

Before this, Formal needed dress trousers (wool, tailored), and every pair he
owns is chinos, jeans, linen, drawstring or seersucker, so Formal was empty.
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLOSET = [
    {"id": "bz1", "name": "Burgundy Blazer", "category": "Blazers", "colourName": "Burgundy", "colourHex": "#5e2129"},
    {"id": "bz2", "name": "Cream Blazer", "category": "Blazers", "colourName": "Cream", "colourHex": "#efe6d2"},
    {"id": "sh1", "name": "Light Blue Shirt", "category": "Shirts", "colourName": "Light Blue", "colourHex": "#a8c3d1"},
    {"id": "sh2", "name": "White Shirt", "category": "Shirts", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "po1", "name": "White Long-Sleeve Polo", "category": "Polos", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "te1", "name": "Navy Tee", "category": "Tees", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "ch1", "name": "Beige Stretch Cotton Chino", "category": "Trousers", "colourName": "Beige", "colourHex": "#cdbb98"},
    {"id": "ch2", "name": "Stone Non-Iron Stretch Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#b9ad98"},
    {"id": "ss1", "name": "Navy Stretch Seersucker Dress Pant", "category": "Trousers", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "dr1", "name": "Navy Drawstring Trousers", "category": "Trousers", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "fp1", "name": "Cream Stretch Slub Twill 5-Pocket", "category": "Trousers", "colourName": "Cream", "colourHex": "#e9dfc8"},
    {"id": "je1", "name": "Dark Indigo Jeans", "category": "Jeans", "colourName": "Indigo", "colourHex": "#2c3e63"},
    {"id": "lo1", "name": "Belgian Shoes Dark Brown Suede Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "sn1", "name": "White Leather Sneakers", "category": "Shoes", "colourName": "White", "colourHex": "#f5f5f0"},
    {"id": "be1", "name": "Dark Brown Leather Belt", "category": "Belts", "colourName": "Dark Brown", "colourHex": "#4a2e1f"},
    {"id": "ti1", "name": "Navy Knit Tie", "category": "Ties", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "ti2", "name": "Burgundy Knit Tie", "category": "Ties", "colourName": "Burgundy", "colourHex": "#6b1f2a"},
    {"id": "sg1", "name": "Tortoise Sunglasses", "category": "Sunglasses", "colourName": "Tortoise", "colourHex": "#5a3a22"},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof WardrobeComposer.build === 'function'")
    out = page.evaluate("""closet => {
      const deck = WardrobeComposer.build(closet);
      const deal = (lv, n) => { const all = []; for (let k = 0; k < 6; k++) deck.deal(n, { level: lv, temp: 70, recent: [], prefs: {}, exposure: {}, banned: {} }).forEach(o => all.push(
        { top: o.top.id, bottom: o.bottom.id, shoes: o.shoes.id, layer: o.layer ? o.layer.id : null, acc: o.acc ? o.acc.id : null, belt: o.belt ? o.belt.id : null })); return all; };
      return { formal: deal(6, 6), dressy: deal(5, 6), casual: deal(3, 6), day: deal(2, 6) };
    }""", CLOSET)
    formal = out["formal"]
    assert formal, "Formal dealt nothing from a closet with blazers, shirts, ties and chinos"
    for o in formal:
        assert o["layer"] in ("bz1", "bz2"), o                     # a blazer, no suit needed
        assert o["top"] in ("sh1", "sh2"), o                       # a shirt that takes a tie: never a polo or tee
        assert o["acc"] in ("ti1", "ti2"), o                       # always a tie
        assert o["bottom"] in ("ch1", "ch2"), o                    # dressier chinos: never seersucker, drawstring, five-pocket or jeans
        assert o["shoes"] == "lo1", o                              # never sneakers
    # the same outfit always wears the same tie
    by = {}
    for o in formal:
        k = (o["layer"], o["top"], o["bottom"], o["shoes"])
        assert by.setdefault(k, o["acc"]) == o["acc"], (k, by[k], o["acc"])
    # below Formal a tie is never dealt, and seersucker still is (it is the more casual trouser)
    for lv in ("dressy", "casual", "day"):
        assert not [o for o in out[lv] if o["acc"] in ("ti1", "ti2")], (lv, out[lv])
    assert not errors, errors
    print("Confirmed: Formal dealt %d outfits, each a blazer, shirt, tie and chinos; no tie below Formal" % len(formal))
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        browser.close()
