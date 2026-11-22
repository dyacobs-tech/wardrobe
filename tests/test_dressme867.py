"""Dress me asks the try-on for a shirt tucked under a blazer, and a loose tee two inches below the waistband (.86.67).

David, 22 Nov 2026: "Shirts ALWAYS tucked under a blazer" (on The Edit > Dress
me) and "T shirts are too long they should be a hanging a couple inches below
my belt line."
The try-on worker is never called: the request is caught by a local mock.
"""
import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
MOCK = URL.rstrip("/") + "/__mock_tryon867"
PHOTO = "assets/photos/2f6757ee2dbc.jpg"

CLOSET = [
    {"id": "bz", "name": "Navy Linen Blazer", "category": "Blazers", "colourName": "Navy", "colourHex": "#1f2a44", "photo": PHOTO},
    {"id": "sh", "name": "White Oxford Shirt", "category": "Shirts", "colourName": "White", "colourHex": "#f7f5ef", "photo": PHOTO},
    {"id": "te", "name": "White Cotton Tee", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef", "photo": PHOTO},
    {"id": "ch", "name": "Stone Cotton Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#c9b896", "photo": PHOTO},
    {"id": "lf", "name": "Dark Brown Suede Penny Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f", "photo": PHOTO},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
    bodies = []

    def route(r):
        u = r.request.url
        if u.startswith(MOCK):
            if r.request.method == "POST":
                bodies.append(json.loads(r.request.post_data or "{}"))
                return r.fulfill(status=200, content_type="application/json", body=json.dumps({"id": "job1", "status": "queued", "steps": 4, "step": 1}))
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"id": "job1", "status": "queued", "steps": 4, "step": 1}))
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

    def dress(top):
        page.evaluate("() => document.querySelector('#bottombar [data-section=\"inspo\"]').click()")
        page.wait_for_timeout(500)
        page.evaluate("() => document.querySelector('[data-ins-seg=\"dress\"]').click()")
        page.wait_for_timeout(500)
        for slot, name in (("top", top), ("bottom", "Stone Cotton Chino"), ("shoes", "Dark Brown Suede Penny Loafers"), ("layer", "Navy Linen Blazer")):
            page.evaluate("s => document.querySelector('[data-dm-pick=\"' + s + '\"][data-dm-from=\"mine\"]').click()", slot)
            page.wait_for_selector("#dm-sheet841:not([hidden]) [data-dm-choose]", timeout=10000)
            ok = page.evaluate("n => { const b = [...document.querySelectorAll('#dm-sheet841 [data-dm-choose]')].find(x => x.textContent.indexOf(n) !== -1); if (b) b.click(); return !!b; }", name)
            assert ok, (slot, name, page.evaluate("() => document.getElementById('dm-sheet841').textContent.slice(0, 300)"))
            page.wait_for_timeout(200)
        n0 = len(bodies)
        page.evaluate("() => document.querySelector('[data-dm-go]').click()")
        page.wait_for_function("n => window.__dm867n === undefined || true", arg=n0)
        for _ in range(40):
            if len(bodies) > n0:
                break
            page.wait_for_timeout(250)
        assert len(bodies) > n0, "no try-on request"
        items = bodies[-1]["items"]
        return {it["slot"]: it.get("prompt", "") for it in items}

    shirt = dress("White Oxford Shirt")
    assert "Tucked" in shirt.get("top", ""), shirt
    page.evaluate("() => { const c = document.getElementById('tryon-close'); if (c) c.click(); }")
    page.wait_for_timeout(300)
    tee = dress("White Cotton Tee")
    assert "untucked" in tee.get("top", "") and "two inches" in tee.get("top", ""), tee
    assert not errors, errors
    ctx.close()
    return shirt, tee


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        shirt, tee = run(browser)
        print("Confirmed: Dress me asks for the shirt tucked under the blazer (%r) and the tee untucked two inches below the waistband" % shirt.get("top"))
        browser.close()
