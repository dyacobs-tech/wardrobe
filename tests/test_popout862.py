"""Tapping the outfit on Home opens that same picture, never another outfit's (.86.62).

David, 22 Nov 2026, with a screenshot of the full-size photo showing a
burgundy blazer outfit: "When I click on outfit in home page this OTHER wrong
outfit shows up every time what the fuck!!!!" (earlier: "When I click the
first images the second photo came up - this is wrong pls fix").

On a phone a tap on Home's picture opens the full-size photo. It used the
look's stored image, which could be an older picture than the one Home
shows. It now opens the file Home is showing. The test makes the stored image
point at another outfit, as it did on his phone, and taps.
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
    page.wait_for_function("() => window.__homeShownAt850 > 0 && /onbody/.test(document.getElementById('today-img').currentSrc || '')", timeout=30000)
    page.wait_for_timeout(800)
    shown = page.evaluate("() => (document.getElementById('today-img').currentSrc || '').split('/').pop()")
    # the look's stored image now names a different outfit's picture
    page.evaluate("() => { const i = document.getElementById('today-img'); i.setAttribute('data-popout', 'assets/onbody/some-other-outfit.webp'); todayLook.swapPhoto = 'assets/onbody/some-other-outfit.webp'; todayLook.swapComboId = 'stale'; }")
    box = page.evaluate("() => { const r = document.getElementById('today-img').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height * 0.45 }; }")
    page.touchscreen.tap(box["x"], box["y"])
    page.wait_for_timeout(800)
    pop = page.evaluate("() => { const p = document.getElementById('photo-popout'); return p && !p.hidden ? (document.getElementById('popout-img').getAttribute('src') || '') : null; }")
    if pop is not None:
        assert pop.split("/").pop() == shown and "some-other" not in pop, (pop, shown)
    else:
        # a mouse-style click opens the outfit page instead; it must show the same picture too
        ov = page.evaluate("() => { const i = document.getElementById('ov-img'); return i ? (i.currentSrc || i.src || '') : ''; }")
        assert ov.split("/").pop() == shown, (ov, shown)
    assert not errors, errors
    ctx.close()
    return shown, pop


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        shown, pop = run(browser)
        print("Confirmed: tapping Home's %s opens %s" % (shown, pop))
        browser.close()
