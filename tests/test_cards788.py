"""Build .78.8 — the shared product card in The Edit's Build and in
Render me. Chromium, workers.dev aborted, no try-on spend.
  - Build: a shop piece in a slot shows on the horizontal product card
    (photo, brand, name, price, icon row) between the arrows; arrows
    still cycle; Fills a gap is a row of product cards whose + Look
    puts the piece on the board; tapping a card opens the product sheet.
  - Render me: a cached render lists its shop pieces as product cards
    under "In this render" and his own pieces by name.
  - 375/390/430 fit, no page errors."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parent.parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
W = json.loads((ROOT / "tests/fixture_edit76.json").read_text())["shopWishlist"]
fails = []
def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(info)[:300]))
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
        pg.evaluate("switchTab('find'); editShow('build')"); pg.wait_for_timeout(700)
        slot_cards = pg.locator("#edit-board .vp-card.vp-h")
        check("%d: shop pieces in Build slots on the product card" % vw, slot_cards.count() >= 1, slot_cards.count())
        c = slot_cards.first
        check("%d: slot card has photo, brand, price, icons" % vw, (c.locator(".vp-ph img").get_attribute("src") or "") != "" and c.locator(".vp-brand").inner_text().strip() != "" and "$" in c.locator(".vp-price").inner_text() and c.locator(".vp-acts .vp-ico").count() >= 4)
        box = pg.evaluate("(() => { const s = document.querySelector('#edit-board .vp-card.vp-h').closest('.edit-slot-row').getBoundingClientRect(); return [s.left, s.right, innerWidth]; })()")
        check("%d: slot row fits" % vw, box[0] >= 0 and box[1] <= box[2], box)
        slot = c.evaluate("e => e.closest('[data-edit-slot]').getAttribute('data-edit-slot')")
        k0 = c.get_attribute("data-vp-key")
        nxt = pg.locator('[data-edit-step="1"][data-slot="%s"]' % slot)
        if nxt.is_enabled():
            nxt.click(); pg.wait_for_timeout(300)
            st = pg.evaluate("editBoardState()")[slot]
            check("%d: arrows still cycle the slot" % vw, not (st and st.get("t") == "p" and st["p"]["key"] == k0), st)
        gf = pg.locator("#edit-gapfill .vp-card")
        check("%d: Fills a gap on product cards" % vw, gf.count() >= 3, gf.count())
        put = pg.locator("#edit-gapfill [data-edit-gap-put]").first
        k1 = put.get_attribute("data-edit-gap-put")
        put.click(); pg.wait_for_timeout(400)
        check("%d: + Look puts it on the board" % vw, pg.evaluate("k => Object.values(editBoardState()).some(r => r && r.t === 'p' && r.p.key === k)", k1))
        pg.locator("#edit-board .vp-card.vp-h .vp-ph").first.click(); pg.wait_for_timeout(300)
        check("%d: slot card opens the product sheet" % vw, pg.locator("#vp-sheet").is_visible())
        pg.click("#vp-sheet-close"); pg.wait_for_timeout(200)
        # Render me picks from a cached render (no spend)
        pg.evaluate("""(() => { const ic = iconById('kraft'); const lk = ic.looks.filter(l => l.spec === 'kraft-1')[0];
          const shop = shopCatalogueAll().filter(e => e.img && e.img.indexOf('assets/') === 0 && e.cat === 'blazer').slice(0, 2).map(e => ({brand: e.brand, name: e.name, url: e.url, price: e.price, img: e.img, retailer: e.retailer}));
          emulateOnMeCache[lk.img] = { u: 'assets/og-preview.jpg', t: Date.now(), title: 'Kraft', names: ['x'], own: [{id: 'a', name: 'Navy polo', category: 'Polos', hex: '#223'}], shop: shop };
          openEmulate('kraft', 'kraft-1'); })()""")
        pg.wait_for_timeout(900)
        check("%d: Render me picks on product cards" % vw, pg.locator("#emulate-view .rm-picks .vp-card").count() == 2 and "Navy polo" in pg.inner_text("#emulate-view .emulate-render"))
        check("%d: no horizontal overflow" % vw, pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        check("%d: no page errors" % vw, not errs, errs[:3])
        ctx.close()
    b.close()
print("ALL PASS" if not fails else "FAILED %d" % len(fails))
sys.exit(1 if fails else 0)
