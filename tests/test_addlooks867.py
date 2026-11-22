"""An icon look added with "Add to Looks" (never "lookbook") lands in Looks > Liked (.86.67).

David, 22 Nov 2026: "Add to "looks" not lookbook. When I hit emulate. It said
save to "lookbook" should be "looks" but then I go to liked section and nothing
appeared. This needs to WORK."
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(browser):
    src = open(os.path.join(ROOT, "src", "app.html"), encoding="utf-8").read()
    assert ">Add to lookbook<" not in src and src.count(">Add to Looks<") >= 2
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    # one icon look saved by the old button, without a verdict
    old = {"id": "iconlook-kraft-1", "title": "Alexander Kraft — The Riviera uniform", "img": "assets/photos/2f6757ee2dbc.jpg", "iconSpec": True, "swatches": []}
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");localStorage.setItem('wardrobe.looks'," + json.dumps(json.dumps([old])) + ")")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && typeof addIconLookToLookbook === 'function' && typeof STYLE_ICONS !== 'undefined'", timeout=60000)
    added = page.evaluate("() => { const ic = STYLE_ICONS[0], lk = ic.looks[3]; addIconLookToLookbook(ic, lk); return { id: 'iconlook-' + lk.spec, title: ic.name, toast: document.getElementById('toast').textContent }; }")
    assert "Looks" in added["toast"] and "lookbook" not in added["toast"].lower(), added
    page.evaluate("() => document.querySelector('#bottombar [data-section=\"ideas\"]').click()")
    page.wait_for_timeout(600)
    page.evaluate("() => document.querySelector('[data-lk-go=\"liked\"]').click()")
    page.wait_for_timeout(1500)
    titles = page.evaluate("() => [...document.querySelectorAll('#lk-liked841 .oc-title')].map(e => e.textContent)")
    assert any(t.startswith(added["title"]) for t in titles), titles
    assert "Alexander Kraft — The Riviera uniform" in titles, titles   # the one saved by the old button shows too
    assert not errors, errors
    ctx.close()
    return len(titles)


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        n = run(browser)
        print("Confirmed: Add to Looks lands in Looks > Liked (%d liked looks shown), including looks saved by the old lookbook button" % n)
        browser.close()
