"""Looks: the dress level is multi-select like the temperature (.86.38).

David (21 Nov): "Dress level should allow for multiple looks as well."
Ticking levels adds them, the last one cannot be removed, Home keeps a
level that is in the list, the Mine feed mixes the chosen levels (blazer
looks from Nighttime Dressy beside unlayered Daytime looks) and stays
avatar-only, and a few quick ticks refill the feed promptly.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
LEVEL_BTN = '#lk-ctl837 [data-kind="level"] .lk-ddb837'
LABEL = '#lk-ctl837 [data-kind="level"] .lk-ddl837'


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL)
              and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," +
                        json.dumps(json.dumps(photographed_closet())) + ");" +
                        "localStorage.setItem('wardrobe.formality','5')")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.locator("#section-ideas").tap()
    page.wait_for_function("() => window.__cfLooks81 && __cfLooks81().length >= 4")

    # the menu offers checkboxes; Home's level starts ticked
    page.locator(LEVEL_BTN).tap()
    items = page.evaluate("""() => [...document.querySelectorAll('#lk-ctl837 [data-kind="level"] .lk-opt837')]
      .map(o => [o.getAttribute('role'), o.dataset.level, o.getAttribute('aria-checked')])""")
    assert all(r == "menuitemcheckbox" for r, _, _ in items), items
    assert [lv for _, lv, on in items if on == "true"] == ["5"], items

    # tick Daytime: both stay ticked, the menu stays open, Home keeps its level
    page.locator('#lk-ctl837 [data-level="2"]').tap()
    assert page.evaluate("() => window.dressLevels838.get()") == [2, 5]
    assert page.evaluate("() => !document.querySelector('#lk-ctl837 [data-kind=\"level\"] .lk-menu837').hidden")
    assert page.evaluate("() => formalityLevel") == 5
    label = page.locator(LABEL).text_content()
    assert label == "Day + Dressy", label
    assert page.evaluate(f"() => {{ const e = document.querySelector('{LABEL}'); return e.scrollWidth <= e.clientWidth; }}"), "label is cut off"
    page.keyboard.press("Escape")

    # the Mine feed mixes both levels and stays avatar-only
    page.wait_for_function("""() => {
      const L = __cfLooks81();
      const blazer = L.filter(l => (l.fwPieces || []).some(p => /blazer|sport coat/i.test((p.category || '') + ' ' + (p.name || '')))).length;
      return L.length >= 6 && blazer >= 1 && blazer < L.length;
    }""", timeout=20000)
    assert page.evaluate("() => [...document.querySelectorAll('#cf-grid article:has([data-cf-open])')].every(c => !!c.querySelector('.mine-avatar'))")

    # untick Home's level: Home moves to the level that is left
    page.locator(LEVEL_BTN).tap()
    page.locator('#lk-ctl837 [data-level="5"]').tap()
    assert page.evaluate("() => window.dressLevels838.get()") == [2]
    assert page.evaluate("() => formalityLevel") == 2
    # the last level cannot be unticked
    page.locator('#lk-ctl837 [data-level="2"]').tap()
    assert page.evaluate("() => window.dressLevels838.get()") == [2]
    page.keyboard.press("Escape")

    # a change on Home resets Looks to that one level
    page.evaluate("() => setFormality(3, { silent: true })")
    assert page.evaluate("() => window.dressLevels838.get()") == [3]

    # several quick ticks: one refill, and it is prompt
    page.locator(LEVEL_BTN).tap()
    for lv in (2, 5, 6, 6):
        page.locator(f'#lk-ctl837 [data-level="{lv}"]').tap()
    page.keyboard.press("Escape")
    assert page.evaluate("() => window.dressLevels838.get()") == [2, 3, 5]
    page.wait_for_function("() => __cfLooks81().length >= 4", timeout=6000)
    assert page.locator(LABEL).text_content() == "Day +2"

    # .86.39 Mix: ready-made outfits on him carry no style title ("Palm
    # Beach" read as a location) and join only at a ticked level
    page.evaluate("() => window.dressLevels838.set([5])")
    page.locator('#section-inspo').tap()   # .86.42: Mix lives in Inspo (With mine)
    page.wait_for_function("() => document.querySelectorAll('#panel-withmine .en-card .en-render').length >= 2", timeout=20000)
    page.wait_for_timeout(500)
    made = page.evaluate("""() => [...document.querySelectorAll('#panel-withmine .en-card')].filter(c => c.querySelector('.en-render'))
      .map(c => ({ title: !!c.querySelector('.oc-title'), src: !!c.querySelector('.en-src'), alt: c.querySelector('.en-render img').alt }))""")
    assert made, "no ready-made outfits at Nighttime Dressy"
    assert not any(m["title"] or m["src"] for m in made), made
    assert all(any(w in m["alt"].lower() for w in ("blazer", "jacket", "sport coat", "sportcoat", "suit")) for m in made), made

    assert not errors, errors
    print("Confirmed multi-select dress level: ticks, label, Home sync, mixed avatar-only feed; Mix ready-made looks follow the level")
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        browser.close()
