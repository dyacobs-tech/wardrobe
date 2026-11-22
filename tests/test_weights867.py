"""Icon weightings share 100%: moving one slider moves the others in proportion (.86.67).

David, 22 Nov 2026: "Slider weightings don't work they should add to 100 no?"
(his screenshot showed 20, 61, 0, 20, 0, 20, 20 ...).
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ")")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function'", timeout=60000)
    page.evaluate("() => document.querySelector('#bottombar [data-section=\"find\"]').click()")
    page.wait_for_timeout(600)
    page.evaluate("() => document.querySelector('[data-edit-section=\"curate\"]').click()")
    page.wait_for_function("() => document.querySelectorAll('#cw-sliders .cw-row input').length >= 3", timeout=20000)
    read = "() => [...document.querySelectorAll('#cw-sliders .cw-row input')].map(i => +i.value)"
    start = page.evaluate(read)
    assert sum(start) == 100, start
    page.evaluate("() => { const i = document.querySelector('#cw-sliders .cw-row input'); i.value = 70; i.dispatchEvent(new Event('change', { bubbles: true })); }")
    page.wait_for_timeout(300)
    after = page.evaluate(read)
    assert after[0] == 70 and sum(after) == 100, after
    labels = page.evaluate("() => [...document.querySelectorAll('#cw-sliders .cw-val')].map(x => parseInt(x.textContent, 10))")
    assert labels == after, (labels, after)
    # the others keep their proportions
    rest_before = [v for v in start[1:]]
    if sum(rest_before):
        big = max(range(len(rest_before)), key=lambda k: rest_before[k])
        assert after[1 + big] == max(after[1:]), (start, after)
    assert not errors, errors
    ctx.close()
    return after


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        a = run(browser)
        print("Confirmed: icon weightings add to 100 (%s)" % a)
        browser.close()
