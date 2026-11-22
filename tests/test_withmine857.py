"""The Edit's "with mine" feed shows outfits drawn on him; undrawn ideas are one tap away (.86.57, Icon filter .86.67).

David, 22 Nov 2026, with a screenshot of The Edit showing boxes of pieces
under "With mine": "With mine should be on my avatar!!!"
David, 22 Nov 2026 (later), on Icons > Ideas for you with an Icon filter on,
showing product photos: "I should be on my avatar for these!!!!"
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

STATE = """() => { const cards = [...document.querySelectorAll('#en-grid-withmine .cf-card:not(.en-skel)')]; const n = document.querySelector('.en-undrawn857');
  return { cards: cards.length, drawn: cards.filter(c => c.querySelector('.en-render img')).length, skel: document.querySelectorAll('#en-grid-withmine .en-skel').length,
           note: n && !n.hidden ? n.textContent : null, button: !!(n && !n.hidden && n.querySelector('[data-en-undrawn857]')) }; }"""


def run_lens(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");localStorage.setItem('wardrobe.formality','3')")
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function'", timeout=60000)
    page.evaluate("() => switchTab('inspo')")
    page.wait_for_function("() => !!window.endlessLens81", timeout=60000)
    page.evaluate("() => window.endlessLens81.set('beckham')")
    page.wait_for_function("() => { const n = document.querySelector('.en-undrawn857'); return (n && !n.hidden) || document.querySelectorAll('#en-grid-withmine .cf-card:not(.en-skel)').length >= 4; }", timeout=60000)
    page.wait_for_timeout(800)
    a = page.evaluate(STATE)
    assert a["cards"] == a["drawn"], ("with an Icon filter on, an outfit not drawn on him is in New + mine", a)
    ctx.close()
    return a


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");localStorage.setItem('wardrobe.formality','3')")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    # the app has to have started before the tab is opened (a tap during start-up is lost)
    page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function'", timeout=60000)
    page.evaluate("() => switchTab('inspo')")
    page.wait_for_function("() => { const n = document.querySelector('.en-undrawn857'); return (n && !n.hidden) || document.querySelectorAll('#en-grid-withmine .cf-card:not(.en-skel)').length >= 4; }", timeout=60000)
    # scroll to the end of what is drawn on him
    for _ in range(12):
        page.evaluate("() => window.scrollTo(0, document.scrollingElement.scrollHeight)")
        page.wait_for_timeout(350)
        if page.evaluate(STATE)["button"]:
            break
    a = page.evaluate(STATE)
    assert a["button"] and a["skel"] == 0, a
    assert a["cards"] == a["drawn"], ("an outfit that is not drawn on him is in With mine", a)
    assert ("drawn on you" in a["note"]), a
    # the ideas that are not drawn on him yet are one tap away, and they are marked by having no figure
    page.evaluate("() => document.querySelector('[data-en-undrawn857]').click()")
    page.wait_for_function("n => document.querySelectorAll('#en-grid-withmine .cf-card:not(.en-skel)').length > n", arg=a["cards"], timeout=45000)
    b = page.evaluate(STATE)
    assert b["cards"] > a["cards"] and b["drawn"] == a["drawn"] and b["note"] is None, b
    # All new is untouched: ideas, no figure required
    page.evaluate("() => document.querySelector('[data-ins-feed=\"allnew\"]').click()")
    page.wait_for_function("() => document.querySelectorAll('#en-grid-allnew .cf-card:not(.en-skel)').length >= 2", timeout=45000)
    assert not errors, errors
    ctx.close()
    return a["drawn"], b["cards"] - a["cards"]


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        drawn, more = run(browser)
        lens = run_lens(browser)
        print("Confirmed: With mine showed %d outfits, all drawn on him, then the button; it revealed %d undrawn ideas; All new unchanged; with an Icon filter %d of %d drawn" % (drawn, more, lens["drawn"], lens["cards"]))
        browser.close()
