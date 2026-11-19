#!/usr/bin/env python3
"""Safety (Nov 19) — no accidental deletes of user data, in any collection.

  A. A Not for me verdict (recordDislike) never deletes saved looks or
     queued looks: they are hidden from My Outfits, and lifting the ban
     brings them back. The boot repair (enforceSavedInvariants) keeps
     them too. Nothing from the verdict is tombstoned.
  B. For EVERY synced user collection: a record that vanishes without a
     deliberate delete is NOT tombstoned (no delete marker, nothing sent);
     a deliberate delete (syDeliberateDelete) IS tombstoned and sent.
  C. Real UI delete paths still mark deliberately (wishlist remove,
     palette delete, worn-entry delete) so deletes still reach devices.
All workers.dev traffic is intercepted locally — nothing reaches a server.
"""
from __future__ import annotations

import http.server, json, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
fails: list[str] = []

COLLS = {"looks": "savedLooks", "queue": "queueLooks", "worn": "wornLog", "inspo": "inspoImages",
         "finds": "finds", "palettes": "customPalettes", "icons": "customIcons", "plan": "weekPlan",
         "anchors": "buildAnchors", "trips": "userTrips", "packed": "packedItems", "receipts": "receiptInbox",
         "shopwish": "shopWishlist", "pricedrops": "priceDrops", "edits": "editMeta", "searches": "editSearches",
         "ask": "askSync", "items": "wardrobeItems", "watches": "watches"}


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:400]))
    if not ok:
        fails.append(name)


def start_server():
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(ROOT), **k)

        def log_message(self, *a):
            pass
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Q)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def main():
    httpd, base = start_server()
    sent = []

    def route(r):
        if r.request.method == "POST" and "/sync" in r.request.url:
            try:
                sent.append(json.loads(r.request.post_data or "{}"))
            except Exception:
                pass
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"now": 1, "recs": [], "meta": None}))
        return r.abort()

    seed = ("(() => { if (sessionStorage.getItem('s1119')) return; sessionStorage.setItem('s1119', '1');"
            " localStorage.setItem('wardrobe.sync', JSON.stringify({key: 't1119t1119t1119t1119t1119t1119t1119t1119t1119t11', acct: 'test1119', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'x', lastOk: 0})); })();")
    with sync_playwright() as p:
        b = p.webkit.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        ctx.add_init_script(seed)
        ctx.route("**/*.workers.dev/**", route)
        errors = []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base, wait_until="load")
        for _ in range(60):
            if pg.evaluate("() => typeof syTrackChanges === 'function' && typeof recordDislike === 'function' && typeof RENDER_POOL !== 'undefined' && RENDER_POOL.length > 0"):
                break
            pg.wait_for_timeout(500)
        pg.wait_for_timeout(2500)

        # ---------- A. dislike never deletes ----------
        a = pg.evaluate("""() => {
          const img = RENDER_POOL[0].img;
          const look = { id: 'tA-look-1', title: 'Test look', img: img, swatches: [{name:'Navy', hex:'#223'}], savedAt: Date.now() };
          const img2 = RENDER_POOL[1].img;
          const q = { id: 'tA-q-1', title: 'Test queued', img: img2, swatches: [], savedAt: Date.now() };
          savedLooks.unshift(look); queueLooks.unshift(q); persistAll(); saveQueue(); syTrackChanges();
          recordDislike(img); recordDislike(img2);
          syTrackChanges();
          const r = {
            savedKept: savedLooks.some(l => l.id === 'tA-look-1'),
            queueKept: queueLooks.some(l => l.id === 'tA-q-1'),
            storedKept: JSON.stringify(store.get('looks', [])).indexOf('tA-look-1') !== -1,
            tombLook: !!(SY.tomb.looks && SY.tomb.looks['tA-look-1']),
            tombQueue: !!(SY.tomb.queue && SY.tomb.queue['tA-q-1']),
            hidden: isDislikedLookAny(look)
          };
          window.enforceSavedInvariants && window.enforceSavedInvariants();
          syTrackChanges();
          r.afterRepairSaved = savedLooks.some(l => l.id === 'tA-look-1'); r.afterRepairQueue = queueLooks.some(l => l.id === 'tA-q-1');
          r.afterRepairKept = r.afterRepairSaved && r.afterRepairQueue;
          r.afterRepairTomb = !!(SY.tomb.looks && SY.tomb.looks['tA-look-1']);
          removeDislike(img); removeDislike(img2);
          r.unbanned = !isDislikedLookAny(look) && savedLooks.some(l => l.id === 'tA-look-1');
          return r;
        }""")
        check("A: dislike keeps the saved look", a["savedKept"] and a["storedKept"], a)
        check("A: dislike keeps the queued look", a["queueKept"], a)
        check("A: dislike tombstones nothing", not a["tombLook"] and not a["tombQueue"], a)
        check("A: disliked look is hidden (view filter)", a["hidden"], a)
        check("A: boot repair keeps disliked looks, no tomb", a["afterRepairKept"] and not a["afterRepairTomb"], a)
        check("A: lifting the ban restores the look", a["unbanned"], a)

        # ---------- B. every collection ----------
        res = pg.evaluate("""(COLLS) => {
          const out = {};
          Object.keys(COLLS).forEach(c => {
            const v = COLLS[c];
            const mk = (n) => {
              const r = { id: 't1119-' + c + '-' + n, title: 'T ' + n, date: '2026-01-0' + n, key: 't1119-' + c + '-' + n, name: 'T ' + n, kind: 'look' };
              if (c === 'items') { r.category = 'Tops'; r.color = 'Navy'; }
              return r;
            };
            const r1 = mk(1), r2 = mk(2);
            try {
              window[v].push(r1, r2);
              syTrackChanges(c);
              const id1 = syRecId(c, r1), id2 = syRecId(c, r2);
              const snapped = !!SY.snap[c][id1] && !!SY.snap[c][id2];
              // accidental disappearance
              window[v] = window[v].filter(x => x !== r1);
              syTrackChanges(c);
              const accTomb = !!(SY.tomb[c] && SY.tomb[c][id1]);
              // deliberate delete
              syDeliberateDelete(c, id2);
              window[v] = window[v].filter(x => x !== r2);
              syTrackChanges(c);
              const delTomb = !!(SY.tomb[c] && SY.tomb[c][id2]) && !!SY.dirty[c][id2];
              out[c] = { snapped, accTomb, delTomb, id1, id2 };
            } catch (e) { out[c] = { err: String(e) }; }
          });
          return out;
        }""", COLLS)
        for c, r in res.items():
            check(f"B[{c}]: tracked", r.get("snapped"), r)
            check(f"B[{c}]: accidental disappearance is NOT tombstoned", r.get("snapped") and not r.get("accTomb"), r)
            check(f"B[{c}]: deliberate delete IS tombstoned", r.get("delTomb"), r)

        # ---------- C. real UI delete paths mark deliberately ----------
        c = pg.evaluate("""() => {
          const r = {};
          shopWishlist.push({ key: 'tC-wish', brand: 'B', name: 'N', price: 1 }); syTrackChanges('shopwish');
          removeWishlistItem('tC-wish'); syTrackChanges('shopwish');
          r.wish = !!(SY.tomb.shopwish && SY.tomb.shopwish['tC-wish']);
          wornLog.unshift({ id: 'tC-worn', date: '2026-01-01', title: 'W', pieces: [] }); store.set('wornLog', wornLog); syTrackChanges('worn');
          removeWornEntryById('tC-worn'); syTrackChanges('worn');
          r.worn = !!(SY.tomb.worn && SY.tomb.worn['tC-worn']);
          return r;
        }""")
        check("C: wishlist remove still deletes everywhere", c["wish"], c)
        check("C: worn-entry delete still deletes everywhere", c["worn"], c)

        pg.evaluate("syncNow && syncNow(false, true)")
        pg.wait_for_timeout(2500)
        accidental = {r["id1"] for r in res.values() if "id1" in r} | {"tA-look-1", "tA-q-1"}
        dels = [ch["id"] for body in sent for ch in (body.get("changes") or []) if ch.get("deleted")]
        check("no accidental delete was ever sent", not (set(dels) & accidental), sorted(set(dels) & accidental))
        # ---------- D. consolidated helpers (Nov 19): one esc, stable names + aliases ----------
        d = pg.evaluate(r"""() => ({
          esc: esc('<a href="x">&\'') === '&lt;a href=&quot;x&quot;&gt;&amp;&#39;' && esc(null) === '' && esc(undefined) === '' && esc(0) === '0',
          aliases: window.cutFor784 === window.cutoutFor && window.cutManifest784 === window.cutoutManifest && window.removeDislike56 === removeDislike
                   && window.lookPhotoBanned56 === lookPhotoBanned && window.syQuarantine56 === syQuarantine && window.enforceSavedInvariants53 === window.enforceSavedInvariants,
          stable: typeof window.cutoutFor === 'function' && typeof lookPhotoBanned === 'function'
        })""")
        check("D: one esc helper, null-safe", d["esc"], d)
        check("D: stable helper names, old names alias them", d["aliases"] and d["stable"], d)
        check("no page errors", not errors, errors)
        b.close()
    httpd.shutdown()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
