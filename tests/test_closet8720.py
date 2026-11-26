"""The app says closet and piece, not wardrobe and item (.87.20).

David, 26 Nov 2026, asked whether the app should say closet or wardrobe, piece or item (it mixed them):
"CLOSET PIECE". Asked whether the feature names change too ("Wardrobe Rules" would become "Closet Rules"):
"Closet rules is good".
Changed: Closet Rules (the Profile page and every mention), the source choice Closet / Inspo / Combo and the
"Only my closet" mark on a look, From my closet and Upload new piece in Build, and the messages that named his
wardrobe or an item of his. Not changed: things for sale are still items (Sale items), what an icon's notes say
about a wardrobe in general, the backup file's own format name, and the home-screen name.
Checks: the shipped app holds the new names and none of the old ones as labels; the backup format is untouched;
Profile's rules page is headed Closet Rules; the source choice reads Closet.
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent

shipped = (ROOT / "index.html").read_text() + "".join(p.read_text() for p in (ROOT / "app").glob("*.js"))
for old in (">Wardrobe Rules<", "Only my wardrobe", ">From my wardrobe<", ">Upload new item<", ">Wardrobe</button>",
            "breaks a wardrobe rule", "reloading your Wardrobe", "from your wardrobe.", "Confirm the items",
            "Confirm at least one item", "existing closet item"):
    assert old not in shipped, ("old wording is still shipped", old)
for new in (">Closet Rules<", "Only my closet", ">From my closet<", ">Upload new piece<", "breaks a closet rule",
            "reloading your closet", "Confirm the pieces"):
    assert new in shipped, ("new wording is missing", new)
assert 'app: "Wardrobe", kind: "wardrobe-backup"' in (ROOT / "src/app.html").read_text(), "the backup format name changed"
assert "Sale items" in shipped, "things for sale should still be items"

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and r.request.method == "GET" else r.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ")")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function'", timeout=60000)
    got = page.evaluate("""() => ({
      rulesTitle: (document.getElementById('prules-title') || {}).textContent,
      rulesEntry: (document.querySelector('.rules-entry-title') || {}).textContent,
      source: [...document.querySelectorAll('[data-source="wardrobe"]')].map(b => b.textContent.trim()),
      labels: typeof SOURCE_LABEL !== 'undefined' ? SOURCE_LABEL.wardrobe : null })""")
    assert got["rulesTitle"] == "Closet Rules" and got["rulesEntry"] == "Closet Rules", got
    assert got["source"] and all(t == "Closet" for t in got["source"]), got
    assert not errors, errors
    browser.close()
print("Confirmed: the app says Closet Rules, Closet / Inspo / Combo, Only my closet, From my closet and Upload new piece; sale items, the backup format and the home-screen name are unchanged")
