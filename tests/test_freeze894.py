#!/usr/bin/env python3
"""The app reports its own freezes to Claude (.86.94).

David, 24 Nov 2026: "And app is freezing when I click the edit !!!!!!!" and "Figure this out pls". The freeze did
not happen on any test device, so the app records the last tap, any stretch of more than 1.5s where the page could
not respond, and a session that ended stuck, and saves a report to the synced feedback list.
  1. A 3.5s stall after a tap is saved as an "[auto] page stuck" note naming the tap, and is sent with the next sync.
  2. A session that ended while stuck (no clean close) is reported on the next open.
"""
import http.server, json, socketserver, sys, threading, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
fails = []
def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:300]))
    if not ok: fails.append(name)

class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(ROOT), **k)
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{httpd.server_address[1]}/"
sent = []
def route(r):
    if r.request.method == "POST" and "/sync" in r.request.url:
        try: sent.append(json.loads(r.request.post_data or "{}"))
        except Exception: pass
        return r.fulfill(status=200, content_type="application/json", body=json.dumps({"now": 1, "recs": [], "meta": None}))
    return r.abort()
seed = ("(() => { if (sessionStorage.getItem('f894')) return; sessionStorage.setItem('f894', '1');"
        " localStorage.setItem('wardrobe.sync', JSON.stringify({key: 'f894f894f894f894f894f894f894f894f894f894f894f894', acct: 'test894', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'x', lastOk: 0})); })()")
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 402, "height": 874}, service_workers="block")
    ctx.add_init_script(seed); ctx.route("**/*.workers.dev/**", route)
    pg = ctx.new_page(); pg.goto(base, wait_until="load"); pg.wait_for_timeout(2500)
    pg.locator("#section-inspo").dispatch_event("pointerdown")
    pg.evaluate("() => { const t = Date.now(); while (Date.now() - t < 3500) {} }")
    pg.wait_for_timeout(1200)
    notes = pg.evaluate("() => feedbackNotes.filter(n => n.auto894).map(n => n.note)")
    check("a 3.5s stall is reported, naming the tap", any("page stuck" in n and "section-inspo" in n for n in notes), notes)
    pg.evaluate("() => syncNow()"); pg.wait_for_timeout(4000)
    up = [c for body in sent for c in (body.get("changes") or []) if c.get("coll") == "feedback"]
    check("the report is sent with the next sync", any("page stuck" in json.dumps(c.get("data")) for c in up), len(up))
    # 2. a session that ended stuck: tap, then the page is closed with no clean hide
    pg.close()
    # a frozen app never gets to record a clean close: the next open finds the session still marked as running
    pg2 = ctx.new_page()
    pg2.add_init_script("(() => { const x = JSON.parse(localStorage.getItem('wardrobe.diag894') || '{}'); x.clean = 0; x.tap = 'BUTTON#section-inspo The Edit'; x.tapAt = Date.now() - 3000; x.alive = Date.now() - 100; localStorage.setItem('wardrobe.diag894', JSON.stringify(x)); })()")
    pg2.goto(base, wait_until="load"); pg2.wait_for_timeout(10000)
    notes2 = pg2.evaluate("() => feedbackNotes.filter(n => n.auto894).map(n => n.note)")
    check("a session that ended stuck is reported on the next open", any("ended without closing" in n for n in notes2), notes2)
    b.close()
httpd.shutdown()
print("FAILED %d" % len(fails) if fails else "ALL PASS"); sys.exit(1 if fails else 0)
