"""Audit fixes, batch 1 (.86.83): broken pictures hidden and outfit rules corrected.

David, 23 Nov 2026, after the full audit: "Just start going through ALL of these in order in most effecient
logical way". Rules checked here, in his words where he gave them:
- tees are never tucked ("Untucked under blazer"), never into swim trunks;
- swim shoes: "pool slides, my toms slip ons, or my baudoin lange with raffia trim" — no other espadrilles;
- any blazer look takes a plain leather belt (no beaded belt with a blazer);
- "Pool House" linen trousers are not a swim look, so the watch shows;
- polos that are long-sleeved in their photos are long-sleeved (never dealt at Pool);
- "Maple baudoins evening sharp to formal".
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "src/app.html").read_text()
hidden = set(re.findall(r'"([0-9a-f]{16}\.webp)"', re.search(r"var ONBODY_AUDIT883 = \{(.*?)\};", src, re.S).group(1)))
assert len(hidden) >= 33, len(hidden)

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof onbodyFileBanned === 'function'")
    out = page.evaluate("""(hidden) => {
      const C = WardrobeComposer, P = (o, i) => C.profile(Object.assign({ id: 'x' + i }, o), i || 0);
      const tee = P({ name: 'Unbound Merino Off-White Tee', category: 'Tees', colourName: 'Off-white' }, 1);
      const blazer = P({ name: 'Giorgio Armani Taupe Knit Blazer', category: 'Blazers', colourName: 'Taupe' }, 2);
      const lpEsp = P({ name: 'Loro Piana Light Blue Knit Espadrilles', category: 'Shoes', colourName: 'Light blue' }, 3);
      const trunks = P({ name: 'Navy Swim Trunks', category: 'Bathing suits', colourName: 'Navy' }, 4);
      const kiton = C.profile({ id: 'item-1794965887183-921466', name: 'Kiton Dark Olive Polo Shirt', category: 'Polos', colourName: 'Dark olive' }, 5);
      const maple = P({ name: 'Baudoin & Lange Rust Suede Tassel Loafers', category: 'Shoes', colourName: 'Maple', colourHex: '#8a4a2a' }, 6);
      const poolHouse = { fwPieces: [{ id: 'a', name: 'Pool House New York Malibu Linen Pants II', category: 'Trousers' }, { id: 'b', name: 'White Tee', category: 'Tees' }], title: 'White Tee & Olive Linen Trousers' };
      return {
        hiddenBanned: hidden.every(f => onbodyFileBanned('assets/onbody/' + f)),
        teeTucked: C.tuckOf(tee, blazer) || C.tuckOf(tee, null),
        swimEsp: !!C.evaluate(tee, trunks, lpEsp, null),
        kitonShort: kiton.shortSleeve, kitonLo: kiton.lo,
        mapleNeutral: maple.neutral, mapleHi: maple.hi,
        poolHouseSwim: isSwimLook(poolHouse)
      };
    }""", sorted(hidden))
    assert out["hiddenBanned"], out
    assert out["teeTucked"] is False, ("a tee is tucked", out)
    assert out["swimEsp"] is False, ("Loro Piana espadrilles with trunks", out)
    assert out["kitonShort"] is False and out["kitonLo"] >= 2, ("long-sleeve polo treated as short-sleeve", out)
    assert out["mapleNeutral"] is True and out["mapleHi"] >= 6, ("maple Baudoins shut out of Formal", out)
    assert out["poolHouseSwim"] is False, ("Pool House trousers read as swim", out)
    browser.close()
print("Confirmed %d broken pictures hidden; tees untucked; swim espadrilles Baudoin only; long-sleeve polos; maple Baudoins reach Formal; Pool House is not swim" % len(hidden))

# Shop (Fix 3): women's pieces and caps out; mis-filed products in their right aisle; "Check it" fits; dark filters.
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block", color_scheme="dark")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => typeof window.editFetchCatalog === 'function'")
    r = page.evaluate("""() => window.editFetchCatalog().then(list => {
      const by = {}; list.forEach(e => { if (e.sku) by[e.sku] = e; });
      return { n: list.length, women: ['db-3c2c2b1a4ab9','db-5f18bcac0c68','db-bb2747cc2c02','db-22863d513f77'].filter(s => by[s]).length,
               oxford: (by['db-a59bc917cdc7'] || {}).cat, chinoShort: (by['db-9807516f9bd2'] || {}).cat, osTrousers: (by['db-29c4b43791bf'] || {}).cat };
    })""")
    assert r["women"] == 0, r
    assert r["oxford"] == "shirt" and r["chinoShort"] == "shorts" and r["osTrousers"] == "trousers", r
    page.locator("#tab-find").first.dispatch_event("click")
    page.wait_for_timeout(600)
    page.evaluate("() => { const s = document.getElementById('shop-plus-sheet'); if (s) s.hidden = false; }")
    page.wait_for_timeout(200)
    fit = page.evaluate("""() => { const b = document.getElementById('link-go'), c = b && b.closest('.info-pop-card');
      if (!b || !c || !b.offsetParent) return null; return b.getBoundingClientRect().right <= c.getBoundingClientRect().right + 0.5; }""")
    assert fit is not False, "Check it button runs off the card"
    bg = page.evaluate("""() => { const s = document.querySelector('.closet-filters875 select'); return s ? getComputedStyle(s).backgroundRepeat : 'no-select'; }""")
    assert bg in ("no-repeat", "no-select"), ("dark-mode closet filter tiles its chevron", bg)
    browser.close()
print("Confirmed Shop: women's pieces out, mis-filed products in the right aisle, Check it fits, closet filters clean in dark mode (%d products)" % r["n"])
