"""Build .78.9 — a card's person icon opens the try-on directly when a
render of that piece already exists on the device; otherwise it opens
the product sheet and renders inline. MOCK try-on worker (never
production), so no FASHN credits.
  1. Saved card, no render yet -> product sheet with the inline render
     (one POST).
  2. Same card again -> the try-on sheet opens straight away with the
     render, no second POST, product sheet stays shut.
  3. A different card with no render -> product sheet again.
  4. Shop the look card with a seeded cache entry -> try-on directly."""
import json, os, sys, base64
SHOTS = os.environ.get("SHOTS")  # optional screenshot dir
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parent.parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
TRY = "https://wardrobe-tryon.dyacobs.workers.dev"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
WISH = json.loads((ROOT / "tests/fixture_edit76.json").read_text())["shopWishlist"]
fails = []
def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(info)[:300]))
    if not ok: fails.append(name)
seen = {"posts": 0}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844})
    ctx.add_init_script("if(!sessionStorage.getItem('s')){sessionStorage.setItem('s','1');localStorage.setItem('wardrobe.shopWishlist', %s); localStorage.setItem('wardrobe.sync', JSON.stringify({key:'%s', acct:'test', last:0, snap:{}, st:{}, tomb:{}, dirty:{}, status:'x', lastOk:0}));}" % (json.dumps(json.dumps(WISH)), "a" * 48))
    def route(r):
        u = r.request.url
        if u.startswith(TRY + "/tryon") and r.request.method == "POST":
            seen["posts"] += 1
            return r.fulfill(status=202, content_type="application/json", body=json.dumps({"id": "%032x" % seen["posts"], "status": "running", "step": 1, "steps": 1}))
        if u.startswith(TRY + "/tryon/"):
            jid = u.rsplit("/", 1)[1]
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"id": jid, "status": "done", "step": 1, "steps": 1, "resultUrl": TRY + "/r/" + jid + ".png"}))
        if u.startswith(TRY + "/r/"):
            return r.fulfill(status=200, content_type="image/png", body=PNG)
        return r.abort()
    ctx.route("**/*.workers.dev/**", route)
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE); pg.wait_for_timeout(2500)
    pg.evaluate("switchTab('find'); editShow('saved')"); pg.wait_for_timeout(600)
    card = pg.locator("#edit-saved-out .vp-card").first
    key = card.get_attribute("data-vp-key")
    card.locator('[data-vp-act="onme"]').click(); pg.wait_for_timeout(400)
    check("no render yet -> product sheet with inline render", pg.locator("#vp-sheet").is_visible() and pg.locator("#vp-onme").is_visible() and not pg.locator("#tryon-sheet").is_visible())
    pg.wait_for_selector("#vp-onme-img:not([hidden])", timeout=15000)
    check("one render requested", seen["posts"] == 1, seen["posts"])
    if SHOTS: pg.screenshot(path=SHOTS + "/onme-first-sheet-390.png")
    pg.click("#vp-sheet-close"); pg.wait_for_timeout(200)
    pg.locator('#edit-saved-out .vp-card[data-vp-key="%s"] [data-vp-act="onme"]' % key.replace('"', '\\"')).click(); pg.wait_for_timeout(600)
    check("render exists -> try-on opens directly", pg.locator("#tryon-sheet").is_visible() and not pg.locator("#vp-sheet").is_visible())
    pg.wait_for_selector("#tryon-img:not([hidden])", timeout=8000)
    check("served from the device cache (no second render)", seen["posts"] == 1, seen["posts"])
    if SHOTS: pg.screenshot(path=SHOTS + "/onme-direct-tryon-390.png")
    pg.click("#tryon-close"); pg.wait_for_timeout(200)
    other = pg.locator("#edit-saved-out .vp-card").nth(3)
    other.locator('[data-vp-act="onme"]').click(); pg.wait_for_timeout(400)
    check("another piece without a render -> product sheet", pg.locator("#vp-sheet").is_visible() and not pg.locator("#tryon-sheet").is_visible())
    pg.evaluate("vpRun++; vpClose()"); pg.wait_for_timeout(300)
    # Shop the look card with a seeded cache entry
    pg.evaluate("var ic=iconById('kraft'); var lk=ic.looks.filter(function(l){return l.spec==='kraft-1'})[0]; openFindLookMode(iconPhotoFindLook(ic,lk)); editShow('searches');"); pg.wait_for_timeout(1200)
    sk = pg.locator("#find-look-mode .vp-card").nth(1).get_attribute("data-vp-key")
    pg.evaluate("""k => tryonEntryItems(vpEntryFor(VP[k].e)).then(items => { tryonCachePut(tryonCacheKey(items.slice(0, 6)), '%s/r/seeded.png'); })""" % TRY, sk)
    pg.wait_for_timeout(300)
    n0 = seen["posts"]
    pg.locator("#find-look-mode .vp-card").nth(1).locator('[data-vp-act="onme"]').click(); pg.wait_for_timeout(600)
    check("Shop the look: existing render -> try-on directly", pg.locator("#tryon-sheet").is_visible() and not pg.locator("#vp-sheet").is_visible() and seen["posts"] == n0)
    check("no page errors", not errs, errs[:3])
    b.close()
print("ALL PASS" if not fails else "FAILED %d" % len(fails))
sys.exit(1 if fails else 0)
