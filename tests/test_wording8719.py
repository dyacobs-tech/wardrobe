"""One name for the try-on action, and DONNA in capitals (.87.19).

David, 26 Nov 2026, asked which of "See it on me", "Show it on me" and "Put it on me" is right: "See it on me ."
Asked whether running text says DONNA or Donna: "DONNA".
The Dress me button said "Show it on me" or "Put it on me"; it now says "See it on me" like every other screen.
Six messages said "Donna" (the update bar, the backup messages, the relink note, the name on Profile); they now say
DONNA. The home-screen name, the page title and the manifest are not touched: changing them would make the phone
treat the app as a new one.
Checks: Dress me's button reads "See it on me"; the update bar and Profile say DONNA; the shipped app holds neither
old button name as a label; the home-screen name is still what it was.
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent

src = (ROOT / "src/app.html").read_text()
assert '<meta name="apple-mobile-web-app-title" content="Donna" />' in src, "the home-screen name changed"
assert "<title>Donna</title>" in src, "the page title changed"
shipped = (ROOT / "index.html").read_text() + "".join(p.read_text() for p in (ROOT / "app").glob("*.js"))
for old in ('"Show it on me"', '"Put it on me"', ">Show it on me<", ">Put it on me<"):
    assert old not in shipped, ("an old name for See it on me is still a label", old)
for msg in ("A newer DONNA is ready.", "isn't a DONNA backup", "the live DONNA app"):
    assert msg in shipped, ("message does not say DONNA", msg)
assert not re.search(r"(newer|a|live) Donna\b", shipped), "a message still says Donna"

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
    page.evaluate("() => document.querySelector('#bottombar [data-section=\"inspo\"]').click()")
    page.wait_for_timeout(500)
    page.evaluate("() => document.querySelector('[data-ins-seg=\"dress\"]').click()")
    page.wait_for_selector("[data-dm-go]", timeout=15000)
    label = page.evaluate("() => document.querySelector('[data-dm-go]').textContent.trim()")
    assert label == "See it on me", ("Dress me's button", label)
    about = page.evaluate("() => (document.querySelector('.about-name') || {}).textContent")
    assert about == "DONNA", about
    bar = page.evaluate("() => document.querySelector('#update-bar span').textContent")
    assert bar == "A newer DONNA is ready.", bar
    assert not errors, errors
    browser.close()
print("Confirmed: Dress me's button reads See it on me; the update bar, the backup messages and Profile say DONNA; the home-screen name is unchanged")
