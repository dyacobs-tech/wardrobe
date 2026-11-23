"""Pictures where the tee hangs too long are never shown (.86.79).

David, 23 Nov 2026, Home screenshot of the cream ribbed tee under the burgundy blazer:
"T shirt too long make sure all looks are updated!!!!!!!" (earlier the same night: "T shirt height
wasn't fixed - please review all images make sure they are within my rules and have incorporated my edits!!!")
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
SCREENSHOT_PICTURE = "8202e2ac515b2308.webp"

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items',%s)" % json.dumps(json.dumps(photographed_closet())))
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => typeof onbodyKeys === 'function' && window.ONBODY && Object.keys(ONBODY.map).length > 100")
    page.wait_for_timeout(1500)
    r = page.evaluate("""(f) => {
      const long = Object.keys(ONBODY_TEELONG879);
      const shown = Object.values(onbodyKeys() || {}).map(s => String(s).split('/').pop());
      return { n: long.length, has: !!ONBODY_TEELONG879[f], banned: onbodyFileBanned('assets/onbody/' + f),
               leaked: shown.filter(s => ONBODY_TEELONG879[s]) };
    }""", SCREENSHOT_PICTURE)
    assert r["n"] >= 50 and r["has"] and r["banned"], r
    assert not r["leaked"], ("long-tee pictures still offered", r["leaked"][:5])
    browser.close()
print("Confirmed the %s long-tee pictures, including the burgundy blazer one, are never shown" % r["n"])
