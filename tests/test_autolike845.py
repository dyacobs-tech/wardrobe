"""Liking an outfit in The Edit puts it on him (.86.45), against a MOCK try-on service.

David (21 Nov): "Are we able to pull these new items on me????" and then
"Yes auto on like is good". A like on an outfit with new pieces starts the
same try-on Dress me uses: one POST /tryon with garment slots only, a
status line on the card, then the card shows him wearing it; Looks > Liked
shows the same picture, and it is still there after a reload. A second
like of the same outfit never posts again. The preview copy never posts.
Never calls production.
"""
import base64
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
TRY = "https://wardrobe-tryon.dyacobs.workers.dev"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
JOB = "0123456789abcdef0123456789abcdef"
RESULT = TRY + "/r/" + JOB + ".jpg"
# "All new" always has outfits that are not on him yet; "With mine" can open on a page of ready-made ones
FLAT = "#panel-allnew .en-card:has(.en-flat) [data-en-like]"


def run(browser, engine):
    seen = {"posts": [], "polls": 0}
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block")

    def route(r):
        u, m = r.request.url, r.request.method
        if u.startswith(URL) and m == "GET":
            return r.continue_()
        if u == TRY + "/tryon" and m == "POST":
            seen["posts"].append(json.loads(r.request.post_data))
            return r.fulfill(status=202, content_type="application/json",
                             body=json.dumps({"id": JOB, "status": "running", "step": 1, "steps": 3}))
        if u.startswith(TRY + "/tryon/" + JOB):
            seen["polls"] += 1
            done = seen["polls"] >= 2
            return r.fulfill(status=200, content_type="application/json", body=json.dumps(
                {"id": JOB, "status": "done" if done else "running", "step": 2, "steps": 3, "resultUrl": RESULT if done else None}))
        if u.startswith(TRY + "/r/"):
            return r.fulfill(status=200, content_type="image/png", body=PNG)
        return r.abort()

    ctx.route("**/*", route)
    ctx.add_init_script(
        "if (!sessionStorage.getItem('seeded845')) { sessionStorage.setItem('seeded845', '1');"
        "localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");"
        "localStorage.setItem('wardrobe.formality','2');"
        "localStorage.setItem('wardrobe.sync', JSON.stringify({key:'" + "b" * 48 + "', acct:'test', last:0, snap:{}, st:{}, tomb:{}, dirty:{}, status:'x', lastOk:0})); }")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.locator("#section-inspo").tap()
    page.wait_for_selector('[data-ins-feed="allnew"]', timeout=30000)
    page.evaluate("() => document.querySelector('[data-ins-feed=\"allnew\"]').click()")
    page.wait_for_function("() => document.querySelectorAll('%s').length >= 2" % FLAT, timeout=30000)

    like = page.locator(FLAT).first
    idx = like.get_attribute("data-en-like")
    look = page.evaluate("i => { const l = __enLookAt841('allnew', +i); return { key: l.key, shop: l.pieces.filter(p => p.shop).length, n: l.pieces.length }; }", idx)
    assert look["shop"] >= 1, look
    like.tap()
    card = '#panel-allnew .en-card[data-en-i="%s"]' % idx
    page.wait_for_function("c => { const n = document.querySelector(c + ' .en-auto845'); return n && /Putting|Dressing/.test(n.textContent); }", arg=card, timeout=8000)
    page.wait_for_function("c => { const i = document.querySelector(c + ' .ob-figure.en-render img'); return i && i.getAttribute('src') === '%s'; }" % RESULT, arg=card, timeout=30000)
    after = page.evaluate("""c => { const el = document.querySelector(c); return { note: !!el.querySelector('.en-auto845'), pieces: el.querySelectorAll('.ob-pieces .fl-cell').length,
      pressed: el.querySelector('[data-en-like]').getAttribute('aria-pressed'), title: !!el.querySelector('.oc-title') }; }""", card)
    assert not after["note"] and after["pieces"] >= 2 and after["pressed"] == "true" and after["title"], after
    assert len(seen["posts"]) == 1, len(seen["posts"])
    items = seen["posts"][0]["items"]
    slots = [i["slot"] for i in items]
    assert 1 <= len(items) <= 4 and set(slots) <= {"top", "outer", "bottom", "shoes"} and len(set(slots)) == len(slots), slots
    for i in items:
        assert i["image"].startswith("data:image/") or i["image"].startswith("https://"), i["image"][:40]

    # liking it again (tap, tap) never pays twice
    page.locator(card + " [data-en-like]").tap()
    page.wait_for_timeout(600)
    assert len(seen["posts"]) == 1, "posted again"

    # the preview copy never spends credits: a like there starts nothing
    page.evaluate("() => { window.__PV81 = true; }")
    page.locator(FLAT + '[aria-pressed="false"]').first.tap()
    page.wait_for_timeout(800)
    assert len(seen["posts"]) == 1, "the preview posted to the try-on service"
    assert page.evaluate("() => Object.keys(window.__enAuto845.state()).length") == 0
    page.evaluate("() => { window.__PV81 = false; }")

    # Looks > Liked shows him wearing it, and it survives a reload
    page.evaluate("() => window.scrollTo(0, 0)")
    page.locator("#section-ideas").tap()
    page.locator('#panel-looks [data-lk-go="liked"]').tap()
    page.wait_for_function("() => !!document.querySelector('#lk-liked841 .en-card .ob-figure.en-render img[src=\"%s\"]')" % RESULT, timeout=15000)
    page.reload(wait_until="domcontentloaded")
    page.locator("#section-ideas").tap()
    page.locator('#panel-looks [data-lk-go="liked"]').tap()
    page.wait_for_function("() => !!document.querySelector('#lk-liked841 .en-card .ob-figure.en-render img[src=\"%s\"]')" % RESULT, timeout=30000)
    assert len(seen["posts"]) == 1, "posted again after reload"

    assert not errors, errors
    print("Confirmed auto on like (%s): one job for slots %s, picture on the card and in Liked, kept after reload, none in preview" % (engine, slots))
    ctx.close()


with sync_playwright() as pw:
    for name, engine in (("chromium", pw.chromium), ("webkit", pw.webkit)):
        browser = engine.launch()
        run(browser, name)
        browser.close()
