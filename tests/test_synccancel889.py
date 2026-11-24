#!/usr/bin/env python3
"""A delete the sync server refuses leaves the piece on this phone too (audit, fix 10, .86.89).

From the audit David asked to have fixed ("Just start going through ALL of these in order"): the hardened sync
worker (worker/README.md, not deployed; deploying it needs David's yes) answers a delete it will not apply with
200, a `cancelled` list and the live record. The app used to clear its own delete mark first and then ignore the
live record, so the piece stayed deleted on this phone while it was still on every other device. This must be
fixed in the app before that worker can go live.

  1. A refused delete: the piece comes back on this phone (memory and storage), with no delete mark left.
  2. Today's server (no `cancelled`): the same delete still goes through.
  4. (.86.92) Every delete carries the version this phone last had of the piece (baseUpdatedAt), which the
     hardened worker needs to accept a bulk delete David confirms.
  3. (.86.97) Edits are stamped with the phone's own time, whatever the server's "now" says: that value is a paging
     bookmark 3-4 minutes behind the server's clock, and .86.89-.86.96 wrongly used it as the clock, stamping every
     edit minutes in the past.
All workers.dev traffic is answered locally; nothing reaches a server.
"""
from __future__ import annotations

import http.server
import json
import socketserver
import sys
import threading
import time
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


def run(base, refuse, skew=None):
    state = {"now": 100}
    piece = [i for i in FX if not i["id"].startswith("t77-dup")][3]

    def route(r):
        if r.request.method == "POST" and "/sync" in r.request.url:
            body = json.loads(r.request.post_data or "{}")
            state.setdefault("bodies", []).append(body)
            state["now"] += 1
            out = {"now": state["now"] if skew is None else int(time.time() * 1000) + skew, "recs": [], "meta": None}
            if body.get("since") == 0 and not state.get("served"):
                state["served"] = 1   # the first full download: the server has this piece at version 777
                out["recs"] = [{"coll": "items", "id": piece["id"], "updatedAt": 777, "data": piece}]
            dels = [c for c in (body.get("changes") or []) if c.get("coll") == "items" and c.get("deleted")]
            if refuse and dels:
                out["cancelled"] = [{"coll": "items", "id": c["id"], "reason": "server_truth"} for c in dels]
                out["recs"] = [{"coll": "items", "id": c["id"], "updatedAt": 5, "data": piece} for c in dels if c["id"] == piece["id"]]
            return r.fulfill(status=200, content_type="application/json", body=json.dumps(out))
        return r.abort()

    seed = ("(() => { if (sessionStorage.getItem('s889')) return; sessionStorage.setItem('s889', '1');"
            " localStorage.setItem('wardrobe.items', %s);"
            " localStorage.setItem('wardrobe.sync', JSON.stringify({key: 't889t889t889t889t889t889t889t889t889t889t889t889', acct: 'test889', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'x', lastOk: 0})); })()"
            % json.dumps(json.dumps(FX)))
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
        ctx.add_init_script(seed)
        ctx.route("**/*.workers.dev/**", route)
        errors = []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base, wait_until="load")
        pg.wait_for_function("() => typeof syncNow === 'function' && typeof SY !== 'undefined' && SY.lastOk > 0", timeout=30000)
        pg.wait_for_timeout(500)
        pid = piece["id"]
        if skew is not None:
            pg.evaluate("() => syncNow()")
            pg.wait_for_function("() => !_syBusy", timeout=30000)
            pg.wait_for_timeout(300)
            stamp = pg.evaluate("""id => { const it = wardrobeItems.find(i => i.id === id); it.notes = 'edited ' + Date.now(); persistAll(); syTrackChanges();
              return [SY.st.items[id], Date.now()]; }""", pid)
            off = stamp[0] - stamp[1]
            if True:
                check("the edit is stamped with the phone's own time (server bookmark %+ds)" % (skew // 1000), abs(off) < 5000, off)
            check("no page errors", not errors, errors)
            b.close()
            return
        pg.evaluate("id => { deleteEntry('items', id); syTrackChanges(); }", pid)
        check("the delete is queued", pg.evaluate("id => !!SY.tomb.items[id] && !!SY.dirty.items[id]", pid))
        before = pg.evaluate("() => SY.lastOk")
        pg.evaluate("() => syncNow()")
        pg.wait_for_function("t => SY.lastOk > t && !_syBusy", arg=before, timeout=30000)
        pg.wait_for_timeout(500)
        st = pg.evaluate("""id => ({ mem: wardrobeItems.some(i => i.id === id), stored: JSON.parse(localStorage.getItem('wardrobe.items') || '[]').some(i => i.id === id),
            tomb: !!(SY.tomb.items && SY.tomb.items[id]), status: (SY.status || '') })""", pid)
        sentdels = [c for body in state.get("bodies", []) for c in (body.get("changes") or []) if c.get("deleted")]
        # the server's version of the piece: the last copy this phone uploaded, else the one it downloaded (777)
        ups = [c["updatedAt"] for body in state.get("bodies", []) for c in (body.get("changes") or []) if c.get("id") == pid and not c.get("deleted")]
        server_ver = ups[-1] if ups else 777
        check("the delete carries the version the server has", sentdels and all(c.get("baseUpdatedAt") == server_ver for c in sentdels), (sentdels, server_ver))
        if refuse:
            check("refused delete: the piece is back on this phone", st["mem"] and st["stored"], st)
            check("refused delete: no delete mark is left", not st["tomb"], st)
        else:
            check("today's server: the delete still goes through", not st["mem"] and not st["stored"], st)
        check("no page errors", not errors, errors)
        b.close()


def main():
    httpd, base = start_server()
    run(base, refuse=True)
    run(base, refuse=False)
    run(base, refuse=False, skew=3600000)
    run(base, refuse=False, skew=30000)
    run(base, refuse=False, skew=-237000)   # the live server's bookmark: about 4 minutes behind its clock
    httpd.shutdown()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
