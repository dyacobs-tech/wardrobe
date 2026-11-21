"""A closet piece's brand can be typed in and edited (.86.44).

David (21 Nov): "You need to allow me to input Brand into the app. Once an
item is uploaded if it is not automatically catalogue by AI." The Add / Edit
form has a Brand field. A piece with no brand offers "Add brand" on its page;
the saved brand shows on the page and in front of the name on the closet card
when the name does not already carry it, is searchable, and is kept on a new
piece too.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"


def run(browser):
    items = photographed_closet()
    items.append({"id": "item-belt-test", "name": "Cognac Croc Belt", "brand": "", "category": "Belts",
                  "colourName": "Cognac", "colourHex": "#7c564b", "extraColours": [], "notes": "", "price": None,
                  "wearCount": 0, "lastWorn": None, "addedISO": "2026-11-21", "laundry": False, "photo": items[0].get("photo")})
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL)
              and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(items)) + ")")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.locator("#section-ideas").tap()
    page.locator('#panel-looks [data-lk-go="wardrobe"]').tap()
    page.wait_for_function("() => document.querySelectorAll('#panel-wardrobe .item-card').length > 5")

    # the piece has no brand: its page offers to add one
    page.evaluate("() => { detailItemId = 'item-belt-test'; renderItemDetail(); }")
    stats = page.locator("#item-detail .wear-stats")
    assert "Brand" in stats.inner_text() and "Add brand" in stats.inner_text(), stats.inner_text()
    page.locator('#item-detail .link-btn844').tap()
    page.wait_for_function("() => document.getElementById('add-form-title').textContent === 'Edit'")
    labels = page.evaluate("() => [...document.querySelectorAll('#add-form label.field')].map(l => l.textContent.trim())")
    assert labels[:2] == ["Name", "Brand"], labels
    assert page.locator("#item-brand").input_value() == ""
    page.locator("#item-brand").tap()
    assert page.evaluate("() => document.querySelectorAll('#item-brand-list option').length") >= 3, "no brand suggestions from his closet"
    page.locator("#item-brand").fill("Ralph Lauren")
    page.locator("#item-submit").tap()
    page.wait_for_function("() => (wardrobeItems.find(i => i.id === 'item-belt-test') || {}).brand === 'Ralph Lauren'")
    saved = page.evaluate("""() => { const it = wardrobeItems.find(i => i.id === 'item-belt-test');
      const stored = JSON.parse(localStorage.getItem('wardrobe.items')).find(i => i.id === 'item-belt-test');
      return { name: it.name, photo: !!it.photo, stored: stored.brand, key: wardBrandKey(it) }; }""")
    assert saved == {"name": "Cognac Croc Belt", "photo": True, "stored": "Ralph Lauren", "key": "Ralph Lauren"}, saved
    page.evaluate("() => { detailItemId = 'item-belt-test'; renderItemDetail(); }")
    assert page.locator("#item-detail h3").inner_text() == "Ralph Lauren Cognac Croc Belt"
    assert "Ralph Lauren" in stats.inner_text() and "Add brand" not in stats.inner_text(), stats.inner_text()
    page.evaluate("() => { detailItemId = null; renderItemDetail(); renderWardrobe(); }")
    names = page.evaluate("() => [...document.querySelectorAll('#panel-wardrobe .item-card .item-name')].map(n => n.textContent)")
    assert "Ralph Lauren Cognac Croc Belt" in names and "Cognac Croc Belt" not in names, [n for n in names if "Croc" in n]

    # editing again shows the brand; a name that already carries it is not doubled
    page.evaluate("() => startItemEdit(wardrobeItems.find(i => i.id === 'item-belt-test'))")
    assert page.locator("#item-brand").input_value() == "Ralph Lauren"
    page.locator("#item-name").fill("Ralph Lauren Cognac Croc Belt")
    page.locator("#item-submit").tap()
    page.wait_for_function("() => (wardrobeItems.find(i => i.id === 'item-belt-test') || {}).name === 'Ralph Lauren Cognac Croc Belt'")
    assert page.evaluate("() => itemDisplayName844(wardrobeItems.find(i => i.id === 'item-belt-test'))") == "Ralph Lauren Cognac Croc Belt"

    # a new piece keeps its brand
    page.evaluate("() => switchTab('add')")
    page.locator("#item-name").fill("Navy Knit Tie")
    page.locator("#item-brand").fill("Drake's")
    page.locator("#item-cat").select_option("Ties")
    page.locator("#item-submit").tap()
    page.wait_for_function("() => wardrobeItems.some(i => i.name === 'Navy Knit Tie')")
    assert page.evaluate("() => wardrobeItems.find(i => i.name === 'Navy Knit Tie').brand") == "Drake's"
    assert page.locator("#item-brand").input_value() == "", "the Brand field was not cleared after saving"
    assert not errors, errors
    print("Confirmed Brand: add from the piece's page, shown on page and card, suggested, kept on edit and on a new piece")
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        browser.close()
