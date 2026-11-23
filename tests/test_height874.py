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
  const m = String(im.getAttribute('src') || '').match(/onbody-cut(?:-hq)?\\/([^\\/?#]+?)\\.(webp|png)/); const f = m && F && F[m[1]];
  if (!f) return null; const k = parseFloat(im.style.scale || '1') || 1;
  const cs = getComputedStyle(im), w = im.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight), h = im.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
  const s = Math.min(w / 362, h / 1200); const T = e => Math.round(document.querySelector(e).getBoundingClientRect().top);
  return { id: m[1], fig: 1200 - f[0] - f[2], k, px: (1200 - f[0] - f[2]) * s * k, name: T('#today-name'), row: T('#today-simple-actions') }; }"""


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
    texts = set()
    for n in range(14):
        page.wait_for_timeout(700)
        if n == 5:   # .86.75: the sharper copy that replaces each picture keeps the same height and placement
            page.evaluate("() => { const im = document.getElementById('today-img'); im.src = im.getAttribute('src').replace('onbody-cut/', 'onbody-cut-hq/'); }")
            page.wait_for_timeout(900)
        r = page.evaluate(PROBE)
        if r:
            seen[r["id"] + str(n == 5)] = r
            texts.add((r["name"], r["row"]))
        page.evaluate("() => document.getElementById('today-next').click()")
    # .86.75 (David, 23 Nov 2026: "My height still fluctuating as it text placement on Home Screen. None of it
    # stays fixed entirely as I scroll through items."): the name and the buttons never move
    assert len(texts) == 1, texts
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


# .86.74, the same day: "MY HEIGHT IS INCONSISTENT THROURGOUT ALMOST ALL IMAGES PINGING BACK AND FORTH"
# every picture of him on every screen, here the Outfits grid, has the same height and the same floor line
GRID = """() => [...document.querySelectorAll('#cf-grid img')].filter(i => i.getBoundingClientRect().width > 40 && i.dataset.h874).map(i => {
  const cs = getComputedStyle(i), k = parseFloat(i.style.scale || '1') || 1, t = (i.style.translate || '0px 0px').split(' ').map(parseFloat);
  const o = cs.transformOrigin.split(' ').map(parseFloat); const f = i.__f874 || null;
  return { k, ty: t[1] || 0, oy: o[1], h: i.clientHeight, src: i.getAttribute('src') }; })"""


def run_grid(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ")")
    page = ctx.new_page()
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function'", timeout=60000)
    page.evaluate("() => switchTab('wardrobe')")
    page.wait_for_timeout(600)
    page.evaluate("() => { const b = document.getElementById('section-ideas'); if (b) b.click(); }")
    page.wait_for_function("() => document.querySelectorAll('#cf-grid img[data-h874]').length >= 4", timeout=30000)
    page.wait_for_timeout(800)
    # where his feet and the top of his head land, measured from each card picture's own top
    out = page.evaluate("""async () => { const F = await (await fetch('assets/onbody-cut/feet.json')).json(), M = await (await fetch('assets/feet-more874.json')).json();
      const RE = /assets\\/(onbody(?:-cut|-cut-hq)?|inspo-cut|inspo-concepts)\\/([^\\/?#]+?)\\.webp/;
      return [...document.querySelectorAll('#cf-grid img[data-h874]')].filter(i => i.clientWidth > 40).map(i => {
        const m = RE.exec(i.getAttribute('src')); const f = /^onbody/.test(m[1]) ? F.feet[m[2]] : M.feet[m[1] + '/' + m[2]];
        const cs = getComputedStyle(i), k = parseFloat(i.style.scale || '1') || 1, ty = parseFloat((i.style.translate || '0 0').split(' ')[1]) || 0;
        const oy = parseFloat(cs.transformOrigin.split(' ')[1]);
        const s = Math.max(i.clientWidth / i.naturalWidth, i.clientHeight / i.naturalHeight), px = i.naturalHeight / 1200 * s;
        const feet = oy + ty, head = oy + ty - (1200 - f[0] - f[2]) * px * k;
        return [Math.round(feet * 10) / 10, Math.round(head * 10) / 10]; }); }""")
    ctx.close()
    return out


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        pts = run_grid(browser)
        feet = [p[0] for p in pts]; head = [p[1] for p in pts]
        assert len(pts) >= 4 and max(feet) - min(feet) <= 3 and max(head) - min(head) <= 3, pts
        print("Confirmed: %d Outfits cards, his feet within %.1fpx and his head within %.1fpx of each other" % (len(pts), max(feet) - min(feet), max(head) - min(head)))
        browser.close()
