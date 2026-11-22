"""A linen jacket is a light layer: Evening Casual deals it on warm days, a wool jacket is not (.86.71).

David, 22 Nov 2026, on the Human Assembly Ochre Linen-Blend Chore Jacket:
"It's light layer correct."
No level dealt a casual jacket before; Evening Casual now does (Daytime stays
without a layer, as he set it).
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLOSET = [
    {"id": "lj", "name": "Human Assembly Ochre Linen-Blend Chore Jacket", "category": "Jackets", "colourName": "Ochre", "colourHex": "#b08a3e",
     "notes": "Chore jacket in a slubby linen blend"},
    {"id": "wj", "name": "Navy Wool Field Jacket", "category": "Jackets", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "t", "name": "White Cotton Tee", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "t2", "name": "Navy Cotton Tee", "category": "Tees", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "ch", "name": "Stone Cotton Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#c9b896"},
    {"id": "jn", "name": "Dark Indigo Jeans", "category": "Jeans", "colourName": "Indigo", "colourHex": "#22304f"},
    {"id": "lf", "name": "Dark Brown Suede Penny Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "sn", "name": "White Leather Sneakers", "category": "Shoes", "colourName": "White", "colourHex": "#f4f4f0"},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof WardrobeComposer.build === 'function'")
    out = page.evaluate("""closet => { const deck = WardrobeComposer.build(closet), seen = {};
      [76, 80, 86].forEach(temp => [3].forEach(lv => deck.deal(40, { level: lv, temp: temp, recent: [], prefs: {}, exposure: {}, banned: {} })
        .forEach(o => { if (o.layer) seen[o.layer.id + '@' + temp] = 1; })));
      return { seen: Object.keys(seen), warm: closet.map((x, i) => [x.id, WardrobeComposer.profile(x, i).warm]) }; }""", CLOSET)
    warm = dict(out["warm"])
    assert warm["lj"] < 2 and warm["wj"] >= 2, warm
    assert "lj@76" in out["seen"] and "lj@80" in out["seen"], out["seen"]
    assert "lj@86" not in out["seen"], out["seen"]          # past 84°F no layer at all
    assert not any(s.startswith("wj@") for s in out["seen"]), out["seen"]
    assert not errors, errors
    ctx.close()
    return out["seen"]


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        s = run(browser)
        print("Confirmed: the linen chore jacket is dealt on warm days (%s); the wool jacket is not" % ", ".join(sorted(s)))
        browser.close()
