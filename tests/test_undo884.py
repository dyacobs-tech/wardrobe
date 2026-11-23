"""Deleting a closet piece offers Undo, and Undo brings it back (.86.84).

From the audit David asked to have fixed ("Just start going through ALL of these in order"): deleting a piece
or a wardrobe rule had no Undo, so one slip lost it.
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
    ctx.add_init_script("if(!sessionStorage.getItem('u884')){sessionStorage.setItem('u884','1');localStorage.setItem('wardrobe.items',%s)}" % json.dumps(json.dumps(photographed_closet())))
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => typeof renderItemDetail === 'function' && wardrobeItems.length > 0")

    # 1. delete a piece (two taps), then Undo
    page.locator("#tab-wardrobe").dispatch_event("click")
    page.wait_for_timeout(300)
    target = page.evaluate("() => { const it = wardrobeItems.find(i => i.id.indexOf('seed-') !== 0) || wardrobeItems[0]; detailItemId = it.id; renderItemDetail(); return [it.id, it.name, wardrobeItems.length]; }")
    page.wait_for_timeout(200)
    btn = page.locator('#item-detail [data-item-act="delete"]')
    btn.click()
    btn.click()
    page.wait_for_timeout(200)
    assert page.evaluate("(id) => !wardrobeItems.some(i => i.id === id)", target[0]), "piece was not deleted"
    assert page.evaluate("() => !document.getElementById('undo-toast').hidden"), "no Undo after deleting a piece"
    page.evaluate("() => document.getElementById('undo-btn').click()")
    page.wait_for_timeout(200)
    back = page.evaluate("(id) => [wardrobeItems.some(i => i.id === id), wardrobeItems.length, (id.indexOf('seed-') === 0 ? !JSON.parse(localStorage.getItem('wardrobe.deletedIds') || '[]').includes(id) : JSON.parse(localStorage.getItem('wardrobe.items')).some(i => i.id === id))]", target[0])
    assert back[0] and back[1] == target[2] and back[2], ("Undo did not bring the piece back", back)

    browser.close()
print("Confirmed deleting a piece offers Undo and Undo restores it")
