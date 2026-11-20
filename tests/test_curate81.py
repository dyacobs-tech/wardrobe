#!/usr/bin/env python3
"""Live .83.0 — The Edit > Curate, icon weightings, engine + Shop the look ranker.

Usage: PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 python3 tests/test_curate81.py
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

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
SHOTS = Path("/workspace/wardrobe-audit/curate")
SHOTS.mkdir(parents=True, exist_ok=True)
CLOSET = json.loads((HERE / "fixture_onbody.json").read_text())
fails: list[str] = []
MEASURE: dict = {}


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
    import threading
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "http://127.0.0.1:%s/" % httpd.server_address[1]


def seed_js(items):
    return (
        "(() => { if (sessionStorage.getItem('seededCurate81')) return; "
        "localStorage.clear(); sessionStorage.setItem('seededCurate81','1');"
        " localStorage.setItem('wardrobe.items', %s);"
        " localStorage.setItem('wardrobe.todaySource', JSON.stringify('wardrobe'));"
        " localStorage.setItem('wardrobe-theme', 'light');"
        " localStorage.setItem('wardrobe.formality', JSON.stringify(4));"
        " })();" % json.dumps(json.dumps(items))
    )


def pct(rows, pred):
    if not rows:
        return 0.0
    return round(100.0 * sum(1 for r in rows if pred(r)) / len(rows), 1)


def launch(p):
    for kind in ("webkit", "chromium"):
        try:
            return getattr(p, kind).launch(), kind
        except Exception as e:
            last = e
    raise last


def main():
    items = [dict(i, addedISO=i.get("addedISO") or "2026-11-17", photo=i.get("photo") or "assets/icon-192.png") for i in CLOSET]
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
        ctx.add_init_script(seed_js(items))
        ctx.route("**/*.workers.dev/**", lambda r: r.abort())
        errors = []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base + "?pv81", wait_until="load")
        pg.wait_for_timeout(2500)
        check("build is .83.0", "83.0" in (pg.evaluate("window.WARDROBE_BUILD") or ""), pg.evaluate("window.WARDROBE_BUILD"))
        check("preview class", pg.evaluate("document.documentElement.classList.contains('pv81')"))

        # ---- The Edit default is Shop catalog ----
        pg.click("#tab-find")
        pg.wait_for_timeout(600)
        check("Shop is default", pg.evaluate("""() => {
          const shop = document.querySelector('[data-edit-section=shop]');
          const cur = document.querySelector('[data-edit-section=curate]');
          const saved = document.getElementById('edit-v-saved');
          const cu = document.getElementById('edit-v-curate');
          return shop && shop.getAttribute('aria-pressed') === 'true'
            && cur && cur.getAttribute('aria-pressed') === 'false'
            && saved && !saved.hidden && cu && cu.hidden;
        }"""))
        check("no page title on The Edit", pg.evaluate("""() => {
          const t = document.getElementById('page-title');
          return !t || t.hidden || !t.offsetParent;
        }"""))

        # ---- Curate ----
        pg.click("#edit-tab-curate")
        pg.wait_for_timeout(800)
        # wait for sliders (icons may lazy-load)
        for _ in range(20):
            n = pg.locator("#cw-sliders .cw-row").count()
            if n >= 9:
                break
            pg.wait_for_timeout(300)
        n_sliders = pg.locator("#cw-sliders .cw-row").count()
        check("Curate opens with icon weight sliders", n_sliders >= 9, n_sliders)
        names = pg.evaluate("() => [...document.querySelectorAll('.cw-name')].map(e => e.textContent)")
        check("Kraft and Beckham are icons", "Alexander Kraft" in names and "David Beckham" in names, names)
        check("Skarsgård is not an icon", not any("skarsg" in (n or "").lower() for n in names), names)
        check("Squarzi is present (casual stand-in)", any("Squarzi" in (n or "") for n in names), names)
        check("dress-level selector", pg.locator("#cw-levels [data-cw-level]").count() == 4)
        check("same-for-all control", pg.locator("#cw-same").count() == 1)
        check("Icons sub-tab active", pg.evaluate("document.querySelector('[data-curate-view=icons]').getAttribute('aria-pressed')") == "true")
        # overflow at 390
        overflow = pg.evaluate("""() => {
          const w = 390;
          const bad = [];
          document.querySelectorAll('#panel-find, #edit-v-curate, #curate-weights, #cw-levels, #cw-sliders, #panel-icons, .edit-section-tabs, .curate-subs').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width - 0.5 > w) bad.push({id: el.id || el.className, w: Math.round(r.width*10)/10, l: r.left, rgt: r.right});
          });
          return bad;
        }""")
        check("nothing cut off at 390px (light)", overflow == [], overflow)

        pg.screenshot(path=str(SHOTS / "390-light-curate-icons-weights.png"), full_page=False)
        # scroll weights into a full view already at top
        pg.screenshot(path=str(SHOTS / "390-light-weighting-ui.png"), full_page=False)

        # Palettes
        pg.click("[data-curate-view=palettes]")
        pg.wait_for_timeout(700)
        check("Palettes moved into Curate", pg.evaluate("""() => {
          const pal = document.getElementById('panel-palettes');
          const host = document.getElementById('curate-pages');
          return pal && host && host.contains(pal) && !pal.hidden
            && document.getElementById('curate-weights').hidden;
        }"""))
        check("Palettes plates or colours visible", pg.locator("#panel-palettes .pal-subtabs, #plate-grid, #featured").count() >= 1)
        pg.screenshot(path=str(SHOTS / "390-light-curate-palettes.png"), full_page=False)

        # Icons again + old entry points gone
        pg.click("[data-curate-view=icons]")
        pg.wait_for_timeout(400)
        check("Icons not in ideas subnav", pg.locator("#subnav-ideas [data-tab=icons], #subnav-ideas [data-tab=palettes]").count() == 0)
        check("Icons panel is inside Curate", pg.evaluate("""() => {
          const ic = document.getElementById('panel-icons');
          return ic && document.getElementById('curate-pages').contains(ic) && !ic.hidden;
        }"""))

        # Dark mode 390
        pg.evaluate("document.documentElement.setAttribute('data-theme','dark')")
        pg.wait_for_timeout(200)
        overflow_d = pg.evaluate("""() => {
          const w = 390, bad = [];
          document.querySelectorAll('#edit-v-curate, #curate-weights, #cw-levels, .edit-section-tabs, .curate-subs').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width - 0.5 > w) bad.push({id: el.id || el.className, w: r.width});
          });
          return bad;
        }""")
        check("nothing cut off at 390px (dark)", overflow_d == [], overflow_d)
        pg.screenshot(path=str(SHOTS / "390-dark-curate-icons-weights.png"), full_page=False)
        pg.click("[data-curate-view=palettes]")
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(SHOTS / "390-dark-curate-palettes.png"), full_page=False)
        pg.evaluate("document.documentElement.setAttribute('data-theme','light')")
        pg.click("[data-curate-view=icons]")
        pg.wait_for_timeout(200)

        # Desktop
        pg.set_viewport_size({"width": 1280, "height": 800})
        pg.wait_for_timeout(400)
        overflow_desk = pg.evaluate("""() => {
          const w = 1280, bad = [];
          document.querySelectorAll('#edit-v-curate, #curate-weights, #panel-find').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.right - 0.5 > w) bad.push({id: el.id || el.className, right: r.right});
          });
          return bad;
        }""")
        check("nothing cut off on desktop", overflow_desk == [], overflow_desk)
        pg.screenshot(path=str(SHOTS / "desktop-curate-icons-weights.png"), full_page=False)
        pg.click("[data-curate-view=palettes]")
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(SHOTS / "desktop-curate-palettes.png"), full_page=False)

        # Looks Filters sheet uses the same Icons data + current-level weights
        pg.set_viewport_size({"width": 390, "height": 844})
        pg.wait_for_timeout(200)
        pg.click("#section-ideas")
        pg.wait_for_timeout(900)
        check("Looks page is open", pg.evaluate("""() => {
          const f = document.getElementById('pv-filter');
          return !!f && f.offsetParent !== null;
        }"""))
        pg.click("#pv-filter")
        pg.wait_for_timeout(500)
        filt = pg.evaluate("""() => {
          const host = document.getElementById('pvf-icons');
          if (!host) return { error: 'no #pvf-icons' };
          const btns = [...host.querySelectorAll('[data-pv-lens]')];
          const none = btns[0] && btns[0].getAttribute('data-pv-lens') === '';
          const ids = btns.filter(b => b.getAttribute('data-pv-lens')).map(b => b.getAttribute('data-pv-lens'));
          const lv = (typeof formalityLevel !== 'undefined') ? formalityLevel : 4;
          const wt = (window.iconWeights81 && window.iconWeights81.weightsForLevel) ? window.iconWeights81.weightsForLevel(lv) : {};
          const expected = (typeof iconList === 'function' ? iconList() : allIcons()).map(ic => ic.id);
          const sorted = expected.slice().sort((a,b) => (+wt[b]||0) - (+wt[a]||0));
          const badges = btns.filter(b => b.querySelector('.pv-w')).map(b => ({ id: b.getAttribute('data-pv-lens'), w: b.querySelector('.pv-w').textContent, off: b.classList.contains('pv-ic-off') }));
          const off = btns.filter(b => b.classList.contains('pv-ic-off')).map(b => b.getAttribute('data-pv-lens'));
          return { noneFirst: none, ids, expected, sorted, sameSet: expected.every(id => ids.includes(id)) && ids.every(id => expected.includes(id)), orderOk: ids.join() === sorted.join(), badges, off, weights: wt };
        }""")
        check("Filters icon list uses same Icons data", filt.get("sameSet") and filt.get("noneFirst"), filt)
        check("Filters icon list is sorted by current-level weights", filt.get("orderOk"), filt)
        # seed a zero weight so dimming is observable (smart-casual default mid=2, none off)
        pg.evaluate("""() => {
          const st = window.iconWeights81.state();
          const mid = {}; allIcons().forEach(ic => mid[ic.id] = 2);
          mid.ford = 0; mid.squarzi = 8;
          window.iconWeights81.setState({ mode: 'all', all: mid, byLevel: st.byLevel });
        }""")
        pg.wait_for_timeout(400)
        pg.evaluate("""() => { if (window.pvSyncLens81) window.pvSyncLens81(); }""")
        pg.wait_for_timeout(200)
        filt2 = pg.evaluate("""() => {
          const host = document.getElementById('pvf-icons');
          const btns = [...host.querySelectorAll('[data-pv-lens]')].filter(b => b.getAttribute('data-pv-lens'));
          const ids = btns.map(b => b.getAttribute('data-pv-lens'));
          const first = ids[0];
          const ford = host.querySelector('[data-pv-lens=ford]');
          return { first, fordOff: ford && ford.classList.contains('pv-ic-off'), fordBadge: !!(ford && ford.querySelector('.pv-w')), squarziBadge: host.querySelector('[data-pv-lens=squarzi] .pv-w') && host.querySelector('[data-pv-lens=squarzi] .pv-w').textContent };
        }""")
        check("Filters dims weight-0 icons and badges the rest", filt2.get("first") == "squarzi" and filt2.get("fordOff") and filt2.get("squarziBadge") == "8" and not filt2.get("fordBadge"), filt2)
        pg.screenshot(path=str(SHOTS / "390-light-looks-filters-icons.png"), full_page=False)
        # restore seeded per-level defaults so later engine tests use the same weights
        pg.evaluate("() => window.iconWeights81.resetDefaults()")
        pg.click("#lfp-close")
        pg.wait_for_timeout(200)

        # Deep links
        pg.goto(base + "?pv81#icons", wait_until="load")
        pg.wait_for_timeout(2000)
        check("deep link #icons opens The Edit > Curate > Icons", pg.evaluate("""() => {
          return currentTab === 'find'
            && document.getElementById('edit-v-curate') && !document.getElementById('edit-v-curate').hidden
            && document.getElementById('panel-icons') && !document.getElementById('panel-icons').hidden;
        }"""))
        pg.goto(base + "?pv81#palettes", wait_until="load")
        pg.wait_for_timeout(2000)
        check("deep link #palettes opens The Edit > Curate > Palettes", pg.evaluate("""() => {
          return currentTab === 'find'
            && document.getElementById('edit-v-curate') && !document.getElementById('edit-v-curate').hidden
            && document.getElementById('panel-palettes') && !document.getElementById('panel-palettes').hidden;
        }"""))

        # Look at an icon from Curate
        pg.goto(base + "?pv81#icons/kraft", wait_until="load")
        pg.wait_for_timeout(2200)
        check("deep link #icons/kraft opens Kraft detail in Curate", pg.evaluate("""() => {
          const d = document.getElementById('icon-detail');
          return currentTab === 'find' && d && !d.hidden && /Kraft/i.test(d.textContent || '');
        }"""))

        # ---- Engine measurements ----
        # Wait for icons + worker
        pg.evaluate("""() => { if (window.endlessLoad81) window.endlessLoad81(); }""")
        ready = False
        for _ in range(60):
            ready = pg.evaluate("""() => {
              try {
                if (window.endlessLoad81) window.endlessLoad81();
                return typeof allIcons === 'function' && allIcons().length >= 9
                  && typeof window.endlessMeasure81 === 'function'
                  && window.__endless81 && window.__endless81.stats && !!window.__endless81.stats().ready;
              } catch (e) { return false; }
            }""")
            if ready:
                break
            pg.wait_for_timeout(500)
        check("endless worker ready for measure", ready, pg.evaluate("() => window.__endless81 && window.__endless81.stats && window.__endless81.stats()"))

        ids = pg.evaluate("() => allIcons().map(i => i.id)")
        check("icon set includes kraft, beckham, squarzi", set(["kraft", "beckham", "squarzi"]).issubset(set(ids)), ids)
        check("icon set does not include Skarsgård", not any("skars" in i for i in ids), ids)

        def mid_weights():
            return pg.evaluate("""() => {
              const mid = {};
              allIcons().forEach(ic => mid[ic.id] = 2);
              const by = { casual: Object.assign({}, mid), smart: Object.assign({}, mid), business: Object.assign({}, mid), formal: Object.assign({}, mid) };
              return { mode: 'per', all: mid, byLevel: by };
            }""")

        def seeded_weights():
            return pg.evaluate("""() => {
              const mid = {};
              allIcons().forEach(ic => mid[ic.id] = 2);
              const by = { casual: Object.assign({}, mid), smart: Object.assign({}, mid), business: Object.assign({}, mid), formal: Object.assign({}, mid) };
              by.casual.squarzi = 8;
              by.business.kraft = 8; by.business.beckham = 8;
              by.formal.kraft = 8; by.formal.beckham = 8;
              return { mode: 'per', all: mid, byLevel: by };
            }""")

        def measure(feed, level, weights, n=80, lens=None):
            return pg.evaluate(
                """async ({feed, level, weights, n, lens}) => {
                  const m = await window.endlessMeasure81({ feed, level, weights, n, lens });
                  return m;
                }""",
                {"feed": feed, "level": level, "weights": weights, "n": n, "lens": lens},
            )

        if ready:
            uniform = mid_weights()
            seeded = seeded_weights()
            # confirm defaults match seeded
            pg.evaluate("w => window.iconWeights81.setState(w)", seeded)
            st = pg.evaluate("() => window.iconWeights81.weightsForLevel(3)")
            check("casual default seeds Squarzi high", st.get("squarzi") == 8, st)
            stf = pg.evaluate("() => window.iconWeights81.weightsForLevel(6)")
            check("formal default seeds Kraft and Beckham high", stf.get("kraft") == 8 and stf.get("beckham") == 8, stf)

            results = {}
            for label, wts in (("before", uniform), ("after", seeded)):
                results[label] = {}
                for feed in ("mine", "withmine", "allnew"):
                    results[label][feed] = {}
                    for level, key in ((3, "casual"), (6, "formal")):
                        try:
                            m = measure(feed, level, wts, 80, lens=None)
                            rows = m.get("looks") or []
                            results[label][feed][key] = {
                                "n": len(rows),
                                "squarzi_top": pct(rows, lambda r: r.get("top") == "squarzi"),
                                "kraft_beckham_top": pct(rows, lambda r: r.get("top") in ("kraft", "beckham")),
                                "icon_src": pct(rows, lambda r: (r.get("src") or {}).get("t") == "icon"),
                                "icon_src_squarzi": pct(rows, lambda r: (r.get("src") or {}).get("id") == "squarzi"),
                                "icon_src_kraft_beckham": pct(rows, lambda r: (r.get("src") or {}).get("id") in ("kraft", "beckham")),
                                "ms": m.get("ms"),
                            }
                        except Exception as e:
                            results[label][feed][key] = {"error": str(e)}
                            check("measure %s %s %s" % (label, feed, key), False, e)

            MEASURE.update(results)
            print("MEASURE", json.dumps(results, indent=2))

            after_c_new = results.get("after", {}).get("allnew", {}).get("casual", {})
            after_f_new = results.get("after", {}).get("allnew", {}).get("formal", {})
            before_c_new = results.get("before", {}).get("allnew", {}).get("casual", {})
            after_c_mine = results.get("after", {}).get("mine", {}).get("casual", {})
            after_f_mine = results.get("after", {}).get("mine", {}).get("formal", {})
            before_c_mine = results.get("before", {}).get("mine", {}).get("casual", {})
            before_f_mine = results.get("before", {}).get("mine", {}).get("formal", {})
            before_f_new = results.get("before", {}).get("allnew", {}).get("formal", {})

            # weights shift the icon mix on New
            if after_c_new.get("n") and after_f_new.get("n"):
                check(
                    "casual New favours Squarzi-seeded looks vs formal",
                    after_c_new.get("icon_src_squarzi", 0) > after_f_new.get("icon_src_squarzi", 0)
                    or after_c_new.get("squarzi_top", 0) > after_f_new.get("squarzi_top", 0),
                    {"casual": after_c_new, "formal": after_f_new},
                )
                check(
                    "formal New favours Kraft/Beckham-seeded looks vs casual",
                    after_f_new.get("icon_src_kraft_beckham", 0) > after_c_new.get("icon_src_kraft_beckham", 0)
                    or after_f_new.get("kraft_beckham_top", 0) > after_c_new.get("kraft_beckham_top", 0),
                    {"casual": after_c_new, "formal": after_f_new},
                )
                check(
                    "weights shift New icon mix vs uniform",
                    after_c_new.get("squarzi_top", 0) >= before_c_new.get("squarzi_top", 0)
                    or after_c_new.get("icon_src_squarzi", 0) > before_c_new.get("icon_src_squarzi", 0),
                    {"before": before_c_new, "after": after_c_new},
                )
            after_c_mix = results.get("after", {}).get("withmine", {}).get("casual", {})
            after_f_mix = results.get("after", {}).get("withmine", {}).get("formal", {})
            before_c_mix = results.get("before", {}).get("withmine", {}).get("casual", {})
            if after_c_mix.get("n") and after_f_mix.get("n"):
                check(
                    "Mix icon-seeded share rises when top weights are high",
                    after_c_mix.get("icon_src", 0) >= 35 or after_c_mix.get("icon_src", 0) > before_c_mix.get("icon_src", 0) + 10,
                    {"before": before_c_mix, "after": after_c_mix, "formal_after": after_f_mix},
                )
                check(
                    "casual Mix favours Squarzi vs formal / formal favours Kraft-Beckham",
                    after_c_mix.get("icon_src_squarzi", 0) > after_f_mix.get("icon_src_squarzi", 0)
                    or after_f_mix.get("icon_src_kraft_beckham", 0) > after_c_mix.get("icon_src_kraft_beckham", 0)
                    or after_c_mix.get("squarzi_top", 0) > after_f_mix.get("squarzi_top", 0),
                    {"casual": after_c_mix, "formal": after_f_mix},
                )

            # Mine re-rank: top lens should lean after weights
            if after_c_mine.get("n") and after_f_mine.get("n"):
                check(
                    "casual Mine top-lens share for Squarzi rises or beats formal",
                    after_c_mine.get("squarzi_top", 0) >= before_c_mine.get("squarzi_top", 0)
                    or after_c_mine.get("squarzi_top", 0) > after_f_mine.get("squarzi_top", 0),
                    {"before": before_c_mine, "after": after_c_mine, "formal_after": after_f_mine},
                )
                check(
                    "formal Mine top-lens share for Kraft/Beckham rises or beats casual",
                    after_f_mine.get("kraft_beckham_top", 0) >= before_f_mine.get("kraft_beckham_top", 0)
                    or after_f_mine.get("kraft_beckham_top", 0) > after_c_mine.get("kraft_beckham_top", 0),
                    {"before": before_f_mine, "after": after_f_mine, "casual_after": after_c_mine},
                )

            # Seeded looks score via lens: a New look with icon src should have a numeric lens score for that icon
            try:
                m = measure("allnew", 3, seeded, 40, lens=None)
                lensy = [r for r in (m.get("looks") or []) if (r.get("src") or {}).get("t") == "icon"]
                ok_lens = False
                if lensy:
                    ok_lens = all(isinstance((r.get("scores") or {}).get((r.get("src") or {}).get("id")), (int, float)) for r in lensy)
                check("icon-seeded New looks are scored via full lens data", ok_lens and len(lensy) > 0, {"n_icon": len(lensy), "sample": lensy[:2]})
            except Exception as e:
                check("icon-seeded New looks are scored via full lens data", False, e)

            # Single icon override still wins: force kraft lens at casual should not pick squarzi as src
            try:
                kraft_lens = pg.evaluate("() => window.iconLensOf(allIcons().filter(i => i.id==='kraft')[0])")
                m = measure("allnew", 3, seeded, 40, lens=kraft_lens)
                srcs = [(r.get("src") or {}).get("id") for r in (m.get("looks") or []) if (r.get("src") or {}).get("t") == "icon"]
                check("Looks filter single-icon override still wins (Kraft at casual)", bool(srcs) and all(s == "kraft" for s in srcs), srcs[:12])
            except Exception as e:
                check("Looks filter single-icon override still wins (Kraft at casual)", False, e)

            # The Edit / Shop the look ranker
            shop = pg.evaluate(
                """() => {
                  if (typeof catalogueScored !== 'function') return { error: 'no catalogueScored' };
                  const pc = { garment: 'Navy double-breasted blazer', detail: 'wool flannel', hex: '#1f2a44' };
                  const mid = {}; allIcons().forEach(ic => mid[ic.id] = 2);
                  const uniform = { mode: 'per', all: mid, byLevel: { casual: Object.assign({}, mid), smart: Object.assign({}, mid), business: Object.assign({}, mid), formal: Object.assign({}, mid) } };
                  const seeded = JSON.parse(JSON.stringify(uniform));
                  seeded.byLevel.casual.squarzi = 8;
                  seeded.byLevel.formal.kraft = 8; seeded.byLevel.formal.beckham = 8;
                  function run(level, w) {
                    const prev = formalityLevel;
                    formalityLevel = level;
                    window.iconWeights81.setState(w);
                    const scored = catalogueScored(pc, false).slice(0, 12);
                    formalityLevel = prev;
                    return scored.map(s => ({ name: s.e.name, brand: s.e.brand, score: Math.round(s.score*100)/100, url: s.e.url }));
                  }
                  return {
                    before_casual: run(3, uniform),
                    before_formal: run(6, uniform),
                    after_casual: run(3, seeded),
                    after_formal: run(6, seeded)
                  };
                }"""
            )
            MEASURE["shop"] = shop
            if shop.get("error"):
                check("Shop the look ranker exists", False, shop)
            else:
                def mean(rows):
                    return (sum(r["score"] for r in rows) / len(rows)) if rows else 0
                def dressy_share(rows):
                    if not rows:
                        return 0
                    hits = sum(1 for r in rows if any(k in (r.get("name") or "").lower() for k in ("double-breasted", "suit", "blazer", "loafer", "trouser", "wool")))
                    return hits / len(rows)
                bf, af = shop.get("before_formal") or [], shop.get("after_formal") or []
                bc, ac = shop.get("before_casual") or [], shop.get("after_casual") or []
                check("Shop the look returns ranked products", len(bf) + len(af) + len(bc) + len(ac) > 0, {k: len(shop.get(k) or []) for k in shop})
                # Formal weights should change the ranking or lift scores vs uniform
                shift = False
                if af and bf:
                    names_before = [r["name"] for r in bf]
                    names_after = [r["name"] for r in af]
                    shift = names_before != names_after or mean(af) != mean(bf)
                if ac and bc:
                    shift = shift or [r["name"] for r in ac] != [r["name"] for r in bc] or mean(ac) != mean(bc)
                # even if names stay, scores should move when lens bonus applies
                # After weights, Casual vs Formal must actually change the top 12
                if ac and af:
                    shift = shift or [r["name"] for r in ac] != [r["name"] for r in af]
                check("The Edit / Shop the look recommendations shift with weights", shift, {
                    "before_formal_top": (bf[:3] if bf else []),
                    "after_formal_top": (af[:3] if af else []),
                    "before_casual_top": (bc[:3] if bc else []),
                    "after_casual_top": (ac[:3] if ac else []),
                    "mean_formal": [mean(bf), mean(af)],
                    "mean_casual": [mean(bc), mean(ac)],
                })
                MEASURE["shop_means"] = {
                    "before_casual": round(mean(bc), 3),
                    "after_casual": round(mean(ac), 3),
                    "before_formal": round(mean(bf), 3),
                    "after_formal": round(mean(af), 3),
                }

            # Rules override: a veto must drop the piece from shop scoring
            veto = pg.evaluate(
                """() => {
                  const pc = { garment: 'Navy double-breasted blazer', detail: 'wool flannel', hex: '#1f2a44' };
                  const before = catalogueScored(pc, false).length;
                  const orig = window.wardrobeRulesAllow;
                  window.wardrobeRulesAllow = function () { return false; };
                  const after = catalogueScored(pc, false).length;
                  window.wardrobeRulesAllow = orig;
                  return { before, after };
                }"""
            )
            check("Wardrobe Rules override weightings (shop veto)", veto.get("before", 0) > 0 and veto.get("after") == 0, veto)

        page_errors = [e for e in errors if "ResizeObserver" not in e]
        check("no page errors", page_errors == [], page_errors[:5])
        browser.close()
    httpd.shutdown()

    (SHOTS / "measurement.json").write_text(json.dumps(MEASURE, indent=2))
    if fails:
        print("FAILED", len(fails), ":", ", ".join(fails))
        return 1
    print("ALL PASSED")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    sys.exit(main())
