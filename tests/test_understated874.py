"""Understated shoes come first; loud ones still appear, less often (.86.74).

David, 23 Nov 2026: "Use existing actual shoes!!!!!! ... they shouldn't be made
up styles and colors!!!! Generally I prefer UNDERSTATED style shoes!!!!!"
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLOSET = [
    {"id": "t", "name": "White Cotton Tee", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "t2", "name": "Navy Cotton Tee", "category": "Tees", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "b", "name": "Stone Cotton Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#c9b896"},
    {"id": "b2", "name": "White Cotton Trousers", "category": "Trousers", "colourName": "White", "colourHex": "#f4f1ea"},
    {"id": "plain", "name": "Dark Brown Suede Penny Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "camo", "name": "Belgian Shoes Camo Pony-Hair Loafers", "category": "Shoes", "colourName": "Camo", "colourHex": "#6b5a3f"},
    {"id": "check", "name": "Vibi Venezia Mustard Check Furlane Slippers", "category": "Shoes", "colourName": "Mustard", "colourHex": "#c9a227"},
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
      const score = {}; d.combos.forEach(c => { (score[c.s.id] = score[c.s.id] || []).push(c.score); });
      const avg = k => (score[k] || [0]).reduce((a, b) => a + b, 0) / (score[k] || [1]).length;
      return { plain: avg('plain'), camo: avg('camo'), check: avg('check'), loud: !!score.camo || !!score.check }; }""", CLOSET)
    assert out["plain"] > out["camo"] and out["plain"] > out["check"], out
    assert out["loud"], out          # loud shoes are not banned
    assert not errors, errors
    ctx.close()
    return out


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        o = run(browser)
        print("Confirmed: plain shoes score %.2f, camo %.2f, check %.2f" % (o["plain"], o["camo"], o["check"]))
        browser.close()
