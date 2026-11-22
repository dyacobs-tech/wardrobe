"""Formatting audit: no squashed buttons on Profile, Looks > Closet or Shop (.86.62).

David, 22 Nov 2026: "Want formatting to be DIALED!!!! Make sure all pages for
viewing are correct in formatting and buttons are smushed or hidden!!!!"

Every page was checked at 402px. Fixed: Profile's Info / Location / Rules /
Advanced pills (33-69px wide, 4px padding); the Closet search box crushed to
"Sear" beside its filters; Shop's Saved / Searches / Build / Ask / Price row
with the counts against the edge; "+ Look" 24px tall; Profile size boxes out
of line when a label ran to two lines.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
W, H = 402, 874


def run(browser):
    ctx = browser.new_context(viewport={"width": W, "height": H}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ")")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function'", timeout=60000)

    # Profile tabs: roomy pills, all on screen
    page.evaluate("() => switchTab('pinfo')")
    page.wait_for_timeout(800)
    tabs = page.evaluate("() => [...document.querySelectorAll('#subnav-me .subnav-scroll .subtab')].map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), Math.round(r.left), Math.round(r.right)]; })")
    assert len(tabs) == 4 and all(w >= 48 and h >= 36 and l >= 0 and r <= W for w, h, l, r in tabs), tabs
    # Profile sizes: the two boxes in a row sit level even when one label wraps
    rows = page.evaluate("""() => { const ins = [...document.querySelectorAll('.profile-grid input:not([type=file])')].filter(i => i.getBoundingClientRect().width > 0);
      const grids = [...document.querySelectorAll('.profile-grid')], by = {}; ins.forEach(i => { const g = i.closest('.profile-grid'), cells = [...g.children], k = cells.indexOf(i.closest('.profile-grid > *')), key = grids.indexOf(g) + '|' + Math.floor(k / 2); (by[key] = by[key] || []).push([Math.round(i.getBoundingClientRect().bottom), Math.round(i.getBoundingClientRect().left)]); });
      return Object.values(by).filter(v => v.length === 2 && v[0][1] !== v[1][1]).map(v => [v[0][0], v[1][0]]); }""")
    assert rows and all(abs(a - b) <= 1 for a, b in rows), rows

    # Looks > Closet: the search box has its own full row
    page.evaluate("() => switchTab('wardrobe')")
    page.wait_for_timeout(1000)
    sw = page.evaluate("() => Math.round(document.getElementById('ward-search').getBoundingClientRect().width)")
    assert sw >= W - 60, sw

    # Shop: Saved / Searches / Build / Ask / Price, nothing cut, the counts clear of the edge
    page.evaluate("() => switchTab('find')")
    page.wait_for_timeout(1000)
    cells = page.evaluate("""() => [...document.querySelectorAll('#panel-find .outfits-toggle:has(> #edit-tab-saved) > .chip')].filter(e => e.getBoundingClientRect().width > 0)
      .map(e => ({ t: e.textContent.trim(), cut: e.scrollWidth > e.clientWidth + 1, r: Math.round(e.getBoundingClientRect().right) }))""")
    assert len(cells) == 5 and not any(c["cut"] for c in cells) and all(c["r"] <= W for c in cells), cells
    assert not errors, errors
    ctx.close()
    return tabs, sw


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        tabs, sw = run(browser)
        print("Confirmed: Profile tabs %s; Closet search %dpx wide; Shop row uncut; size boxes level" % ([t[:2] for t in tabs], sw))
        browser.close()
