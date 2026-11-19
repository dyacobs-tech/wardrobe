"""See it on me — client flow against a MOCK try-on worker (never production).

Boots the app with a fake sync key, blocks every real workers.dev call,
mocks POST /tryon + GET /tryon/<id> + the render image, then taps
"See it on me" on a Shop product card and asserts the loading state
followed by the render. Also checks the not-configured message.
Run: python -m http.server 8000 & python tests/test_tryon.py [base_url]
"""
import json, sys, base64
from pathlib import Path
# Build .76: one saved product so The Edit's Saved view carries an "On me" card
WISH = json.loads((Path(__file__).resolve().parent / "fixture_edit76.json").read_text())["shopWishlist"][:2]
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
TRY = "https://wardrobe-tryon.dyacobs.workers.dev"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
JOB = "0123456789abcdef0123456789abcdef"

def run(mode):
    seen = {"post": None, "polls": 0}
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        ctx.add_init_script("localStorage.setItem('wardrobe.shopWishlist', %s); localStorage.setItem('wardrobe.editView', JSON.stringify('saved'));" % json.dumps(json.dumps(WISH)))
        ctx.add_init_script("localStorage.setItem('wardrobe.sync', JSON.stringify({key:'%s', acct:'test', last:0, snap:{}, st:{}, tomb:{}, dirty:{}, status:'x', lastOk:0}));" % ("a" * 48))
        def route(r):
            u = r.request.url
            if u.startswith(TRY + "/tryon") and r.request.method == "POST":
                seen["post"] = json.loads(r.request.post_data)
                if mode == "unconfigured":
                    return r.fulfill(status=503, content_type="application/json", body=json.dumps({"error": "not_configured"}))
                return r.fulfill(status=202, content_type="application/json", body=json.dumps({"id": JOB, "status": "running", "step": 1, "steps": 1}))
            if u.startswith(TRY + "/tryon/" + JOB):
                seen["polls"] += 1
                done = seen["polls"] >= 2
                return r.fulfill(status=200, content_type="application/json", body=json.dumps({"id": JOB, "status": "done" if done else "running", "step": 1, "steps": 1, "resultUrl": TRY + "/r/" + JOB + ".jpg" if done else None}))
            if u.startswith(TRY + "/r/"):
                return r.fulfill(status=200, content_type="image/png", body=PNG)
            return r.abort()
        ctx.route("**/*.workers.dev/**", route)
        errors = []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE)
        pg.wait_for_timeout(2500)
        pg.click("#tab-find")
        pg.wait_for_timeout(800)
        btn = pg.locator("[data-tryon-shop], [data-tryon-sale], [data-tryon-wish], [data-edit-onme]").locator("visible=true")
        n = btn.count()
        if n == 0:
            # Sale view renders its cards on demand
            pg.evaluate("typeof renderSale === 'function' && renderSale()")
            n = btn.count()
        assert n > 0, "no See it on me buttons on Shop"
        btn.first.scroll_into_view_if_needed()
        btn.first.click()
        assert pg.locator("#tryon-sheet").is_visible(), "sheet did not open"
        if mode == "unconfigured":
            pg.wait_for_timeout(1500)
            t = pg.locator("#tryon-status").inner_text()
            assert "isn't switched on" in t, t
        else:
            assert pg.locator("#tryon-wait").is_visible(), "no loading state: " + pg.locator("#tryon-status").inner_text()
            try:
                pg.wait_for_selector("#tryon-img:not([hidden])", timeout=15000)
            except Exception:
                raise AssertionError("render never shown: status=%r seen=%r errors=%r" % (pg.locator("#tryon-status").inner_text(), {k: (str(v)[:200]) for k, v in seen.items()}, errors))
            assert seen["post"] and seen["post"]["items"][0]["slot"] in ("top", "outer", "bottom", "shoes", "accessory")
            img = seen["post"]["items"][0]["image"]
            assert img.startswith("https://") or img.startswith("data:image/"), img[:40]
        pg.click("#tryon-close")
        assert not pg.locator("#tryon-sheet").is_visible()
        assert not errors, errors
        b.close()
    print("PASS", mode, "buttons:", n, "polls:", seen["polls"])

run("ok")
run("unconfigured")
