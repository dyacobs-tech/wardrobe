"""Calendar day, photo and month navigation with isolated wardrobe storage."""
import json
import os
import sys
from datetime import datetime, timezone
from playwright.sync_api import expect, sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
DAY = "2027-12-27"
TOMORROW = "2027-12-31"
WORN = [
    {"id": "am", "date": DAY, "title": "Morning suit", "pieces": ["Navy suit", "White shirt"],
     "watch": "Dress watch", "img": "assets/icon-192.png"},
    {"id": "pm", "date": DAY, "title": "Dinner outfit", "pieces": ["Olive knit", "Grey trousers"],
     "img": "assets/icon-512.png"},
    {"id": "friday", "date": TOMORROW, "title": "Morning run", "pieces": ["Running shoes"]},
]


def check(browser):
    ctx = browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                              has_touch=True, timezone_id="America/New_York", service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and
              r.request.method == "GET" else r.abort())
    ctx.add_init_script("if (!localStorage.getItem('wardrobe.wornLog')) localStorage.setItem("
                        "'wardrobe.wornLog'," + json.dumps(json.dumps(WORN)) + ")")
    page = ctx.new_page()
    page.clock.set_fixed_time(datetime(2027, 12, 30, 18, tzinfo=timezone.utc))
    page.goto(URL, wait_until="domcontentloaded")
    page.locator("#section-calendar").tap()
    day = page.locator(f'[data-plan-day="{DAY}"]')
    expect(day.locator(".wp-worn-count")).to_have_text("2")
    day.locator("img").tap()
    expect(page.locator("#plan-sheet")).to_be_visible()
    expect(page.locator(".wp-choice")).to_have_count(2)
    expect(page.locator(".wp-outfit")).to_contain_text("White shirt")
    expect(page.locator(".wp-outfit")).to_contain_text("Dress watch")
    page.get_by_role("button", name="Next outfit", exact=True).tap()
    expect(page.locator(".wp-outfit")).to_contain_text("Grey trousers")
    page.get_by_role("button", name="Enlarge Dinner outfit").tap()
    expect(page.locator("#popout-img")).to_have_attribute("alt", "Dinner outfit")
    page.get_by_role("button", name="Previous outfit photo").tap()
    expect(page.locator("#popout-img")).to_have_attribute("alt", "Morning suit")
    page.locator("#popout-close").tap()
    expect(page.locator(".wp-choice").first).to_have_attribute("aria-pressed", "true")
    page.locator("#plan-sheet-close").tap()
    page.locator("#plan-month-open").tap()
    expect(page.locator("#plan-sheet-title")).to_have_text("December 2027")
    expect(page.locator("[data-month-day]")).to_have_count(31)
    page.locator(f'[data-month-day="{DAY}"]').tap()
    page.locator('[data-outfit-index="1"]').tap()
    expect(page.locator(".wp-outfit")).to_contain_text("Olive knit")
    page.locator("[data-month-back]").tap()
    expect(page.locator(f'[data-month-day="{DAY}"]')).to_be_focused()
    for name in ("January 2028", "February 2028"):
        page.get_by_role("button", name="Next month").tap()
        expect(page.locator("#plan-sheet-title")).to_have_text(name)
    expect(page.locator("[data-month-day]")).to_have_count(29)
    page.locator('[data-month-day="2028-02-29"]').tap()
    expect(page.locator("#plan-sheet-body")).to_contain_text("No outfits recorded")
    expect(page.locator("[data-plan-deal]")).to_be_visible()
    page.locator("#plan-sheet-close").tap()

    # Exercise the real plan storage format on a day that already has a wear.
    added = page.evaluate("""iso => {
      const look = SEED_LOOKS.find(planLookValid);
      return look && setPlanForDate(iso, look) ? look.title : "";
    }""", TOMORROW)
    assert added
    page.reload(wait_until="domcontentloaded")
    page.locator("#section-calendar").tap()
    page.locator("#plan-month-open").tap()
    friday = page.locator(f'[data-month-day="{TOMORROW}"]')
    expect(friday.locator(".wp-month-count")).to_have_text("2")
    friday.tap()
    page.locator('.wp-choice').filter(has_text=added).tap()
    expect(page.locator(".wp-outfit")).to_contain_text(added)
    page.locator("[data-plan-clear]").tap()
    expect(page.locator(f'[data-plan-day="{TOMORROW}"] .wp-worn-count')).to_have_count(0)
    assert page.evaluate("iso => !planEntryFor(iso) && wornForDate(iso).length === 1", TOMORROW)
    ctx.close()


if __name__ == "__main__":
    with sync_playwright() as pw:
        for name in ("chromium", "webkit"):
            opts = {"executable_path": os.environ["CAL_CHROMIUM"]} if name == "chromium" and "CAL_CHROMIUM" in os.environ else {}
            browser = getattr(pw, name).launch(**opts)
            check(browser)
            browser.close()
            print(name, "passed Calendar week, month, photo navigation and plan removal", flush=True)
