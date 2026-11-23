"""A picture list saved on the phone by an older build never brings back a replaced picture (.86.78).

David, 23 Nov 2026, Home screenshot of the navy tee and stone grey chinos:
"Head messed up and no belt again!!!!!!!" The picture he saw was the one
replaced in .86.76; the list saved on his phone by the older build was read
after the built-in list and put it back.
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parents[1]
BUILD = re.search(r"WARDROBE_BUILD\s*=\s*['\"]([^'\"]+)['\"]", (ROOT / "sw.js").read_text()).group(1)
SEED = json.loads((ROOT / "assets/onbody/manifest.json").read_text())["r"]
KEY, FILE = SEED[0]["k"], SEED[0]["f"]
STALE = {"v": 1, "r": [{"k": e["k"], "f": ("0000stale0000000.webp" if e["k"] == KEY else e["f"])} for e in SEED]}


def run(browser, saved, block_manifest):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")

    def route(r):
        u = r.request.url
        if not u.startswith(URL) or (block_manifest and "onbody/manifest.json" in u):
            return r.abort()
        return r.continue_()
    ctx.route("**/*", route)
    ctx.add_init_script("if(!sessionStorage.getItem('s878')){sessionStorage.setItem('s878','1');localStorage.setItem('wardrobe.onbody', %s);}" % json.dumps(json.dumps(saved)))
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.ONBODY && ONBODY.map && Object.keys(ONBODY.map).length > 100")
    page.wait_for_timeout(2500)
    got = page.evaluate("k => ONBODY.map[k]", KEY)
    stored = page.evaluate("() => { try { return JSON.parse(localStorage.getItem('wardrobe.onbody')).b878 || null } catch (e) { return null } }")
    ctx.close()
    return got, stored


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    # 1. an old saved list (no build mark) must not override the built-in list, even before the fresh list arrives
    got, _ = run(browser, STALE, block_manifest=True)
    assert got == "assets/onbody/" + FILE, ("old saved list brought back a replaced picture", got)
    # 2. a saved list from a different build is ignored too
    got, _ = run(browser, dict(STALE, b878="2000-01-01.0"), block_manifest=True)
    assert got == "assets/onbody/" + FILE, ("other build's saved list was used", got)
    # 3. with the network, the fresh list is saved and marked with this build
    got, stored = run(browser, STALE, block_manifest=False)
    assert got == "assets/onbody/" + FILE, got
    assert stored == BUILD, ("saved list not marked with this build", stored, BUILD)
    browser.close()
print("Confirmed an older saved picture list never replaces the current pictures, and the saved list carries the build")
