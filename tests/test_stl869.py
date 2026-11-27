"""An icon's photo opens Shop the look and Add to Looks, and Shop the look lands on that outfit's pieces (.86.69).

David (21 Nov 2026), on the icon lookboard: "Shop the look button doesn't work /
Add to lookbook doesn't work on main page / Nor does inspo / So this entire
feature set is broken". Shop opened empty: the Shop tab swapped the chosen
look for Home's outfit, or let it go when that outfit was all his own.
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
    page.evaluate("() => switchTab('inspo')")
    page.wait_for_selector("[data-ins-icon]", timeout=30000)
    page.evaluate("() => document.querySelector('[data-ins-icon]').click()")
    page.wait_for_selector("[data-ins-look868]", timeout=15000)
    n = page.evaluate("() => document.querySelectorAll('#ins-icon841 [data-ins-look868]').length")
    assert 10 <= n <= 12, n
    page.evaluate("() => document.querySelector('[data-ins-look868]').click()")
    page.wait_for_selector("#ins-look-sheet868:not([hidden]) [data-find-icon-look]", timeout=10000)
    btns = page.evaluate("() => [...document.querySelectorAll('#ins-look-sheet868 button')].map(b => b.textContent.trim())")
    assert "Shop the look" in btns and "Add to Looks" in btns, btns
    page.evaluate("() => document.querySelector('#ins-look-sheet868 [data-find-icon-look]').click()")
    page.wait_for_selector("#find-sheet:not([hidden]) [data-find-sheet-piece]", timeout=10000)
    title = page.evaluate("() => findSheetLook && findSheetLook.title")
    page.evaluate("() => document.querySelector('#find-sheet [data-find-sheet-piece]').click()")
    page.wait_for_timeout(2500)
    st = page.evaluate("""() => ({ page: document.body.getAttribute('data-page'), look: !!(typeof findLookMode !== 'undefined' && findLookMode), title: findLookMode && findLookMode.title,
      filled: (document.getElementById('find-look-mode') || { innerHTML: '' }).innerHTML.length })""")
    assert st["page"] == "find" and st["look"] and st["title"] == title and st["filled"] > 500, (st, title)
    assert not errors, errors
    ctx.close()
    return title


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        t = run(browser)
        print("Confirmed: an icon photo opens Shop the look and Add to Looks; Shop shows '%s' with its pieces" % t)
        browser.close()
