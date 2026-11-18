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

ROOT = Path(__file__).resolve().parents[1]
SHOTS = Path("/workspace/wardrobe-audit/build-70")
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
                    f"{name}: build is .70",
                    info and info.get("build") == "2026-11-18.70",
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

                # Closet five-tab row (required at 375, checked at all sizes)
                page.locator("#section-closet").click()
                page.wait_for_timeout(280)
                closet = page.evaluate(CLOSET_JS)
                check(
                    f"{name}: Closet has 5 tabs, Closet gaps after Today, none clipped",
                    closet
                    and closet.get("count") == 5
                    and closet.get("oneRow")
                    and closet.get("allFit")
                    and closet.get("ids") == ["tab-wardrobe", "tab-looks", "tab-watches", "tab-wearing", "tab-gaps"]
                    and any("gaps" in t.lower() for t in (closet.get("texts") or [])),
                    str(closet),
                )
                if vw == 375:
                    page.screenshot(path=str(SHOTS / f"{name}-closet-subnav.png"), full_page=False)
                    page.locator("#tab-gaps").click()
                    page.wait_for_timeout(250)
                    gaps_ok = page.evaluate(
                        """() => {
                          const p = document.getElementById('panel-gaps');
                          return !!(p && !p.hidden && /closet gaps/i.test(p.innerText || ''));
                        }"""
                    )
                    check(f"{name}: Closet gaps tab opens the existing gaps page", gaps_ok, "")
                    page.screenshot(path=str(SHOTS / f"{name}-closet-gaps.png"), full_page=False)

                # Shop landing must not show a Receipts block; Receipts page remains
                page.locator("#tab-find").click()
                page.wait_for_timeout(250)
                page.locator("#tab-shopmain").click()
                page.wait_for_timeout(250)
                shop = page.evaluate(SHOP_JS)
                check(
                    f"{name}: Shop landing has no Receipts teaser",
                    shop and shop.get("findShown") and not shop.get("hasTeaserEl") and not shop.get("findHasReceiptsHeading"),
                    str(shop),
                )
                if vw == 390:
                    page.screenshot(path=str(SHOTS / f"{name}-shop-landing.png"), full_page=False)
                page.locator("#tab-receipts").click()
                page.wait_for_timeout(250)
                rec = page.evaluate(SHOP_JS)
                check(
                    f"{name}: Receipts sub page still works",
                    rec and rec.get("receiptsShown") and rec.get("tabExists") and "Receipts" in (rec.get("receiptsHeading") or ""),
                    str(rec),
                )
                if vw == 390:
                    page.screenshot(path=str(SHOTS / f"{name}-shop-receipts.png"), full_page=False)

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
    print("\nAll .70 Home-fit / Closet-gaps / Shop-receipts checks passed.")
    print(f"Screenshots: {SHOTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
