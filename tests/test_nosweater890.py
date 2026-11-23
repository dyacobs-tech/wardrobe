"""No sweater over a button-down shirt (.86.90).

David, 23 Nov 2026: "There are too many outfits with a sweater over a button-down shirt. I rarely wear this.
I prefer button-down shirt untucked for evening, casual or evening, sharp or button down shirt tucked in".
The outfit maker no longer deals a sweater layered over a button-down, at any level or temperature, on Home,
Looks or in the background worker (same composer).
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof composerLooks === 'function'")
    items = photographed_closet()
    found = page.evaluate("""(items) => {
      const bad = [];
      for (const lv of [2, 3, 4, 5]) for (const temp of [45, 58, 66, 78]) {
        let looks = [];
        try { looks = composerLooks({ count: 40, level: lv, temp: temp, only: items, exclude: [] }) || []; } catch (e) { continue; }
        looks.forEach(l => { const ps = (l.fwPieces || []).map(p => WardrobeComposer.profile(p));
          const knitLayer = ps.some(p => p.kind === 'knit') && ps.some(p => p.kind === 'shirt');
          if (knitLayer) bad.push([lv, temp, l.title]); });
      }
      return bad; }""", items)
    assert not found, ("a sweater was dealt over a button-down", found[:5])
    # the rule itself: a knit over a shirt is refused, the shirt alone is fine
    r = page.evaluate("""() => { const C = window.WardrobeComposer; const P = (n, c) => C.profile({ id: n, name: n, category: c });
      const shirt = P('Brunello Cucinelli Light Blue Oxford Shirt', 'Shirts'), knit = P('Eleventy Navy Crewneck Sweater', 'Sweaters'),
        trousers = P('Proper Cloth Beige Non-Iron Stretch Chino', 'Trousers'), shoes = P('Edward Green Dark Brown Suede Penny Loafers', 'Shoes');
      if (typeof C.evaluate !== 'function') return null;
      return [C.evaluate(shirt, trousers, shoes, Object.assign({}, knit, { role: 'layer', kind: 'knit' })), !!C.evaluate(shirt, trousers, shoes, null)]; }""")
    if r is not None:
        assert not r[0], ("a knit over a shirt still evaluates as a look", r)
    browser.close()
print("Confirmed no sweater is dealt over a button-down shirt")
