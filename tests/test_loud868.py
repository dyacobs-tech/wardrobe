"""Bright blue trousers are a statement, and loud patterned shoes only go with a quiet outfit (.86.68).

David, 22 Nov 2026, on a suggested outfit of a cream blazer, navy knit tee,
bright blue trousers and mustard check slippers: "This could be the ugliest
outfit I have ever seen"
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLOSET = [
    {"id": "bz", "name": "Cream Blazer", "category": "Blazers", "colourName": "Cream", "colourHex": "#ece3cf"},
    {"id": "t", "name": "Navy Knit Tee", "category": "Tees", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "blue", "name": "Bright Blue Cotton Trousers", "category": "Trousers", "colourName": "Blue", "colourHex": "#1f86d6"},
    {"id": "stone", "name": "Stone Cotton Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#c9b896"},
    {"id": "jeans", "name": "Light Wash Jeans", "category": "Jeans", "colourName": "Light Blue", "colourHex": "#8aa8c4"},
    {"id": "check", "name": "Vibi Venezia Mustard Check Furlane Slippers", "category": "Shoes", "colourName": "Mustard", "colourHex": "#c9a227"},
    {"id": "loafer", "name": "Dark Brown Suede Penny Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "black", "name": "Black Leather Penny Loafers", "category": "Shoes", "colourName": "Black", "colourHex": "#111111"},   # navy tee + blue jeans is all blue: black shoes
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof WardrobeComposer.build === 'function'")
    combos = page.evaluate("closet => WardrobeComposer.build(closet).combos.map(c => c.t.id + '/' + c.b.id + '/' + c.s.id)", CLOSET)
    assert not any(c.endswith("/blue/check") for c in combos), combos
    assert any(c.endswith("/stone/check") for c in combos), combos          # quiet outfit: fine
    assert any(c.endswith("/blue/loafer") or c.endswith("/blue/black") for c in combos), combos   # the blue trousers still get dealt with quiet shoes
    # .86.72 (David: "lighter goes under darker"): the navy tee never goes under the cream blazer again
    assert not page.evaluate("closet => WardrobeComposer.build(closet).combos.some(c => c.l && c.l.id === 'bz' && c.t.id === 't')", CLOSET)
    neutral = page.evaluate("closet => closet.map((x, i) => [x.id, WardrobeComposer.profile(x, i).neutral])", CLOSET)
    neutral = dict(neutral)
    assert neutral["jeans"] is True and neutral["blue"] is False and neutral["t"] is True, neutral   # denim and navy stay neutrals; bright blue is a statement
    assert not errors, errors
    ctx.close()
    return len(combos)


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        n = run(browser)
        print("Confirmed: bright blue trousers never meet loud check slippers (%d outfits built)" % n)
        browser.close()
