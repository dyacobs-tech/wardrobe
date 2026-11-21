#!/usr/bin/env python3
"""Build .84.0 — Palm Beach warm-weather looks (HAN-18).

At 78°F, Casual and Smart Casual deals on Mine, Mix and New must
favour unlayered short-sleeve outfits (T-shirt + jeans/trousers,
short-sleeve shirt/polo). .85.3: shorts are an occasional Casual
option (~10-15% at 78°F, band 5-20% for sampling) and never deal at
Smart Casual or above. Wardrobe Rules still hold, and pool slides stay
in pool outfits only.

Usage:
  PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_warm_weather.py
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from buildinfo import CURRENT_BUILD  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
BUILD = CURRENT_BUILD
SHOTS = Path("/workspace/wardrobe-audit/warm-weather")
SHOTS.mkdir(parents=True, exist_ok=True)

LIVE = json.loads((HERE / "fixture_closet_live.json").read_text())
# Storage holds only uploaded (non-seed) pieces; the app merges the
# built-in seed library (his tees, short-sleeve polos, etc.) on boot.
UPLOADED = [
    dict(i, addedISO=i.get("addedISO") or "2026-11-17",
         photo=i.get("photo") or i.get("src") or "assets/icon-192.png")
    for i in LIVE
    if not str(i.get("id") or "").startswith("seed-")
]

# Before numbers measured on .83.0 (uploaded closet, no tees in the deal
# because seed tees were held back and regular tees stopped at level 3).
BEFORE = {
    "casual": {"ss": 42.5, "unlayered": 61.3, "teeBottom": 0.0, "shorts": 11.3},
    "smart": {"ss": 35.0, "unlayered": 67.5, "teeBottom": 0.0, "shorts": 0.0},
    "home_rendered": {"ss": 48.8, "unlayered": 58.8, "teeBottom": 0.0, "shorts": 0.0},
}

fails: list[str] = []
MEASURE: dict = {}


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:600]))
    if not ok:
        fails.append(name)


def pct(rows, pred):
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if pred(r)) / len(rows), 1)


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
    return httpd, "http://127.0.0.1:%s/" % httpd.server_address[1]


def seed_js(items):
    return (
        "(() => { if (sessionStorage.getItem('seededWarm84')) return; "
        "localStorage.clear(); sessionStorage.setItem('seededWarm84','1');"
        " localStorage.setItem('wardrobe.items', %s);"
        " localStorage.setItem('wardrobe.todaySource', JSON.stringify('wardrobe'));"
        " localStorage.setItem('wardrobe.formality', JSON.stringify(3));"
        " localStorage.setItem('wardrobe-theme', 'light');"
        " })();" % json.dumps(json.dumps(items))
    )


def launch(p):
    last = None
    for kind in ("webkit", "chromium"):
        try:
            return getattr(p, kind).launch(), kind
        except Exception as e:
            last = e
    raise last


CLASSIFY_JS = r"""
({ level, temp, n }) => {
  const items = (wardrobeItems || []).filter(i => i && i.id && !i.laundry);
  const deck = WardrobeComposer.build(items);
  const keys = (typeof onbodyKeys === 'function') ? onbodyKeys() : null;
  const rules = window.WardrobeRules;
  function row(o) {
    const t = o.top, b = o.bottom, l = o.layer, s = o.shoes;
    const ss = !!(t && (t.shortSleeve || t.kind === 'tee'));
    const teeBottom = !!(t && t.kind === 'tee' && b && (b.kind === 'jeans' || b.kind === 'trousers' || b.kind === 'chinos' || b.kind === 'linen'));
    const poolSlide = !!(s && s.poolOnly && !(b && (b.kind === 'swim' || b.swim)));
    let ruleBreak = false;
    if (rules && typeof rules.lookAllowed === 'function') {
      ruleBreak = !rules.lookAllowed({ t, b, s, l, tuck: o.tuck }, { temp, level });
    }
    return {
      ss, unlayered: !l, teeBottom,
      shorts: !!(b && b.kind === 'shorts'),
      tee: !!(t && t.kind === 'tee'),
      poolSlide, ruleBreak,
      topKind: t && t.kind, layerKind: l && l.kind, bottomKind: b && b.kind
    };
  }
  function stats(outs) {
    const rows = (outs || []).map(row);
    const p = pred => rows.length ? Math.round(1000 * rows.filter(pred).length / rows.length) / 10 : 0;
    return {
      n: rows.length,
      ss: p(r => r.ss),
      unlayered: p(r => r.unlayered),
      teeBottom: p(r => r.teeBottom),
      shorts: p(r => r.shorts),
      tee: p(r => r.tee),
      poolSlide: rows.filter(r => r.poolSlide).length,
      ruleBreak: rows.filter(r => r.ruleBreak).length,
      topKinds: rows.reduce((a,r) => { a[r.topKind||'?']=(a[r.topKind||'?']||0)+1; return a; }, {}),
      layers: rows.reduce((a,r) => { a[r.layerKind||'none']=(a[r.layerKind||'none']||0)+1; return a; }, {}),
      bottoms: rows.reduce((a,r) => { a[r.bottomKind||'?']=(a[r.bottomKind||'?']||0)+1; return a; }, {})
    };
  }
  const free = deck.deal(n, { level, temp, recent: [], banned: {} }) || [];
  const rendered = deck.deal(n, { level, temp, onlyKeys: keys || undefined, recent: [], banned: {} }) || [];
  return { free: stats(free), renderedFirst: stats(rendered), closet: items.length };
}
"""


FEED_JS = r"""
async ({ feed, level, temp, n, weights }) => {
  const m = await window.endlessMeasure81({ feed, level, weights, n, temp });
  const rows = m.looks || [];
  const byId = {};
  (wardrobeItems || []).forEach(i => { if (i && i.id) byId[i.id] = i; });
  let catalog = [];
  try {
    const r = await fetch('assets/edit-catalog.json', { cache: 'force-cache' });
    const j = r.ok ? await r.json() : null;
    catalog = (j && (j.products || j)) || [];
    if (!Array.isArray(catalog)) catalog = [];
  } catch (e) { catalog = []; }
  if (!catalog.length) {
    try {
      if (typeof SHOP_CATALOGUE !== 'undefined' && Array.isArray(SHOP_CATALOGUE) && SHOP_CATALOGUE.length && SHOP_CATALOGUE.some(x => x && x.sku)) catalog = SHOP_CATALOGUE;
    } catch (e) {}
  }
  function shopItem(id) {
    if (typeof id !== 'string' || id.indexOf('sku:') !== 0) return null;
    const sku = id.slice(4);
    let e = null;
    for (const x of catalog) {
      if (!x) continue;
      if (x.sku === sku || x.id === id || x.id === sku || ('sku:' + x.sku) === id) { e = x; break; }
    }
    if (!e) return null;
    const name = e.name || '';
    const c = String(e.cat || e.category || '').toLowerCase();
    let category = 'Shirts';
    if (c === 'jeans' || c === 'Jeans') category = 'Jeans';
    else if (c === 'shorts' || c === 'Shorts') category = /swim|trunk/i.test(name) ? 'Bathing suits' : 'Shorts';
    else if (c === 'trousers' || c === 'Trousers') category = 'Trousers';
    else if (c === 'shoes' || c === 'Shoes') category = 'Shoes';
    else if (c === 'blazer' || c === 'outerwear' || c === 'Blazers' || c === 'Jackets') category = /blazer|sport coat/i.test(name) ? 'Blazers' : (c === 'Blazers' ? 'Blazers' : 'Jackets');
    else if (c === 'knitwear' || c === 'Sweaters') category = /polo/i.test(name) ? 'Polos' : /\btee\b|t-shirt|t shirt/i.test(name) ? 'Tees' : 'Sweaters';
    else if (c === 'shirt' || c === 'shirts' || c === 'tees' || c === 'tee' || c === 't-shirt' || c === 'Tees' || c === 'Shirts' || c === 'Polos') {
      category = /polo/i.test(name) || c === 'Polos' ? 'Polos' : (/\btee\b|t-shirt|t shirt/i.test(name) || c === 'Tees') ? 'Tees' : 'Shirts';
    } else if (c === 'polos' || c === 'polo') category = 'Polos';
    return { id, name, category, colourName: e.colour || e.colourName || '', colourHex: e.hex || e.colourHex || '#888' };
  }
  function asItem(id) { return byId[id] || shopItem(id); }
  const C = window.WardrobeComposer;
  const classified = rows.map(r => {
    const ids = r.ids || [];
    const profs = ids.map(asItem).filter(Boolean).map(it => C.profile(it));
    const t = profs.find(p => p.role === 'top');
    const b = profs.find(p => p.role === 'bottom');
    const l = profs.find(p => p.role === 'layer');
    const s = profs.find(p => p.role === 'shoes');
    const ss = !!(t && (t.shortSleeve || t.kind === 'tee'));
    const teeBottom = !!(t && t.kind === 'tee' && b && (b.kind === 'jeans' || b.kind === 'trousers' || b.kind === 'chinos' || b.kind === 'linen'));
    const poolSlide = !!(s && s.poolOnly && !(b && (b.kind === 'swim' || b.swim)));
    return { ss, unlayered: !l, teeBottom, shorts: !!(b && b.kind === 'shorts'), tee: !!(t && t.kind === 'tee'), poolSlide };
  });
  const p = pred => classified.length ? Math.round(1000 * classified.filter(pred).length / classified.length) / 10 : 0;
  const unresolved = rows.length ? rows.filter(r => !(r.ids||[]).some(id => asItem(id))).length : 0;
  return {
    n: classified.length,
    ss: p(r => r.ss),
    unlayered: p(r => r.unlayered),
    teeBottom: p(r => r.teeBottom),
    shorts: p(r => r.shorts),
    tee: p(r => r.tee),
    poolSlide: classified.filter(r => r.poolSlide).length,
    unresolved,
    catalog: catalog.length,
    sampleIds: (rows[0] && rows[0].ids) || [],
    ms: m.ms
  };
}
"""


def main():
    httpd, base = start_server()
    with sync_playwright() as p:
        browser, kind = launch(p)
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            service_workers="block",
        )
        ctx.add_init_script(seed_js(UPLOADED))
        ctx.route("**/*.workers.dev/**", lambda r: r.abort())
        errors = []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base, wait_until="load")
        pg.wait_for_timeout(2500)

        build = pg.evaluate("window.WARDROBE_BUILD") or ""
        check("build is current", BUILD in build, f"{build} vs {BUILD}")

        inv = pg.evaluate("""() => {
          const items = wardrobeItems || [];
          const c = {};
          items.forEach(i => { c[i.category] = (c[i.category]||0)+1; });
          return { n: items.length, cats: c, tees: items.filter(i => i.category==='Tees').length, shorts: items.filter(i => i.category==='Shorts').length, jeans: items.filter(i => i.category==='Jeans').length };
        }""")
        print("CLOSET", json.dumps(inv))
        check("closet includes his tees", inv.get("tees", 0) >= 15, inv)
        check("closet includes shorts", inv.get("shorts", 0) >= 1, inv)
        check("closet includes jeans", inv.get("jeans", 0) >= 2, inv)

        # Seed wardrobe rules if the helper exists
        pg.evaluate("""() => {
          if (typeof currentWeather !== 'undefined') {
            currentWeather = Object.assign({}, currentWeather || {}, { temp: 78, label: 'Clear', rain: 0, feels: 78 });
          }
          if (typeof formalityLevel !== 'undefined') formalityLevel = 2;
        }""")

        after = {}
        for level, key in ((2, "casual"), (3, "smart")):  # .86.34: Daytime, Nighttime Casual
            after[key] = pg.evaluate(CLASSIFY_JS, {"level": level, "temp": 78, "n": 80})
            print("MINE", key, json.dumps(after[key]))

        MEASURE["mine"] = after

        # Thresholds: unlayered and short-sleeve must be the clear majority
        cfree = after["casual"]["free"]
        sfree = after["smart"]["free"]
        check("casual 80 looks dealt", cfree["n"] == 80, cfree)
        check("smart 80 looks dealt", sfree["n"] == 80, sfree)
        check("casual short-sleeve is the majority (>=70%)", cfree["ss"] >= 70, cfree)
        check("casual unlayered is the majority (>=75%)", cfree["unlayered"] >= 75, cfree)
        check("casual has plenty of T-shirt + jeans/trousers (>=25%)", cfree["teeBottom"] >= 25, cfree)
        check("daytime includes shorts on a warm day (>=5%)", cfree["shorts"] >= 5, cfree)
        check("nighttime casual deals no shorts", sfree["shorts"] == 0, sfree)
        check("smart-casual short-sleeve is the majority (>=60%)", sfree["ss"] >= 60, sfree)
        check("smart-casual unlayered is the majority (>=70%)", sfree["unlayered"] >= 70, sfree)
        check("smart-casual has T-shirt + jeans/trousers (>=20%)", sfree["teeBottom"] >= 20, sfree)
        check("0 wardrobe rule violations (casual+smart)", cfree["ruleBreak"] + sfree["ruleBreak"] == 0, {"c": cfree, "s": sfree})
        check("0 pool slides outside pool (casual+smart)", cfree["poolSlide"] + sfree["poolSlide"] == 0, {"c": cfree, "s": sfree})

        # Improvement vs .83.0 baseline
        check("casual short-sleeve improved vs .83.0", cfree["ss"] > BEFORE["casual"]["ss"], {"before": BEFORE["casual"], "after": cfree})
        check("casual tee+jeans improved vs .83.0", cfree["teeBottom"] > BEFORE["casual"]["teeBottom"], {"before": BEFORE["casual"], "after": cfree})
        check("smart-casual short-sleeve improved vs .83.0", sfree["ss"] > BEFORE["smart"]["ss"], {"before": BEFORE["smart"], "after": sfree})

        cr = after["casual"]["renderedFirst"]
        check("Home/Mine rendered-first is not trapped in long-sleeve layered looks", cr["ss"] >= 60 and cr["unlayered"] >= 70, cr)
        check("Home/Mine rendered-first can include tees or shorts when warm", cr["tee"] > 0 or cr["shorts"] > 0, cr)

        # Mix + New via the endless worker. Inject the module script
        # with an onload hook so a stuck idle loader cannot block us.
        load = pg.evaluate("""() => new Promise((resolve) => {
          if (typeof window.endlessMeasure81 === 'function') return resolve({ already: true });
          const u = window.__mod81 && window.__mod81.endless;
          if (!u) return resolve({ noUrl: true, mod: window.__mod81 || null });
          const s = document.createElement('script');
          s.src = u;
          s.onload = () => resolve({ loaded: true, hasMeasure: typeof window.endlessMeasure81, hasShow: typeof window.endlessShow81 });
          s.onerror = () => resolve({ loaded: false, u: u });
          document.head.appendChild(s);
          setTimeout(() => resolve({ timeout: true, hasMeasure: typeof window.endlessMeasure81 }), 8000);
        })""")
        print("ENDLESS_LOAD", load)
        ready = False
        diag = load
        for _ in range(50):
            diag = pg.evaluate("""() => {
              const st = window.__endless81 && window.__endless81.stats && window.__endless81.stats();
              return {
                hasShow: typeof window.endlessShow81 === 'function',
                hasMeasure: typeof window.endlessMeasure81 === 'function',
                ready: !!(st && st.ready),
                buf: st && st.buf,
              };
            }""")
            ready = bool(diag and diag.get("hasMeasure") and diag.get("ready"))
            if ready:
                break
            pg.wait_for_timeout(400)
        check("endless worker ready", bool(ready), diag)

        feeds = {}
        if ready:
            weights = pg.evaluate("() => window.iconWeights81 && window.iconWeights81.state ? window.iconWeights81.state() : null")
            for feed in ("withmine", "allnew"):
                feeds[feed] = {}
                for level, key in ((2, "casual"), (3, "smart")):  # .86.34: Daytime, Nighttime Casual
                    try:
                        feeds[feed][key] = pg.evaluate(FEED_JS, {"feed": feed, "level": level, "temp": 78, "n": 80, "weights": weights})
                    except Exception as e:
                        feeds[feed][key] = {"error": str(e)}
                        check("measure %s %s" % (feed, key), False, e)
                    print("FEED", feed, key, json.dumps(feeds[feed].get(key)))
            MEASURE["feeds"] = feeds
            for feed, label in (("withmine", "Mix"), ("allnew", "New")):
                cf = feeds.get(feed, {}).get("casual") or {}
                sf = feeds.get(feed, {}).get("smart") or {}
                if cf.get("n"):
                    check("%s casual short-sleeve majority (>=55%%)" % label, cf.get("ss", 0) >= 55, cf)
                    check("%s casual unlayered majority (>=65%%)" % label, cf.get("unlayered", 0) >= 65, cf)
                    check("%s casual 0 pool slides outside pool" % label, cf.get("poolSlide", 0) == 0, cf)
                    check("%s daytime includes shorts (>=5%%)" % label, cf.get("shorts", 0) >= 5, cf)
                if sf.get("n"):
                    check("%s smart-casual unlayered majority (>=55%%)" % label, sf.get("unlayered", 0) >= 55, sf)
                    check("%s smart-casual 0 pool slides outside pool" % label, sf.get("poolSlide", 0) == 0, sf)
                    check("%s nighttime casual deals no shorts" % label, sf.get("shorts", 0) == 0, sf)

        # Polo classification: a knit short-sleeve polo is not treated as long-sleeve
        polo = pg.evaluate("""() => {
          const C = WardrobeComposer;
          const ss = C.profile({ id:'p1', name:'Isaia Cream Knit Polo', category:'Polos', colourName:'Cream', colourHex:'#ece1c9' });
          const ls = C.profile({ id:'p2', name:'Loro Piana White Long-Sleeve Polo', category:'Polos', colourName:'White', colourHex:'#f5f5f2' });
          const tee = C.profile({ id:'t1', name:'Whitesville Navy Heavyweight Tee', category:'Tees', colourName:'Navy', colourHex:'#252c3e' });
          const shorts = C.profile({ id:'s1', name:'Theory Olive Shorts', category:'Shorts', colourName:'Olive', colourHex:'#6b6b3a' });
          return { ss: { kind: ss.kind, shortSleeve: !!ss.shortSleeve, lo: ss.lo, hi: ss.hi },
                   ls: { kind: ls.kind, shortSleeve: !!ls.shortSleeve, lo: ls.lo, hi: ls.hi },
                   tee: { kind: tee.kind, hi: tee.hi, shortSleeve: !!tee.shortSleeve },
                   shorts: { kind: shorts.kind, hi: shorts.hi } };
        }""")
        check("knit polo is short-sleeve", polo["ss"]["shortSleeve"] is True and polo["ss"]["hi"] >= 4, polo)
        check("long-sleeve polo is not marked short-sleeve", polo["ls"]["shortSleeve"] is False, polo)
        check("T-shirts reach Smart Casual (hi>=4)", polo["tee"]["hi"] >= 4 and polo["tee"]["shortSleeve"] is True, polo)
        check("shorts stop at Casual (hi==3)", polo["shorts"]["hi"] == 3, polo)

        if errors:
            check("no page errors", False, errors[:4])
        else:
            check("no page errors", True)

        print("MEASURE", json.dumps({"before": BEFORE, "after": MEASURE}, indent=2))

        # Screenshots of Home and Looks at 390 and 1440, light + dark
        def shot(name):
            pg.screenshot(path=str(SHOTS / name), full_page=False)

        def open_tab(tab):
            # The Looks nav section is "ideas", but the tab name is "looks".
            # switchTab("ideas") is not in TABS and falls back to Home.
            name = "looks" if tab in ("ideas", "looks") else tab
            pg.evaluate("""(name) => { if (typeof switchTab === 'function') switchTab(name); }""", name)
            if name == "looks":
                pg.wait_for_function("""() => {
                  const p = document.getElementById('panel-looks');
                  return p && !p.hidden;
                }""", timeout=8000)
                pg.wait_for_timeout(600)
            else:
                pg.wait_for_function("""() => {
                  const p = document.getElementById('panel-today');
                  return p && !p.hidden;
                }""", timeout=8000)
                # Wait until a cut-out or a closet flat-lay is actually on screen
                # (never settle the shot on the grey LQ silhouette).
                try:
                    pg.wait_for_function("""() => {
                      const h = document.getElementById('today-hero');
                      if (!h) return false;
                      if (h.classList.contains('hero-flatlay')) {
                        const imgs = [...h.querySelectorAll('#today-collage img')];
                        return imgs.length > 0 && imgs.some(im => im.complete && im.naturalWidth > 40);
                      }
                      const im = document.getElementById('today-img');
                      return !!(im && !im.hidden && !im.hasAttribute('data-nocut') && im.complete && im.naturalWidth > 40 && !h.classList.contains('lq-show'));
                    }""", timeout=8000)
                except Exception:
                    pass
                pg.wait_for_timeout(400)

        for theme, tname in (("light", "light"), ("dark", "dark")):
            pg.evaluate("""(t) => {
              try { localStorage.setItem('wardrobe-theme', t); } catch (e) {}
              document.documentElement.setAttribute('data-theme', t);
              document.documentElement.classList.toggle('dark', t === 'dark');
              if (typeof applyTheme === 'function') applyTheme(t);
            }""", theme)
            pg.wait_for_timeout(400)
            pg.set_viewport_size({"width": 390, "height": 844})
            open_tab("today")
            shot("390x844-%s-home.png" % tname)
            open_tab("ideas")
            shot("390x844-%s-looks.png" % tname)
            pg.set_viewport_size({"width": 1440, "height": 900})
            open_tab("today")
            shot("1440x900-%s-home.png" % tname)
            open_tab("ideas")
            shot("1440x900-%s-looks.png" % tname)

        # reset viewport for any leftover
        browser.close()

    httpd.shutdown()
    print("SCREENSHOTS", SHOTS)
    if fails:
        print("FAILED %d checks:" % len(fails))
        for f in fails:
            print(" -", f)
        return 1
    print("ALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
