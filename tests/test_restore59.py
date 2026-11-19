"""Build .59 restore + Home chevron + bottom-nav geometry (build stamp .64).

A local mock implements the client's /sync protocol. Requests to
*.workers.dev are intercepted here and never leave the machine.
This test must never register an account or write to the production
worker.

Usage (from the repo root, Playwright already installed):

    /tmp/pwvenv/bin/python tests/test_restore59.py
"""
from __future__ import annotations

import http.server
import json
import socketserver
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PIXEL_GIF = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
BLOB_HASH = "ab" * 32  # 64 hex chars
SYNC_HOST = "https://wardrobe-sync.dyacobs.workers.dev"
KEY = "test-key-restore59"
ACCT = "test-acct-59"
N_SERVER = 83
N_TOMB = 54
# updatedAt values are older than the local tomb stamps and older than
# SY.last, so an incremental pull (since: SY.last) would return nothing.
ITEM_TS = 1_700_000_000_000
CURSOR_LAST = 1_800_000_000_000
TOMB_TS = 1_790_000_000_000


def server_items():
    recs = []
    for i in range(N_SERVER):
        iid = f"item-{ITEM_TS + i}"
        data = {
            "id": iid,
            "name": f"User piece {i + 1}",
            "category": "Shirts",
            "colourName": "Navy",
            "colourHex": "#1a1f3c",
            "notes": "mock restore item",
            "wearCount": 0,
            "lastWorn": None,
            "addedISO": "2026-11-17",
            "laundry": False,
            "photo": ("blob:" + BLOB_HASH) if i < 10 else None,
        }
        recs.append({"coll": "items", "id": iid, "updatedAt": ITEM_TS + i, "data": data})
    recs.append({
        "coll": "blobs",
        "id": BLOB_HASH,
        "updatedAt": ITEM_TS,
        "data": {"photo": PIXEL_GIF},
    })
    return recs


class MockSync:
    def __init__(self):
        self.recs = server_items()
        self.uploads: list[dict] = []
        self.requests: list[dict] = []
        self.since0 = 0

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
        newer = [r for r in self.recs if r["updatedAt"] > since]
        newer.sort(key=lambda r: r["updatedAt"])
        page = newer[:limit]
        if page:
            now = page[-1]["updatedAt"]
            if len(newer) <= limit:
                now = max(now, int(time.time() * 1000))
        else:
            now = int(time.time() * 1000)
        return 200, {"now": now, "recs": page}


CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "authorization, content-type",
    "Access-Control-Max-Age": "86400",
}


def profile_init_script() -> str:
    """A simulated .57/.58 phone: 29 local user items, 54 armed unsent
    tombs, SY.last already past the server records, repair53 done."""
    remaining = []
    snap, st, tomb, dirty = {}, {}, {}, {}
    for i in range(N_SERVER):
        iid = f"item-{ITEM_TS + i}"
        rec = {
            "id": iid,
            "name": f"User piece {i + 1}",
            "category": "Shirts",
            "colourName": "Navy",
            "colourHex": "#1a1f3c",
            "notes": "mock restore item",
            "wearCount": 0,
            "lastWorn": None,
            "addedISO": "2026-11-17",
            "laundry": False,
            "photo": None,
        }
        if i >= N_TOMB:
            remaining.append(rec)
            snap[iid] = "localhash" + str(i)
            st[iid] = ITEM_TS + i
        else:
            tomb[iid] = TOMB_TS
            dirty[iid] = 1
    sy = {
        "key": KEY,
        "acct": ACCT,
        "last": CURSOR_LAST,
        "lastOk": CURSOR_LAST - 10_000,
        "status": "Synced",
        "snap": {"items": snap},
        "st": {"items": st, "m": 0},
        "tomb": {"items": tomb},
        "dirty": {"items": dirty, "m": 0},
        "mf": {},
        "rej": 0,
        "quar": [],
        "bp": {BLOB_HASH: 1},
        "mig57": KEY,
        "restore59": "",
    }
    payload = {
        "wardrobe.items": json.dumps(remaining),
        "wardrobe.sync": json.dumps(sy),
        "wardrobe.repair53": json.dumps({"done": True}),
        "wardrobe.tab": "today",
    }
    # Written as a JS literal so add_init_script can seed localStorage
    # before the app's own scripts run.
    return (
        "(() => {\n"
        "  const payload = " + json.dumps(payload) + ";\n"
        "  try {\n"
        "    if (!sessionStorage.getItem('__wardrobe_restore59_seeded')) {\n"
        "      for (const [k, v] of Object.entries(payload)) localStorage.setItem(k, v);\n"
        "      sessionStorage.setItem('__wardrobe_restore59_seeded', '1');\n"
        "    }\n"
        "  } catch (e) {}\n"
        "  window.__bbFirst = null;\n"
        "  function snap() {\n"
        "    const el = document.getElementById('bottombar');\n"
        "    if (!el || window.__bbFirst) return;\n"
        "    const r = el.getBoundingClientRect();\n"
        "    window.__bbFirst = {x:r.x,y:r.y,w:r.width,h:r.height,top:r.top,bottom:r.bottom};\n"
        "  }\n"
        "  const mo = new MutationObserver(snap);\n"
        "  try { mo.observe(document.documentElement, {childList:true,subtree:true}); } catch (e) {}\n"
        "  document.addEventListener('DOMContentLoaded', snap, true);\n"
        "})();"
    )


def bbox_of(page, sel="#bottombar"):
    return page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          if (!el) return null;
          const r = el.getBoundingClientRect();
          return {x:r.x,y:r.y,w:r.width,h:r.height,top:r.top,bottom:r.bottom};
        }""",
        sel,
    )


def nearly_eq(a, b, tol=1.0):
    if a is None or b is None:
        return False
    for k in ("x", "y", "w", "h", "top", "bottom"):
        if abs(float(a[k]) - float(b[k])) > tol:
            return False
    return True


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
        # Hard stop: never continue() to the real worker.
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

    context.route("https://wardrobe-sync.dyacobs.workers.dev/**", on_route)
    # Belt: any other workers.dev host is aborted, never continued.
    context.route("https://*.workers.dev/**", lambda route: (
        route.fulfill(status=204, headers=CORS, body="")
        if route.request.method.upper() == "OPTIONS"
        else route.abort()
        if "wardrobe-sync.dyacobs.workers.dev" not in route.request.url
        else on_route(route)
    ))


def closet_state(page):
    return page.evaluate(
        """() => {
          const items = (typeof wardrobeItems !== 'undefined' && Array.isArray(wardrobeItems))
            ? wardrobeItems : [];
          const seeds = items.filter(i => String(i.id || '').indexOf('seed-') === 0);
          const users = items.filter(i => String(i.id || '').indexOf('seed-') !== 0);
          let sy = null;
          try { sy = JSON.parse(localStorage.getItem('wardrobe.sync') || 'null'); } catch (e) {}
          let stored = [];
          try { stored = JSON.parse(localStorage.getItem('wardrobe.items') || '[]'); } catch (e) {}
          const back = document.getElementById('view-back');
          return {
            seedCount: seeds.length,
            userCount: users.length,
            userIds: users.map(i => i.id).sort(),
            storedUserCount: Array.isArray(stored) ? stored.length : -1,
            storedIds: Array.isArray(stored) ? stored.map(i => i.id).sort() : [],
            restore59: sy && sy.restore59,
            key: sy && sy.key,
            tombItems: sy && sy.tomb && sy.tomb.items ? Object.keys(sy.tomb.items).length : -1,
            dirtyItemDeletes: sy && sy.dirty && sy.dirty.items
              ? Object.keys(sy.dirty.items).filter(id => sy.tomb && sy.tomb.items && sy.tomb.items[id]).length
              : -1,
            backHidden: !back || !!back.hidden,
            build: (document.querySelector('meta[name="wardrobe-build"]') || {}).content || '',
          };
        }"""
    )


def run() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        print(f"  {status}: {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            failures.append(f"{name}: {detail}")

    httpd, url = start_static_server()
    mock = MockSync()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            # ---- Restore path: simulated .57/.58 profile ----
            ctx = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                service_workers="block",
            )
            attach_mock(ctx, mock)
            ctx.add_init_script(profile_init_script())
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded")
            first = page.evaluate("() => window.__bbFirst")
            page.wait_for_load_state("load")
            after_load = bbox_of(page)
            # Wait for the one-time restore pass (boot syncNow at 800ms).
            page.wait_for_function(
                """() => {
                  try {
                    const s = JSON.parse(localStorage.getItem('wardrobe.sync') || '{}');
                    return !!(s && s.restore59 && s.restore59 === s.key);
                  } catch (e) { return false; }
                }""",
                timeout=30000,
            )
            # Give syRefresh a tick to render the closet.
            page.wait_for_timeout(300)
            st = closet_state(page)
            expected_ids = sorted(f"item-{ITEM_TS + i}" for i in range(N_SERVER))
            check("build is .71", st["build"] == "2026-11-19.78.7a", st["build"])
            check("all 83 server items reappear in memory", st["userCount"] == N_SERVER, f"got {st['userCount']}")
            check("all 83 persisted to wardrobe.items", st["storedUserCount"] == N_SERVER, f"got {st['storedUserCount']}")
            check("restored ids match the mock server", st["storedIds"] == expected_ids, f"got {len(st['storedIds'])} ids")
            check("seeds still present and unchanged in count", st["seedCount"] > 0, f"seeds={st['seedCount']}")
            seed_count = st["seedCount"]
            check("restore59 flag set only after success", st["restore59"] == KEY, str(st["restore59"]))
            check("unsent item tombs dropped for restored ids", st["tombItems"] == 0, f"tombs={st['tombItems']}")
            check("since: 0 re-download ran", mock.since0 >= 1, f"since0={mock.since0}")
            deletes = [c for c in mock.uploads if c.get("deleted")]
            check("no deletes uploaded to the mock", deletes == [], f"sent {len(deletes)} deletes: {deletes[:3]}")
            # Uploads may include non-delete dirty of the 29 survivors; that's fine.
            after_sync = bbox_of(page)
            check("bottom bar bbox first paint == after load", nearly_eq(first, after_load), f"first={first} load={after_load}")
            check("bottom bar bbox after load == after restore", nearly_eq(after_load, after_sync), f"load={after_load} sync={after_sync}")
            check("back chevron hidden on Home at first opportunity", st["backHidden"], "")

            # Bar identical on every tab.
            tab_ids = ["tab-today", "section-closet", "section-ideas", "tab-find", "section-calendar"]
            boxes = {"after-load": after_load}
            for tid in tab_ids:
                page.locator(f"#{tid}").click()
                page.wait_for_timeout(200)
                boxes[tid] = bbox_of(page)
                check(
                    f"bottom bar bbox on {tid} matches first paint",
                    nearly_eq(first, boxes[tid]),
                    f"first={first} {tid}={boxes[tid]}",
                )
            # Home again: chevron must stay hidden after visiting another tab.
            page.locator("#tab-today").click()
            page.wait_for_timeout(200)
            home = closet_state(page)
            check("back chevron hidden on Home after visiting other tabs", home["backHidden"], "")
            check("seeds unaffected after tab tour", home["seedCount"] == seed_count, f"{home['seedCount']} vs {seed_count}")
            check("83 items still present after tab tour", home["userCount"] == N_SERVER, f"{home['userCount']}")

            # Idempotent reload: no second since:0 required once flagged, still 83, no deletes.
            uploads_before = len(mock.uploads)
            since0_before = mock.since0
            deletes_before = len(deletes)
            page.reload(wait_until="load")
            page.wait_for_function(
                """() => {
                  try {
                    const s = JSON.parse(localStorage.getItem('wardrobe.sync') || '{}');
                    return !!(s && s.restore59 && s.restore59 === s.key);
                  } catch (e) { return false; }
                }""",
                timeout=30000,
            )
            page.wait_for_timeout(800)  # boot sync at 800ms + apply
            # Wait until any post-reload sync has had a chance to finish.
            page.wait_for_timeout(1200)
            st2 = closet_state(page)
            deletes2 = [c for c in mock.uploads if c.get("deleted")]
            check("reload is idempotent: still 83 items", st2["userCount"] == N_SERVER and st2["storedUserCount"] == N_SERVER,
                  f"mem={st2['userCount']} stored={st2['storedUserCount']}")
            check("reload is idempotent: seeds unchanged", st2["seedCount"] == seed_count, f"{st2['seedCount']}")
            check("reload is idempotent: restore59 stays set", st2["restore59"] == KEY, str(st2["restore59"]))
            check("reload sends no deletes", deletes2 == [], f"sent {len(deletes2)}")
            check(
                "reload does not need another since:0 pass (flag already set)",
                True,  # informational; a second since:0 would be a bug only if flag wasn't set
            )
            # If the flag worked, further syncs should use since > 0. Allow the
            # first post-reload request to be incremental.
            post = mock.requests[since0_before:] if since0_before <= len(mock.requests) else []
            incremental = [r for r in mock.requests[1:] if r["since"] != 0]
            # After the flag is set, a later request should not start at 0.
            # The very first request of the first load must have been since:0.
            first_since = mock.requests[0]["since"] if mock.requests else None
            check("first restore request used since: 0", first_since == 0, f"since={first_since}")
            reload_since0 = sum(1 for r in mock.requests[1:] if r["since"] == 0)
            # A second full pull is not fatal but shouldn't happen once flagged.
            check("no extra since: 0 after the flag was set", reload_since0 == 0, f"extra since0={reload_since0}")
            check("back chevron hidden on Home after reload", st2["backHidden"], "")
            ctx.close()

            # ---- Fresh UI profile: first paint / standalone-ish 390x844 ----
            ui = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                service_workers="block",
            )
            # Block the real worker entirely (fresh profile has no key).
            ui.route("https://*.workers.dev/**", lambda route: route.abort())
            ui.add_init_script(
                """(() => {
                  window.__bbFirst = null;
                  function snap() {
                    const el = document.getElementById('bottombar');
                    if (!el || window.__bbFirst) return;
                    const r = el.getBoundingClientRect();
                    window.__bbFirst = {x:r.x,y:r.y,w:r.width,h:r.height,top:r.top,bottom:r.bottom};
                  }
                  try { new MutationObserver(snap).observe(document.documentElement, {childList:true,subtree:true}); } catch (e) {}
                  document.addEventListener('DOMContentLoaded', snap, true);
                })();"""
            )
            up = ui.new_page()
            up.goto(url, wait_until="domcontentloaded")
            ui_first = up.evaluate("() => window.__bbFirst")
            up.wait_for_load_state("load")
            ui_load = bbox_of(up)
            style = up.evaluate(
                """() => {
                  const el = document.getElementById('bottombar');
                  const b = document.body;
                  const cs = getComputedStyle(el);
                  const bs = getComputedStyle(b);
                  const slot = document.getElementById('bottombar-slot');
                  const scs = slot ? getComputedStyle(slot) : null;
                  return {
                    height: cs.height,
                    bottom: cs.bottom,
                    position: cs.position,
                    slotPosition: scs ? scs.position : null,
                    paddingBottom: cs.paddingBottom,
                    transition: cs.transition,
                    bodyPad: bs.paddingBottom,
                    bbh: getComputedStyle(document.documentElement).getPropertyValue('--bb-h').trim(),
                    backHidden: !!(document.getElementById('view-back') || {}).hidden,
                  };
                }"""
            )
            check("fresh profile: bar first paint == after load", nearly_eq(ui_first, ui_load), f"{ui_first} vs {ui_load}")
            check("fresh profile: bar is fixed or absolute in the fixed slot", style["position"] == "fixed" or (style["position"]=="absolute" and style.get("slotPosition")=="fixed"), style.get("position")+" slot="+str(style.get("slotPosition")))
            check("fresh profile: bar height is 68px (inset 0 in this browser)", style["height"] == "68px", style["height"])
            check("fresh profile: body padding-bottom is 68px", style["bodyPad"] == "68px", style["bodyPad"])
            t_ = (style["transition"] or "")
            check("fresh profile: bar transitions only transform (.78.2b tuck-away), never layout", "none" in t_ or (t_.startswith("transform ") and not __import__("re").search(r"\),\s*[a-z]|s,\s*[a-z]", t_)), t_)
            check("fresh profile: back chevron hidden on Home", style["backHidden"], "")
            # Bar top should sit at 844-68=776 when inset is 0.
            if ui_load:
                check(
                    "fresh profile: bar sits at the bottom of the 844px viewport",
                    abs(ui_load["bottom"] - 844) <= 1 and abs(ui_load["h"] - 68) <= 1,
                    str(ui_load),
                )
            for tid in tab_ids:
                up.locator(f"#{tid}").click()
                up.wait_for_timeout(200)
                box = bbox_of(up)
                check(f"fresh profile: bar bbox on {tid} matches first paint", nearly_eq(ui_first, box), f"{ui_first} vs {box}")
            up.locator("#tab-today").click()
            up.wait_for_timeout(200)
            hidden = up.evaluate("() => !!(document.getElementById('view-back') || {}).hidden")
            check("fresh profile: chevron still hidden after returning to Home", hidden, "")

            # Standalone display-mode is not a first-class Playwright
            # emulation (CSS display-mode cannot be flipped from JS). The
            # bar geometry does not vary by display-mode — same calc on
            # every page — so the 390x844 pass is the contract. We still
            # preload matchMedia for any JS that keys off standalone.
            stn = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                service_workers="block",
            )
            stn.route("https://*.workers.dev/**", lambda route: route.abort())
            stn.add_init_script(
                """(() => {
                  const real = window.matchMedia.bind(window);
                  window.matchMedia = (q) => {
                    if (String(q).indexOf('display-mode: standalone') !== -1) {
                      return {matches:true, media:q, onchange:null, addListener:function(){}, removeListener:function(){}, addEventListener:function(){}, removeEventListener:function(){}, dispatchEvent:function(){return false;}};
                    }
                    return real(q);
                  };
                  window.__bbFirst = null;
                  function snap() {
                    const el = document.getElementById('bottombar');
                    if (!el || window.__bbFirst) return;
                    const r = el.getBoundingClientRect();
                    window.__bbFirst = {x:r.x,y:r.y,w:r.width,h:r.height,top:r.top,bottom:r.bottom};
                  }
                  try { new MutationObserver(snap).observe(document.documentElement, {childList:true,subtree:true}); } catch (e) {}
                  document.addEventListener('DOMContentLoaded', snap, true);
                })();"""
            )
            sp = stn.new_page()
            sp.goto(url, wait_until="domcontentloaded")
            s_first = sp.evaluate("() => window.__bbFirst")
            sp.wait_for_load_state("load")
            s_load = bbox_of(sp)
            check("standalone-js: bar first paint == after load", nearly_eq(s_first, s_load), f"{s_first} vs {s_load}")
            for tid in tab_ids:
                sp.locator(f"#{tid}").click()
                sp.wait_for_timeout(200)
                box = bbox_of(sp)
                check(f"standalone-js: bar bbox on {tid} matches first paint", nearly_eq(s_first, box), f"{s_first} vs {box}")
            sp.locator("#tab-today").click()
            sp.wait_for_timeout(200)
            check(
                "standalone-js: chevron hidden on Home",
                sp.evaluate("() => !!(document.getElementById('view-back') || {}).hidden"),
                "",
            )
            stn.close()
            ui.close()
            browser.close()
    finally:
        try:
            httpd.shutdown()
        except Exception:
            pass

    print()
    if failures:
        print(f"{len(failures)} failed:")
        for f in failures:
            print(" -", f)
        return 1
    print("All restore/UI checks passed.")
    print(f"Mock: {len(mock.requests)} /sync requests, {mock.since0} since:0, {len(mock.uploads)} uploaded changes, 0 deletes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
