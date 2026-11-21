"""Mine shows only exact on-body portraits of him; a level with none says so (.86.32)."""
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
CARDS = "#cf-grid article:has([data-cf-open])"


STATE_JS = """() => ({
  looks: window.__cfLooks81 ? __cfLooks81().length : null,
  cards: document.querySelectorAll('#cf-grid article').length,
  skeletons: document.querySelectorAll('#cf-grid .en-skel').length,
  empty: !!document.querySelector('#cf-grid .mine-empty829'),
  tab: typeof currentTab !== 'undefined' ? currentTab : null,
  mode: document.documentElement.getAttribute('data-lkm'),
  renders: (window.ONBODY && ONBODY.map) ? Object.keys(ONBODY.map).length : null,
  avatarWidth: (document.querySelector('#cf-grid .mine-avatar') || {}).naturalWidth || 0 })"""


def wait(page, js, what, where, errors, arg=None):
    """wait_for_function that says which step stalled and what the feed looked like.

    This file failed once in CI (21 Nov, run 197) with a bare 30s timeout and
    passed on the commits either side; the message now names the engine, the
    dress level, the step and the feed state.
    """
    try:
        page.wait_for_function(js, arg=arg)
    except Exception as e:
        try:
            state = page.evaluate(STATE_JS)
        except Exception as e2:  # the page itself is gone
            state = "unreadable: %s" % e2
        raise AssertionError("FAIL %s: timed out waiting for %s; feed state %s; page errors %s" % (where, what, state, errors[:3])) from e


def check(browser, level):
    where = "%s, dress level %s" % (browser.browser_type.name, level)
    errors = []
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL)
              and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," +
                        json.dumps(json.dumps(photographed_closet())) + ");" +
                        f"localStorage.setItem('wardrobe.formality','{level}')")
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)[:200]))
    page.goto(URL, wait_until="domcontentloaded")
    page.locator("#section-ideas").tap()
    if level == 5:
        wait(page, "() => window.__cfLooks81 && __cfLooks81().length >= 4", "four dealt looks", where, errors)
    else:
        # a level with few renders: wait until the feed has settled
        wait(page, "() => window.__cfLooks81 && (document.querySelector('#cf-grid .mine-empty829') || (__cfLooks81().length >= 1 && !document.querySelector('#cf-grid .en-skel')))", "the feed to settle", where, errors)
        page.wait_for_timeout(1500)
    cards = page.locator(CARDS)
    if level == 5:
        first = cards.first.locator("img.mine-avatar")
        expect(first).to_be_visible()
        wait(page, "() => document.querySelector('#cf-grid .mine-avatar')?.naturalWidth > 20", "the first avatar image to load", where, errors)
        verified = cards.evaluate_all("""cards => cards.slice(0, 8).map(card => {
          const button = card.querySelector('[data-cf-open]');
          const look = __cfLooks81()[Number(button.dataset.cfOpen)];
          const photo = ONBODY.map[look.composerKey];
          const image = button.querySelector('.mine-avatar');
          return !!photo && !!image && image.getAttribute('src') === (cutoutFor(photo) || photo)
            && button.querySelectorAll('img').length === 1 && !card.querySelector('[data-cf-rme]');
        })""")
        assert len(verified) >= 4 and all(verified), verified
        if os.environ.get("SHOTS"):
            page.screenshot(path=str(Path(os.environ["SHOTS"]) / "looks-mine-avatars.png"))
        button = cards.first.locator("[data-cf-open]")
        title = button.get_attribute("aria-label")
        button.tap()
        expect(page.locator("#look-layer-body")).to_contain_text(title)
        page.locator("#look-layer-close").tap()
        count = cards.count()
        cards.last.scroll_into_view_if_needed()
        wait(page, "n => __cfLooks81().length > n", "more looks after scrolling to the last card (had %d)" % count, where, errors, arg=count)
        assert page.evaluate("() => new Set(__cfLooks81().map(l => l.composerKey)).size === __cfLooks81().length")
        print(f"Confirmed {len(verified)} exact outfit portraits, detail and additional unique cards")
    else:
        # .86.32 (David, 21 Nov: "always on avatar"): Mine shows only outfits
        # rendered on him; a level with none says so instead of flat-lays.
        assert page.locator("#cf-grid [data-cf-rme]").count() == 0
        assert cards.evaluate_all("cards => cards.every(c => !!c.querySelector('.mine-avatar'))")
        if not cards.count():
            expect(page.locator("#cf-grid .mine-empty829")).to_be_visible()
        print("Confirmed Mine shows only outfits rendered on him (%d cards)" % cards.count())
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        for level in (5, 2):
            check(browser, level)
        browser.close()
