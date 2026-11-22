"""A level chosen on Home re-deals Looks > Outfits: Evening Casual never keeps Evening Sharp's blazer looks (.86.68).

David, 22 Nov 2026, with a screenshot of Looks > Outfits at Evening Casual
showing a navy blazer and a taupe blazer: "Evening casual shouldn't have
blazer!!!!!!!" The outfits had been dealt at Evening Sharp; changing the level
on Home did not re-deal them.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");localStorage.setItem('wardrobe.formality','4')")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function' && !!window.dressLevels838", timeout=60000)
    page.evaluate("() => switchTab('looks')")
    page.wait_for_function("() => window.__cfLooks81 && window.__cfLooks81().length > 0", timeout=60000)
    page.wait_for_timeout(1500)
    # Home's level button
    page.evaluate("() => { switchTab('today'); setFormality(3); }")
    page.wait_for_timeout(1200)
    page.evaluate("() => switchTab('looks')")
    page.wait_for_timeout(4000)
    got = page.evaluate("""() => { const C = window.WardrobeComposer;
      const L = window.__cfLooks81();
      return { lv: window.dressLevels838.get(), n: L.length,
        layered: L.filter(l => (l.fwPieces || []).some(p => /^(Blazers|Suits)$/.test(String(p.category || '')))).map(l => l.title) }; }""")
    assert got["lv"] == [3], got
    assert not got["layered"], got
    assert not errors, errors
    ctx.close()
    return got


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        g = run(browser)
        print("Confirmed: after choosing Evening Casual on Home, Outfits has %d looks and no blazer" % g["n"])
        browser.close()
