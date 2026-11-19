"""Build .74.2: studio photos reach Home, and the outfit of the day uses
only his own synced pieces that have photos.

Checks, in headless WebKit at iPhone size, against a LOCAL mock of /sync
(requests to *.workers.dev are fulfilled or aborted here, never sent):

1. A phone whose cursor already equals the server's, holding the OLD photos,
   whose .74.1 re-pull flag is set, still re-pulls once (photoPull742) and
   ends with the server (studio) photos persisted.
2. If IndexedDB refuses the photo writes during that pull, the flag is NOT
   set, so the next open pulls again; the next clean open sets it.
3. After a reload (photos held as "idb:" vault refs), the Home flat-lay shows
   every piece as a real photo: no colour-block swatch cells, every piece is
   a non-seed closet item, and the images hydrate to data:image bytes.
4. A look saved for today that contains a built-in (seed) piece is not
   restored; a fresh closet deal replaces it.

Usage: PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 python tests/test_fix742.py
"""
from __future__ import annotations

import base64
import datetime
import http.server
import json
import os
import random
import socketserver
import struct
import sys
import threading
import time
import zlib
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BUILD = "2026-11-19.79.4"
KEY = "test-key-fix742"
ACCT = "test-acct-742"
CURSOR = 603
TS = 1_795_055_902_959
SY_COLLS = ["looks", "queue", "items", "watches", "worn", "inspo", "finds", "palettes",
            "icons", "plan", "anchors", "trips", "packed", "receipts", "shopwish",
            "pricedrops", "blobs"]
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "authorization, content-type"}


def png_uri(seed: int, rgb: tuple[int, int, int]) -> str:
    """A valid noisy 48x48 PNG data URI (several KB, distinct per seed)."""
    rnd = random.Random(seed)
    w = h = 48
    raw = b"".join(b"\x00" + bytes(
        max(0, min(255, c + rnd.randint(-40, 40))) for _ in range(w) for c in rgb) for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


PIECES = [
    ("u-shirt-1", "Aspesi Slate Blue Shirt", "Shirts", "Slate blue", "#5b7290"),
    ("u-shirt-2", "Brunello Cucinelli Navy Shirt", "Shirts", "Navy", "#1f2a44"),
    ("u-polo-1", "Theory Cream Knit Polo", "Polos", "Cream", "#efe6d0"),
    ("u-knit-1", "Eleventy Navy Crewneck Sweater", "Sweaters", "Navy", "#233050"),
    ("u-blazer-1", "Loro Piana Light Blue Linen Blazer", "Blazers", "Light blue", "#a8c3d1"),
    ("u-trs-1", "Proper Cloth Faded Navy Twill", "Trousers", "Navy", "#2a3550"),
    ("u-trs-2", "Proper Cloth Beige Chino", "Trousers", "Beige", "#d8c6a5"),
    ("u-shoe-1", "Prada Dark Brown Suede Boat Shoes", "Shoes", "Dark brown", "#5d4030"),
    ("u-shoe-2", "Christian Dior Tan Suede Penny Loafers", "Shoes", "Tan", "#c59f6b"),
]
OLD = {pid: png_uri(i, (120, 110, 100)) for i, (pid, *_r) in enumerate(PIECES)}
NEW = {pid: png_uri(100 + i, (235, 225, 210)) for i, (pid, *_r) in enumerate(PIECES)}


def item(pid, name, cat, cname, hexv, photo):
    return {"id": pid, "name": name, "category": cat, "colourName": cname, "colourHex": hexv,
            "notes": "", "wearCount": 0, "lastWorn": None, "addedISO": "2026-11-17",
            "laundry": False, "photo": photo}


class Mock:
    def __init__(self):
        self.recs = [{"coll": "items", "id": p[0], "updatedAt": TS, "data": item(*p, NEW[p[0]])} for p in PIECES]
        self.reqs = []
        self.uploads = []

    def handle(self, body):
        since = body.get("since") or 0
        ch = body.get("changes") or []
        self.reqs.append({"since": since, "changes": len(ch)})
        self.uploads.extend(ch)
        if since >= CURSOR:
            return {"now": CURSOR, "recs": []}
        return {"now": CURSOR, "recs": self.recs}


def init_script() -> str:
    snap, st, tomb, dirty = {}, {}, {}, {}
    for c in SY_COLLS:
        snap[c], st[c], tomb[c], dirty[c] = {}, {}, {}, {}
    snap["m"], st["m"], dirty["m"] = "", 0, 0
    for p in PIECES:
        st["items"][p[0]] = TS
        snap["items"][p[0]] = "stale"
    sy = {"key": KEY, "acct": ACCT, "last": CURSOR, "lastOk": CURSOR, "status": "Synced",
          "snap": snap, "st": st, "tomb": tomb, "dirty": dirty, "mf": {}, "rej": 0, "quar": [],
          "bp": {}, "mig57": KEY, "restore59": KEY, "photoPull741": KEY}
    today = datetime.date.today().isoformat()
    stale_look = {"id": "look-stale", "title": "Stale Seed Look", "source": "wardrobe", "img": None,
                  "fwRender": None, "composer": True, "composerKey": "stale",
                  "swatches": [{"name": "Navy", "hex": "#1f2a44", "role": "Blazer"}],
                  "fwPieces": [{"id": "u-shirt-1", "name": "Aspesi Slate Blue Shirt", "photo": None, "colourHex": "#5b7290", "category": "Shirts"},
                               {"id": "seed-belgian-brown-lizard-loafers", "name": "Belgian Shoes Brown Lizard Loafers", "photo": None, "colourHex": "#5d4030", "category": "Shoes"}]}
    payload = {
        "wardrobe.items": json.dumps([item(*p, OLD[p[0]]) for p in PIECES]),
        "wardrobe.sync": json.dumps(sy),
        "wardrobe.repair53": json.dumps({"done": True}),
        "wardrobe.todaySource": json.dumps("wardrobe"),
        "wardrobe.todayOpeningCloset": json.dumps({"date": today, "look": stale_look}),
    }
    return """(() => {
      const payload = %s;
      try {
        if (!localStorage.getItem('__fix742_seeded')) {
          for (const [k, v] of Object.entries(payload)) localStorage.setItem(k, v);
          localStorage.setItem('__fix742_seeded', '1');
        }
        if (localStorage.getItem('__fix742_failvault') === '1') {
          const put = IDBObjectStore.prototype.put;
          IDBObjectStore.prototype.put = function (v, k) {
            if (typeof v === 'string' && v.indexOf('data:image/') === 0) {
              throw new DOMException('quota', 'QuotaExceededError');
            }
            return put.apply(this, arguments);
          };
        }
      } catch (e) {}
    })();""" % json.dumps(payload)


def serve():
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(ROOT), **k)

        def log_message(self, *a):
            pass
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Q)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


STATE_JS = """async (newMap) => {
  const sy = JSON.parse(localStorage.getItem('wardrobe.sync') || 'null') || {};
  const V = window.photoVault;
  const stored = JSON.parse(localStorage.getItem('wardrobe.items') || '[]');
  async function res(p) {
    if (p && p.indexOf('idb:') === 0 && V) return await new Promise(r => V.fetch(p.slice(4), v => r(v || p)));
    return p;
  }
  let newCount = 0;
  for (const it of stored) { if ((await res(it.photo)) === newMap[it.id]) newCount++; }
  return {build: window.WARDROBE_BUILD, status: sy.status, p742: sy.photoPull742 || '', newCount,
          storedRefs: stored.filter(i => String(i.photo||'').indexOf('idb:') === 0).length};
}"""

HERO_JS = """() => {
  const cells = Array.from(document.querySelectorAll('#today-collage .fl-cell'));
  return {title: (document.getElementById('today-name') || {}).textContent || '',
          composer: !!(window.todayLook && todayLook.composer),
          ids: (todayLook && todayLook.fwPieces || []).map(p => p.id),
          swatches: cells.filter(c => c.classList.contains('fl-swatch')).length,
          /* .78.2c: Home is him only; the pieces live in the outfit view */
          pieceImgs: (() => { const d = document.createElement('div'); d.innerHTML = window.outfitPieceRows782 ? window.outfitPieceRows782(todayLook) : ''; return Array.from(d.querySelectorAll('.ov-piece')).map(b => { const i = b.querySelector('img'); return i ? (i.getAttribute('src') || '').slice(0, 15) : 'NONE'; }); })(),
          homeDealSwatches: (() => { let n = 0, seeds = 0; (buildClosetLooks({count: 12}) || []).forEach(l => {
              n += (window.composerFlatlayHTML(l, false).match(/fl-swatch/g) || []).length;
              seeds += l.fwPieces.filter(p => p.id.indexOf('seed-') === 0).length; }); return {n, seeds}; })()};
}"""


def main() -> int:
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    fails: list[str] = []

    def check(name, ok, detail=""):
        print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail != "" else ""))
        if not ok:
            fails.append(name)

    httpd, url = serve()
    mock = Mock()
    leaked = []
    with sync_playwright() as p:
        b = p.webkit.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True,
                            has_touch=True, service_workers="block")
        ctx.add_init_script(init_script())

        def on_sync(route):
            r = route.request
            if r.method.upper() == "OPTIONS":
                route.fulfill(status=204, headers=CORS, body="")
                return
            if (r.headers.get("authorization") or "") != "Bearer " + KEY:
                route.fulfill(status=401, headers=CORS, body="{}")
                return
            body = json.loads(r.post_data or "{}")
            route.fulfill(status=200, headers={**CORS, "content-type": "application/json"},
                          body=json.dumps(mock.handle(body)))

        def on_other(route):
            leaked.append(route.request.url)
            route.abort()
        ctx.route("https://wardrobe-sync.dyacobs.workers.dev/**", on_sync)
        ctx.route("https://*.workers.dev/**", lambda r: on_sync(r) if "wardrobe-sync.dyacobs" in r.request.url else on_other(r))
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def wait_state(pred, secs=40):
            t = time.time()
            s = None
            while time.time() - t < secs:
                s = page.evaluate(STATE_JS, NEW)
                if pred(s):
                    return s
                page.wait_for_timeout(400)
            return s

        # Open 1: IndexedDB refuses photo writes during the re-pull.
        page.goto(url)
        page.evaluate("() => localStorage.setItem('__fix742_failvault', '1')")
        page.reload()
        s1 = wait_state(lambda s: "Synced" in str(s["status"]) and len(mock.reqs) >= 1, 40)
        page.wait_for_timeout(1500)
        s1 = page.evaluate(STATE_JS, NEW)
        check("build is current", s1["build"] == BUILD, s1["build"])
        check("re-pull ran from 0 although .74.1 flag was set", any(r["since"] == 0 for r in mock.reqs), mock.reqs)
        check("vault write failure leaves photoPull742 unset", s1["p742"] == "", s1)

        # Open 2: storage healthy again.
        page.evaluate("() => localStorage.removeItem('__fix742_failvault')")
        n0 = sum(1 for r in mock.reqs if r["since"] == 0)
        page.reload()
        s2 = wait_state(lambda s: s["p742"] == KEY and s["newCount"] == len(PIECES), 40)
        check("second open re-pulled again", sum(1 for r in mock.reqs if r["since"] == 0) > n0, mock.reqs)
        check("photoPull742 set after a clean pull", s2["p742"] == KEY, s2)
        check("all studio photos persisted", s2["newCount"] == len(PIECES), s2)

        # Open 3: reload — photos are vault refs now; Home must show them.
        n1 = sum(1 for r in mock.reqs if r["since"] == 0)
        page.reload()
        page.wait_for_timeout(4000)
        s3 = page.evaluate(STATE_JS, NEW)
        check("no further since-0 pull once done", sum(1 for r in mock.reqs if r["since"] == 0) == n1, mock.reqs)
        check("photos stored as vault refs (lazy vault path exercised)", s3["storedRefs"] == len(PIECES), s3)
        h = page.evaluate(HERO_JS)
        check("Home hero is a closet-composer look", h["composer"], h)
        check("stale seed look was not restored", h["title"] != "Stale Seed Look" and not any(i.startswith("seed-") for i in h["ids"]), h)
        check("hero pieces are all his synced items", h["ids"] and all(i.startswith("u-") for i in h["ids"]), h["ids"])
        check("hero flat-lay has no colour-block swatches", h["swatches"] == 0, h)
        check("hero pieces hydrate to real photo bytes", h["pieceImgs"] and all(x.startswith("data:image/") for x in h["pieceImgs"]), h["pieceImgs"])
        check("Home deals carry no swatches and no seed pieces", h["homeDealSwatches"] == {"n": 0, "seeds": 0}, h["homeDealSwatches"])
        old_up = [u.get("id") for u in mock.uploads if OLD.get(u.get("id")) and json.dumps(u).find(OLD[u["id"]][40:120]) != -1
                  or any(v[40:120] in json.dumps(u) for v in OLD.values())]
        check("no upload ever carries an old photo back to the server", not old_up, old_up)
        check("no other workers.dev requests", not leaked, leaked)
        check("no page errors", not errors, errors[:3])
        b.close()
    httpd.shutdown()
    print("\n%d failure(s)" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
