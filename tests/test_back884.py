"""Back closes open sheets and steps back through sub-tabs; one Back on the outfit sheet; Edit pictures open (.86.84).

From the audit David asked to have fixed ("Just start going through ALL of these in order"): Back did nothing while a
sheet was open (Shop +, Filters, Price, Calendar month), skipped sub-tabs straight to Home, two Back buttons
overlapped on the outfit sheet, and tapping an outfit picture in The Edit did nothing.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
    ctx.add_init_script("if(!sessionStorage.getItem('b884')){sessionStorage.setItem('b884','1');localStorage.setItem('wardrobe.items',%s);localStorage.setItem('wardrobe.formality','4')}" % json.dumps(json.dumps(photographed_closet())))
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => typeof window.editShow === 'function' && typeof viewBack === 'function'")

    # 1. a sheet open: Back closes it
    page.locator("#tab-find").first.dispatch_event("click")
    page.wait_for_timeout(500)
    plus = page.locator("#shop-plus, [data-shop-plus], button[aria-label^='Add']").first
    if plus.count():
        plus.click()
    else:
        page.evaluate("() => { document.getElementById('shop-plus-sheet').hidden = false; }")
    page.wait_for_timeout(300)
    assert page.evaluate("() => !document.getElementById('shop-plus-sheet').hidden"), "Shop + sheet did not open"
    page.evaluate("() => viewBack()")
    page.wait_for_timeout(300)
    assert page.evaluate("() => { const s = document.getElementById('shop-plus-sheet'); return s.hidden || s.getClientRects().length === 0; }"), "Back left the sheet open"
    assert page.evaluate("() => currentTab") == "find", "Back left Shop instead of only closing the sheet"

    # 2. Shop sub-tabs: Saved -> Build, Back returns to Saved (not Home)
    page.evaluate("() => window.editShow('saved')")
    page.locator("#edit-tab-build").click()
    page.wait_for_timeout(300)
    assert page.evaluate("() => document.getElementById('panel-find').getAttribute('data-edit-mode')") == "build"
    page.evaluate("() => viewBack()")
    page.wait_for_timeout(300)
    state = page.evaluate("() => [currentTab, document.getElementById('panel-find').getAttribute('data-edit-mode')]")
    assert state == ["find", "saved"], ("Back did not step back to Saved", state)

    # 3. The Edit: tapping the picture of an outfit opens it in Dress me
    page.locator("#section-inspo").click()
    page.wait_for_function("() => document.querySelector('.en-card:not(.en-skel) .en-media')", timeout=30000)
    page.locator(".en-card:not(.en-skel) .en-media").first.click()
    page.wait_for_function("() => document.documentElement.getAttribute('data-insv') === 'dress'", timeout=5000)

    # 4. outfit sheet: only its own Back is shown
    page.locator("#section-ideas").click()
    page.wait_for_function("() => document.querySelector('#cf-grid [data-cf-open]')", timeout=30000)
    page.locator("#cf-grid [data-cf-open]").first.click()
    page.wait_for_timeout(500)
    assert page.evaluate("() => !document.getElementById('look-layer').hidden"), "outfit sheet did not open"
    assert page.evaluate("() => getComputedStyle(document.getElementById('view-back')).display") == "none", "two Back buttons on the outfit sheet"
    browser.close()
print("Confirmed Back closes sheets and steps through sub-tabs; Edit pictures open; one Back on the outfit sheet")
