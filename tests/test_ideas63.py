"""Build .75 Outfits page + Home outfit-type pill.

The Ideas / Studio landing was folded into Outfits (Mine / Inspo).
Outfit type lives on Home as a single pill. This test checks:

  * Home type pill sets formality and the menu closes after a pick
  * Outfits opens on #panel-looks with a two-chip Mine/Inspo toggle
    that is one centered row, equal width, no overflow
  * Mine shows the closet feed; Inspo hides it
  * Bottom nav stays on the .62 flush-bottom contract after the tour

Never talks to the production sync worker.
Usage (from the repo root):

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_ideas63.py
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
AUDIT = Path("/workspace/wardrobe-audit")
BLOCK = re.compile(r"https?://[^/]*workers.dev/.*")
BUILD = "2026-11-19.78.5"

TYPE_JS = """() => {
  const btn = document.getElementById('today-type-btn');
  const menu = document.getElementById('today-type-row');
  const label = document.getElementById('today-type-label');
  if (!btn || !menu) return { error: 'no type pill' };
  const r = btn.getBoundingClientRect();
  let stored = null;
  try { stored = JSON.parse(localStorage.getItem('wardrobe.formality')); } catch (e) {
    stored = localStorage.getItem('wardrobe.formality');
  }
  const overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  return {
    build: window.WARDROBE_BUILD || null,
    visible: !!(btn.offsetParent) && r.width > 0 && r.height > 0,
    label: (label && label.textContent || '').trim(),
    formality: window.formalityLevel,
    any: window.studioTypeAny,
    stored,
    menuHidden: menu.hidden || getComputedStyle(menu).display === 'none',
    overflow,
    width: r.width,
    height: r.height,
  };
}"""

TOGGLE_JS = """() => {
  const panel = document.getElementById('panel-looks');
  const bar = document.querySelector('#panel-looks .outfits-toggle');
  const mine = document.getElementById('outfits-mine');
  const inspo = document.getElementById('outfits-inspo');
  if (!panel || !bar || !mine || !inspo) return { error: 'no outfits toggle', present: [!!panel, !!bar, !!mine, !!inspo] };
  const els = [mine, inspo];
  const rects = els.map(e => {
    const r = e.getBoundingClientRect();
    return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height,
             text: (e.innerText || '').replace(/\\s+/g, ' ').trim() };
  });
  const tops = rects.map(r => r.top);
  const widths = rects.map(r => r.width);
  const heights = rects.map(r => r.height);
  const docW = document.documentElement.clientWidth;
  const barR = bar.getBoundingClientRect();
  const mid = (rects[0].left + rects[1].right) / 2;
  const overflow = document.documentElement.scrollWidth - docW;
  const bodyOverflow = document.body.scrollWidth - docW;
  const feed = document.getElementById('closet-feed');
  const mineView = document.getElementById('outfits-mine-view');
  const inspoView = document.getElementById('outfits-inspo-view');
  return {
    build: window.WARDROBE_BUILD || null,
    panelShown: !panel.hidden && panel.offsetParent !== null,
    count: els.length,
    rects,
    sameRow: (Math.max(...tops) - Math.min(...tops)) <= 2,
    equalWidth: (Math.max(...widths) - Math.min(...widths)) <= 4,
    heightClose: (Math.max(...heights) - Math.min(...heights)) <= 2,
    heights,
    widths,
    centered: Math.abs(mid - docW / 2) <= 8,
    padEqual: Math.abs(barR.left - (docW - barR.right)) <= 8,
    noHorizOverflow: overflow <= 1 && bodyOverflow <= 1,
    overflow, bodyOverflow, docW,
    minePressed: mine.getAttribute('aria-pressed') === 'true',
    inspoPressed: inspo.getAttribute('aria-pressed') === 'true',
    mineViewShown: !!(mineView && !mineView.hidden),
    inspoViewShown: !!(inspoView && !inspoView.hidden),
    feedHidden: !feed || feed.hidden,
    feedCards: document.querySelectorAll('#cf-grid .cf-card').length,
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


def nav_bbox(page):
    return page.evaluate(
        """() => {
          const el = document.getElementById('bottombar');
          if (!el) return null;
          const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el);
          return {
            top: r.top, bottom: r.bottom, height: r.height,
            position: cs.position, transform: cs.transform,
            innerH: window.innerHeight,
            build: window.WARDROBE_BUILD || null,
          };
        }"""
    )


def open_outfits(page):
    page.locator("#section-ideas").click()
    page.wait_for_timeout(250)
    page.wait_for_selector("#panel-looks", state="visible")


def main() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        print(f"  {status}: {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            failures.append(f"{name}: {detail}")

    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    httpd, url = start_static_server()
    AUDIT.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()

            def new_page(vw, vh, dsf=2, is_mobile=True):
                ctx = browser.new_context(
                    viewport={"width": vw, "height": vh},
                    device_scale_factor=dsf,
                    is_mobile=is_mobile,
                    has_touch=True,
                    service_workers="block",
                )
                ctx.route(BLOCK, lambda route: route.abort())
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("load")
                page.wait_for_timeout(250)
                return ctx, page

            for vw, vh, dsf in ((390, 844, 2), (402, 874, 3)):
                name = f"{vw}x{vh}"
                ctx, page = new_page(vw, vh, dsf)
                home = nav_bbox(page)
                check(
                    f"{name}: build is .75",
                    home and home.get("build") == BUILD,
                    str(home and home.get("build")),
                )
                check(
                    f"{name}: Home bar is flush and fixed",
                    home
                    and home["position"] in ("fixed", "absolute")
                    and nearly(home["bottom"], vh)
                    and nearly(home["height"], 68)
                    and home["transform"] in ("none", "matrix(1, 0, 0, 1, 0, 0)"),
                    str(home),
                )

                typ = page.evaluate(TYPE_JS)
                check(
                    f"{name}: Home type pill is visible",
                    typ and typ.get("visible") and typ.get("overflow", 99) <= 1,
                    str(typ),
                )

                page.locator("#today-type-btn").click()
                page.wait_for_selector("#today-type-row", state="visible")
                page.locator('#today-type-row [data-studio-type="5"]').click()
                page.wait_for_timeout(200)
                after5 = page.evaluate(TYPE_JS)
                check(
                    f"{name}: type pill sets Business Casual",
                    after5
                    and after5.get("label") == "Business Casual"
                    and after5.get("formality") == 5
                    and after5.get("stored") == 5,
                    str(after5),
                )
                check(
                    f"{name}: type menu closes after a pick",
                    page.locator("#today-type-row").is_hidden(),
                    "menu still open",
                )

                page.locator("#today-type-btn").click()
                page.wait_for_selector("#today-type-row", state="visible")
                page.locator('#today-type-row [data-studio-type="6"]').click()
                page.wait_for_timeout(200)
                after6 = page.evaluate(TYPE_JS)
                check(
                    f"{name}: type pill sets Formal and stores it",
                    after6 and after6.get("formality") == 6 and after6.get("stored") == 6
                    and after6.get("label") == "Formal",
                    str(after6),
                )

                open_outfits(page)
                info = page.evaluate(TOGGLE_JS)
                check(
                    f"{name}: Outfits panel is shown",
                    info and info.get("panelShown"),
                    str(info),
                )
                check(
                    f"{name}: Mine/Inspo toggle is two equal chips in one centered row",
                    info
                    and info.get("count") == 2
                    and info.get("sameRow")
                    and info.get("equalWidth")
                    and info.get("heightClose")
                    and info.get("centered")
                    and info.get("padEqual"),
                    str(info),
                )
                check(
                    f"{name}: no horizontal overflow",
                    info and info.get("noHorizOverflow"),
                    str({k: (info or {}).get(k) for k in ("overflow", "bodyOverflow", "docW")}),
                )
                check(
                    f"{name}: Mine is the default view",
                    info and info.get("minePressed") and info.get("mineViewShown") and not info.get("inspoViewShown"),
                    str(info),
                )

                if vw == 390:
                    page.screenshot(path=str(AUDIT / "outfits-390-build75-ideas63.png"), full_page=False)
                    print(f"  wrote {AUDIT / 'outfits-390-build75-ideas63.png'}")

                page.locator("#outfits-inspo").click()
                page.wait_for_timeout(300)
                insp = page.evaluate(TOGGLE_JS)
                check(
                    f"{name}: Inspo shows the inspo view and hides Mine / the closet feed",
                    insp
                    and insp.get("inspoPressed")
                    and insp.get("inspoViewShown")
                    and not insp.get("mineViewShown")
                    and insp.get("feedHidden"),
                    str(insp),
                )
                page.locator("#outfits-mine").click()
                page.wait_for_timeout(300)

                outfits_nav = nav_bbox(page)
                check(
                    f"{name}: Outfits bar stays flush with Home",
                    outfits_nav
                    and home
                    and nearly(outfits_nav["bottom"], home["bottom"])
                    and nearly(outfits_nav["top"], home["top"]),
                    f"home={home} outfits={outfits_nav}",
                )

                page.locator("#tab-today").click()
                page.wait_for_timeout(250)
                home2 = nav_bbox(page)
                check(
                    f"{name}: Home nav unchanged after Outfits",
                    home2
                    and nearly(home2["bottom"], vh)
                    and nearly(home2["height"], 68)
                    and home2["position"] in ("fixed", "absolute")
                    and nearly(home2["top"], home["top"]),
                    f"before={home} after={home2}",
                )
                ctx.close()

            ctx, page = new_page(1280, 800, dsf=1, is_mobile=False)
            typ = page.evaluate(TYPE_JS)
            check(
                "1280x800: build is .75",
                typ and typ.get("build") == BUILD,
                str(typ and typ.get("build")),
            )
            check(
                "1280x800: Home type pill is visible, no overflow",
                typ and typ.get("visible") and typ.get("overflow", 99) <= 1,
                str(typ),
            )
            open_outfits(page)
            desk = page.evaluate(TOGGLE_JS)
            check(
                "1280x800: Mine/Inspo toggle in one row, no overflow",
                desk and desk.get("count") == 2 and desk.get("sameRow") and desk.get("noHorizOverflow"),
                str(desk),
            )
            page.screenshot(path=str(AUDIT / "outfits-1280x800-build75.png"), full_page=False)
            print(f"  wrote {AUDIT / 'outfits-1280x800-build75.png'}")
            ctx.close()
            browser.close()
    finally:
        httpd.shutdown()

    print()
    if failures:
        print(f"{len(failures)} failed:")
        for f in failures:
            print(" -", f)
        return 1
    print("All Outfits / Home type-pill .75 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
