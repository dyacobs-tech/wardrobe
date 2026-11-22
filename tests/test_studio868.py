"""The old Ideas studio ("Give me ideas") is retired: every way into it opens The Edit > Inspo (.86.68).

David, 21-22 Nov 2026: "some page called looks - took forever - but isn't shown
or linked anywhere!!!! We need to clean this up" and "This is basically linking
to an old page concept let's clean this up!!!"
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
    for old in ("studio", "outfitideas"):
        page.evaluate("n => switchTab(n)", old)
        page.wait_for_timeout(800)
        st = page.evaluate("""() => ({ page: document.body.getAttribute('data-page'),
          studio: !!(document.getElementById('panel-studio') && !document.getElementById('panel-studio').hidden),
          ideas: (document.querySelector('[data-ins-seg="ideas"]') || { getAttribute: () => null }).getAttribute('aria-selected') })""")
        assert st["page"] == "inspo" and not st["studio"] and st["ideas"] == "true", (old, st)
        page.evaluate("() => switchTab('today')")
        page.wait_for_timeout(300)
    assert not errors, errors
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        print("Confirmed: the old Ideas studio is never shown; its links open The Edit > Inspo")
        browser.close()
