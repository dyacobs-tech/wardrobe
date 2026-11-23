"""Opening an outfit from The Edit shows that outfit, and Back returns to The Edit (.86.79).

David, 23 Nov 2026: "When I click on an outfit in the edit they put on me section shows a different
outfit. When I click back from that page, it goes back to my looks, not to the edit homepage. MUST BE
FIXED!!!!!!"
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
    ctx.add_init_script("if(!sessionStorage.getItem('s879')){sessionStorage.setItem('s879','1');localStorage.setItem('wardrobe.items',%s);localStorage.setItem('wardrobe.formality','4')}" % json.dumps(json.dumps(photographed_closet())))
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    # Looks first, then The Edit: Back must not fall through to Looks
    page.locator("#section-ideas").click()
    page.wait_for_timeout(1200)
    page.locator("#section-inspo").click()
    page.wait_for_function("() => document.querySelector('.en-card:not(.en-skel) [data-pv-edit]')", timeout=30000)
    card = page.locator(".en-card:not(.en-skel)").first
    i = int(card.get_attribute("data-en-i"))
    fig = card.locator(".en-render img").first.get_attribute("src")
    card.locator("[data-pv-edit]").click()
    page.wait_for_function("() => document.documentElement.getAttribute('data-insv') === 'dress'")
    page.wait_for_timeout(500)
    shown = page.evaluate("() => (document.querySelector('.dm-av841 img') || {}).getAttribute ? document.querySelector('.dm-av841 img').getAttribute('src') : null")
    note = page.locator(".dm-note841").count()
    assert shown == fig, ("Dress me shows a different picture from the card tapped", fig, shown)
    assert note == 0, "the card's own picture is labelled Not on you yet"
    assert page.locator("#view-back").is_visible(), "no Back button on Dress me"
    page.locator("#view-back").click()
    page.wait_for_timeout(800)
    state = page.evaluate("() => [currentTab, document.documentElement.getAttribute('data-insv')]")
    assert state[0] == "inspo" and state[1] != "dress", ("Back did not return to The Edit", state)
    assert page.locator(".en-card:not(.en-skel)").first.is_visible(), "The Edit outfits are not showing after Back"
    browser.close()
print("Confirmed an outfit opened from The Edit shows its own picture, and Back returns to The Edit")
