"""Dress me keeps its place when a piece is changed, and a stalled "Put it on me" says so (.86.70).

David, 22 Nov 2026, on The Edit > Dress me:
  "When I tried to change an item In dress me it didn't work and navigated me
   back to Prev page" (the picker locked the page at the top, so choosing the
   jacket or shoes left him at the top of the page)
  "When I press Put it on me button in dress me it is not loading" (stuck on
   "Dressing you — piece 1 of 4...")
The try-on worker is never called: a local mock answers "step 1" twice, then
stops answering.
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
MOCK = URL.rstrip("/") + "/__mock_tryon870"
PHOTO = "assets/photos/2f6757ee2dbc.jpg"

CLOSET = [
    {"id": "bz", "name": "Navy Linen Blazer", "category": "Blazers", "colourName": "Navy", "colourHex": "#1f2a44", "photo": PHOTO},
    {"id": "bz2", "name": "Cream Linen Blazer", "category": "Blazers", "colourName": "Cream", "colourHex": "#ece3cf", "photo": PHOTO},
    {"id": "te", "name": "White Cotton Tee", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef", "photo": PHOTO},
    {"id": "ch", "name": "Stone Cotton Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#c9b896", "photo": PHOTO},
    {"id": "lf", "name": "Dark Brown Suede Penny Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f", "photo": PHOTO},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 700}, is_mobile=True, has_touch=True, service_workers="block")
    polls = []

    def route(r):
        u = r.request.url
        if u.startswith(MOCK):
            if r.request.method == "POST":
                return r.fulfill(status=200, content_type="application/json", body=json.dumps({"id": "a" * 32, "status": "running", "steps": 4, "step": 1}))
            polls.append(u)
            if len(polls) <= 2:
                return r.fulfill(status=200, content_type="application/json", body=json.dumps({"id": "a" * 32, "status": "running", "steps": 4, "step": 1}))
            return r.abort()
        if u.startswith(URL) and r.request.method == "GET":
            return r.continue_()
        return r.abort()

    ctx.route("**/*", route)
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(CLOSET)) + ");"
                        "localStorage.setItem('wardrobe.tryonurl'," + json.dumps(MOCK) + ");"
                        "localStorage.setItem('wardrobe.sync', JSON.stringify({ key: 'test-placeholder', acct: 'TEST', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'test' }));")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function'", timeout=60000)
    page.evaluate("() => document.querySelector('#bottombar [data-section=\"inspo\"]').click()")
    page.wait_for_timeout(500)
    page.evaluate("() => document.querySelector('[data-ins-seg=\"dress\"]').click()")
    page.wait_for_timeout(500)

    def pick(slot, name):
        page.evaluate("s => document.querySelector('[data-dm-pick=\"' + s + '\"][data-dm-from=\"mine\"]').click()", slot)
        page.wait_for_selector("#dm-sheet841:not([hidden]) [data-dm-choose]", timeout=10000)
        ok = page.evaluate("n => { const b = [...document.querySelectorAll('#dm-sheet841 [data-dm-choose]')].find(x => x.textContent.indexOf(n) !== -1); if (b) b.click(); return !!b; }", name)
        assert ok, (slot, name)
        page.wait_for_timeout(300)

    # the jacket row sits below the fold: choosing one leaves him where he was
    page.evaluate("() => document.querySelector('[data-dm-pick=\"layer\"]').scrollIntoView({ block: 'center' })")
    page.wait_for_timeout(300)
    y0 = page.evaluate("() => scrollY")
    assert y0 > 40, y0
    page.evaluate("() => document.querySelector('[data-dm-pick=\"layer\"][data-dm-from=\"mine\"]').click()")
    page.wait_for_selector("#dm-sheet841:not([hidden]) [data-dm-choose]", timeout=10000)
    top = page.evaluate("() => Math.round(document.body.getBoundingClientRect().top)")
    assert abs(top + y0) <= 2, (top, y0)
    page.evaluate("() => [...document.querySelectorAll('#dm-sheet841 [data-dm-choose]')].find(x => x.textContent.indexOf('Cream Linen Blazer') !== -1).click()")
    page.wait_for_timeout(500)
    st = page.evaluate("() => ({ y: scrollY, page: document.body.getAttribute('data-page'), insv: document.documentElement.getAttribute('data-insv'), lock: document.documentElement.classList.contains('sheet-lock'), chosen: document.body.textContent.indexOf('Cream Linen Blazer') !== -1 })")
    assert abs(st["y"] - y0) <= 2 and st["page"] == "inspo" and st["insv"] == "dress" and not st["lock"] and st["chosen"], (st, y0)

    # Put it on me: the clock runs while it waits, then a dead connection is reported
    pick("top", "White Cotton Tee")
    pick("bottom", "Stone Cotton Chino")
    pick("shoes", "Dark Brown Suede Penny Loafers")
    page.evaluate("() => document.querySelector('[data-dm-go]').click()")
    page.wait_for_function("() => /0:1\\d/.test(document.getElementById('tryon-status').textContent)", timeout=30000)
    t0 = time.time()
    page.wait_for_function("() => /Lost touch/.test(document.getElementById('tryon-status').textContent)", timeout=90000)
    assert time.time() - t0 < 80
    assert not errors, errors
    ctx.close()
    return y0


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        y = run(browser)
        print("Confirmed: Dress me keeps its place (%dpx) after a change; a stalled try-on shows its clock, then says it lost touch" % y)
        browser.close()
