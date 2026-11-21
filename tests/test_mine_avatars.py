"""Mine opens on exact on-body portraits and offers rendering for unmatched outfits."""
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
    page.wait_for_function("() => window.__cfLooks81 && __cfLooks81().length >= 4")
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
        card = cards.filter(has=page.locator("[data-cf-rme]")).first
        expect(card.get_by_role("button", name="Render me")).to_be_visible()
        expect(card.locator(".flatlay .fl-cell").first).to_be_visible()
        expect(card.locator(".mine-avatar")).to_have_count(0)
        print("Confirmed unmatched outfit shows its pieces and Render me")
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        for level in (5, 2):
            check(browser, level)
        browser.close()
