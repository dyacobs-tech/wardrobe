"""Shop never opens on Ask DONNA, even when the phone had it open last (.86.79).

David, 23 Nov 2026, screenshot of Shop opening on the Ask DONNA chat:
"Shop opening to this page even though we removed ask Donna fix this!!!!!"
Ask DONNA was removed in .86.75 ("Remove ask Donna - this does NOT seem to work.").
"""
import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
        ctx.add_init_script("localStorage.setItem('wardrobe.editView', %s)" % json.dumps(json.dumps("ask")))
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_function("() => typeof window.editShow === 'function'")
        page.locator("#tab-find").first.dispatch_event("click")
        page.wait_for_timeout(1200)
        state = page.evaluate("""() => ({
          mode: document.getElementById('panel-find').getAttribute('data-edit-mode'),
          askHidden: document.getElementById('edit-v-ask').hidden,
          askBox: !!(document.getElementById('ask-q') && document.getElementById('ask-q').offsetParent),
          shopPressed: document.getElementById('edit-tab-shop').getAttribute('aria-pressed') })""")
        assert state["mode"] != "ask" and state["askHidden"] and not state["askBox"], (engine.name, state)
        assert state["shopPressed"] == "true", (engine.name, state)
        # asking for the Ask view directly still lands on Shop
        page.evaluate("() => window.editShow('ask')")
        assert page.evaluate("() => document.getElementById('panel-find').getAttribute('data-edit-mode')") != "ask"
        saved = page.evaluate("() => JSON.parse(localStorage.getItem('wardrobe.editView'))")
        assert saved != "ask", saved
        ctx.close()
        browser.close()
print("Confirmed Shop opens on Shop, never on Ask DONNA, even when Ask was the last view")
