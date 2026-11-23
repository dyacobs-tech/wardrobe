"""The Closet searches by brand and by colour: Brand and Colour dropdowns, and every word of the search on its own (.86.75).

David, 23 Nov 2026: "Should be able to search by brand in my closet or color"
"""
import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
PHOTO = "assets/photos/2f6757ee2dbc.jpg"

CLOSET = [
    {"id": "a", "name": "Brunello Cucinelli Navy Polo", "brand": "Brunello Cucinelli", "category": "Polos", "colourName": "Navy", "colourHex": "#1f2a44", "photo": PHOTO},
    {"id": "b", "name": "Brunello Cucinelli White Tee", "brand": "Brunello Cucinelli", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef", "photo": PHOTO},
    {"id": "c", "name": "Loro Piana Navy Tipped Polo", "brand": "Loro Piana", "category": "Polos", "colourName": "Navy", "colourHex": "#1f2a44", "photo": PHOTO},
    {"id": "d", "name": "Oxford Shirt", "category": "Shirts", "colourName": "Light blue", "colourHex": "#a9c2de", "photo": PHOTO,
     "extraColours": [{"name": "White", "hex": "#ffffff"}]},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(CLOSET)) + ")")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function'", timeout=60000)
    page.evaluate("() => switchTab('wardrobe')")
    page.wait_for_selector("#ward-brand875", state="attached", timeout=15000)
    page.wait_for_timeout(500)
    mine = lambda: sorted(page.evaluate("() => [...document.querySelectorAll('#item-grid [data-item-open]')].map(e => e.getAttribute('data-item-open')).filter(id => ['a','b','c','d'].includes(id))"))
    def pick(sel, v):
        page.evaluate("([s, v]) => { const e = document.getElementById(s); e.value = v; e.dispatchEvent(new Event('change', { bubbles: true })); }", [sel, v])
        page.wait_for_timeout(300)
    def search(q):
        page.fill("#ward-search", q); page.wait_for_timeout(400)

    brands = page.evaluate("() => [...document.querySelectorAll('#ward-brand875 option')].map(o => o.value)")
    assert "Brunello Cucinelli" in brands and "Loro Piana" in brands, brands
    pick("ward-brand875", "Brunello Cucinelli")
    assert mine() == ["a", "b"], mine()
    pick("ward-brand875", "")
    pick("ward-colour875", "Navy")
    assert mine() == ["a", "c"], mine()
    pick("ward-colour875", "")
    search("navy brunello")                      # every word on its own, in any order
    assert mine() == ["a"], mine()
    search("white")                              # a second colour counts too
    assert mine() == ["b", "d"], mine()
    w = page.evaluate("() => [...document.querySelectorAll('.closet-filters875 select')].map(s => Math.round(s.getBoundingClientRect().right))")
    assert len(w) == 2 and all(r <= 402 for r in w), w
    assert not errors, errors
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        print("Confirmed: the Closet filters by brand and colour, and searches every word on its own")
        browser.close()
