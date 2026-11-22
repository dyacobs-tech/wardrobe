"""Dress me's piece picker filters by clothing type and by brand (.86.70).

David, 22 Nov 2026, on The Edit > Dress me: "Should be a drop down toggle in
dress me for clothing type and brand!"
"""
import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
PHOTO = "assets/photos/2f6757ee2dbc.jpg"

CLOSET = [
    {"id": "p1", "name": "Brunello Cucinelli Oatmeal Polo", "brand": "Brunello Cucinelli", "category": "Polos", "colourName": "Oatmeal", "colourHex": "#d8ccb4", "photo": PHOTO},
    {"id": "p2", "name": "Loro Piana Navy Polo", "brand": "Loro Piana", "category": "Polos", "colourName": "Navy", "colourHex": "#1f2a44", "photo": PHOTO},
    {"id": "t1", "name": "Brunello Cucinelli White Tee", "brand": "Brunello Cucinelli", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef", "photo": PHOTO},
    {"id": "s1", "name": "Oxford Shirt", "category": "Shirts", "colourName": "White", "colourHex": "#f7f5ef", "photo": PHOTO},
    {"id": "ch", "name": "Stone Cotton Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#c9b896", "photo": PHOTO},
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
    page.evaluate("() => document.querySelector('#bottombar [data-section=\"inspo\"]').click()")
    page.wait_for_timeout(500)
    page.evaluate("() => document.querySelector('[data-ins-seg=\"dress\"]').click()")
    page.wait_for_timeout(500)
    page.evaluate("() => document.querySelector('[data-dm-pick=\"top\"][data-dm-from=\"mine\"]').click()")
    page.wait_for_selector("#dm-sheet841:not([hidden]) .dm-type869", timeout=10000)

    names = lambda: page.evaluate("() => [...document.querySelectorAll('#dm-sheet841 [data-dm-choose] .dm-tn841')].map(x => x.textContent).sort()")
    def choose(cls, v):
        page.evaluate("([c, v]) => { const s = document.querySelector('#dm-sheet841 .' + c); s.value = v; s.dispatchEvent(new Event('change', { bubbles: true })); }", [cls, v])
        page.wait_for_timeout(200)

    opts = page.evaluate("() => ({ t: [...document.querySelectorAll('.dm-type869 option')].map(o => o.value), b: [...document.querySelectorAll('.dm-brand869 option')].map(o => o.value) })")
    # the app may add starter pieces to a small closet, so check by what each tile is
    cat = lambda: page.evaluate("() => { const by = {}; wardrobeItems.forEach(i => by[i.name] = [i.category, i.brand || '']); return [...document.querySelectorAll('#dm-sheet841 [data-dm-choose] .dm-tn841')].map(x => by[x.textContent] || ['?', '?']); }")
    assert opts["t"][0] == "" and {"Polos", "Shirts", "Tees"} <= set(opts["t"]) and opts["t"][1:] == sorted(opts["t"][1:]), opts
    assert {"Brunello Cucinelli", "Loro Piana"} <= set(opts["b"]) and opts["b"][-1] == "Other", opts
    allN = len(names())
    choose("dm-type869", "Polos")
    pol = names()
    assert 0 < len(pol) < allN and all(c[0] == "Polos" for c in cat()) and "Loro Piana Navy Polo" in pol, pol
    choose("dm-brand869", "Brunello Cucinelli")
    bc = names()
    assert "Brunello Cucinelli Oatmeal Polo" in bc and "Loro Piana Navy Polo" not in bc and all(c == ["Polos", "Brunello Cucinelli"] for c in cat()), cat()
    choose("dm-type869", "")
    assert "Brunello Cucinelli White Tee" in names() and all(c[1] == "Brunello Cucinelli" for c in cat()), cat()
    # both boxes fit side by side on the phone
    w = page.evaluate("() => [...document.querySelectorAll('.dm-filters869 select')].map(s => { const r = s.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right)]; })")
    assert len(w) == 2 and all(l >= 0 and r <= 402 for l, r in w), w
    assert not errors, errors
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        print("Confirmed: Dress me's picker filters by clothing type and brand")
        browser.close()
