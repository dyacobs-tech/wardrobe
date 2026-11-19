"""Build .78.3 — Render me in this look (Emulate) against a MOCK try-on worker.

Opens an Icons look with no pre-rendered match, taps Render me in this
look, asserts one POST /tryon with top/outer/bottom/shoes items only,
progress text in the button, the full-length result, Save look into
Outfits → Mine, and that a second tap never posts again (cache).
Never calls production. Run: python -m http.server 8000 & python tests/test_renderme783.py [base]
"""
import json, sys, base64
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
TRY = "https://wardrobe-tryon.dyacobs.workers.dev"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
JOB = "fedcba9876543210fedcba9876543210"
seen = {"posts": [], "polls": 0}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844})
    ctx.add_init_script("localStorage.setItem('wardrobe.sync', JSON.stringify({key:'%s', acct:'test', last:0, snap:{}, st:{}, tomb:{}, dirty:{}, status:'x', lastOk:0}));" % ("b" * 48))
    def route(r):
        u = r.request.url
        if u == TRY + "/tryon" and r.request.method == "POST":
            seen["posts"].append(json.loads(r.request.post_data))
            return r.fulfill(status=202, content_type="application/json", body=json.dumps({"id": JOB, "status": "running", "step": 1, "steps": 4}))
        if u.startswith(TRY + "/tryon/" + JOB):
            seen["polls"] += 1
            done = seen["polls"] >= 3
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"id": JOB, "status": "done" if done else "running", "step": min(4, seen["polls"] + 1), "steps": 4, "resultUrl": TRY + "/r/" + JOB + ".jpg" if done else None}))
        if u.startswith(TRY + "/r/"):
            return r.fulfill(status=200, content_type="image/png", body=PNG)
        return r.abort()
    ctx.route("**/*.workers.dev/**", route)
    errors = []
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE)
    pg.wait_for_timeout(2500)
    pg.evaluate("openEmulate('kraft', 'kraft-1')")
    pg.wait_for_timeout(800)
    btn = pg.locator("#emulate-view [data-emulate-onme]")
    assert btn.count() == 1, "no on-demand Render me button"
    assert btn.is_enabled(), "button disabled"
    assert "don\u2019t map to the render library" not in pg.locator("#emulate-view").inner_text()
    btn.click()
    pg.wait_for_function("() => { var b = document.querySelector('#emulate-view [data-emulate-onme]'); return b && /piece \\d of \\d|Putting|Dressing|Getting/.test(b.textContent) && b.disabled; }", timeout=8000)
    pg.wait_for_selector("#emulate-view img.emulate-onme", timeout=20000)
    assert len(seen["posts"]) == 1, seen["posts"]
    items = seen["posts"][0]["items"]
    slots = [i["slot"] for i in items]
    assert 1 <= len(items) <= 4 and set(slots) <= {"top", "outer", "bottom", "shoes"} and len(set(slots)) == len(slots), slots
    for i in items:
        assert i["image"].startswith("data:image/") or i["image"].startswith("https://"), i["image"][:30]
    pg.click("#emulate-view [data-emulate-onme-save]")
    pg.wait_for_timeout(400)
    saved = pg.evaluate("savedLooks.filter(function(l){return l.onMe})[0] || null")
    assert saved and saved["img"].startswith(TRY + "/r/"), saved
    assert pg.evaluate("lookIsMine(savedLooks.filter(function(l){return l.onMe})[0]) && savedLookHome(savedLooks.filter(function(l){return l.onMe})[0]) === 'outfits'")
    assert "saved to outfits" in pg.locator("#emulate-view [data-emulate-onme-save]").inner_text().lower()
    pg.evaluate("renderSaved()")
    assert pg.locator('#saved-grid img[src="%s"]' % (TRY + "/r/" + JOB + ".jpg")).count() >= 1, "not in Outfits -> Mine grid"
    pg.reload(); pg.wait_for_timeout(2500)
    pg.evaluate("openEmulate('kraft', 'kraft-1')"); pg.wait_for_timeout(800)
    assert pg.locator("#emulate-view img.emulate-onme").count() == 1, "render not cached across reload"
    assert len(seen["posts"]) == 1, "re-posted"
    assert not errors, errors
    b.close()
print("PASS render-me: slots", slots, "polls", seen["polls"])
