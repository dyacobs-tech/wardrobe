"""Mine shows only exact on-body portraits of him; a level with none says so (.86.32)."""
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
CARDS = "#cf-grid article:has([data-cf-open])"


def check(browser, level):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL)
              and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," +
                        json.dumps(json.dumps(photographed_closet())) + ");" +
                        f"localStorage.setItem('wardrobe.formality','{level}')")
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.locator("#section-ideas").tap()
    if level == 5:
        page.wait_for_function("() => window.__cfLooks81 && __cfLooks81().length >= 4")
    else:
        # a level with few renders: wait until the feed has settled
        page.wait_for_function("() => window.__cfLooks81 && (document.querySelector('#cf-grid .mine-empty829') || (__cfLooks81().length >= 1 && !document.querySelector('#cf-grid .en-skel')))")
        page.wait_for_timeout(1500)
    cards = page.locator(CARDS)
    if level == 5:
        first = cards.first.locator("img.mine-avatar")
        expect(first).to_be_visible()
        page.wait_for_function("() => document.querySelector('#cf-grid .mine-avatar')?.naturalWidth > 20")
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
        page.wait_for_function("n => __cfLooks81().length > n", arg=count)
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
