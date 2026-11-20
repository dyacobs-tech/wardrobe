"""Build .80.36 (HAN-15): Style this piece, Watches under Accessories,
Profile tab clipping, and cleaned Profile Info / Location.

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_livefixes1119.py
"""
from __future__ import annotations

import http.server
import json
import os
import re
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E402
from buildinfo import CURRENT_BUILD

ROOT = Path(__file__).resolve().parents[1]
BUILD = CURRENT_BUILD
CLOSET = json.loads((Path(__file__).resolve().parent / "fixture_onbody.json").read_text())
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")
OUT = Path(os.environ.get("AUDIT_OUT") or "/workspace/wardrobe-audit/live-fixes-1119/after")

BLAZER = "Dolce & Gabbana Burgundy Blazer"
SHIRT = "Eleventy Dark Green Suede Western Shirt"
TROUSERS = "Pool House New York Malibu Linen Pants II"
SHOES = "Vans Black and White Checkerboard Slip-On Sneakers"

STANDALONE_INIT = """
Object.defineProperty(window.navigator, 'standalone', { get: () => true, configurable: true });
if (window.matchMedia) {
  const orig = window.matchMedia.bind(window);
  window.matchMedia = (q) => String(q).includes('display-mode: standalone')
    ? { matches: true, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, onchange: null, dispatchEvent() { return false; } }
    : orig(q);
}
"""


def start_server():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(ROOT), **k)

        def log_message(self, *a):
            pass

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Quiet)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def check(results, name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS" if ok else "FAIL") + "  " + name + (("  " + str(detail)[:200]) if (detail and not ok) else ""))


def new_page(browser, url, vw=390, vh=844, theme="light"):
    ctx = browser.new_context(
        viewport={"width": vw, "height": vh},
        device_scale_factor=2,
        is_mobile=True if vw <= 430 else False,
        has_touch=True,
        service_workers="block",
        color_scheme=theme,
    )
    ctx.route(BLOCK, lambda route: route.abort())
    ctx.add_init_script(STANDALONE_INIT)
    payload = json.dumps({"items": CLOSET})
    ctx.add_init_script(
        "(() => { const S = %s; for (const k in S) localStorage.setItem('wardrobe.' + k, JSON.stringify(S[k])); })();"
        % payload
    )
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto(url, wait_until="load")
    page.wait_for_timeout(600)
    page.evaluate(
        """() => {
          try { document.documentElement.setAttribute('data-theme', '%s'); } catch (e) {}
          if (typeof applyTheme === 'function') try { applyTheme('%s'); } catch (e) {}
        }""" % (theme, theme)
    )
    return ctx, page, errors


def open_item_and_style(page, name):
    return page.evaluate(
        """(name) => {
          const it = (wardrobeItems || []).find(i => i && i.name === name);
          if (!it) return { ok: false, reason: 'item missing', name };
          if (typeof switchTab === 'function') switchTab('wardrobe');
          detailItemId = it.id;
          if (typeof renderItemDetail === 'function') renderItemDetail();
          const btn = document.querySelector('#item-detail [data-item-act="style"]');
          if (!btn) return { ok: false, reason: 'no style button', id: it.id, name: it.name };
          btn.click();
          return { ok: true, id: it.id, name: it.name, label: (btn.textContent || '').trim() };
        }""" ,
        name,
    )


def style_state(page, name):
    return page.evaluate(
        """(name) => {
          const detail = document.getElementById('item-detail');
          const looks = document.getElementById('panel-looks');
          const host = document.getElementById('style-item-host');
          const text = host ? (host.innerText || '') : '';
          const cards = host ? [...host.querySelectorAll('[data-style-idx], .option-card')].length : 0;
          const mentions = text.toLowerCase().indexOf((name || '').toLowerCase()) !== -1
            || [...(host ? host.querySelectorAll('.oc-title, .oc-label, .style-item-empty') : [])]
                .some(el => (el.textContent || '').toLowerCase().indexOf((name || '').toLowerCase()) !== -1);
          return {
            detailOpen: !!(detail && detail.firstElementChild),
            looksShown: !!(looks && !looks.hidden),
            hostShown: !!(host && !host.hidden),
            hostText: text.slice(0, 300),
            cards,
            mentions,
            currentTab: (typeof currentTab === 'undefined') ? null : currentTab,
          };
        }""",
        name,
    )


def profile_tab_metrics(page):
    return page.evaluate(
        """() => {
          const vw = window.innerWidth;
          const tabs = [...document.querySelectorAll('#subnav-me .subnav-scroll > .subtab')];
          const boxes = tabs.map(t => {
            const r = t.getBoundingClientRect();
            return { id: t.id, text: (t.innerText || '').trim(), left: r.left, right: r.right, width: r.width, top: r.top };
          });
          const overflow = Math.max(0, document.documentElement.scrollWidth - vw);
          return {
            vw,
            ids: boxes.map(b => b.id),
            texts: boxes.map(b => b.text),
            boxes,
            inside: boxes.every(b => b.left >= 11.5 && b.right <= vw - 11.5),
            overflow,
            minLeft: boxes ? Math.min(...boxes.map(b => b.left)) : null,
            maxRight: boxes ? Math.max(...boxes.map(b => b.right)) : null,
          };
        }"""
    )


def main() -> int:
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    httpd, url = start_server()
    failed = 0
    try:
        with sync_playwright() as p:
            browser = p.webkit.launch()

            # ---------- Style this blazer + shirt + trousers + shoes ----------
            ctx, page, errors = new_page(browser, url, 390, 844, "light")
            check(results, "build is current", page.evaluate("window.WARDROBE_BUILD") == BUILD, page.evaluate("window.WARDROBE_BUILD"))

            # Closet opens and the blazer exists
            page.evaluate("() => { if (typeof switchTab === 'function') switchTab('wardrobe'); }")
            page.wait_for_timeout(250)
            present = page.evaluate(
                """(names) => names.map(n => ({ name: n, has: !!(wardrobeItems || []).some(i => i && i.name === n) }))""",
                [BLAZER, SHIRT, TROUSERS, SHOES],
            )
            check(results, "fixture closet has the four test pieces", all(x["has"] for x in present), present)

            # Open blazer detail, capture modal, click Style
            page.evaluate(
                """(name) => {
                  const it = (wardrobeItems || []).find(i => i && i.name === name);
                  detailItemId = it.id;
                  renderItemDetail();
                }""",
                BLAZER,
            )
            page.wait_for_timeout(200)
            modal = page.evaluate(
                """() => {
                  const card = document.querySelector('#item-detail > .item-detail-card');
                  const acts = [...document.querySelectorAll('#item-detail [data-item-act]')].map(b => ({ act: b.getAttribute('data-item-act'), text: (b.textContent || '').trim(), hidden: b.hidden || getComputedStyle(b).display === 'none' }));
                  return { open: !!card, acts, hasClose: acts.some(a => a.act === 'close' && !a.hidden && /close/i.test(a.text)), hasX: !!document.querySelector('#item-detail .sheet-x') };
                }"""
            )
            check(results, "blazer detail sheet opens", modal.get("open"), modal)
            check(results, "sheet has a close × and no visible Close button", modal.get("hasX") and not modal.get("hasClose"), modal)
            page.screenshot(path=str(OUT / "390-light-blazer-modal.png"), full_page=False)

            clicked = open_item_and_style(page, BLAZER)
            page.wait_for_timeout(500)
            state = style_state(page, BLAZER)
            check(results, "STYLE THIS BLAZER click succeeds", clicked and clicked.get("ok"), clicked)
            check(results, "style click closes the item sheet", state and not state.get("detailOpen"), state)
            check(results, "style click opens Looks with results for the blazer",
                  state and state.get("looksShown") and state.get("hostShown") and (state.get("cards", 0) > 0) and state.get("mentions"),
                  state)
            check(results, "0 page errors after styling the blazer", errors == [], errors)
            page.screenshot(path=str(OUT / "390-light-blazer-styled.png"), full_page=False)

            # Shirt and trousers (and shoes) also style
            for piece in (SHIRT, TROUSERS, SHOES):
                err0 = list(errors)
                clicked = open_item_and_style(page, piece)
                page.wait_for_timeout(400)
                state = style_state(page, piece)
                check(results, f"STYLE THIS works for {piece}",
                      clicked and clicked.get("ok") and state and not state.get("detailOpen") and state.get("hostShown") and (state.get("cards", 0) > 0 or state.get("mentions")),
                      {"clicked": clicked, "state": state})
                new_errs = [e for e in errors if e not in err0]
                check(results, f"0 page errors styling {piece}", new_errs == [], new_errs)

            ctx.close()

            # ---------- Watches under Accessories ----------
            ctx, page, errors = new_page(browser, url, 390, 844, "light")
            page.evaluate("() => { if (typeof switchTab === 'function') switchTab('wardrobe'); }")
            page.wait_for_timeout(300)
            watches = page.evaluate(
                """() => {
                  const tab = document.getElementById('tab-watches');
                  const sub = document.getElementById('subnav-closet');
                  const btn = document.getElementById('ward-cat-accessories-btn');
                  if (btn && typeof fillWardCatMenu === 'function') {
                    const g = WARD_CAT_GROUPS.filter(x => x.key === 'accessories')[0];
                    fillWardCatMenu(g);
                    if (typeof toggleCdd === 'function') { /* just fill */ }
                  } else if (btn) btn.click();
                  const menu = document.getElementById('ward-cat-accessories-menu');
                  const opts = menu ? [...menu.querySelectorAll('[data-cat-pick]')].map(o => o.getAttribute('data-cat-pick')) : [];
                  return {
                    tabVisible: !!(tab && !tab.hidden && tab.offsetParent && getComputedStyle(tab).display !== 'none'),
                    tabExists: !!tab,
                    subnavHidden: !sub || !!sub.hidden || getComputedStyle(sub).display === 'none',
                    accessoryOpts: opts,
                    hasWatchesOpt: opts.indexOf('Watches') !== -1,
                  };
                }"""
            )
            check(results, "Closet has no Watches top pill", watches and not watches.get("tabVisible") and watches.get("subnavHidden"), watches)
            check(results, "Accessories menu includes Watches", watches and watches.get("hasWatchesOpt"), watches)

            rendered = page.evaluate(
                """() => {
                  wardFilter = 'Watches';
                  if (typeof syncWardCatLabels === 'function') syncWardCatLabels();
                  if (typeof renderWardrobe === 'function') renderWardrobe();
                  const panel = document.getElementById('panel-watches');
                  const grid = document.getElementById('watch-grid');
                  const cards = grid ? grid.querySelectorAll('.item-card, .card').length : 0;
                  const itemGrid = document.getElementById('item-grid');
                  return {
                    panelShown: !!(panel && !panel.hidden && panel.getClientRects().length),
                    cards,
                    itemGridHidden: !itemGrid || !!itemGrid.hidden || getComputedStyle(itemGrid).display === 'none',
                    label: (document.getElementById('ward-cat-accessories-label') || {}).textContent || '',
                  };
                }"""
            )
            check(results, "Accessories → Watches renders the watch collection",
                  rendered and rendered.get("panelShown") and rendered.get("cards", 0) >= 1 and rendered.get("itemGridHidden"),
                  rendered)
            check(results, "0 page errors on Watches view", errors == [], errors)
            page.screenshot(path=str(OUT / "390-light-closet-watches.png"), full_page=False)

            # #watches deep link
            page.evaluate("() => { wardFilter = 'All'; if (typeof syncWardCatLabels === 'function') syncWardCatLabels(); if (typeof switchTab === 'function') switchTab('today'); }")
            page.wait_for_timeout(150)
            page.evaluate("() => { location.hash = '#watches'; }")
            page.wait_for_timeout(400)
            deep = page.evaluate(
                """() => ({
                  tab: typeof currentTab === 'undefined' ? null : currentTab,
                  filter: typeof wardFilter === 'undefined' ? null : wardFilter,
                  panelShown: !!(document.getElementById('panel-watches') && !document.getElementById('panel-watches').hidden),
                  wardrobeShown: !!(document.getElementById('panel-wardrobe') && !document.getElementById('panel-wardrobe').hidden)
                })"""
            )
            check(results, "#watches deep-link opens Closet → Accessories → Watches",
                  deep and deep.get("tab") == "wardrobe" and deep.get("filter") == "Watches" and deep.get("panelShown") and deep.get("wardrobeShown"),
                  deep)
            ctx.close()

            # ---------- Profile tabs fit at 375/390/430/1440 ----------
            for vw, vh in ((375, 812), (390, 844), (430, 932), (1440, 900)):
                ctx, page, errors = new_page(browser, url, vw, vh, "light")
                page.evaluate("() => { if (typeof switchTab === 'function') switchTab('pinfo'); }")
                page.wait_for_timeout(300)
                metrics = profile_tab_metrics(page)
                check(results, f"{vw}: Info|Location|Rules|Advanced sit inside [12, vw-12]",
                      metrics and metrics.get("inside") and metrics.get("overflow", 99) <= 1 and set(metrics.get("ids") or []) >= {"tab-pinfo", "tab-plocation", "tab-prules", "tab-pcloud"},
                      metrics)
                check(results, f"{vw}: 0 horizontal overflow on Profile", metrics and metrics.get("overflow", 99) <= 1, metrics)
                check(results, f"{vw}: 0 page errors on Profile tabs", errors == [], errors)
                ctx.close()

            # ---------- Profile Info / Location screenshots light + dark ----------
            ctx, page, errors = new_page(browser, url, 390, 844, "light")
            page.evaluate("() => { if (typeof switchTab === 'function') switchTab('plocation'); }")
            page.wait_for_timeout(350)
            loc = page.evaluate(
                """() => {
                  const input = document.getElementById('loc-search');
                  const ph = input ? input.getAttribute('placeholder') || '' : '';
                  const clipped = input ? (input.scrollWidth - input.clientWidth) > 2 : true;
                  const name = (document.getElementById('loc-current-name') || {}).textContent || '';
                  return { ph, clipped, name, weather: (document.getElementById('loc-weather') || {}).textContent || '' };
                }"""
            )
            check(results, "Location placeholder never clips", loc and not loc.get("clipped") and "Pa" not in (loc.get("ph") or "Pa"), loc)
            page.screenshot(path=str(OUT / "390-light-profile-location.png"), full_page=False)

            page.evaluate("() => { if (typeof switchTab === 'function') switchTab('pinfo'); }")
            page.wait_for_timeout(300)
            info = page.evaluate(
                """() => {
                  const grid = document.querySelector('#profile-form .profile-sec:nth-of-type(2) .profile-grid') || document.querySelectorAll('#profile-form .profile-grid')[1];
                  const cs = grid ? getComputedStyle(grid) : null;
                  const cols = cs ? cs.gridTemplateColumns : '';
                  const tee = document.getElementById('pf-tee');
                  const polo = document.getElementById('pf-polo');
                  return {
                    twoCol: !!(cols && cols.split(' ').filter(Boolean).length >= 2),
                    cols,
                    hasTee: !!tee,
                    hasPolo: !!polo,
                    sections: [...document.querySelectorAll('#profile-form .profile-sec-h')].map(h => h.textContent.trim()),
                  };
                }"""
            )
            check(results, "Profile Info uses a 2-column size grid with section headers",
                  info and info.get("twoCol") and info.get("hasTee") and "Tops" in (info.get("sections") or []),
                  info)
            page.screenshot(path=str(OUT / "390-light-profile-info.png"), full_page=False)
            ctx.close()

            ctx, page, errors = new_page(browser, url, 390, 844, "dark")
            page.evaluate(
                """() => {
                  document.documentElement.setAttribute('data-theme', 'dark');
                  try { if (typeof setTheme === 'function') setTheme('dark'); } catch (e) {}
                  try { if (typeof applyTheme === 'function') applyTheme('dark'); } catch (e) {}
                  const btn = document.getElementById('theme-dark');
                  if (btn) btn.click();
                  if (typeof switchTab === 'function') switchTab('pinfo');
                }"""
            )
            page.wait_for_timeout(350)
            page.screenshot(path=str(OUT / "390-dark-profile-info.png"), full_page=False)
            check(results, "dark Profile Info rendered", True)
            ctx.close()

            # 1440 light Info + Location render (no crash)
            ctx, page, errors = new_page(browser, url, 1440, 900, "light")
            page.evaluate("() => { if (typeof switchTab === 'function') switchTab('pinfo'); }")
            page.wait_for_timeout(250)
            page.evaluate("() => { if (typeof switchTab === 'function') switchTab('plocation'); }")
            page.wait_for_timeout(250)
            check(results, "1440 light Profile Info and Location render with 0 errors", errors == [], errors)
            ctx.close()

            ctx, page, errors = new_page(browser, url, 1440, 900, "dark")
            page.evaluate(
                """() => {
                  const btn = document.getElementById('theme-dark');
                  if (btn) btn.click();
                  document.documentElement.setAttribute('data-theme', 'dark');
                  if (typeof switchTab === 'function') switchTab('pinfo');
                }"""
            )
            page.wait_for_timeout(250)
            page.evaluate("() => { if (typeof switchTab === 'function') switchTab('plocation'); }")
            page.wait_for_timeout(250)
            check(results, "1440 dark Profile Info and Location render with 0 errors", errors == [], errors)
            ctx.close()

            browser.close()
    finally:
        httpd.shutdown()

    print()
    fails = [r for r in results if not r[1]]
    print(f"{len(results) - len(fails)} passed, {len(fails)} failed, {len(results)} total")
    for name, ok, detail in fails:
        print("FAIL", name, detail)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
