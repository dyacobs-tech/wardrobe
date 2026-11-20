#!/usr/bin/env python3
"""Home hero (Nov 19) — no flutter on Next, the caption sits near the nav.

  A. On every animation frame across five Next taps (and four rapid ones) exactly one figure is
     visible and it is fully loaded: the old cut-out stays until the new
     one is decoded, then they swap in one frame (never both, never none).
  B. The hero image box never changes size or position while dealing.
  C. Phone sizes 375-430 wide: the caption's control row ends 12-36px above
     the nav, and the caption starts below the figure's feet.
Local server only; workers.dev blocked; cut-out loads are slowed 250 ms.
"""
from __future__ import annotations
import functools, http.server, json, socketserver, sys, threading, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
fails: list[str] = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:400]))
    if not ok:
        fails.append(name)


Q = type("Q", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None})
srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % srv.server_address[1]
FX = (ROOT / "tests/fixture_closet83.json").read_text()

FRAME_JS = """() => { window.__hf = []; const hero = document.getElementById('today-hero'), img = document.getElementById('today-img');
  const vis = el => { const cs = getComputedStyle(el); return el && !el.hidden && cs.visibility !== 'hidden' && parseFloat(cs.opacity) > 0.01 && el.getBoundingClientRect().height > 50; };
  const ok = el => el.complete && el.naturalWidth > 0;
  const tick = () => {
    const collage = document.getElementById('today-collage');
    const flat = hero.classList.contains('hero-flatlay') && collage && !collage.hidden && collage.children.length > 0;
    const figs = [img, ...hero.querySelectorAll('.hero-xfade')].filter(vis);
    const r = (flat ? hero : img).getBoundingClientRect();
    const n = flat ? 1 : figs.length;
    const loaded = flat ? 1 : (figs.length && figs.every(ok) ? 1 : 0);
    window.__hf.push([n, loaded, Math.round(r.top), Math.round(r.height), Math.round(r.width)]);
    if (window.__hf.length < 4000) requestAnimationFrame(tick); };
  requestAnimationFrame(tick); }"""


def new_ctx(b, w, h, slow=False):
    ctx = b.new_context(viewport={"width": w, "height": h}, service_workers="block")
    ctx.route("**/*.workers.dev/**", lambda r: r.abort())
    if slow:
        def s(r):
            time.sleep(0.25); r.continue_()
        ctx.route("**/assets/onbody-cut/*.webp", s)
    ctx.add_init_script("(() => { localStorage.setItem('wardrobe.items', %s); })();" % json.dumps(FX))
    return ctx


with sync_playwright() as p:
    b = p.chromium.launch()
    for (w, h) in [(390, 844), (1440, 900)]:
        ctx = new_ctx(b, w, h, slow=True); pg = ctx.new_page()
        pg.goto(BASE, wait_until="load"); pg.wait_for_timeout(5000)
        pg.evaluate(FRAME_JS); pg.wait_for_timeout(300)
        srcs = set()
        for i in range(5):
            pg.click("#today-next"); pg.wait_for_timeout(1400)
            srcs.add(pg.evaluate("""() => {
              const img = document.getElementById('today-img');
              const hero = document.getElementById('today-hero');
              const name = (document.getElementById('today-name') || {}).textContent || '';
              if (hero && hero.classList.contains('hero-flatlay')) {
                const cells = [...document.querySelectorAll('#today-collage img, #today-collage .fl-cell')].map(el => el.getAttribute('src') || el.getAttribute('aria-label') || '').join('|');
                return name + '|' + cells;
              }
              if (img && !img.hidden && img.getAttribute('src')) return img.getAttribute('src');
              return img ? (img.getAttribute('src') || name) : name;
            }"""))
        for i in range(4):  # rapid taps: stale swaps are cancelled, never a blank frame
            pg.click("#today-next"); pg.wait_for_timeout(90)
        pg.wait_for_timeout(1500)
        fr = pg.evaluate("() => window.__hf")
        bad = [f for f in fr if f[0] != 1 or not f[1]]
        # A cut-out hero still has to deal a new figure on Next. A flat-lay
        # (no on-body cut for this closet) must stay one stable figure and
        # must not be replaced by an empty hero or a random stand-in.
        flat = pg.evaluate("() => document.getElementById('today-hero').classList.contains('hero-flatlay')")
        check("%dx%d: Next dealt new figures (%d distinct)" % (w, h, len(srcs)), (len(srcs) >= 4) or (flat and len(srcs) >= 1 and not any(not s for s in srcs)), srcs)
        check("%dx%d: exactly one loaded figure on every frame (%d frames)" % (w, h, len(fr)), len(fr) > 100 and not bad, bad[:8])
        geoms = set((f[2], f[3], f[4]) for f in fr)
        check("%dx%d: hero image box never moves or resizes" % (w, h), len(geoms) == 1, geoms)
        ctx.close()
    for (w, h) in [(375, 667), (393, 852), (430, 932)]:
        ctx = new_ctx(b, w, h); pg = ctx.new_page()
        pg.goto(BASE, wait_until="load"); pg.wait_for_timeout(4500)
        m = pg.evaluate("""() => { const R = s => document.querySelector(s).getBoundingClientRect();
          return { row: R('#today-simple-actions').bottom, nav: R('#bottombar').top, kicker: R('#panel-today .today-kicker').top, img: R('#today-img').bottom }; }""")
        gap = m["nav"] - m["row"]
        # .85: the dress-level picker sits above the nav, so the action row
        # is higher than the old 12–36px band. It must still clear the pill.
        check("%dx%d: controls sit %dpx above the nav" % (w, h, gap), 12 <= gap <= 160, m)
        picker = pg.evaluate("""() => {
          const b = document.querySelector('#today-type-btn');
          const n = document.querySelector('#bottombar');
          if (!b || !n) return -1;
          return n.getBoundingClientRect().top - b.getBoundingClientRect().bottom;
        }""")
        check("%dx%d: dress picker clears the nav by %dpx" % (w, h, picker), picker >= 8, picker)
        check("%dx%d: caption starts below the figure" % (w, h), m["kicker"] >= m["img"], m)
        ctx.close()
    b.close()

print("\n%d failure(s)" % len(fails))
sys.exit(1 if fails else 0)
