"""Build .78.5 — Shop redesign: one product card everywhere.
Mock-free (workers.dev aborted). At 375/390/430:
  - Shop the look (Kraft · Riviera) renders per-piece sections with a
    colour dot, a swipe row of shared cards and a search icon; the old
    per-section tier / Search dropdowns are gone; Closet gaps hide.
  - Summary shows a total and a Buy missing pieces list that links out.
  - Wishlist / Purchased toggle instantly on every card for that product
    and in the sheet; the sheet opens with a Buy link and Pick moves the
    card first; the search icon opens the store-search sheet.
  - The Price pill narrows the shop-the-look options.
  - The Edit Saved and Icons Emulate use the same card; no page errors."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
W = json.loads((Path(__file__).resolve().parent / "fixture_edit76.json").read_text())["shopWishlist"]
fails = []
def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(info)))
    if not ok: fails.append(name)
OPEN = "var ic=iconById('kraft'); var lk=ic.looks.filter(function(l){return l.spec==='kraft-1'})[0]; openFindLookMode(iconPhotoFindLook(ic,lk)); editShow('searches');"
with sync_playwright() as p:
    b = p.chromium.launch()
    for vw in (375, 390, 430):
        ctx = b.new_context(viewport={"width": vw, "height": 844})
        ctx.add_init_script("if(!sessionStorage.getItem('seeded')){sessionStorage.setItem('seeded','1');localStorage.setItem('wardrobe.shopWishlist', %s);}" % json.dumps(json.dumps(W)))
        ctx.route("**/*.workers.dev/**", lambda r: r.abort())
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE); pg.wait_for_timeout(2500)
        pg.evaluate(OPEN); pg.wait_for_timeout(1500)
        secs = pg.locator("#find-look-mode .stl-piece")
        n_secs = secs.count()
        check("%d: per-piece sections" % vw, n_secs >= 3, n_secs)
        check("%d: header has dot, name, search icon" % vw, secs.first.locator(".stl-head .cdot").count() == 1 and secs.first.locator(".stl-name").inner_text().strip() != "" and secs.first.locator("[data-stl-search]").count() == 1)
        check("%d: swipe rows of shared cards" % vw, secs.first.locator(".vp-row .vp-card").count() >= 2)
        check("%d: old tier / Search dropdowns gone" % vw, pg.locator("#find-look-mode select").count() == 0 and pg.locator("#find-look-mode .shop-tier-sel, #find-look-mode details.shop-search").count() == 0)
        check("%d: Closet gaps hidden during a look" % vw, not pg.locator("#edit-gapcards").is_visible())
        card = secs.first.locator(".vp-card").first
        check("%d: card brand/name/price/retailer/icons" % vw, card.locator(".vp-brand").count() == 1 and card.locator(".vp-name").count() == 1 and "$" in card.locator(".vp-price").inner_text() and card.locator("[data-vp-act]").count() >= 3)
        cw = pg.evaluate("(function(){var c=document.querySelector('#find-look-mode .vp-card').getBoundingClientRect();return [c.left, c.right, c.width]})()")
        check("%d: card fits on screen" % vw, cw[0] >= 0 and cw[2] < vw / 2, cw)
        summ = pg.inner_text("#stl-summary")
        check("%d: summary total" % vw, "Shop the look" in summ and "$" in summ, summ[:120])
        pg.click("#stl-summary summary"); pg.wait_for_timeout(200)
        links = pg.locator("#stl-summary .stl-buy a[href^='http']").count()
        check("%d: Buy missing pieces links out" % vw, links >= 1, links)
        # wishlist sync across cards + sheet
        c = secs.nth(1).locator(".vp-card").nth(1); k = c.get_attribute("data-vp-key")
        c.locator("[data-vp-act=wish]").click(); pg.wait_for_timeout(250)
        same = pg.evaluate("k => [].map.call(document.querySelectorAll('.vp-card[data-vp-key=\"'+CSS.escape(k)+'\"] [data-vp-wish]'), b => b.getAttribute('aria-pressed'))", k)
        check("%d: wishlist instant on every card" % vw, same and all(x == "true" for x in same) and pg.evaluate("k => !!wishlistFor(k)", k), same)
        c.locator("[data-vp-act=bought]").click(); pg.wait_for_timeout(250)
        check("%d: purchased toggles" % vw, c.locator("[data-vp-act=bought]").get_attribute("aria-pressed") == "true" and pg.evaluate("k => !!shopPurchaseFor(k)", k))
        c.locator(".vp-body").click(); pg.wait_for_timeout(300)
        check("%d: sheet opens with Buy + states" % vw, pg.locator("#vp-sheet").is_visible() and (pg.locator("#vp-sheet .vp-sh-buy").count() == 0 or pg.locator("#vp-sheet .vp-sh-buy").get_attribute("target") == "_blank") and pg.locator("#vp-sheet [data-vp-act=wish]").get_attribute("aria-pressed") == "true")
        pg.click("#vp-sheet [data-vp-act=bought]"); pg.wait_for_timeout(200)
        check("%d: sheet toggle updates the card" % vw, c.locator("[data-vp-act=bought]").get_attribute("aria-pressed") == "false")
        pg.click("#vp-sheet [data-vp-act=pick]"); pg.wait_for_timeout(400)
        check("%d: Pick moves card first + closes" % vw, secs.nth(1).locator(".vp-card").first.get_attribute("data-vp-key") == k and secs.nth(1).locator(".vp-card").first.evaluate("e => e.classList.contains('is-picked')") and not pg.locator("#vp-sheet").is_visible())
        pg.click("[data-stl-search='0']"); pg.wait_for_timeout(250)
        check("%d: search sheet" % vw, pg.locator("#vp-sheet").is_visible() and pg.locator("#vp-sheet .stl-link").count() >= 1)
        pg.click("#vp-sheet-close"); pg.wait_for_timeout(150)
        # price pill
        n0 = pg.locator("#find-look-mode .vp-card").count()
        pg.evaluate("setPriceRange('r:0-150')"); pg.wait_for_timeout(500)
        n1 = pg.locator("#find-look-mode .vp-card").count()
        pr = pg.evaluate("[].map.call(document.querySelectorAll('#find-look-mode .vp-price'), e => parseFloat(e.textContent.replace(/[^0-9.]/g,'')))")
        check("%d: Price pill narrows options (%d -> %d)" % (vw, n0, n1), n1 < n0 and all(x <= 150 for x in pr), pr)
        pg.evaluate("setPriceRange('any','')"); pg.wait_for_timeout(300)
        pg.evaluate("clearFindLookMode && clearFindLookMode()") if pg.evaluate("typeof clearFindLookMode === 'function'") else pg.click("#shop-clear-look")
        pg.wait_for_timeout(300)
        pg.evaluate("switchTab('find'); editShow('saved')"); pg.wait_for_timeout(400)
        check("%d: The Edit Saved uses the shared card" % vw, pg.locator("#edit-saved-out .vp-card.edit-pc").count() > 0)
        pg.evaluate("openEmulate('kraft','kraft-1')"); pg.wait_for_timeout(1200)
        check("%d: Emulate uses the shared card" % vw, pg.locator("#emulate-view .emulate-piece .vp-card").count() > 0)
        ov = pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        check("%d: no horizontal overflow" % vw, ov)
        check("%d: no page errors" % vw, not errs, errs[:3])
        ctx.close()
    b.close()
print("ALL PASS" if not fails else "FAILED %d" % len(fails))
sys.exit(1 if fails else 0)
