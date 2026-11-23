"""On Home he stands the same height in every picture, whichever look is dealt (.86.74).

David, 23 Nov 2026, on four Home pictures side by side: "My height isn't
consistent throughout these!!!!!!!" The drawings put him between 1088 and 1165px
tall (head to sole) in the 1200px frame; Home now scales each one to the same
height, anchored on his feet.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

PROBE = """() => { const im = document.getElementById('today-img'), F = window.heroFeet801 && window.heroFeet801();
  const m = String(im.getAttribute('src') || '').match(/onbody-cut\\/([^\\/?#]+?)\\.(webp|png)/); const f = m && F && F[m[1]];
  if (!f) return null; const k = parseFloat(im.style.scale || '1') || 1;
  const cs = getComputedStyle(im), w = im.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight), h = im.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
  const s = Math.min(w / 362, h / 1200); return { id: m[1], fig: 1200 - f[0] - f[2], k, px: (1200 - f[0] - f[2]) * s * k }; }"""


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ")")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && window.heroFeet801 && window.heroFeet801()", timeout=60000)
    seen = {}
    for _ in range(14):
        page.wait_for_timeout(700)
        r = page.evaluate(PROBE)
        if r:
            seen[r["id"]] = r
        page.evaluate("() => document.getElementById('today-next').click()")
    figs = [r["fig"] for r in seen.values()]
    px = [r["px"] for r in seen.values()]
    assert len(seen) >= 4, seen
    assert max(px) - min(px) <= 3 or max(figs) - min(figs) < 3, (sorted(px), sorted(figs))   # within 3px on screen
    assert not errors, errors
    ctx.close()
    return len(seen), min(figs), max(figs), min(px), max(px)


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        n, f0, f1, p0, p1 = run(browser)
        print("Confirmed: %d looks drawn %d-%dpx tall all show him %.1f-%.1fpx tall on Home" % (n, f0, f1, p0, p1))
        browser.close()
