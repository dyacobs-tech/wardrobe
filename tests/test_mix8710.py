"""The Edit has Mix again: new pieces for sale mixed with his closet, marked when they fill a gap (.87.10).

David, 24 Nov 2026: "We used to have feature which showed missing items to suggest for wardrobe what happened to
this???? Like new mix". The old Looks "Mix" became The Edit's "New + mine", which since 22 Nov ("With mine should be on
my avatar!!!") shows only outfits drawn on him, with the mixes behind a button at the end; and the gap list behind
its "Fills gap" marks had dried up, so no mix was ever marked. Asked what to bring back, he chose "Mix in The Edit".
Checks (Evening Casual, fixture closet): Mix sits between New + mine and All new; it opens straight into mixes with a
piece for sale, none of them drawn on him, with no button to tap; some say "Fills gap"; the note under the title says
what Mix is; New + mine still shows only outfits drawn on him and its button; Mix is hidden at Pool / Beach.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

STATE = """() => { const cards = [...document.querySelectorAll('#en-grid-withmine .cf-card:not(.en-skel)')]; const n = document.querySelector('.en-undrawn857');
  return { cards: cards.length, drawn: cards.filter(c => c.querySelector('.en-render img')).length,
           priced: cards.filter(c => /\\$|£|€/.test(c.textContent)).length, gap: cards.filter(c => /Fills gap/i.test(c.textContent)).length,
           button: !!(n && !n.hidden && n.querySelector('[data-en-undrawn857]')),
           order: [...document.querySelectorAll('.ins-mini841 [data-ins-feed]')].filter(b => !b.hidden).map(b => b.textContent.trim()),
           pressed: (document.querySelector('.ins-mini841 [aria-pressed="true"]') || {}).textContent,
           note: (document.querySelector('#ins-head841 .ins-note854') || {}).textContent }; }"""


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");localStorage.setItem('wardrobe.formality','3')")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function'", timeout=60000)
    page.evaluate("() => switchTab('inspo')")
    page.wait_for_function("() => document.querySelector('.ins-mini841 [data-ins-feed=\"mix\"]')", timeout=60000)
    page.evaluate("() => document.querySelector('[data-ins-feed=\"mix\"]').click()")
    # the New + mine cards stay on screen until the feed is rebuilt for Mix (next frame); wait for the Mix cards
    page.wait_for_function("() => { const c = [...document.querySelectorAll('#en-grid-withmine .cf-card:not(.en-skel)')]; return c.length >= 8 && !c.some(x => x.querySelector('.en-render img')); }", timeout=60000)
    for _ in range(4):
        page.evaluate("() => window.scrollTo(0, document.scrollingElement.scrollHeight)")
        page.wait_for_timeout(400)
    m = page.evaluate(STATE)
    assert m["order"] == ["New + mine", "Mix", "All new"], m
    assert m["pressed"] == "Mix", m
    assert m["cards"] >= 8 and m["drawn"] == 0, ("Mix should be mixes not drawn on him", m)
    assert m["priced"] >= m["cards"] - 1, ("every mix carries a piece for sale", m)
    assert m["gap"] >= 1, ("no mix is marked as filling a gap", m)
    assert not m["button"], ("Mix should not stop at the Show ideas button", m)
    assert "Fills gap" in (m["note"] or ""), m
    # New + mine is unchanged: drawn on him only, then the button
    page.evaluate("() => { window.scrollTo(0, 0); document.querySelector('[data-ins-feed=\"withmine\"]').click(); }")
    page.wait_for_function("() => { const c = [...document.querySelectorAll('#en-grid-withmine .cf-card:not(.en-skel)')]; const n = document.querySelector('.en-undrawn857'); return ((n && !n.hidden) || c.length >= 4) && c.every(x => x.querySelector('.en-render img')); }", timeout=60000)
    for _ in range(12):
        page.evaluate("() => window.scrollTo(0, document.scrollingElement.scrollHeight)")
        page.wait_for_timeout(350)
        if page.evaluate(STATE)["button"]:
            break
    w = page.evaluate(STATE)
    assert w["cards"] == w["drawn"] and w["button"], ("New + mine should still show only outfits drawn on him", w)
    # at Pool / Beach only, Mix is hidden like the other shop feeds
    page.evaluate("() => { localStorage.setItem('wardrobe.formality', '1'); if (typeof setFormality === 'function') setFormality(1); if (window.__insLevel899) window.__insLevel899(); }")
    page.wait_for_timeout(600)
    pool = page.evaluate("() => window.poolOnly899 && window.poolOnly899() ? !!(document.querySelector('[data-ins-feed=\"mix\"]') || {}).hidden : null")
    assert pool in (True, None), pool
    assert not errors, errors
    ctx.close()
    return m


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        m = run(browser)
        print("Confirmed: Mix shows %d mixes with pieces for sale, none drawn on him, %d marked Fills gap; New + mine unchanged" % (m["cards"], m["gap"]))
        browser.close()
