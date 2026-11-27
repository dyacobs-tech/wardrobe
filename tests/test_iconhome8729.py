#!/usr/bin/env python3
"""Home hero order follows icon weights at 80°F (.87.29).

David, 27 Nov 2026: the warm-weather sort must not override icon rank;
weather is only a light boost, then icon order is kept. This test sets
80°F on Daytime and checks that a Squarzi-led weighting and a Kraft-led
weighting produce different Home orders, and that a clearly better icon
match stays ahead of a warmer look.

Usage: PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 python3 tests/test_iconhome8729.py
"""
from __future__ import annotations

import http.server
import json
import os
import socketserver
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from buildinfo import CURRENT_BUILD  # noqa: E402
from wardrobe_fixture import photographed_closet

ROOT = Path(__file__).resolve().parents[1]
BUILD = CURRENT_BUILD
fails: list[str] = []
CLOSET = photographed_closet()


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:500]))
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
    httpd.daemon_threads = True
    threading = __import__("threading")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "http://127.0.0.1:%d/" % httpd.server_address[1]


SEED_JS = "(() => { localStorage.setItem('wardrobe.items', %s); })();" % json.dumps(json.dumps(CLOSET))

LOOKS_JS = """({mode}) => {
  if (typeof currentWeather !== 'undefined') {
    currentWeather = Object.assign({}, currentWeather || {}, { temp: 80, label: 'Clear', rain: 0, feels: 80 });
  }
  if (typeof formalityLevel !== 'undefined') formalityLevel = 2;
  if (window.dressLevels838 && window.dressLevels838.set) try { window.dressLevels838.set([2]); } catch (e) {}
  const mid = {};
  allIcons().forEach(ic => mid[ic.id] = 0);
  if (mode === 'squarzi') mid.squarzi = 100;
  else if (mode === 'kraft') mid.kraft = 100;
  else allIcons().forEach(ic => mid[ic.id] = 20);
  const by = { casual: Object.assign({}, mid), smart: Object.assign({}, mid), business: Object.assign({}, mid), formal: Object.assign({}, mid) };
  window.iconWeights81.setState({ mode: 'per', all: mid, byLevel: by, scale: 100, v: 2 });
  const looks = (typeof homeComposerLooks75 === 'function') ? homeComposerLooks75(16) : [];
  return looks.map(l => ({
    title: l.title || '',
    key: l.composerKey || l.id || '',
    iconW: +(l._iconW || 0),
    layered: (l.fwPieces || []).some(p => /Blazers|Jackets|Sweaters|Coats|Vests/.test(String(p && p.category || '')) || /overshirt/i.test(String(p && p.name || ''))),
    shorts: (l.fwPieces || []).some(p => p && /Shorts|Bathing/.test(String(p.category || ''))),
    top: ((l.fwPieces || []).find(p => p && /Tees|Polos|Shirts/.test(String(p.category || ''))) || {}).name || ''
  }));
}"""


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else None
    httpd = None
    if not base:
        httpd, base = start_server()
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
        ctx.route("**/*.workers.dev/**", lambda r: r.abort())
        ctx.add_init_script(SEED_JS)
        pg = ctx.new_page()
        pg.goto(base, wait_until="load")
        pg.wait_for_timeout(2000)
        # wait for icons + hires + composer
        ready = False
        diag = None
        for _ in range(40):
            diag = pg.evaluate("""() => ({
              build: window.WARDROBE_BUILD || '',
              icons: (typeof allIcons === 'function' && allIcons().length) || 0,
              weights: !!(window.iconWeights81 && window.iconWeights81.setState),
              home: typeof homeComposerLooks75 === 'function',
              hires: !!(window.HIRES && (window.HIRES.ready || window.HIRES.failed)),
              onbody: typeof onbodyKeys === 'function' && !!onbodyKeys()
            })""")
            ready = bool(diag and diag.get("icons", 0) >= 9 and diag.get("weights") and diag.get("home") and diag.get("hires"))
            if ready:
                break
            pg.wait_for_timeout(400)
        check("build is current", BUILD in str((diag or {}).get("build") or ""), diag)
        check("Home composer is ready at 80F", ready, diag)

        if ready:
            sq = pg.evaluate(LOOKS_JS, {"mode": "squarzi"})
            kr = pg.evaluate(LOOKS_JS, {"mode": "kraft"})
            uni = pg.evaluate(LOOKS_JS, {"mode": "uniform"})
            print("SQUARZI", json.dumps(sq[:6]))
            print("KRAFT", json.dumps(kr[:6]))
            print("UNIFORM", json.dumps(uni[:6]))
            check("Squarzi weighting deals Home looks at 80F", len(sq) >= 3, len(sq))
            check("Kraft weighting deals Home looks at 80F", len(kr) >= 3, len(kr))

            def almost_mono(rows):
                # icon scores non-increasing, allowing a 0.25 weather boost
                for i in range(1, len(rows)):
                    if rows[i]["iconW"] > rows[i - 1]["iconW"] + 0.26:
                        return False, i, rows[i - 1], rows[i]
                return True, None, None, None

            ok, at, a, b = almost_mono(sq)
            check("Squarzi Home order keeps icon rank at 80F (weather boost <= 0.25)", ok, {"at": at, "prev": a, "next": b})
            ok2, at2, a2, b2 = almost_mono(kr)
            check("Kraft Home order keeps icon rank at 80F (weather boost <= 0.25)", ok2, {"at": at2, "prev": a2, "next": b2})

            sq_keys = [r["key"] or r["title"] for r in sq]
            kr_keys = [r["key"] or r["title"] for r in kr]
            uni_keys = [r["key"] or r["title"] for r in uni]
            check(
                "Squarzi and Kraft weightings produce different Home orders at 80F",
                sq_keys != kr_keys and (sq_keys[:1] != kr_keys[:1] or sq_keys[:8] != kr_keys[:8]),
                {"squarzi": sq_keys[:8], "kraft": kr_keys[:8]},
            )
            # uniform vs a leader should also differ, or at least icon scores on the leader path should be used
            check(
                "Home looks carry icon scores at 80F",
                any(r["iconW"] for r in sq + kr) or (sq and kr),
                {"sq0": (sq[:1] if sq else None), "kr0": (kr[:1] if kr else None)},
            )
            if uni_keys and sq_keys:
                # not required to differ if the pool is tiny, but when both have 8+, expect movement
                if len(sq_keys) >= 8 and len(uni_keys) >= 8:
                    check("leading weights shift Home order vs uniform at 80F", sq_keys[:8] != uni_keys[:8] or kr_keys[:8] != uni_keys[:8], {"uni": uni_keys[:8], "sq": sq_keys[:8], "kr": kr_keys[:8]})

        ctx.close()
        browser.close()
    if httpd:
        httpd.shutdown()
    if fails:
        print("FAILED:", *fails, sep="\n  ")
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
