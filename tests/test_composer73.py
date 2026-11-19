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

ROOT = Path(__file__).resolve().parents[1]
BUILD = "2026-11-19.78.1"
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

ENGINE_JS = """(items) => {
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
    deck.deal(6, { level: null, recent, exposure }).forEach(o => {
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
  for (let page = 0; page < 10 && firstNew < 0; page++) {
    const pg = d2.deal(6, { level: null, recent: r2, exposure: e2 });
    pg.forEach((o, i) => { if (firstNew < 0 && o.ids.includes('new-1')) firstNew = page * 6 + i; r2.push(o.key); o.ids.forEach(id => { e2[id] = (e2[id] || 0) + 1; }); });
  }
  out.newPieceAt = firstNew;
  out.newPiecePlaceable = !!d2.coverage(null)['new-1'];
  // levels
  out.levels = {};
  for (let L = 1; L <= 7; L++) {
    const pg = deck.deal(6, { level: L });
    out.levels[L] = { pool: deck.uniqueCount(L), dealt: pg.length, inLevel: pg.every(o => (o.mask & (1 << L)) || L >= 6) };
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
            seed = {"items": [dict(i, addedISO="2026-11-17", photo=FIXTURE_PHOTO) for i in FIXTURE], "todaySource": "wardrobe", "formality": 4}
            ctx.add_init_script("(() => { if (localStorage.getItem('wardrobe.items')) return; const S = %s;"
                                " for (const k in S) localStorage.setItem('wardrobe.' + k, JSON.stringify(S[k])); })();" % json.dumps(seed))
            ctx.route(BLOCK, lambda r: r.abort())
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url, wait_until="load")
            page.wait_for_timeout(1500)
            check("build is .73", page.evaluate("window.WARDROBE_BUILD") == BUILD)

            eng = page.evaluate(ENGINE_JS, FIXTURE)
            check("composer present", eng.get("ok"))
            check("83-piece closet makes thousands of outfits", eng["combos"] >= 5000, eng["combos"])
            check("every outfit is unique", eng["uniqueKeys"] == eng["combos"])
            check("every outfit is top + bottom + shoes (+ layer)", eng["structureOk"])
            check("every piece can appear", eng["coverage"] == len(FIXTURE), f'{eng["coverage"]}/{len(FIXTURE)}')
            check("600 dealt with no repeats", eng["dealt"] == 600 and eng["dups"] == 0, f'{eng["dealt"]} unique, {eng["dups"]} repeats')
            check("all 83 pieces shown within 600 deals", eng["shown"] == len(FIXTURE), eng["shown"])
            check("a new piece is placeable", eng["newPiecePlaceable"])
            check("a new piece is dealt within the first pages", 0 <= eng["newPieceAt"] < 60, eng["newPieceAt"])
            for L, v in eng["levels"].items():
                check(f"outfit type {L} deals", v["dealt"] >= 1 and v["inLevel"], v)
            check("a disliked combo never returns", not eng["bannedReturned"])

            closet_n = page.evaluate("wardrobeItems.filter(i => !String(i.id).startsWith('seed-')).length")
            check("fixture closet loaded", closet_n == len(FIXTURE), closet_n)
            home = page.evaluate("""() => ({ composer: !!(todayLook && todayLook.composer), key: todayLook && todayLook.composerKey,
                cells: document.querySelectorAll('#today-collage .flatlay .fl-cell').length,
                collage: !document.getElementById('today-collage').hidden,
                fits: (document.scrollingElement || document.documentElement).scrollHeight <= window.innerHeight + 1 })""")
            check("Home deals a composed closet look", home["composer"], home)
            check("Home shows the flat-lay", home["collage"] and home["cells"] >= 3, home["cells"])
            check("Home still fits one screen", home["fits"])
            dis_before = page.evaluate("localStorage.getItem('wardrobe.dislikedImgs')")
            # Dislike is hidden on Home in .75 (heart + next only); still invoke the handler.
            page.evaluate("document.getElementById('today-dislike') && document.getElementById('today-dislike').click()")
            page.wait_for_timeout(300)
            after = page.evaluate("({ key: todayLook.composerKey, dis: localStorage.getItem('wardrobe.dislikedImgs'), banned: Object.keys((JSON.parse(localStorage.getItem('wardrobe.composerPrefs') || '{}').banned) || {}) })")
            check("hero Dislike deals a new combo", after["key"] and after["key"] != home["key"])
            check("hero Dislike bans the combo, not a photo", home["key"] in after["banned"] and after["dis"] == dis_before)

            page.locator("#section-ideas").click(); page.wait_for_timeout(250)
            page.locator("#outfits-mine").click(); page.wait_for_timeout(700)
            n0 = page.evaluate("document.querySelectorAll('#cf-grid .cf-card').length")
            check("Outfits Mine closet feed shows", n0 >= 12 and not page.evaluate("document.getElementById('closet-feed').hidden"), n0)
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)"); page.wait_for_timeout(500)
            n1 = page.evaluate("document.querySelectorAll('#cf-grid .cf-card').length")
            check("infinite scroll appends", n1 > n0, f"{n0} -> {n1}")
            check("feed cards have flat-lays", page.evaluate("document.querySelectorAll('#cf-grid .cf-card .flatlay').length") == n1)
            page.locator("#outfits-inspo").click(); page.wait_for_timeout(300)
            check("Inspo hides the closet feed", page.evaluate("document.getElementById('closet-feed').hidden"))
            page.locator("#outfits-mine").click(); page.wait_for_timeout(300)
            check("no JS errors", not errors, errors[:3])
            ctx.close(); browser.close()
    finally:
        httpd.shutdown()
    print(f"{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
