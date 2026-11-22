"""Home is sized to the whole screen in the installed iPhone app, even when the window reports short (.86.52).

David, 22 Nov 2026, with a screenshot of Home showing a dead band between the
Like / Next / level buttons and the nav bar: "Too much spacing again between
the icons".

The same fault was fixed on 19 Nov (.80.31) by sizing Home to innerHeight. In
the installed app innerHeight itself can come back a status bar short, so Home
was sized about 62px small again. In the installed app, in portrait, the
screen's own height is used whenever innerHeight is short of it by no more
than a status bar. A browser tab is unchanged.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
W, H, SHORT = 402, 874, 62

MEASURE = """() => { const q = s => document.querySelector(s); const row = q('#today-simple-actions').getBoundingClientRect(), pill = q('#bottombar .nav-pill').getBoundingClientRect();
  return { vh: getComputedStyle(document.documentElement).getPropertyValue('--home-vh').trim(), gap: Math.round(pill.top - row.bottom), panel: Math.round(q('#panel-today').getBoundingClientRect().height) }; }"""


def open_home(browser, init):
    ctx = browser.new_context(viewport={"width": W, "height": H}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");localStorage.setItem('wardrobe.formality','2');" + init)
    page = ctx.new_page()
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__homeShownAt850 > 0", timeout=8000)
    page.wait_for_timeout(3200)
    m = page.evaluate(MEASURE)
    ctx.close()
    return m


def run(browser):
    short = "Object.defineProperty(window, 'innerHeight', { configurable: true, get: () => %d });" % (H - SHORT)
    screen = "Object.defineProperty(window.screen, 'height', { configurable: true, get: () => %d }); Object.defineProperty(window.screen, 'width', { configurable: true, get: () => %d });" % (H, W)
    app = "Object.defineProperty(navigator, 'standalone', { configurable: true, get: () => true });"
    tab = open_home(browser, "")
    assert tab["vh"] == "%dpx" % H, tab
    # a browser tab whose window is short (toolbar showing) keeps the short height: nothing changes there
    tab_short = open_home(browser, short + screen)
    assert tab_short["vh"] == "%dpx" % (H - SHORT), tab_short   # the reading is kept; Home no longer sizes from it
    # the installed app with a short reading is sized to the screen, and the buttons sit just above the nav
    inst = open_home(browser, short + screen + app)
    assert inst["vh"] == "%dpx" % H, inst
    assert inst["panel"] == tab["panel"] and inst["gap"] == tab["gap"] and 0 <= inst["gap"] <= 40, (inst, tab)
    # .86.68: Home is pinned between the masthead and the nav, so a short report changes nothing on screen
    assert tab_short["panel"] == tab["panel"] and 0 <= tab_short["gap"] <= 40, (tab_short, tab)
    # a reading that is short by much more than a status bar is not trusted to be the screen
    far = open_home(browser, "Object.defineProperty(window, 'innerHeight', { configurable: true, get: () => %d });" % (H - 200) + screen + app)
    assert far["vh"] == "%dpx" % (H - 200), far
    return inst["gap"]


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        gap = run(browser)
        print("Confirmed: installed app with a short window is sized to the full screen; buttons sit %d px above the nav pill; a browser tab is unchanged" % gap)
        browser.close()
