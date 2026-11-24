"""Small photos where photos are small, and no freeze as Home's photo appears (audit, fix 8, .86.87).

From the audit David asked to have fixed ("Just start going through ALL of these in order"):
- The Edit · Icons downloaded ~5 MB on first open because 58px avatars used 900x1200 closet photos; Closet
  tiles and Shop · Build thumbnails did the same. They now use a ~360px copy (assets/photos-sm), and fall back
  to the full photo if a copy is missing.
- At start-up Home composed its next 8 looks the moment its photo appeared, freezing the page for ~0.7s on a
  phone; that now waits 2s after the photo is on screen.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent

# every closet photo has its small copy
full = {p.stem for p in (ROOT / "assets/photos").iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")}
small = {p.stem for p in (ROOT / "assets/photos-sm").iterdir()}
assert not (full - small), ("closet photos with no small copy", sorted(full - small)[:5])

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items',%s)" % json.dumps(json.dumps(photographed_closet())))
    big = []
    page = ctx.new_page()
    page.on("request", lambda r: big.append(r.url) if "/assets/photos/" in r.url else None)
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => typeof smallPhoto886 === 'function' && document.getElementById('today-img')")

    # Home: the look-ahead is not composed as the photo appears, but is ready a few seconds later
    page.wait_for_function("() => { const i = document.getElementById('today-img'); return i.complete && i.naturalWidth > 0; }", timeout=30000)
    early = page.evaluate("() => !!(window.homeLookahead793 && window.homeLookahead793())")
    page.wait_for_function("() => !!(window.homeLookahead793 && window.homeLookahead793())", timeout=15000)
    assert not early, "Home composed its look-ahead the moment its photo appeared"

    # Closet tiles use the small copies
    page.evaluate("() => switchTab('wardrobe')")
    page.wait_for_function("() => document.querySelectorAll('#item-grid img.photo').length >= 4", timeout=30000)
    srcs = page.evaluate("() => [...document.querySelectorAll('#item-grid img.photo')].map(i => i.getAttribute('src'))")
    closet = [s for s in srcs if "assets/photos" in s]
    assert closet and all("assets/photos-sm/" in s for s in closet), ("Closet tiles still load the full photos", closet[:3])

    # a missing small copy falls back to the full photo
    page.evaluate("""() => { const i = document.querySelector('#item-grid img.photo[data-full]');
      window.__fb = i.getAttribute('data-full'); i.setAttribute('src', 'assets/photos-sm/does-not-exist.webp'); }""")
    page.wait_for_function("() => [...document.querySelectorAll('#item-grid img.photo')].some(i => i.getAttribute('src') === window.__fb)", timeout=10000)
    browser.close()
print("Confirmed small photos in Closet with a full-photo fallback, and Home's look-ahead waits until after its photo")
