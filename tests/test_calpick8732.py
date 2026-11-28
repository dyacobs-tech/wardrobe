"""Calendar's "Liked & queued" shows only outfits with a picture (.87.32).

The nightly audit of 28 Nov 2026: Calendar, tap today, "Liked & queued": 22 of the 31 tiles were empty picture
boxes. They were liked looks that are colours only (no picture of him, no pieces). Since .86.53 such a look is a
palette (David, 22 Nov 2026: "Palletes should have its own sub page in liked"), so it is not offered as an outfit
to plan. A tile whose picture fails to load is taken out instead of left as a broken box.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and r.request.method == "GET" else r.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ")")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => typeof planCandidates === 'function' && typeof savedLooks !== 'undefined' && window.__cfLooks81 && __cfLooks81().length >= 1", timeout=30000)
    page.evaluate("""() => {
      savedLooks.push({ id: 'pal-1', title: 'Racing Green & Stone', img: 'assets/photos/316150a1e65e.webp', verdict: 'like', likedAt: 1,
        swatches: [{ name: 'Green', hex: '#1f4d3a', role: 'Knit' }, { name: 'Stone', hex: '#cdbb98', role: 'Chinos' }] });
      savedLooks.push(Object.assign({}, __cfLooks81()[0], { id: 'pictured-1', verdict: 'like', likedAt: 2 }));
      savedLooks.push(Object.assign({}, __cfLooks81()[0], { id: 'gone-1', title: 'Missing picture', verdict: 'like', likedAt: 3, composer: false, composerKey: null, fwPieces: [], img: 'assets/onbody/0000000000000000.webp', fwRender: 'assets/onbody/0000000000000000.webp' }));
    }""")
    page.evaluate("() => document.querySelector('#bottombar [data-section=\"calendar\"]').click()")
    page.wait_for_selector(".wp-today", timeout=15000)
    page.evaluate("() => document.querySelector('.wp-today').click()")
    page.wait_for_selector(".wp-pick-grid", timeout=15000)
    page.wait_for_timeout(1500)
    tiles = page.evaluate("""() => [...document.querySelectorAll('.wp-pick-grid .wp-pick')].map(b => { const i = b.querySelector('img');
      return { id: b.getAttribute('data-plan-pick'), src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0 }; })""")
    ids = [t["id"] for t in tiles]
    assert "pal-1" not in ids, ("a colours-only look is offered as an outfit to plan", tiles)
    assert "pictured-1" in ids, ("a liked outfit with a picture is missing", tiles)
    assert "gone-1" not in ids, ("a tile whose picture cannot load was left in", tiles)
    assert all(t["src"] and t["ok"] for t in tiles), ("an empty or broken picture box", tiles)
    assert not errors, errors
    ctx.close()
    return len(tiles)


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        b = engine.launch()
        n = run(b)
        b.close()
print("Confirmed: Calendar's Liked & queued shows %d outfits, each with its picture; a colours-only look and a tile whose picture is gone are left out" % n)
