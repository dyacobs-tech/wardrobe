"""Looks opens fast: the outfit dealer is warmed up early and builds only what Outfits shows (.86.55).

David, 22 Nov 2026: "Looks is loading SLOW pls make fast and seamless".

Three causes, each checked here:
  * The background dealer was only started by the first tap on Looks. It is
    started once Home has shown and the app is idle.
  * On start it built every combination in the closet before answering, though
    Outfits only shows outfits that have a picture of him. It builds only those.
  * A hidden screen ("On you") was filled with full-size pictures whenever
    prices refreshed. A hidden screen is left alone.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");localStorage.setItem('wardrobe.formality','2')")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    # 1. without touching anything, the dealer starts and is ready while he is still on Home
    page.wait_for_function("() => window.__endless81 && __endless81.stats && __endless81.stats().ready && __endless81.stats().buf.mine >= 4", timeout=15000)
    warm = page.evaluate("""() => ({ tab: currentTab, ready: __endless81.stats().ready, pictured: Object.keys(onbodyKeys() || {}).length,
      everything: (() => { const tops = wardrobeItems.filter(i => /Tees|Polos|Shirts/.test(i.category)).length, bots = wardrobeItems.filter(i => /Trousers|Jeans|Shorts/.test(i.category)).length, shoes = wardrobeItems.filter(i => i.category === 'Shoes').length; return tops * bots * shoes; })() })""")
    assert warm["tab"] == "today", warm
    # 2. it built the pictured outfits, not every combination in the closet
    assert warm["pictured"] > 0 and 0 < warm["ready"]["mine"] <= warm["pictured"] * 2, warm
    assert warm["ready"]["mine"] < warm["everything"] / 4, warm
    # 3. a tap on Looks shows real outfit cards with pictures at once
    took = page.evaluate("""() => new Promise(res => { const t0 = performance.now(); document.getElementById('section-ideas').click();
      const tick = () => { const cards = [...document.querySelectorAll('#panel-looks #cf-grid .cf-card:not(.en-skel)')].filter(c => c.offsetParent && c.querySelector('img'));
        if (cards.length >= 2) return res({ ms: Math.round(performance.now() - t0), cards: cards.length, pictured: __cfLooks81().every(l => !!onbodyForLook(l)) });
        if (performance.now() - t0 > 8000) return res({ ms: -1, cards: cards.length }); requestAnimationFrame(tick); }; tick(); })""")
    assert 0 <= took["ms"] < 1200 and took["pictured"], took
    # more outfits arrive on scroll, each once
    for _ in range(4):
        page.evaluate("() => window.scrollTo(0, document.scrollingElement.scrollHeight)")
        page.wait_for_timeout(500)
    more = page.evaluate("() => ({ n: __cfLooks81().length, uniq: new Set(__cfLooks81().map(l => l.composerKey)).size, pictured: __cfLooks81().every(l => !!onbodyForLook(l)) })")
    assert more["n"] == more["uniq"] and more["n"] >= took["cards"] and more["pictured"], more
    # 4. the hidden "On you" screen is not filled; it is filled when it is shown
    hidden = page.evaluate("""() => { const h = document.getElementById('panel-onyou'); if (!h) return null; h.hidden = true; h.innerHTML = ''; renderInspoOnYou(); const a = h.innerHTML.length; h.hidden = false; renderInspoOnYou(); const b = h.innerHTML.length; h.hidden = true; return { a, b }; }""")
    assert hidden is None or (hidden["a"] == 0 and hidden["b"] > 0), hidden
    # the same list is not worked out again for every batch
    same = page.evaluate("() => { const a = onbodyKeys(), b = onbodyKeys(); a.__x = 1; return { equal: JSON.stringify(Object.keys(b).sort()) === JSON.stringify(Object.keys(a).filter(k => k !== '__x').sort()), leak: '__x' in onbodyKeys() }; }")
    assert same == {"equal": True, "leak": False}, same
    assert not errors, errors
    ctx.close()
    return warm["ready"]["mine"], warm["everything"], took["ms"]


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        mine, everything, ms = run(browser)
        print("Confirmed: dealer ready on Home having built %d pictured outfits (closet has at least %d combinations); Looks showed outfits %d ms after the tap; hidden screen left alone" % (mine, everything, ms))
        browser.close()
