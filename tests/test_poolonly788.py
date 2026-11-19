"""Build .78.8c (shipped as .78.9b): Pool-only pieces.

Pool slides (Frescobol Carioca / Brunello Cucinelli slides, any shoe whose
name or subtype says slide) carry occasionOnly ["Pool"] and are only ever
dealt with swim. On the 83-piece fixture closet plus two pairs of slides
and swim trunks (photos on every piece), in Chromium 390x844:
  * itemOccasionOnly flags both slides (and not loafers / sneakers); the
    flag is written onto the stored pieces
  * the composer deck: no combo puts slides with a non-swim bottom, and
    slides do pair with the swim trunks
  * composerLooks (types 2-7, 200 looks), homeComposerLooks75, closet
    anchors, buildClosetLooks, generateComboLook / dealerLook: no slides
    outside a swim look
  * Home: 40 Next deals, never slides; the safety net repairs a look that
    smuggles slides in with jeans
  * Build board: 30 Shuffles never leave slides on a non-swim board
  * no JS errors

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_poolonly788.py
"""
from __future__ import annotations

import http.server, json, os, re, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BUILD = "2026-11-19.79.3"
PH = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
FIXTURE = json.loads((Path(__file__).resolve().parent / "fixture_closet83.json").read_text())
EXTRA = [
    {"id": "pool-s1", "name": "Frescobol Carioca Suede-Band Slides", "category": "Shoes", "colourName": "White / Navy", "colourHex": "#f2f2f2"},
    {"id": "pool-s2", "name": "Brunello Cucinelli Slides", "category": "Shoes", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "swim-1", "name": "Navy Swim Trunks", "category": "Bathing suits", "colourName": "Navy", "colourHex": "#1f2a44"},
]
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:400]))
    if not ok:
        fails.append(name)


def start_server():
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k): super().__init__(*a, directory=str(ROOT), **k)
        def log_message(self, *a): pass
    h = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Q); h.allow_reuse_address = True
    threading.Thread(target=h.serve_forever, daemon=True).start()
    return h, f"http://127.0.0.1:{h.server_address[1]}/"


POOL = "['pool-s1','pool-s2']"


def main():
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    httpd, url = start_server()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
            items = [dict(i, addedISO="2026-11-17", photo=PH) for i in FIXTURE + EXTRA]
            seed = {"items": items, "todaySource": "wardrobe", "formality": 4}
            ctx.add_init_script("(() => { if (localStorage.getItem('wardrobe.items')) return; const S = %s;"
                                " for (const k in S) localStorage.setItem('wardrobe.' + k, JSON.stringify(S[k])); })();" % json.dumps(seed))
            ctx.route(BLOCK, lambda r: r.abort())
            pg = b and ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(url, wait_until="load"); pg.wait_for_timeout(2000)
            check("build", pg.evaluate("WARDROBE_BUILD") == BUILD, pg.evaluate("WARDROBE_BUILD"))

            f = pg.evaluate("""() => ({ s1: itemOccasionOnly(closetItemById('pool-s1')), s2: itemOccasionOnly(closetItemById('pool-s2')),
              others: wardrobeItems.filter(i => i.category === 'Shoes' && !/^pool-/.test(i.id)).filter(i => itemPoolOnly(i)).map(i => i.name),
              stored: JSON.parse(localStorage.getItem('wardrobe.items')).filter(i => /^pool-/.test(i.id)).map(i => i.occasionOnly) })""")
            check("both slides are Pool-only", f["s1"] == ["Pool"] and f["s2"] == ["Pool"], f)
            check("no other shoe is Pool-only", not f["others"], f["others"])
            check("occasionOnly written onto the stored pieces", f["stored"] == [["Pool"], ["Pool"]], f["stored"])

            d = pg.evaluate("""() => { const deck = WardrobeComposer.build(wardrobeItems.filter(i => !i.laundry)), P = %s;
              const bad = deck.combos.filter(c => P.includes(c.s.id) && !(c.b.kind === 'swim' || c.b.swim)).length;
              const ok = deck.combos.filter(c => P.includes(c.s.id) && (c.b.kind === 'swim' || c.b.swim)).length;
              return { n: deck.combos.length, bad, ok }; }""" % POOL)
            check("composer: slides never with a non-swim bottom", d["bad"] == 0 and d["n"] > 100, d)
            check("composer: slides still pair with the swim trunks", d["ok"] > 0, d)

            hasP = "(l => (l && (l.fwPieces || []).some(p => %s.includes(p.id))) || (l && String(l.composerKey || '').split('|').some(x => %s.includes(x))))" % (POOL, POOL)
            g = pg.evaluate("""() => { const hasP = %s, swim = l => lookItems788(l).some(pieceIsSwim); let n = 0, bad = [];
              for (let t = 2; t <= 7; t++) { formalityLevel = t; for (let k = 0; k < 6; k++) { (composerLooks({ count: 6 }) || []).forEach(l => { n++; if (hasP(l) && !swim(l)) bad.push(l.title); }); } }
              formalityLevel = 4;
              const h = (homeComposerLooks75(12) || []).filter(l => hasP(l) && !swim(l)).length;
              const anchors = closetAnchorItems().filter(i => %s.includes(i.id)).length;
              let bc = 0; for (let k = 0; k < 10; k++) { const r = buildClosetLooks({ count: 6 }); (Array.isArray(r) ? r : r ? [r] : []).forEach(l => { if (hasP(l) && !swim(l)) bc++; }); }
              let combo = 0; for (let k = 0; k < 20; k++) { let l = null; try { l = generateComboLook({}); } catch (e) {} if (hasP(l) && !swim(l)) combo++; }
              return { n, bad: bad.slice(0, 3), nb: bad.length, h, anchors, bc, combo }; }""" % (hasP, POOL))
            check("composerLooks types 2-7: no slides outside swim", g["nb"] == 0 and g["n"] >= 150, g)
            check("homeComposerLooks75: no slides", g["h"] == 0, g)
            check("closet anchors never a slide", g["anchors"] == 0, g)
            check("buildClosetLooks / generateComboLook: no slides", g["bc"] == 0 and g["combo"] == 0, g)

            pg.click("#tab-today"); pg.wait_for_timeout(400)
            seen = []
            for i in range(40):
                seen.append(pg.evaluate("(%s)(todayLook)" % hasP))
                pg.evaluate("dealAnotherToday()"); pg.wait_for_timeout(60)
            check("Home: 40 deals, never slides", not any(seen), seen)

            r = pg.evaluate("""() => { const shoe = closetItemById('pool-s1'), jeans = wardrobeItems.find(i => i.category === 'Jeans'), top = wardrobeItems.find(i => i.category === 'Polos');
              const l = { title: 'x', fwPieces: [top, jeans, shoe].map(i => ({ id: i.id, name: i.name, category: i.category })) };
              const before = lookOccasionOk(l); poolOnlyRepair788(l);
              const sw = { fwPieces: [top, closetItemById('swim-1'), shoe].map(i => ({ id: i.id, name: i.name, category: i.category })) };
              return { before, after: lookOccasionOk(l), shoes: l.fwPieces.filter(p => p.category === 'Shoes').map(p => p.id), swimOk: lookOccasionOk(sw) }; }""")
            check("safety net: slides with jeans are swapped for another shoe", r["before"] is False and r["after"] is True and r["shoes"] and r["shoes"][0] not in ("pool-s1", "pool-s2"), r)
            check("slides with swim trunks are fine", r["swimOk"] is True, r)

            pg.evaluate("switchTab('find')"); pg.wait_for_timeout(300)
            pg.evaluate("editShow('build')"); pg.wait_for_timeout(400)
            leaks = 0
            for i in range(30):
                pg.evaluate("document.getElementById('edit-shuffle').click()"); pg.wait_for_timeout(40)
                t = pg.evaluate("(document.querySelector('#panel-find .edit-board, #edit-board, #panel-find') || document.body).innerText")
                if re.search(r"Slides", t) and not re.search(r"Swim Trunks", t): leaks += 1
            check("Build Shuffle x30: never slides on a non-swim board", leaks == 0, leaks)
            check("no JS errors", not errs, errs[:3])
            b.close()
    finally:
        httpd.shutdown()
    print("FAILS", len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
