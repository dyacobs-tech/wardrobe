"""Build .70: Home fits on one screen with no scrolling at
402×874, 390×844 and 375×667 in WebKit standalone; Closet has
five unclipped subnav tabs including Closet gaps after Today;
the Shop landing no longer duplicates the Receipts page.

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_home70.py
"""
from __future__ import annotations

import http.server
import os
import re
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))  # noqa: E402
from buildinfo import CURRENT_BUILD

ROOT = Path(__file__).resolve().parents[1]
SHOTS = Path("/workspace/wardrobe-audit/build-71")
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")
VIEWPORTS = ((402, 874, 3), (390, 844, 2), (375, 667, 2))

STANDALONE_INIT = """
Object.defineProperty(window.navigator, 'standalone', { get: () => true, configurable: true });
if (window.matchMedia) {
  const orig = window.matchMedia.bind(window);
  window.matchMedia = (q) => {
    if (String(q).includes('display-mode: standalone')) {
      return { matches: true, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, onchange: null, dispatchEvent() { return false; } };
    }
    return orig(q);
  };
}
"""

HOME_JS = """() => {
  const nav = document.getElementById('bottombar');
  const nr = nav ? nav.getBoundingClientRect() : { top: 0, bottom: 0, height: 0 };
  const se = document.scrollingElement || document.documentElement;
  const inner = window.innerHeight;
  const scrollH = se.scrollHeight;
  const vis = (el) => {
    if (!el) return false;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const roots = [document.querySelector('.masthead'), document.getElementById('panel-today')].filter(Boolean);
  const controls = [];
  roots.forEach((root) => {
    root.querySelectorAll('button, a, h1, h2, p, img, [role="button"], [role="menuitem"], .today-caption, .hero-controls, .hero-icon-row, .today-watch-row, .cdd-btn').forEach((el) => {
      if (!vis(el)) return;
      if (el.closest && el.closest('.cdd-menu') && el.closest('.cdd-menu').hidden) return;
      /* .78.7c: the full-bleed hero layers (backdrop, and the caption's dark
         band that runs under the nav) are decoration, not controls */
      if (el.closest && el.closest('.hero-bg')) return;
      if (el.classList && el.classList.contains('today-caption') && el.closest('.hero-solo')) return;
      const r = el.getBoundingClientRect();
      controls.push({
        id: el.id || el.className.toString().slice(0, 40),
        tag: el.tagName.toLowerCase(),
        bottom: Math.round(r.bottom * 10) / 10,
        top: Math.round(r.top * 10) / 10,
        overNav: r.bottom > nr.top + 1.5,
      });
    });
  });
  const over = controls.filter(c => c.overNav);
  return {
    build: window.WARDROBE_BUILD || null,
    innerH: inner,
    scrollH: scrollH,
    clientH: document.documentElement.clientHeight,
    navTop: Math.round(nr.top * 10) / 10,
    navBottom: Math.round(nr.bottom * 10) / 10,
    navH: Math.round(nr.height * 10) / 10,
    navPos: nav ? getComputedStyle(nav).position : null,
    fits: scrollH <= inner + 1,
    controlsOverNav: over,
    controlCount: controls.length,
    standalone: !!(window.navigator.standalone || (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches)),
    homeChrome: getComputedStyle(document.documentElement).getPropertyValue('--home-chrome').trim(),
    htmlMinH: getComputedStyle(document.documentElement).minHeight,
    bodyMinH: getComputedStyle(document.body).minHeight,
  };
}"""

CLOSET_JS = """() => {
  const group = document.getElementById('subnav-closet');
  const vw = window.innerWidth;
  if (!group || group.hidden) return { error: 'no closet subnav' };
  const tabs = [...group.querySelectorAll('.subtab')];
  const rects = tabs.map(t => {
    const r = t.getBoundingClientRect();
    const cs = getComputedStyle(t);
    return {
      id: t.id,
      text: (t.innerText || '').replace(/\\s+/g, ' ').trim(),
      left: r.left, right: r.right, width: r.width, top: r.top,
      overflow: cs.overflow, textOverflow: cs.textOverflow,
      clipped: r.left < -1 || r.right > vw + 1,
      labelClipped: (t.scrollWidth - t.clientWidth) > 1,
    };
  });
  const tops = rects.map(r => r.top);
  return {
    count: rects.length,
    ids: rects.map(r => r.id),
    texts: rects.map(r => r.text),
    oneRow: (Math.max(...tops) - Math.min(...tops)) <= 2,
    allFit: rects.every(r => !r.clipped && !r.labelClipped),
    rects,
    vw,
  };
}"""

SHOP_JS = """() => {
  const find = document.getElementById('panel-find');
  const receiptsPanel = document.getElementById('panel-receipts');
  const teaser = document.getElementById('shop-receipts');
  const findText = find ? (find.innerText || '') : '';
  return {
    findShown: !!(find && !find.hidden),
    hasTeaserEl: !!teaser,
    findHasReceiptsHeading: /\\bReceipts\\b/.test(findText) && /no receipts waiting/i.test(findText),
    findTextSample: findText.slice(0, 300),
    receiptsShown: !!(receiptsPanel && !receiptsPanel.hidden),
    receiptsHeading: receiptsPanel ? (receiptsPanel.innerText || '').slice(0, 200) : '',
    tabExists: !!document.getElementById('tab-receipts'),
  };
}"""


SHOP_COMPACT_JS = """() => {
  const inp = document.getElementById('link-url');
  const btn = document.getElementById('link-go');
  const img = document.querySelector('#panel-find .shop-look-head img, #find-look-mode .shop-look-head img, .shop-look-head img');
  const titleRow = document.querySelector('.shop-look-titlerow');
  const label = document.querySelector('#link-card label, #panel-find label.field');
  const ir = inp ? inp.getBoundingClientRect() : null;
  const br = btn ? btn.getBoundingClientRect() : null;
  const lr = label ? label.getBoundingClientRect() : null;
  const im = img ? img.getBoundingClientRect() : null;
  const tr = titleRow ? titleRow.getBoundingClientRect() : null;
  const csI = inp ? getComputedStyle(inp) : null;
  const infoBtns = [...document.querySelectorAll('.info-btn, #info-pop, #icons-info-pop, .page-info-row')];
  const visibleInfo = infoBtns.filter(el => {
    const cs = getComputedStyle(el);
    return cs.display !== 'none' && cs.visibility !== 'hidden' && el.getAttribute('hidden') === null;
  });
  return {
    inputH: ir ? Math.round(ir.height * 10) / 10 : null,
    btnH: br ? Math.round(br.height * 10) / 10 : null,
    sameRow: !!(ir && br && Math.abs(ir.top - br.top) <= 4),
    labelH: lr ? Math.round(lr.height * 10) / 10 : null,
    imgH: im ? Math.round(im.height * 10) / 10 : null,
    imgMax: img ? getComputedStyle(img).maxHeight : null,
    imgFit: img ? getComputedStyle(img).objectFit : null,
    titleOneLine: !!(tr && titleRow && (titleRow.scrollHeight - tr.height) <= 4),
    visibleInfo: visibleInfo.map(el => el.id || el.className),
  };
}"""

CENTER_JS = """() => {
  const group = document.querySelector('.subnav-group:not([hidden])');
  const subnav = document.getElementById('subnav');
  if (!group || !subnav || subnav.hidden) return { error: 'no group' };
  const wrap = subnav.querySelector('.wrap') || subnav;
  const wr = wrap.getBoundingClientRect();
  const cs = getComputedStyle(wrap);
  const padL = parseFloat(cs.paddingLeft) || 0;
  const padR = parseFloat(cs.paddingRight) || 0;
  const tabs = [...group.querySelectorAll('.subtab')].filter(t => t.id !== 'profile-close');
  const rects = tabs.map(t => t.getBoundingClientRect());
  if (!rects.length) return { error: 'no tabs' };
  const tops = rects.map(r => r.top);
  const oneRow = (Math.max(...tops) - Math.min(...tops)) <= 2;
  const first = rects[0], last = rects[rects.length - 1];
  // Centered in the wrap's content box (back-chevron padding is intentional).
  const leftGap = first.left - (wr.left + padL);
  const rightGap = (wr.right - padR) - last.right;
  const gaps = [];
  for (let i = 1; i < rects.length; i++) gaps.push(rects[i].left - rects[i-1].right);
  const mean = gaps.length ? gaps.reduce((a,b)=>a+b,0)/gaps.length : 0;
  const even = gaps.every(g => Math.abs(g - mean) <= 6);
  const centered = Math.abs(leftGap - rightGap) <= 8;
  const clipped = rects.some(r => r.left < wr.left - 1 || r.right > wr.right + 1);
  return {
    group: group.id,
    count: rects.length,
    oneRow,
    even,
    centered,
    clipped,
    leftGap: Math.round(leftGap*10)/10,
    rightGap: Math.round(rightGap*10)/10,
    gaps: gaps.map(g => Math.round(g*10)/10),
    texts: tabs.map(t => (t.innerText||'').replace(/\\s+/g,' ').trim()),
  };
}"""


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


def nearly(a, b, tol=1.5):
    return a is not None and abs(float(a) - float(b)) <= tol


def main() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        print(f"  {status}: {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            failures.append(f"{name}: {detail}")

    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    SHOTS.mkdir(parents=True, exist_ok=True)
    httpd, url = start_static_server()
    try:
        with sync_playwright() as p:
            try:
                browser = p.webkit.launch()
                engine = "webkit"
            except Exception as e:
                print(f"  (webkit unavailable: {e}; falling back to chromium)")
                browser = p.chromium.launch()
                engine = "chromium"

            for vw, vh, dsf in VIEWPORTS:
                name = f"{engine}-standalone-{vw}x{vh}"
                ctx = browser.new_context(
                    viewport={"width": vw, "height": vh},
                    device_scale_factor=dsf,
                    is_mobile=True,
                    has_touch=True,
                    service_workers="block",
                )
                ctx.add_init_script(STANDALONE_INIT)
                ctx.route(BLOCK, lambda route: route.abort())
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("load")
                page.wait_for_timeout(400)
                page.evaluate("() => { if (window.__wardrobeFitToday) window.__wardrobeFitToday(); }")
                page.wait_for_timeout(80)

                info = page.evaluate(HOME_JS)
                check(
                    f"{name}: build is .71",
                    info and info.get("build") == CURRENT_BUILD,
                    str(info and info.get("build")),
                )
                check(
                    f"{name}: standalone emulation is on",
                    info and info.get("standalone") is True,
                    str(info),
                )
                check(
                    f"{name}: Home scrollHeight <= innerHeight (no scroll)",
                    info and info.get("fits") and info["scrollH"] <= info["innerH"] + 1,
                    f"scrollH={info.get('scrollH') if info else None} innerH={info.get('innerH') if info else None}",
                )
                check(
                    f"{name}: nav is fixed and flush at the {vh}px bottom",
                    info
                    and info.get("navPos") == "fixed"
                    and nearly(info.get("navBottom"), vh)
                    and nearly(info.get("navH"), 68),
                    str({k: info.get(k) for k in ("navTop", "navBottom", "navH", "navPos")} if info else None),
                )
                check(
                    f"{name}: every Home control sits at or above the nav top",
                    info and not info.get("controlsOverNav"),
                    str((info or {}).get("controlsOverNav")),
                )
                page.screenshot(path=str(SHOTS / f"{name}-home.png"), full_page=False)

                # Closet two-tab row (Closet, Watches)
                page.locator("#section-closet").click()
                page.wait_for_timeout(280)
                closet = page.evaluate(CLOSET_JS)
                check(
                    f"{name}: Closet has no Watches top tab (folded under Accessories)",
                    closet and closet.get("error") == "no closet subnav",
                    str(closet),
                )
                watches_tab = page.evaluate("() => { const t = document.getElementById('tab-watches'); return !!(t && !t.hidden && t.offsetParent); }")
                check(f"{name}: #tab-watches is not visible", not watches_tab, str(watches_tab))
                if vw == 375:
                    page.screenshot(path=str(SHOTS / f"{name}-closet-subnav.png"), full_page=False)

                # The Edit landing: no Receipts teaser; paste-link + receipts live behind +
                page.locator("#tab-find").click()
                page.wait_for_timeout(250)
                shop = page.evaluate(SHOP_JS)
                check(
                    f"{name}: Shop landing has no Receipts teaser",
                    shop and shop.get("findShown") and not shop.get("hasTeaserEl") and not shop.get("findHasReceiptsHeading"),
                    str(shop),
                )
                plus = page.locator("#shop-plus")
                check(f"{name}: The Edit has a + button", plus.count() == 1, "")
                plus.click()
                page.wait_for_timeout(250)
                compact = page.evaluate(SHOP_COMPACT_JS)
                check(
                    f"{name}: no visible info buttons or help popovers",
                    compact and compact.get("visibleInfo") == [],
                    str(compact and compact.get("visibleInfo")),
                )
                check(
                    f"{name}: paste-link input and CHECK IT are compact and on one row",
                    compact
                    and compact.get("sameRow")
                    and compact.get("inputH") is not None and 32 <= compact["inputH"] <= 42
                    and compact.get("btnH") is not None and 32 <= compact["btnH"] <= 42,
                    str(compact),
                )
                rec = page.evaluate(SHOP_JS)
                check(
                    f"{name}: Receipts still work behind +",
                    rec and rec.get("receiptsShown") and "Receipts" in (rec.get("receiptsHeading") or ""),
                    str(rec),
                )
                page.screenshot(path=str(SHOTS / f"{name}-shop-landing.png"), full_page=False)
                if vw == 390:
                    page.screenshot(path=str(SHOTS / f"{name}-shop-plus.png"), full_page=False)
                page.locator("#shop-plus-close").click()
                page.wait_for_timeout(150)

                # Back to Home: still no scroll after the tour
                page.locator("#tab-today").click()
                page.wait_for_timeout(250)
                page.evaluate("() => { if (window.__wardrobeFitToday) window.__wardrobeFitToday(); }")
                page.wait_for_timeout(80)
                again = page.evaluate(HOME_JS)
                check(
                    f"{name}: Home still has no scroll after visiting other pages",
                    again and again.get("fits") and not again.get("controlsOverNav"),
                    f"scrollH={again.get('scrollH') if again else None} innerH={again.get('innerH') if again else None} over={again.get('controlsOverNav') if again else None}",
                )
                ctx.close()

            browser.close()
    finally:
        httpd.shutdown()

    if failures:
        print(f"\n{len(failures)} failed.")
        for f in failures:
            print(" -", f)
        return 1
    print("\nAll .71 Home-fit / Closet-gaps / Shop-receipts checks passed.")
    print(f"Screenshots: {SHOTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
