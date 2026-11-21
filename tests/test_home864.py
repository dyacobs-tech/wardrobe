#!/usr/bin/env python3
"""HAN-31 / .86.4 — Home only ever shows an avatar cut-out of him, never a flat-lay grid.

Loads the live closet fixture, Palm Beach 76°F Overcast, then cycles Next
and every dress level in light and dark at 390px. Fails if #today-hero
picks up hero-flatlay or a piece-photo collage.
"""
from __future__ import annotations

import http.server
import json
import os
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from buildinfo import CURRENT_BUILD  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SHOTS = Path("/workspace/han31-shots")
SHOTS.mkdir(parents=True, exist_ok=True)


LABELS = ["Swim/Pool", "Shorts & Tee", "Casual", "Smart Casual", "Business Casual", "Formal", "Black Tie"]
fails: list[str] = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:600]))
    if not ok:
        fails.append(name)


def seed_js(items):
    return (
        "(() => { if (sessionStorage.getItem('seededHome864')) return; "
        "localStorage.clear(); sessionStorage.setItem('seededHome864','1');"
        " localStorage.setItem('wardrobe.items', %s);"
        " localStorage.setItem('wardrobe.todaySource', JSON.stringify('wardrobe'));"
        " localStorage.setItem('wardrobe.formality', JSON.stringify(4));"
        " localStorage.setItem('wardrobe-theme', 'light');"
        " })();" % json.dumps(json.dumps(items))
    )


def start_server():
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(ROOT), **k)

        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Q)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "http://127.0.0.1:%d/" % httpd.server_address[1]


HERO_JS = """() => {
  const h = document.getElementById('today-hero');
  const im = document.getElementById('today-img');
  const c = document.getElementById('today-collage');
  const src = (im && im.getAttribute('src')) || '';
  const flCells = c ? c.querySelectorAll('.flatlay .fl-cell, .fl-cell').length : 0;
  const empty = !!(h && h.classList.contains('hero-empty861'));
  const flat = !!(h && h.classList.contains('hero-flatlay'));
  const cut = /onbody-cut/.test(src);
  const loaded = !!(im && !im.hidden && im.complete && im.naturalWidth > 40);
  return {
    build: window.WARDROBE_BUILD || '',
    title: (document.getElementById('today-name') || {}).textContent || '',
    level: (typeof dressLevel841 === 'function') ? dressLevel841() : null,
    levelLabel: (document.getElementById('today-type-label') || {}).textContent || '',
    empty, flat, cut, loaded, src: src.slice(0, 80),
    flCells,
    collageOpen: !!(c && !c.hidden && (c.innerHTML || '').trim() && !c.querySelector('.hero-empty861-box')),
    hasCut: !!(h && h.classList.contains('has-cut')),
    classes: h ? Array.from(h.classList).join(' ') : '',
    composer: !!(window.todayLook && todayLook.composer),
    visible: (typeof lookHeroVisible84 === 'function' && todayLook) ? lookHeroVisible84(todayLook) : null,
    render: (typeof onbodyForLook === 'function' && todayLook) ? (onbodyForLook(todayLook) || '') : ''
  };
}"""

WAIT_JS = """() => {
  const h = document.getElementById('today-hero');
  if (!h) return false;
  if (h.classList.contains('hero-flatlay')) return true; /* settle so the test can fail it */
  if (h.classList.contains('hero-empty861')) return true;
  const im = document.getElementById('today-img');
  const src = (im && im.getAttribute('src')) || '';
  return !!(im && !im.hidden && im.complete && im.naturalWidth > 40 && /onbody-cut/.test(src) && !h.classList.contains('lq-show'));
}"""

WEATHER_JS = """() => {
  currentWeather = { temp: 76, feels: 76, code: 3, label: 'Overcast', hi: 79, lo: 70, rain: 10 };
  if (typeof currentLoc !== 'undefined') currentLoc = Object.assign({}, currentLoc || {}, { name: 'Palm Beach', admin: 'Florida', country: 'United States' });
  if (typeof renderLoc === 'function') renderLoc();
  if (typeof applyWeatherToToday === 'function') applyWeatherToToday();
  if (typeof window.clearHeroLookahead === 'function') window.clearHeroLookahead();
}"""


def hero_ok(st, allow_empty=True):
    if st.get("flat") or st.get("flCells") or st.get("collageOpen"):
        return False, "flat-lay on Home: " + json.dumps(st)[:400]
    if st.get("empty"):
        return (True, "empty") if allow_empty else (False, "empty: " + json.dumps(st)[:400])
    if st.get("cut") and st.get("loaded"):
        return True, st.get("src")
    return False, "no cut-out: " + json.dumps(st)[:400]


def wait_hero(pg, timeout=12000):
    try:
        pg.wait_for_function(WAIT_JS, timeout=timeout)
    except Exception:
        pass
    pg.wait_for_timeout(250)
    st = pg.evaluate(HERO_JS)
    # A just-dealt cut-out can still be decoding; never fail a shoot on that race.
    if st.get("cut") and not st.get("loaded"):
        try:
            pg.wait_for_function("""() => {
              const im = document.getElementById('today-img');
              return !!(im && !im.hidden && im.complete && im.naturalWidth > 40);
            }""", timeout=8000)
        except Exception:
            pass
        st = pg.evaluate(HERO_JS)
    return st


def set_theme(pg, theme):
    pg.evaluate("""(t) => {
      try { localStorage.setItem('wardrobe-theme', t); } catch (e) {}
      document.documentElement.setAttribute('data-theme', t);
      document.documentElement.classList.toggle('dark', t === 'dark');
      if (typeof applyTheme === 'function') applyTheme(t);
    }""", theme)
    pg.wait_for_timeout(300)


def set_level(pg, level):
    pg.evaluate("""(lv) => {
      if (typeof window.clearHeroLookahead === 'function') window.clearHeroLookahead();
      if (typeof setFormality === 'function') setFormality(lv);
    }""", level)
    return wait_hero(pg)


def main():
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    httpd, base = start_server()
    report = {"build": CURRENT_BUILD, "levels": {}, "next": [], "shots": []}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            service_workers="block",
        )
        ctx.add_init_script(seed_js(photographed_closet()))
        ctx.route("**/*.workers.dev/**", lambda r: r.abort())
        errors = []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base, wait_until="load")
        pg.wait_for_timeout(3500)
        pg.evaluate(WEATHER_JS)
        if pg.evaluate("typeof dealHeroForSource === 'function'"):
            pg.evaluate("dealHeroForSource()")
        st = wait_hero(pg, 15000)
        check("build is .86.4", CURRENT_BUILD in (st.get("build") or ""), st.get("build"))
        ok, detail = hero_ok(st, allow_empty=False)
        check("opening Home is an avatar cut-out, not a grid", ok, detail)
        print("OPENING", json.dumps({k: st[k] for k in st}, indent=2))

        # Render inventory per dress level (owned on-body keys that fit)
        inv = pg.evaluate("""() => {
          const labels = (typeof HERO_TYPE_LABELS !== 'undefined' && HERO_TYPE_LABELS) || [];
          const map = (typeof ONBODY !== 'undefined' && ONBODY.map) || {};
          const own = {};
          (wardrobeItems || []).forEach(i => { if (i && i.id) own[i.id] = i; });
          const out = {};
          labels.forEach(n => { out[n] = { ownedRenders: 0, samples: [] }; });
          Object.keys(map).forEach(k => {
            const ids = k.split('|');
            if (!ids.every(id => own[id])) return;
            const look = { fwPieces: ids.map(id => own[id]) };
            labels.forEach((name, i) => {
              const lv = i + 1;
              if (typeof lookFitsDress841 === 'function' && lookFitsDress841(look, lv)) {
                out[name].ownedRenders++;
                if (out[name].samples.length < 3) out[name].samples.push(map[k]);
              }
            });
          });
          const dealt = {};
          labels.forEach((name, i) => {
            const lv = i + 1;
            const exact = (typeof homeComposerLooksAtLevel864 === 'function') ? (homeComposerLooksAtLevel864(24, lv) || []) : [];
            dealt[name] = { exactRenderedDeals: exact.length, titles: exact.slice(0, 5).map(l => l.title) };
          });
          return { totalMap: Object.keys(map).length, owned: Object.keys(own).length, byLevel: out, deals: dealt };
        }""")
        print("RENDERS", json.dumps(inv, indent=2))
        report["inventory"] = inv
        check("closet has on-body renders", (inv or {}).get("totalMap", 0) >= 400, inv.get("totalMap") if inv else None)
        sc = (inv or {}).get("byLevel", {}).get("Smart Casual", {}).get("ownedRenders", 0)
        check("Smart Casual has owned renders", sc >= 1, sc)

        # Cycle Next several times at Smart Casual (level 4)
        set_level(pg, 4)
        titles = []
        srcs = []
        for i in range(8):
            st = wait_hero(pg)
            ok, detail = hero_ok(st, allow_empty=False)
            check("Next %d at Smart Casual is a cut-out" % (i + 1), ok, detail)
            titles.append(st.get("title"))
            srcs.append(st.get("src"))
            report["next"].append(st)
            if i < 7:
                pg.click("#today-next")
                pg.wait_for_timeout(200)
        check("Next dealt more than one look", len(set(srcs)) >= 2, srcs)

        # Every dress level, several Next taps, light then we'll reshoot dark
        for lv, name in enumerate(LABELS, start=1):
            st = set_level(pg, lv)
            shots_for = []
            for i in range(3):
                st = wait_hero(pg)
                ok, detail = hero_ok(st, allow_empty=True)
                check("%s tap %d is never a grid" % (name, i + 1), ok, detail)
                if st.get("empty"):
                    print("EMPTY", name, json.dumps(st)[:200])
                shots_for.append(st)
                if i < 2:
                    btn = pg.query_selector("#today-next")
                    if btn and btn.is_visible() and not st.get("empty"):
                        btn.click()
                        pg.wait_for_timeout(200)
            report["levels"][name] = shots_for

        def shoot(theme):
            set_theme(pg, theme)
            for lv, name in enumerate(LABELS, start=1):
                st = set_level(pg, lv)
                ok, detail = hero_ok(st, allow_empty=True)
                check("shot %s %s never a grid" % (theme, name), ok, detail)
                slug = name.lower().replace(" ", "-").replace("&", "and").replace("/", "-")
                path = SHOTS / ("%s-390-%s.png" % (theme, slug))
                pg.screenshot(path=str(path), full_page=False)
                report["shots"].append(str(path))
                print("SHOT", path, st.get("title"), st.get("src") or ("empty" if st.get("empty") else ""))
            # Extra: Smart Casual after a few Nexts, the situation in David's shot
            set_level(pg, 4)
            for _ in range(3):
                nxt = pg.query_selector("#today-next")
                if nxt and nxt.is_visible():
                    nxt.click()
                    wait_hero(pg)
            path = SHOTS / ("%s-390-smart-casual-next.png" % theme)
            pg.screenshot(path=str(path), full_page=False)
            report["shots"].append(str(path))
            print("SHOT", path)

        shoot("light")
        shoot("dark")

        if errors:
            print("PAGEERRORS", errors[:8])
            check("no page errors", False, errors[:3])
        else:
            check("no page errors", True)

        browser.close()

    httpd.shutdown()
    (SHOTS / "REPORT.json").write_text(json.dumps(report, indent=2))
    print("SCREENSHOTS", SHOTS)
    print("BUILD", CURRENT_BUILD)
    if fails:
        print("FAILED %d checks:" % len(fails))
        for f in fails:
            print(" -", f)
        return 1
    print("ALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
