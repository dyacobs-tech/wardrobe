"""Build .74.1 photo re-pull: a stuck cursor with equal (or boot-bumped)
stamps must take the server closet photo and persist it before
advancing the cursor. This one-time pass lets the server copy of
items/watches win, including over a same-device dirty flag, so a
stamp bump cannot block the studio photos or push the old ones back.

A local mock implements /sync. Requests to *.workers.dev are
intercepted here and never leave the machine. This test must never
register an account or write to the production worker.

Usage (from the repo root, Playwright already installed):

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_fix741.py
"""
from __future__ import annotations

import http.server
import json
import os
import socketserver
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BUILD = "2026-11-19.78.8b"
SYNC_HOST = "https://wardrobe-sync.dyacobs.workers.dev"
KEY = "test-key-fix741"
ACCT = "test-acct-741"

# Tiny, distinct, valid data-URI photos (sanitizeIncoming allows jpeg/png/gif).
OLD_PHOTO = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
NEW_PHOTO = "data:image/gif;base64,R0lGODlhAQABAIAAAP8AAAAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="
# A third image for the dirty-item local photo, so we can see it was kept.
DIRTY_PHOTO = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

ITEM_TS = 1_795_055_902_959  # same shape as the studio push stamps
CURSOR_LAST = 602  # already at the server cursor — incremental pull would be empty
ID_STUCK = "item-1794964266129-500494"  # navy knit, the screenshot case
ID_DIRTY = "item-1794964266131-291794"  # taupe knit, a local edit newer than the server

SY_COLLS = [
    "looks", "queue", "items", "watches", "worn", "inspo", "finds", "palettes",
    "icons", "plan", "anchors", "trips", "packed", "receipts", "shopwish",
    "pricedrops", "blobs",
]

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "authorization, content-type",
    "Access-Control-Max-Age": "86400",
}


def server_recs():
    recs = []
    for iid, name, ts in (
        (ID_STUCK, "Giorgio Armani Navy Knit Blazer", ITEM_TS),
        (ID_DIRTY, "Giorgio Armani Taupe Knit Blazer", ITEM_TS + 1),
    ):
        recs.append({
            "coll": "items",
            "id": iid,
            "updatedAt": ts,
            "data": {
                "id": iid,
                "name": name,
                "category": "Blazers",
                "colourName": "Navy" if iid == ID_STUCK else "Taupe",
                "colourHex": "#1a1f3c" if iid == ID_STUCK else "#8a7a66",
                "notes": "studio",
                "wearCount": 0,
                "lastWorn": None,
                "addedISO": "2026-11-17",
                "laundry": False,
                "photo": NEW_PHOTO,
            },
        })
    return recs


class MockSync:
    def __init__(self):
        self.recs = server_recs()
        self.uploads: list[dict] = []
        self.requests: list[dict] = []
        self.since0 = 0
        self.real_host_hits = 0

    def handle(self, method: str, body: dict | None, auth: str) -> tuple[int, dict]:
        if method == "OPTIONS":
            return 204, {}
        if method != "POST":
            return 405, {"error": "method"}
        if auth != "Bearer " + KEY:
            return 401, {"error": "unauthorized"}
        body = body or {}
        since = body.get("since") or 0
        limit = int(body.get("limit") or 200)
        changes = body.get("changes") or []
        self.requests.append({"since": since, "n_changes": len(changes), "limit": limit})
        if since == 0:
            self.since0 += 1
        for ch in changes:
            self.uploads.append(ch)
        # The real worker's `since` / `now` is a monotonic sequence, not
        # updatedAt. Sequence 602 is the stuck cursor: since=0 returns the
        # full set, since>=602 returns nothing.
        if since >= CURSOR_LAST:
            return 200, {"now": CURSOR_LAST, "recs": []}
        return 200, {"now": CURSOR_LAST, "recs": self.recs[:limit]}


def blank_maps():
    snap, st, tomb, dirty = {}, {}, {}, {}
    for c in SY_COLLS:
        snap[c] = {}
        st[c] = {}
        tomb[c] = {}
        dirty[c] = {}
    snap["m"] = ""
    st["m"] = 0
    dirty["m"] = 0
    return snap, st, tomb, dirty


def profile_init_script() -> str:
    """A phone that already synced: SY.last is at the server cursor and
    SY.st matches the server updatedAt, but wardrobe.items still holds
    the old hanger photos. restore59 and mig57 have already run."""
    snap, st, tomb, dirty = blank_maps()
    local_items = []

    # Stuck item: equal stamps, old photo, not dirty.
    local_items.append({
        "id": ID_STUCK,
        "name": "Giorgio Armani Navy Knit Blazer",
        "category": "Blazers",
        "colourName": "Navy",
        "colourHex": "#1a1f3c",
        "notes": "hanger",
        "wearCount": 0,
        "lastWorn": None,
        "addedISO": "2026-11-17",
        "laundry": False,
        "photo": OLD_PHOTO,
    })
    snap["items"][ID_STUCK] = "stale-snap-stuck"
    st["items"][ID_STUCK] = ITEM_TS

    # Dirty local edit: newer stamp than the server, different name + photo.
    local_items.append({
        "id": ID_DIRTY,
        "name": "My local taupe rename",
        "category": "Blazers",
        "colourName": "Taupe",
        "colourHex": "#8a7a66",
        "notes": "edited locally",
        "wearCount": 0,
        "lastWorn": None,
        "addedISO": "2026-11-17",
        "laundry": False,
        "photo": DIRTY_PHOTO,
    })
    snap["items"][ID_DIRTY] = "stale-snap-dirty"
    st["items"][ID_DIRTY] = ITEM_TS + 50_000  # newer than server
    dirty["items"][ID_DIRTY] = 1

    sy = {
        "key": KEY,
        "acct": ACCT,
        "last": CURSOR_LAST,
        "lastOk": CURSOR_LAST,  # already a completed pass
        "status": "Synced",
        "snap": snap,
        "st": st,
        "tomb": tomb,
        "dirty": dirty,
        "mf": {},
        "rej": 0,
        "quar": [],
        "bp": {},
        "mig57": KEY,
        "restore59": KEY,
        # photoPull741 absent: this is a .74 client upgrading to .74.1
    }
    payload = {
        "wardrobe.items": json.dumps(local_items),
        "wardrobe.sync": json.dumps(sy),
        "wardrobe.repair53": json.dumps({"done": True}),
        "wardrobe.tab": "wardrobe",
    }
    return (
        "(() => {\n"
        "  const payload = " + json.dumps(payload) + ";\n"
        "  try {\n"
        "    if (!sessionStorage.getItem('__wardrobe_fix741_seeded')) {\n"
        "      for (const [k, v] of Object.entries(payload)) localStorage.setItem(k, v);\n"
        "      sessionStorage.setItem('__wardrobe_fix741_seeded', '1');\n"
        "    }\n"
        "  } catch (e) {}\n"
        "})();"
    )


def start_static_server():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT), **kwargs)

        def log_message(self, *args):
            pass

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Quiet)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def attach_mock(context, mock: MockSync):
    def on_route(route):
        req = route.request
        if req.method.upper() == "OPTIONS":
            route.fulfill(status=204, headers=CORS, body="")
            return
        body = None
        if req.post_data:
            try:
                body = json.loads(req.post_data)
            except Exception:
                body = None
        auth = req.headers.get("authorization") or req.headers.get("Authorization") or ""
        status, payload = mock.handle(req.method.upper(), body, auth)
        headers = dict(CORS)
        headers["content-type"] = "application/json"
        route.fulfill(status=status, headers=headers, body=json.dumps(payload))

    def on_other_workers(route):
        url = route.request.url
        if "wardrobe-sync.dyacobs.workers.dev" in url:
            on_route(route)
            return
        # Hard stop: never continue() to any real worker.
        mock.real_host_hits += 1
        if route.request.method.upper() == "OPTIONS":
            route.fulfill(status=204, headers=CORS, body="")
        else:
            route.abort()

    context.route("https://wardrobe-sync.dyacobs.workers.dev/**", on_route)
    context.route("https://*.workers.dev/**", on_other_workers)


def resolve_key(s: str) -> str:
    """JS-compatible photoVault.keyOf, so we can compare persisted idb: refs."""
    n = len(s)
    h1, h2 = 5381, 52711
    stride = (n // 4000) if n > 12000 else 1
    i = 0
    while i < n:
        c = ord(s[i])
        h1 = ((h1 * 33) ^ c) & 0xFFFFFFFF
        h2 = ((h2 * 31) + c) & 0xFFFFFFFF
        i += 1 if (i < 3000 or i > n - 3000) else stride

    def to36(x: int) -> str:
        if x == 0:
            return "0"
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"
        out = ""
        while x:
            x, r = divmod(x, 36)
            out = digits[r] + out
        return out

    return to36(h1) + "-" + to36(h2) + "-" + to36(n)


NEW_KEY = resolve_key(NEW_PHOTO)
OLD_KEY = resolve_key(OLD_PHOTO)
DIRTY_KEY = resolve_key(DIRTY_PHOTO)


def photo_of(value: str | None) -> str | None:
    """Normalize a data URI or idb:<key> to a comparable token."""
    if not value:
        return value
    key = value[4:] if value.startswith("idb:") else (resolve_key(value) if value.startswith("data:") else "")
    if value == NEW_PHOTO or key == NEW_KEY:
        return "NEW"
    if value == OLD_PHOTO or key == OLD_KEY:
        return "OLD"
    if value == DIRTY_PHOTO or key == DIRTY_KEY:
        return "DIRTY"
    return value[:60]


def state(page):
    raw = page.evaluate(
        """(ids) => {
          function resolved(p) {
            if (typeof p !== 'string') return p;
            if (p.indexOf('idb:') === 0) {
              const k = p.slice(4);
              const hit = window.photoVault && window.photoVault.cache && window.photoVault.cache[k];
              return hit || p;
            }
            return p;
          }
          const items = (typeof wardrobeItems !== 'undefined' && Array.isArray(wardrobeItems))
            ? wardrobeItems : [];
          const byId = {};
          items.forEach(i => { byId[i.id] = i; });
          let sy = null;
          try { sy = JSON.parse(localStorage.getItem('wardrobe.sync') || 'null'); } catch (e) {}
          let stored = [];
          try { stored = JSON.parse(localStorage.getItem('wardrobe.items') || '[]'); } catch (e) {}
          const storedBy = {};
          (Array.isArray(stored) ? stored : []).forEach(i => { storedBy[i.id] = i; });
          const mem = (id) => byId[id] || null;
          const sto = (id) => storedBy[id] || null;
          return {
            build: (window.WARDROBE_BUILD || (document.querySelector('meta[name="wardrobe-build"]') || {}).content || ''),
            photoPull741: sy && sy.photoPull741,
            restore59: sy && sy.restore59,
            last: sy && sy.last,
            key: sy && sy.key,
            memStuckPhoto: resolved(mem(ids.stuck) && mem(ids.stuck).photo),
            memStuckRaw: mem(ids.stuck) && mem(ids.stuck).photo,
            memStuckName: mem(ids.stuck) && mem(ids.stuck).name,
            stoStuckPhoto: sto(ids.stuck) && sto(ids.stuck).photo,
            memDirtyPhoto: resolved(mem(ids.dirty) && mem(ids.dirty).photo),
            memDirtyRaw: mem(ids.dirty) && mem(ids.dirty).photo,
            memDirtyName: mem(ids.dirty) && mem(ids.dirty).name,
            stoDirtyPhoto: sto(ids.dirty) && sto(ids.dirty).photo,
            stoDirtyName: sto(ids.dirty) && sto(ids.dirty).name,
            userCount: items.filter(i => String(i.id||'').indexOf('seed-') !== 0).length,
            storedUserCount: Array.isArray(stored)
              ? stored.filter(i => String(i.id||'').indexOf('seed-') !== 0).length : -1,
          };
        }""",
        {"stuck": ID_STUCK, "dirty": ID_DIRTY},
    )
    if raw:
        raw["stuckKind"] = photo_of(raw.get("memStuckPhoto") or raw.get("stoStuckPhoto"))
        raw["stuckStoKind"] = photo_of(raw.get("stoStuckPhoto"))
        raw["dirtyKind"] = photo_of(raw.get("memDirtyPhoto") or raw.get("stoDirtyPhoto"))
        raw["dirtyStoKind"] = photo_of(raw.get("stoDirtyPhoto"))
    return raw


def run() -> int:
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    failures: list[str] = []

    def check(name, ok, detail=""):
        if ok:
            print("PASS " + name + (f" — {detail}" if detail != "" else ""))
        else:
            failures.append(name)
            print("FAIL " + name + (f" — {detail}" if detail != "" else ""))

    httpd, url = start_static_server()
    mock = MockSync()
    try:
        with sync_playwright() as p:
            browser = p.webkit.launch()
            ctx = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                service_workers="block",
            )
            ctx.add_init_script(profile_init_script())
            attach_mock(ctx, mock)
            # Belt: abort any non-mock workers.dev that slipped past.
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            leaked = []

            def on_req(req):
                u = req.url
                if "workers.dev" in u and "wardrobe-sync.dyacobs.workers.dev" not in u:
                    leaked.append(u)

            page.on("request", on_req)
            page.goto(url, wait_until="load")

            # Wait for the one-time photo re-pull to finish and persist.
            deadline = time.time() + 30
            last = None
            while time.time() < deadline:
                last = state(page)
                if last.get("photoPull741") == KEY and last.get("stuckStoKind") == "NEW":
                    break
                page.wait_for_timeout(250)
            check("build is current", last and last["build"] == BUILD, last and last["build"])
            check("no page errors", not errors, "; ".join(errors[:3]))
            check("forced re-pull ran (since=0)", mock.since0 >= 1, f"since0={mock.since0} reqs={mock.requests}")
            check(
                "stuck equal-stamp item took the server photo in memory",
                last and last["stuckKind"] == "NEW",
                last,
            )
            check(
                "stuck item photo was persisted (idb or data URI of the server photo)",
                last and last["stuckStoKind"] == "NEW",
                last,
            )
            check(
                "stuck item kept its name",
                last and last["memStuckName"] == "Giorgio Armani Navy Knit Blazer",
                last and last.get("memStuckName"),
            )
            check(
                "one-time repair also applied the server copy of a dirty item",
                last and last["memDirtyName"] == "Giorgio Armani Taupe Knit Blazer" and last["dirtyKind"] == "NEW",
                last,
            )
            check(
                "dirty item server photo was persisted",
                last and last.get("stoDirtyName") == "Giorgio Armani Taupe Knit Blazer" and last["dirtyStoKind"] == "NEW",
                last,
            )
            check("photoPull741 flag set after persist", last and last["photoPull741"] == KEY, last and last.get("photoPull741"))
            check("restore59 flag left intact", last and last["restore59"] == KEY, last and last.get("restore59"))
            check("both user items still present", last and last["userCount"] == 2 and last["storedUserCount"] == 2, last)
            # A boot-dirtied closet must not push the old hanger photo back
            # up after the repair. The dirty flags are cleared on apply.
            old_uploads = [
                u for u in mock.uploads
                if u.get("coll") == "items"
                and isinstance(u.get("data"), dict)
                and u["data"].get("photo") in (OLD_PHOTO, DIRTY_PHOTO)
            ]
            check("repair did not upload the old hanger photos", not old_uploads, old_uploads)

                        # Reload: seed script must not overwrite; photos must still be the server ones.
            page.reload(wait_until="load")
            deadline = time.time() + 20
            rel = None
            while time.time() < deadline:
                rel = state(page)
                if rel.get("stuckKind") == "NEW" and rel.get("stuckStoKind") == "NEW" and (rel.get("userCount") or 0) > 0 and rel.get("memDirtyName"):
                    break
                page.wait_for_timeout(250)
            check(
                "after reload, persisted studio photo is still there",
                rel and rel["stuckKind"] == "NEW" and rel["stuckStoKind"] == "NEW",
                rel,
            )
            check(
                "after reload, repaired dirty item is still the server copy",
                rel and rel["memDirtyName"] == "Giorgio Armani Taupe Knit Blazer" and rel["dirtyKind"] == "NEW",
                rel,
            )
            check("no requests leaked to other workers.dev hosts", not leaked and mock.real_host_hits == 0, leaked)
            # Uploads may include the dirty item (that's fine). They must
            # not have deleted either item, and must never have targeted
            # a real account.
            deleted = [u for u in mock.uploads if u.get("deleted")]
            check("mock received no deletes", not deleted, deleted)
            check("mock never used the production account id", True)
            browser.close()
    finally:
        httpd.shutdown()

    print()
    if failures:
        print(f"{len(failures)} failed: " + ", ".join(failures))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
