"""Build .73: endless closet outfits.

Engine (in the page, on a generic 83-piece closet with the same
category mix as the owner's synced closet — tests/fixture_closet83.json,
no brands or photos):
  * thousands of unique, structurally valid outfits; every piece placeable
  * 600 dealt outfits (100 pages of 6) with no repeats; every piece shown
  * a brand-new piece is dealt within the first pages
  * every outfit type 1–7 deals; a disliked combo never comes back
UI (WebKit standalone 390×844, local server, workers.dev blocked):
  * Wardrobe mode: Home's outfit of the day is a composed flat-lay,
    Home still fits one screen, swipe deals a new combo
  * Ideas: the closet feed shows, infinite scroll appends, Inspo hides it
  * hero Dislike on a closet look never bans a photo
  * no JS errors

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_composer73.py
"""
from __future__ import annotations

import http.server
import json
import os
import re
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))  # noqa: E402
from wardrobe_fixture import garments_for_all_levels, photographed_closet
from buildinfo import CURRENT_BUILD

ROOT = Path(__file__).resolve().parents[1]
BUILD = CURRENT_BUILD
# Build .74.2: Home deals only pieces that carry a photo, so each fixture
# piece gets a tiny valid one (the fixture itself stays photo-free).
FIXTURE_PHOTO = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
FIXTURE = json.loads((Path(__file__).resolve().parent / "fixture_closet83.json").read_text())
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")
STANDALONE_INIT = """
Object.defineProperty(window.navigator, 'standalone', { get: () => true, configurable: true });
if (window.matchMedia) {
  const orig = window.matchMedia.bind(window);
  window.matchMedia = (q) => String(q).includes('display-mode: standalone')
    ? { matches: true, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, onchange: null, dispatchEvent() { return false; } }
    : orig(q);
}
"""

ENGINE_JS = """([items, extras]) => {
  const C = window.WardrobeComposer;
  const out = { ok: !!C };
  if (!C) return out;
  const deck = C.build(items);
  out.combos = deck.combos.length;
  const keys = new Set(deck.combos.map(c => c.key));
  out.uniqueKeys = keys.size;
  const roleOk = deck.combos.every(c => c.t.role === 'top' && c.b.role === 'bottom' && c.s.role === 'shoes' && (!c.l || c.l.id !== c.t.id));
  out.structureOk = roleOk;
  out.coverage = Object.keys(deck.coverage(null)).length;
  // 100 pages of 6 with the seen ring
  let recent = [], exposure = {}, seen = new Set(), dups = 0;
  for (let page = 0; page < 100; page++) {
    deck.deal(6, { level: null, temp: 68, recent, exposure }).forEach(o => {
      if (seen.has(o.key)) dups++;
      seen.add(o.key); recent.push(o.key);
      o.ids.forEach(id => { exposure[id] = (exposure[id] || 0) + 1; });
    });
  }
  out.dealt = seen.size; out.dups = dups; out.shown = Object.keys(exposure).length;
  // a new piece
  const today = new Date().toISOString().slice(0, 10);
  const withNew = items.concat([{ id: 'new-1', name: 'Rust Linen Shirt', category: 'Shirts', colourName: 'Rust', colourHex: '#a0522d', addedISO: today }]);
  const d2 = C.build(withNew);
  let firstNew = -1, r2 = [], e2 = {};
  for (const id of Object.keys(exposure)) e2[id] = exposure[id];
  // Same mild 68F as the deals above, and a fixed-seed rng. With no temp the
  // deck assumes a warm 78F day, which marks down a long-sleeve linen shirt,
  // and the new piece then missed the first 60 deals in about 1 run in 8
  // (5 of 40 measured; 0 of 40 at 68F). That failed CI at random.
  let sd = 73; const rng2 = () => { sd = (sd + 0x6D2B79F5) | 0; let t = Math.imul(sd ^ (sd >>> 15), 1 | sd); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  for (let page = 0; page < 10 && firstNew < 0; page++) {
    const pg = d2.deal(6, { level: null, temp: 68, recent: r2, exposure: e2, rng: rng2 });
    pg.forEach((o, i) => { if (firstNew < 0 && o.ids.includes('new-1')) firstNew = page * 6 + i; r2.push(o.key); o.ids.forEach(id => { e2[id] = (e2[id] || 0) + 1; }); });
  }
  out.newPieceAt = firstNew;
  // .86.43: belts in the closet are never attached to an outfit at random
  const d3 = C.build(items.concat([{ id: 'belt-1', name: 'Brown Leather Belt', category: 'Belts', colourName: 'Brown', colourHex: '#663218' },
                                   { id: 'belt-2', name: 'Navy Woven Belt', category: 'Belts', colourName: 'Navy', colourHex: '#1b1a25' }]));
  let beltDealt = 0; const r3 = [];
  for (let page = 0; page < 20; page++) d3.deal(6, { level: null, temp: 68, recent: r3 }).forEach(o => { r3.push(o.key); if (o.acc) beltDealt++; });
  out.beltsInDeck = d3.accs.length; out.beltDealt = beltDealt;
  // sunglasses: on Daytime looks sometimes, never on a night level
  const d4 = C.build(items.concat(extras, [{ id: 'sun-1', name: 'Tortoise Round Sunglasses', category: 'Sunglasses', colourName: 'Tortoise', colourHex: '#6b4423' }]));
  const sunAt = (lvl) => { let n = 0, tot = 0; const r = []; for (let pg = 0; pg < 30; pg++) d4.deal(6, { level: lvl, temp: 68, recent: r }).forEach(o => { r.push(o.key); tot++; if (o.acc && o.acc.id === 'sun-1') n++; }); return [n, tot]; };
  out.sunDay = sunAt(2); out.sunNight = sunAt(3).concat(sunAt(5), sunAt(6));
  // .86.44 belt rules (David, 21 Nov): plain belts match the shoes; no belt with beltless
  // trousers; white sneakers lift the rule; multicolour belts only in harmony with the shoes
  const P = (o, i) => C.profile(Object.assign({ colourHex: '#777777' }, o), 900 + i);
  const BELTS = [
    { id: 'bb-brown', name: 'Dark Brown Leather Belt', category: 'Belts', colourName: 'Dark Brown' },
    { id: 'bb-black', name: 'Black Leather Belt', category: 'Belts', colourName: 'Black' },
    { id: 'bb-navy', name: 'Navy Pebbled Leather Belt', category: 'Belts', colourName: 'Navy' },
    { id: 'bb-grey', name: 'Charcoal Leather Belt', category: 'Belts', colourName: 'Charcoal' },
    { id: 'bb-buckle', name: 'Brown Leather Belt, Engraved Silver Buckle', category: 'Belts', colourName: 'Brown' },
    { id: 'bb-suede', name: 'Tobacco Suede Belt', category: 'Belts', colourName: 'Tobacco' },
    { id: 'bb-woven', name: 'Navy Woven Stretch Belt', category: 'Belts', colourName: 'Navy' },
    { id: 'bb-multi', name: 'Blue & Orange Beaded Belt', category: 'Belts', colourName: 'Blue', notes: 'Beaded zigzag pattern on dark leather; brass buckle.' },
    { id: 'bb-polo', name: 'Navy, Red & Tan Woven Polo Belt', category: 'Belts', colourName: 'Navy', notes: 'Woven diamonds with tan leather ends; silver buckle.' } ].map(P);
  const beltTop = P({ id: 't1', name: 'White Oxford Shirt', category: 'Shirts', colourName: 'White' }, 50);
  const beltChino = P({ id: 'b1', name: 'Beige Stretch Chino', category: 'Trousers', colourName: 'Beige' }, 51);
  const beltShoe = (name, colourName) => P({ id: 's-' + name, name, category: 'Shoes', colourName }, 52);
  const pick = (s, b, lv, belts, key) => { const r = C.beltFor(belts || BELTS, { t: beltTop, b: b || beltChino, s, l: null, key: key || 'k' }, lv); return r ? r.id : null; };
  const beltKeys = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l'];
  const all = (s, lv, b) => [...new Set(beltKeys.map(k => pick(s, b, lv, null, k)))];
  const beltFam = id => id && BELTS.find(x => x.id === id).fam, isMulti = id => !!id && BELTS.find(x => x.id === id).multi;
  const plainFam = (s, lv) => all(s, lv).filter(id => !isMulti(id)).map(beltFam);
  out.belt = {
    profiles: BELTS.map(b => [b.id, b.fam, !!b.multi, !!b.casualBelt]),
    brown: plainFam(beltShoe('Dark Brown Suede Penny Loafers', 'Dark Brown'), 3),
    tan: plainFam(beltShoe('Tan Suede Penny Loafers', 'Tan'), 3),
    black: plainFam(beltShoe('Black Leather Loafers', 'Black'), 3),
    navy: plainFam(beltShoe('Navy Suede Loafers', 'Navy'), 3),
    grey: plainFam(beltShoe('Grey Suede Loafers', 'Grey'), 3),
    greige: plainFam(beltShoe('Greige Suede Penny Loafers', 'Greige'), 3),
    suedeFirst: pick(beltShoe('Tobacco Suede Loafers', 'Tobacco'), null, 5),
    dressy: all(beltShoe('Navy Suede Loafers', 'Navy'), 5).concat(all(beltShoe('Rust Suede Tassel Loafers', 'Rust'), 5)),
    whiteSneaker: all(beltShoe('White Leather Sneakers', 'White'), 2),
    drawstring: pick(beltShoe('Black Leather Loafers', 'Black'), P({ id: 'b2', name: 'Navy Drawstring Trousers', category: 'Trousers', colourName: 'Navy' }, 53), 3),
    sideAdjusters: pick(beltShoe('Black Leather Loafers', 'Black'), P({ id: 'b3', name: 'Ivory Seersucker Pants', category: 'Trousers', colourName: 'Ivory', notes: 'Ivory seersucker with side adjusters.' }, 54), 3),
    noBeltNote: pick(beltShoe('Black Leather Loafers', 'Black'), P({ id: 'b4', name: 'Cream Linen Trousers', category: 'Trousers', colourName: 'Cream', notes: 'No belt.' }, 55), 3),
    swim: pick(beltShoe('Black Leather Loafers', 'Black'), P({ id: 'b5', name: 'Navy Swim Trunks', category: 'Bathing suits', colourName: 'Navy' }, 56), 2),
    blackTie: pick(beltShoe('Black Leather Loafers', 'Black'), null, 7),
    multiOnBlack: all(beltShoe('Black Leather Loafers', 'Black'), 2).filter(isMulti),
    multiAloneBlack: pick(beltShoe('Black Leather Loafers', 'Black'), null, 2, BELTS.filter(b => b.multi)),
    multiAloneRust: pick(beltShoe('Rust Suede Tassel Loafers', 'Rust'), null, 2, BELTS.filter(b => b.id === 'bb-multi')),
    multiAloneDark: pick(beltShoe('Dark Brown Suede Penny Loafers', 'Dark brown'), null, 2, BELTS.filter(b => b.id === 'bb-multi')),
    multiAloneTan: pick(beltShoe('Tan Suede Penny Loafers', 'Tan'), null, 2, BELTS.filter(b => b.id === 'bb-polo')),
    creamLoafer: pick(beltShoe('Cream Leather Loafers', 'Cream'), null, 5, BELTS.filter(b => !b.multi)) };
  const d6 = C.build(items.concat(extras, BELTS.map(b => ({ id: b.id, name: b.name, category: 'Belts', colourName: b.fam === 'grey' ? 'Charcoal' : b.name.split(' ')[0], colourHex: '#555555' }))));
  let dealtBelt = 0, dealtN = 0; const r6 = [];
  for (let pg = 0; pg < 12; pg++) d6.deal(6, { level: 3, temp: 68, recent: r6 }).forEach(o => { r6.push(o.key); dealtN++; if (o.belt) dealtBelt++; });
  out.belt.dealt = [dealtBelt, dealtN];
  out.newPiecePlaceable = !!d2.coverage(null)['new-1'];
  // levels
  out.levels = {};
  const allLevels = C.build(items.concat(extras));
  for (let L = 1; L <= 7; L++) {
    const pg = allLevels.deal(6, { level: L });
    out.levels[L] = { pool: allLevels.uniqueCount(L), dealt: pg.length, inLevel: pg.every(o => (o.mask & (1 << L))) };
  }
  // banned never returns
  const first = deck.deal(1, { level: 4 })[0];
  const banned = {}; banned[first.key] = 1;
  let back = false;
  for (let i = 0; i < 40; i++) if (deck.deal(6, { level: 4, banned }).some(o => o.key === first.key)) back = true;
  out.bannedReturned = back;
  return out;
}"""


def start_server():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(ROOT), **k)

        def log_message(self, *a):
            pass

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Quiet)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def main() -> int:
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    results = []

    def check(name, ok, detail=""):
        results.append(bool(ok))
        print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail != "" else ""))

    httpd, url = start_server()
    try:
        with sync_playwright() as p:
            browser = p.webkit.launch()
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                      is_mobile=True, has_touch=True, service_workers="block")
            ctx.add_init_script(STANDALONE_INIT)
            # These two blue receipt rows describe the same garment, which the app merges.
            ui_items = [i for i in photographed_closet() if i["id"] != "rcptbuy-1dnqhzg17"]
            seed = {"items": ui_items, "todaySource": "wardrobe", "formality": 3}   # .86.65: level 4 is Evening Sharp now; this test means Evening Casual
            ctx.add_init_script("(() => { if (localStorage.getItem('wardrobe.items')) return; const S = %s;"
                                " for (const k in S) localStorage.setItem('wardrobe.' + k, JSON.stringify(S[k])); })();" % json.dumps(seed))
            ctx.route(BLOCK, lambda r: r.abort())
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url, wait_until="load")
            page.wait_for_timeout(1500)
            check("build is .73", page.evaluate("window.WARDROBE_BUILD") == BUILD)

            eng = page.evaluate(ENGINE_JS, [FIXTURE, garments_for_all_levels()])
            check("composer present", eng.get("ok"))
            check("83-piece closet makes thousands of outfits", eng["combos"] >= 5000, eng["combos"])
            check("every outfit is unique", eng["uniqueKeys"] == eng["combos"])
            check("every outfit is top + bottom + shoes (+ layer)", eng["structureOk"])
            check("every piece can appear", eng["coverage"] == len(FIXTURE), f'{eng["coverage"]}/{len(FIXTURE)}')
            check("600 dealt with no repeats", eng["dealt"] == 600 and eng["dups"] == 0, f'{eng["dealt"]} unique, {eng["dups"]} repeats')
            # .86.72 (David, 22 Nov 2026: "I don't like wearing darker colors under lighter colors generally"): a dark
            # shirt no longer goes under a lighter blazer, so a piece or two is now rare rather than everywhere
            check("all 83 pieces shown within 600 deals (two may be rare)", eng["shown"] >= len(FIXTURE) - 2, eng["shown"])
            check("a new piece is placeable", eng["newPiecePlaceable"])
            check("a new piece is dealt within the first pages", 0 <= eng["newPieceAt"] < 60, eng["newPieceAt"])
            check("a belt is never the random accessory", eng["beltsInDeck"] == 2 and eng["beltDealt"] == 0, (eng["beltsInDeck"], eng["beltDealt"]))
            check("sunglasses go with Daytime looks, never a night level", eng["sunDay"][1] > 20 and eng["sunDay"][0] > 0 and eng["sunNight"][0] == 0 and eng["sunNight"][2] == 0 and eng["sunNight"][4] == 0, (eng["sunDay"], eng["sunNight"]))
            bl = eng["belt"]
            prof = {b[0]: b for b in bl["profiles"]}
            check("a belt's colour ignores its buckle", prof["bb-buckle"][1] == "brown" and not prof["bb-buckle"][2], prof["bb-buckle"])
            check("beaded and polo belts are multicolour; one-colour belts are plain", prof["bb-multi"][2] and prof["bb-polo"][2] and not prof["bb-woven"][2] and not prof["bb-brown"][2], bl["profiles"])
            check("plain belt matches brown shoes", bl["brown"] and set(bl["brown"]) == {"brown"}, bl["brown"])
            check("plain belt matches tan shoes (brown leathers)", bl["tan"] and set(bl["tan"]) == {"brown"}, bl["tan"])
            check("plain belt matches black shoes", set(bl["black"]) == {"black"}, bl["black"])
            check("plain belt matches navy shoes", set(bl["navy"]) == {"navy"}, bl["navy"])
            check("plain belt matches grey shoes", set(bl["grey"]) == {"grey"}, bl["grey"])
            check("greige shoes take a brown belt, not what the photo's hex says", bl["greige"] and set(bl["greige"]) == {"brown"}, bl["greige"])
            check("suede shoes prefer the suede belt", bl["suedeFirst"] == "bb-suede", bl["suedeFirst"])
            check("blazer-level looks take a plain leather belt", all(b in ("bb-navy", "bb-brown", "bb-buckle", "bb-suede") for b in bl["dressy"]), bl["dressy"])
            check("white sneakers lift the match rule but still get a belt", bl["whiteSneaker"] and all(bl["whiteSneaker"]), bl["whiteSneaker"])
            check("no belt with drawstring trousers", bl["drawstring"] is None, bl["drawstring"])
            check("no belt with side-adjuster trousers", bl["sideAdjusters"] is None, bl["sideAdjusters"])
            check("no belt when the notes say no belt", bl["noBeltNote"] is None, bl["noBeltNote"])
            check("no belt with swim trunks or at black tie", bl["swim"] is None and bl["blackTie"] is None, (bl["swim"], bl["blackTie"]))
            check("a multicolour belt is never paired with shoes it does not harmonise with", bl["multiOnBlack"] == [] and bl["multiAloneBlack"] is None, (bl["multiOnBlack"], bl["multiAloneBlack"]))
            # .87.09 (David, 24 Nov 2026: "dark brown with dark brown. Caramel with caramel"): a beaded or woven belt
            # counts by its leather, so the beaded belt on dark leather goes with dark brown shoes and no longer with rust
            check("a multicolour belt joins shoes that share its leather's shade", bl["multiAloneDark"] == "bb-multi" and bl["multiAloneRust"] is None and bl["multiAloneTan"] == "bb-polo", (bl["multiAloneDark"], bl["multiAloneRust"], bl["multiAloneTan"]))
            check("with no belt in the shoes' colour, the nearest plain leather is used", bl["creamLoafer"] in ("bb-brown", "bb-buckle", "bb-suede"), bl["creamLoafer"])
            check("dealt outfits carry a belt", bl["dealt"][0] > bl["dealt"][1] * 0.6, bl["dealt"])
            for L, v in eng["levels"].items():
                check(f"outfit type {L} deals", v["dealt"] >= 1 and v["inLevel"], v)
            check("a disliked combo never returns", not eng["bannedReturned"])

            closet_n = page.evaluate("wardrobeItems.filter(i => !String(i.id).startsWith('seed-')).length")
            check("fixture closet loaded", closet_n == len(ui_items), closet_n)
            page.wait_for_timeout(1500)
            home = page.evaluate("""() => ({ composer: !!(todayLook && todayLook.composer), key: todayLook && todayLook.composerKey,
                cells: document.querySelectorAll('#today-collage .flatlay .fl-cell').length,
                collage: !document.getElementById('today-collage').hidden,
                fits: (document.scrollingElement || document.documentElement).scrollHeight <= window.innerHeight + 1 })""")
            check("Home deals a composed closet look", home["composer"], home)
            check("Home shows him, never a tile grid (.78.2c)", not home["collage"], home)
            check("Home still fits one screen", home["fits"])
            dis_before = page.evaluate("localStorage.getItem('wardrobe.dislikedImgs')")
            # Dislike is hidden on Home in .75 (heart + next only); still invoke the handler.
            page.evaluate("document.getElementById('today-dislike') && document.getElementById('today-dislike').click()")
            page.wait_for_timeout(1500)
            after = page.evaluate("({ key: todayLook.composerKey, dis: localStorage.getItem('wardrobe.dislikedImgs'), banned: Object.keys((JSON.parse(localStorage.getItem('wardrobe.composerPrefs') || '{}').banned) || {}) })")
            check("hero Dislike deals a new combo", after["key"] and after["key"] != home["key"])
            added = [x for x in json.loads(after["dis"] or "[]") if x not in json.loads(dis_before or "[]")]
            check("hero Dislike bans the combo (and only his on-body render), not a piece photo", home["key"] in after["banned"] and all("/onbody/" in x or "/onbody-hires/" in x for x in added), (added, home["key"], after))   # .87.23: a redrawn outfit's picture is its high-res copy

            page.locator("#section-ideas").click(); page.wait_for_timeout(250)
            page.wait_for_function("() => __cfLooks81().length >= 8")   # .86.72: fewer layered looks after the lighter-under-darker rule
            n0 = page.evaluate("document.querySelectorAll('#cf-grid .cf-card').length")
            check("Outfits Mine closet feed shows", n0 >= 8 and not page.evaluate("document.getElementById('closet-feed').hidden"), n0)
            page.locator("#cf-sentinel").scroll_into_view_if_needed()
            page.wait_for_function("n => __cfLooks81().length > n", arg=n0)
            n1 = page.evaluate("document.querySelectorAll('#cf-grid .cf-card').length")
            check("infinite scroll appends", n1 > n0, f"{n0} -> {n1}")
            check("every card has an avatar or the outfit's piece grid", page.evaluate("document.querySelectorAll('#cf-grid .cf-card .cf-media > .flatlay, #cf-grid .cf-card .cf-media > .mine-avatar').length") == n1)
            page.locator('#section-inspo').click(); page.wait_for_timeout(300)  # .86.42: Mix lives in Inspo
            check("Inspo hides the closet feed", page.evaluate("document.getElementById('closet-feed').hidden"))
            page.locator('#section-ideas').click(); page.wait_for_timeout(300)
            check("no JS errors", not errors, errors[:3])
            ctx.close(); browser.close()
    finally:
        httpd.shutdown()
    print(f"{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
