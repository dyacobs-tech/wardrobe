#!/usr/bin/env python3
"""Build .77 — closet records are never deleted by accident.

Root cause of ".. trying to delete 13 of 83 records": the one-time .53
closet merge (store key repair53, device-local) clustered DISTINCT
pieces as "the same garment" (same brand + model number, token subset,
60% token overlap) and dropped the losers from the closet; the sync
diff then tombstoned them, which would delete them on every device.

  1. A first boot with his 83-piece closet (+ three different Levi's 517
     and one true duplicate) keeps every distinct piece; only the true
     duplicate merges.
  2. Nothing from that boot is queued as a closet delete, the mass-delete
     alert does not appear, and no sync request carries a closet delete.
  3. A record that vanishes without a deliberate delete is not
     tombstoned; the device schedules a full re-download instead.
  4. A deliberate delete (deleteEntry) still tombstones and is sent.
All workers.dev traffic is intercepted locally — nothing reaches a server.
"""
from __future__ import annotations

import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FX = json.loads((ROOT / "tests/fixture_syncsafety77.json").read_text())
fails: list[str] = []


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
            # answer like an empty server so the client proceeds to push
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"now": 1, "recs": [], "meta": None}))
        return r.abort()

    seed = ("(() => { if (sessionStorage.getItem('s77')) return; sessionStorage.setItem('s77', '1');"
            " localStorage.setItem('wardrobe.items', %s);"
            " localStorage.setItem('wardrobe.sync', JSON.stringify({key: 't77t77t77t77t77t77t77t77t77t77t77t77t77t77t77t77', acct: 'test77', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'x', lastOk: 0})); })();"
            % json.dumps(json.dumps(FX)))
    with sync_playwright() as p:
        b = p.webkit.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        ctx.add_init_script(seed)
        ctx.route("**/*.workers.dev/**", route)
        errors = []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base, wait_until="load")
        pg.wait_for_timeout(4000)
        ids = set(pg.evaluate("wardrobeItems.map(i => i.id)"))
        distinct = [i["id"] for i in FX if not i["id"].startswith("t77-dup")]
        missing = [i for i in distinct if i not in ids]
        check("every distinct piece survives the first-run repair", not missing, missing)
        check("the three Levi's 517 stay three pieces", all(x in ids for x in ("t77-levis-a", "t77-levis-b", "t77-levis-c")))
        check("a true duplicate still merges", len([x for x in ("t77-dup-1", "t77-dup-2") if x in ids]) == 1, ids & {"t77-dup-1", "t77-dup-2"})
        tombs = pg.evaluate("Object.keys(SY.tomb.items || {})")
        check("no closet tombstones queued", not tombs, tombs)
        check("no mass-delete hold", pg.evaluate("_syMassHold") is None, pg.evaluate("_syMassHold"))
        alert = pg.evaluate("(() => { const e = document.getElementById('data-alert'); return !!(e && !e.hidden && /trying to delete/.test(e.textContent)); })()")
        check("no 'trying to delete' alert", not alert)

        # 3. a record vanishing without a deliberate delete
        pg.evaluate("syTrackChanges()")
        victim = distinct[5]
        pg.evaluate("""id => { SY.restore59 = SY.key; wardrobeItems = wardrobeItems.filter(i => i.id !== id); persistAll(); syTrackChanges(); }""", victim)
        st = pg.evaluate("id => ({ tomb: !!(SY.tomb.items && SY.tomb.items[id]), dirty: !!(SY.dirty.items && SY.dirty.items[id]), snap: !!SY.snap.items[id], restore: SY.restore59 })", victim)
        check("an undeliberate disappearance is not tombstoned", not st["tomb"] and not st["dirty"], st)
        check("…and schedules a full re-download", st["restore"] is None, st)

        # 4. a deliberate delete still works
        target = distinct[6]
        pg.evaluate("id => { deleteEntry('items', id); syTrackChanges(); }", target)
        check("a deliberate delete is tombstoned", pg.evaluate("id => !!SY.tomb.items[id] && !!SY.dirty.items[id]", target))

        # what went over the wire during boot: never a closet delete except the deliberate one
        pg.wait_for_timeout(500)
        dels = [c["id"] for body in sent for c in (body.get("changes") or []) if c.get("coll") == "items" and c.get("deleted")]
        check("no accidental closet delete was ever sent", all(d == target for d in dels), dels)
        check("no page errors", not errors, errors)
        b.close()
    httpd.shutdown()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
