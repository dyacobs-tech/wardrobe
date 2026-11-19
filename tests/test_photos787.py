"""Build .78.7 — no product card without a photo.
1. Catalogue audit (offline): every baked / shop-db / Edit catalogue
   photo that points at a local file exists, decodes and is not blank;
   no record points at a host that refuses hot-linking (Todd Snyder's
   CDN sends Cross-Origin-Resource-Policy: same-origin).
2. Render audit (Chromium, workers.dev aborted): Shop the look for
   EVERY icon photo, Icons Emulate for a sample, The Edit Saved and a
   store search — no .vp-card has a missing / empty / unloaded image,
   every section's Picked card has a photo, and a photo-less record is
   never picked (catalogueScored / Edit pool).
3. A saved piece with no photo is listed under "without a photo",
   not as an empty card; a card whose photo fails to load leaves."""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parent.parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
fails = []
def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(info)[:400]))
    if not ok: fails.append(name)

try:
    from PIL import Image, ImageStat
except Exception:
    Image = None
html = (ROOT / "index.html").read_text()
db = json.loads((ROOT / "assets/shop-db.json").read_text())
ed = json.loads((ROOT / "assets/edit-catalog.json").read_text())["products"]
baked = re.findall(r'"img": "([^"]*)"', html)
imgs = set(i for i in baked + [x.get("img") or "" for x in db + ed] if i)
local = sorted(i for i in imgs if i.startswith("assets/"))
missing = [i for i in local if not (ROOT / i).exists()]
check("every local catalogue photo exists (%d)" % len(local), not missing, missing[:5])
check("no hot-link-blocked host (toddsnyder.com)", not [i for i in imgs if "toddsnyder.com" in i])
if Image:
    blank = []
    for i in local:
        try:
            im = Image.open(ROOT / i).convert("L"); im.thumbnail((48, 48))
            if ImageStat.Stat(im).stddev[0] < 1.2: blank.append(i)
        except Exception as ex:
            blank.append(i + " " + str(ex)[:30])
    check("no blank or corrupt catalogue photo", not blank, blank[:5])

CARDS = """(sel) => [].filter.call(document.querySelectorAll(sel), c => c.offsetParent !== null).map(c => {
  const i = c.querySelector('.vp-ph img'); return { k: c.getAttribute('data-vp-key'), src: i ? i.getAttribute('src') : '', ok: !!(i && i.complete && i.naturalWidth > 0) };
}).filter(x => !x.src || !x.ok)"""
DECODE = "(sel) => Promise.all([].map.call(document.querySelectorAll(sel + ' .vp-ph img'), i => { i.loading = 'eager'; return i.decode ? i.decode().catch(() => 0) : 0; }))"
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844})
    W = json.loads((ROOT / "tests/fixture_edit76.json").read_text())["shopWishlist"]
    W = W + [{"key": "NoPhoto|Mystery jacket|https://example.com/p/1", "brand": "NoPhoto", "name": "Mystery jacket", "url": "https://example.com/p/1", "price": 300, "img": "", "cat": "blazer", "retailer": "Example"}]
    ctx.add_init_script("if(!sessionStorage.getItem('seeded')){sessionStorage.setItem('seeded','1');localStorage.setItem('wardrobe.shopWishlist', %s);}" % json.dumps(json.dumps(W)))
    ctx.route("**/*.workers.dev/**", lambda r: r.abort())
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE); pg.wait_for_timeout(2500)
    pg.evaluate("loadShopDb && loadShopDb()"); pg.wait_for_timeout(2500)
    nophoto = pg.evaluate("shopCatalogueAll().filter(e => !prodHasPhoto(e)).length")
    check("photo-less records exist in the data (%d) and are filtered" % nophoto, nophoto > 0)
    looks = pg.evaluate("allIcons().reduce((a, ic) => a.concat((ic.looks || []).map((l, i) => [ic.id, i])), [])")
    bad_cards, bad_pick, n_cards, n_looks = [], [], 0, 0
    for ic, li in looks:
        ok = pg.evaluate("""([id, i]) => { const ic = iconById(id); const lk = (ic.looks || [])[i];
            if (!lk) return false; const fl = iconPhotoFindLook(ic, lk); if (!fl) return false; openFindLookMode(fl); editShow('searches'); return true; }""", [ic, li])
        if not ok: continue
        n_looks += 1
        pg.wait_for_timeout(80)
        pg.evaluate(DECODE, "#find-look-mode")
        n_cards += pg.locator("#find-look-mode .vp-card").count()
        bc = pg.evaluate(CARDS, "#find-look-mode .vp-card")
        if bc: bad_cards.append((ic, li, bc[:2]))
        bp = pg.evaluate("[].map.call(document.querySelectorAll('#find-look-mode .stl-piece'), s => { const c = s.querySelector('.vp-card.is-picked'); const i = c && c.querySelector('.vp-ph img'); return c && !(i && i.getAttribute('src')) ? c.getAttribute('data-vp-key') : ''; }).filter(Boolean)")
        if bp: bad_pick.append((ic, li, bp))
    check("Shop the look: %d looks, %d cards, every card has a loaded photo" % (n_looks, n_cards), n_looks >= 10 and not bad_cards, bad_cards[:3])
    check("every Picked card has a photo", not bad_pick, bad_pick[:3])
    pg.evaluate("clearFindLookMode()"); pg.wait_for_timeout(200)
    specs = pg.evaluate("allIcons().reduce((a, ic) => a.concat((ic.looks || []).filter(l => l.spec).map(l => [ic.id, l.spec])), [])")
    bad_em = []
    for ic, spec in specs[:15]:
        pg.evaluate("([a, b]) => openEmulate(a, b)", [ic, spec]); pg.wait_for_timeout(400)
        pg.evaluate(DECODE, "#emulate-view")
        bc = pg.evaluate(CARDS, "#emulate-view .vp-card")
        if bc: bad_em.append((ic, spec, bc[:2]))
    check("Emulate cards have photos (%d looks)" % min(15, len(specs)), not bad_em, bad_em[:3])
    pg.evaluate("switchTab('find'); editShow('saved')"); pg.wait_for_timeout(600)
    pg.evaluate(DECODE, "#edit-saved-out")
    check("Edit Saved cards have photos", not pg.evaluate(CARDS, "#edit-saved-out .vp-card"), pg.evaluate(CARDS, "#edit-saved-out .vp-card"))
    check("photo-less saved piece listed, not carded", pg.locator("#edit-saved-out .edit-nophoto .edit-np").count() == 1 and pg.locator('#edit-saved-out .vp-card[data-vp-key^="NoPhoto|"]').count() == 0)
    pg.click("#edit-tab-searches"); pg.wait_for_timeout(300)
    pg.fill("#edit-search-q", "navy blazer"); pg.press("#edit-search-q", "Enter"); pg.wait_for_timeout(800)
    pg.evaluate(DECODE, "#edit-search-out")
    check("Edit search cards have photos", pg.locator("#edit-search-out .vp-card").count() > 0 and not pg.evaluate(CARDS, "#edit-search-out .vp-card"))
    check("a broken photo removes its card", pg.evaluate("""() => new Promise(res => { const h = document.createElement('div'); h.innerHTML = vpCardHTML({brand:'X', name:'Broken photo', url:'https://example.com/b', price: 10, img: 'assets/shopimg/does-not-exist.webp'}, {}); document.body.appendChild(h); h.querySelectorAll('img').forEach(i => { i.loading = 'eager'; });
        setTimeout(() => res(!h.querySelector('.vp-card') && !prodHasPhoto({img: 'assets/shopimg/does-not-exist.webp'})), 1200); })"""))
    check("no page errors", not errs, errs[:3])
    b.close()
print("ALL PASS" if not fails else "FAILED %d" % len(fails))
sys.exit(1 if fails else 0)
