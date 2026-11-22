"""Home shows once, settled, when the app opens (.86.50).

David, 22 Nov 2026: "When I open the app it's flickers isn't smooth".

Home is assembled by about two dozen code files run one after another, and
the screen used to repaint between them (the picture changed height several
times, the level label flipped, the buttons moved). Home's panel now stays
clear until the loader has run its last file and nothing on Home has moved
for a quarter of a second, then shows once. The header and the nav bar are
never hidden. It always shows within about 3 seconds, at once on a touch,
and the cover is never used when the app opens on another tab.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

RECORD = """() => {
  window.__fr = []; const t0 = performance.now();
  const sig = () => { const P = document.getElementById('panel-today'); if (!P) return null;
    const im = document.getElementById('today-img'), row = document.getElementById('today-simple-actions'), cap = P.querySelector('.today-caption');
    const a = im ? im.getBoundingClientRect() : { top: 0, height: 0 }, b = row ? row.getBoundingClientRect() : { top: 0, height: 0 };
    const nav = document.getElementById('bottombar'), head = document.getElementById('tab-profile');
    const vis = e => !e ? null : getComputedStyle(e).opacity !== '0' && getComputedStyle(e).visibility !== 'hidden' && e.getBoundingClientRect().height > 0;
    return { covered: document.documentElement.classList.contains('home-cover850'), opacity: getComputedStyle(P).opacity, nav: vis(nav), head: vis(head),
      s: [Math.round(a.top), Math.round(a.height), Math.round(b.top), Math.round(b.height), cap ? cap.textContent.replace(/\\s+/g, ' ').trim() : ''].join('|') }; };
  const loop = () => { const f = sig(); if (f) { f.t = Math.round(performance.now() - t0); window.__fr.push(f); } if (performance.now() - t0 < 6000) requestAnimationFrame(loop); };
  requestAnimationFrame(loop);
}"""


def context(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL)
              and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," +
                        json.dumps(json.dumps(photographed_closet())) + ");" +
                        "localStorage.setItem('wardrobe.formality','2')")
    return ctx


def run(browser):
    # 1. a plain open on Home
    ctx = context(browser)
    ctx.add_init_script("(" + RECORD + ")()")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.__homeShownAt850 > 0", timeout=8000)
    page.wait_for_timeout(2500)
    fr = page.evaluate("() => window.__fr")
    covered = [f for f in fr if f["covered"]]
    shown = [f for f in fr if not f["covered"]]
    assert covered and shown, (len(covered), len(shown))
    assert all(f["opacity"] == "0" for f in covered), [f for f in covered if f["opacity"] != "0"][:3]
    # from the moment each exists in the page, the header and the nav bar are showing (also under the cover)
    bad = [f for f in fr if f["nav"] is False or f["head"] is False]
    assert not bad, ("the nav bar or the header's profile button was hidden during the open", bad[:2], len(bad), len(fr))
    assert any(f["nav"] and f["head"] for f in covered), "the nav bar and the header's profile button were not up while Home was still covered"
    assert shown[0]["t"] <= 3400, shown[0]
    assert page.evaluate("() => window.__appRan850 === true")
    # once Home is showing, nothing on it moves or changes
    states = []
    for f in shown:
        if not states or states[-1] != f["s"]:
            states.append(f["s"])
    assert len(states) == 1, states
    # and it faded all the way in
    assert shown[-1]["opacity"] == "1", shown[-1]
    assert page.evaluate("() => { const im = document.getElementById('today-img'); return im.complete && im.naturalWidth > 1 && im.getBoundingClientRect().height > 200; }")
    before = len({f["s"] for f in covered})
    ctx.close()

    # 2. a touch during the open shows Home at once
    ctx = context(browser)
    ctx.add_init_script("""document.addEventListener('readystatechange', () => { if (document.readyState === 'interactive') {
      window.__coveredAtStart = document.documentElement.classList.contains('home-cover850');
      window.dispatchEvent(new Event('touchstart'));
      window.__coveredAfterTouch = document.documentElement.classList.contains('home-cover850'); } })""")
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    t = page.evaluate("() => ({ a: window.__coveredAtStart, b: window.__coveredAfterTouch })")
    assert t == {"a": True, "b": False}, t
    ctx.close()

    # 3. the app opened on another tab is never covered
    ctx = context(browser)
    ctx.add_init_script("document.addEventListener('readystatechange', () => { if (document.readyState === 'interactive') window.__coveredAtStart = document.documentElement.classList.contains('home-cover850'); })")
    page = ctx.new_page()
    page.goto(URL + "#wardrobe", wait_until="domcontentloaded")
    assert page.evaluate("() => window.__coveredAtStart") is False
    ctx.close()
    assert not errors, errors
    return before, shown[0]["t"]


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        before, t = run(browser)
        print("Confirmed: Home showed once at %d ms and did not change afterwards (%d different layouts happened out of sight); header and nav stayed; a touch shows it at once; other tabs are not covered" % (t, before))
        browser.close()
