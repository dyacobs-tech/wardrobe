"""Build .78.4 — global Price range. Mock-free (workers.dev blocked).
Checks: pill opens the sheet, a chip narrows The Edit Saved count and an
Emulate (shop-the-look) match count, the pill shows the range, sort
orders by price, the setting persists across reload and rides the
synced settings document (syMetaOf), and Any restores everything."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
W = json.loads((Path(__file__).resolve().parent / "fixture_edit76.json").read_text())["shopWishlist"]
fails = []
def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(info)))
    if not ok: fails.append(name)
with sync_playwright() as p:
    b = p.chromium.launch()
    for vw in (375, 390, 430):
        ctx = b.new_context(viewport={"width": vw, "height": 844})
        ctx.add_init_script("if(!sessionStorage.getItem('seeded')){sessionStorage.setItem('seeded','1');localStorage.setItem('wardrobe.shopWishlist', %s);}" % json.dumps(json.dumps(W)))
        ctx.route("**/*.workers.dev/**", lambda r: r.abort())
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE); pg.wait_for_timeout(2500)
        pg.evaluate("switchTab('find'); editShow('saved')"); pg.wait_for_timeout(400)
        n0 = pg.locator("#edit-saved-out .edit-pc").count()
        row = pg.evaluate("(function(){var r=document.querySelector('#panel-find .edit-shop-tabs').getBoundingClientRect();var p=document.getElementById('price-pill').getBoundingClientRect();return [r.right, p.right, p.left, window.innerWidth]})()")
        check("%d: price pill inside the top row" % vw, row[1] <= row[0] + 0.5 and row[2] >= 0, row)
        pg.click("#price-pill"); pg.wait_for_timeout(200)
        check("%d: sheet opens" % vw, pg.locator("#price-sheet").is_visible())
        pg.click('[data-pr-key="r:150-500"]'); pg.wait_for_timeout(150)
        pg.click('[data-pr-sort="asc"]'); pg.wait_for_timeout(150)
        pg.click("#price-done"); pg.wait_for_timeout(300)
        n1 = pg.locator("#edit-saved-out .edit-pc").count()
        check("%d: Saved narrows (%d -> %d)" % (vw, n0, n1), 0 < n1 < n0, (n0, n1))
        check("%d: pill shows range" % vw, pg.locator("#price-pill").inner_text().strip() == "$150\u2013500", pg.locator("#price-pill").inner_text())
        prices = pg.evaluate("[].map.call(document.querySelectorAll('#edit-saved-out .edit-grid'), function(g){return [].map.call(g.querySelectorAll('.vp-price, .edit-price'), function(e){return parseFloat(e.textContent.replace(/[^0-9.]/g,''))})})")
        check("%d: prices in range + low-high" % vw, all(150 <= x <= 500 for g in prices for x in g) and all(g == sorted(g) for g in prices), prices)
        check("%d: synced settings carry it" % vw, pg.evaluate("syMetaOf().priceRange") == "r:150-500|asc")
        pg.reload(); pg.wait_for_timeout(2500)
        check("%d: persists across reload" % vw, pg.evaluate("priceRange") == "r:150-500|asc")
        pg.evaluate("setPriceRange('any', ''); openEmulate('kraft','kraft-1')"); pg.wait_for_timeout(1500)
        PR = "[].map.call(document.querySelectorAll('#emulate-view .vp-price, #emulate-view .shop-price'),function(e){return parseFloat(e.textContent.replace(/[^0-9.]/g,''))})"
        e0 = pg.locator("#emulate-view .emulate-piece").count(); p0 = pg.evaluate(PR)
        pg.evaluate("setPriceRange('r:1500-')"); pg.wait_for_timeout(600)
        p1 = pg.evaluate(PR)
        check("%d: shop-the-look matches follow the range %s -> %s" % (vw, p0, p1), p1 and all(x >= 1500 for x in p1) and any(x < 1500 for x in p0), (p0, p1))
        pg.evaluate("setPriceRange('any', '')"); pg.wait_for_timeout(400)
        check("%d: Any restores" % vw, pg.locator("#emulate-view .emulate-piece").count() == e0 and pg.evaluate("priceRangeShort()") == "Price")
        check("%d: no page errors" % vw, not errs, errs[:3])
        ctx.close()
    b.close()
print("ALL PASS" if not fails else "FAILED %d" % len(fails))
sys.exit(1 if fails else 0)
