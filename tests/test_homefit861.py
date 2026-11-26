"""Home never grows taller than the screen, never scrolls, and the nav never shrinks there (.86.61, pinned .86.68).

David, 22 Nov 2026, with a screenshot of Home in the installed app: the page
had scrolled, the figure sat behind DONNA and the nav had shrunk to bare
icons. "Front page here icons are hidden again - pls make sure you fix this
sizing permanently !!!!! We've had to go back and forth with it !!!!!"

Earlier fixes (.80.31, .86.41, .86.52) each sized Home from a reading of the
window. Now Home also checks itself after layout: if anything on the phone
makes the page taller than the screen, the picture gives up the difference,
and Home stays at the top.

Again on 22 Nov, evening, on the live app: "NOT FITTING AGAIN PUCTURE TOO BIG
AND ICONS HIDDEN UNDER NAVI HOW HARD IS THIS TO GET RIGHT AND STAY
CONSISTANT!!!!!" (.86.68): Home is now pinned between the masthead's real
bottom edge and the nav, with no height worked out from the window size.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
W, H = 402, 874

MEASURE = """() => { const q = s => document.querySelector(s);
  return { body: document.body.scrollHeight, sy: Math.round(scrollY), trim: getComputedStyle(document.documentElement).getPropertyValue('--home-trim').trim(),
    actions: Math.round(q('#today-simple-actions').getBoundingClientRect().bottom), nav: Math.round(q('#bottombar .nav-pill').getBoundingClientRect().top),
    img: Math.round(q('#today-img').getBoundingClientRect().height) }; }"""


def run(browser):
    ctx = browser.new_context(viewport={"width": W, "height": H}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");localStorage.setItem('wardrobe.formality','5')")
    # level 5 (Nighttime Dressy), not 6: since .87.23 Formal only shows outfits with a tie, and this sample
    # closet has no ties, so Formal would show its empty card and there would be no picture to measure
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__homeShownAt850 > 0 && typeof window.__wardrobeFitToday === 'function'", timeout=15000)
    page.wait_for_timeout(1500)
    before = page.evaluate(MEASURE)
    assert before["body"] <= H and before["sy"] == 0 and before["actions"] <= before["nav"], before
    # something on the phone adds 40px below Home (as the home-indicator area did on his phone) and the page has scrolled
    page.evaluate("() => { const x = document.createElement('div'); x.style.height = '40px'; document.getElementById('panel-today').after(x); window.scrollTo(0, 40); window.__wardrobeFitToday(); }")
    page.wait_for_timeout(300)
    after = page.evaluate(MEASURE)
    assert after["body"] <= H and after["sy"] == 0, after
    # .86.68: Home is pinned between the masthead and the nav, so extra height elsewhere cannot push it
    assert after["actions"] <= after["nav"] and after["img"] == before["img"], (before, after)
    # and with an iPhone status bar the masthead grows: the picture starts below it, the buttons stay above the nav
    page.evaluate("() => { document.querySelector('header.masthead').style.paddingTop = '59px'; window.__wardrobeFitToday(); }")
    page.wait_for_timeout(300)
    sb = page.evaluate("() => { const r = s => document.querySelector(s).getBoundingClientRect(); return { mast: Math.round(r('header.masthead').bottom), img: Math.round(r('#today-img').top), actions: Math.round(r('#today-simple-actions').bottom), nav: Math.round(r('#bottombar .nav-pill').top), sy: Math.round(scrollY) }; }")
    assert sb["img"] >= sb["mast"] - 1 and sb["actions"] <= sb["nav"] and sb["sy"] == 0, sb
    # and Home cannot be scrolled by hand
    page.evaluate("() => window.scrollBy(0, 200)")
    page.wait_for_timeout(200)
    assert page.evaluate("() => Math.round(scrollY)") == 0
    assert not errors, errors
    ctx.close()
    return after


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        a = run(browser)
        print("Confirmed: Home stays one screen and at the top; the picture starts under the masthead (status bar or not) and the buttons stay above the nav")
        browser.close()
