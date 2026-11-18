"""Build .63 Ideas outfit-type dropdown: four equal buttons in one
row at phone and desktop widths, no horizontal overflow, the
dropdown changes type and generation uses it. Home nav stays the
.62 flush-bottom contract.

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
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")

ROW_JS = """() => {
  const bar = document.querySelector('#panel-studio .studio-home-bar');
  if (!bar) return { error: 'no bar' };
  const deal = document.getElementById('studio-deal');
  const typ = document.getElementById('ideas-type-btn');
  const cust = document.getElementById('studio-customize');
  const buildBtn = document.getElementById('studio-build');
  const els = [deal, typ, cust, buildBtn];
  if (els.some(e => !e)) return { error: 'missing button', present: els.map(e => !!e) };
  const surfaceChips = [...document.querySelectorAll('#panel-studio [data-studio-type], #panel-studio [data-studio-type-any]')]
    .filter(el => !el.closest('#ideas-type-menu') && !el.closest('#studio-type-row') && !el.closest('#studio-form'));
  const form = document.getElementById('studio-form');
  const outfitTypeHeading = [...document.querySelectorAll('#panel-studio span, #panel-studio p, #panel-studio label, #panel-studio h2, #panel-studio h3')].some(el => {
    if (form && form.contains(el)) return false;
    return (el.textContent || '').trim().toLowerCase() === 'outfit type';
  });
  const rects = els.map(e => {
    const r = e.getBoundingClientRect();
    return {
      top: r.top, bottom: r.bottom, left: r.left, right: r.right,
      width: r.width, height: r.height,
      overflowX: e.scrollWidth - e.clientWidth,
      text: (e.innerText || '').replace(/\\s+/g, ' ').trim(),
    };
  });
  const tops = rects.map(r => r.top);
  const widths = rects.map(r => r.width);
  const heights = rects.map(r => r.height);
  const docW = document.documentElement.clientWidth;
  const overflow = document.documentElement.scrollWidth - docW;
  const bodyOverflow = document.body.scrollWidth - docW;
  const barOverflow = bar.scrollWidth - bar.clientWidth;
  const panel = document.getElementById('panel-studio');
  let stored = null;
  try { stored = JSON.parse(localStorage.getItem('wardrobe.formality')); } catch (e) {
    stored = localStorage.getItem('wardrobe.formality');
  }
  return {
    build: window.WARDROBE_BUILD || null,
    visibleSurfaceChips: surfaceChips.length,
    outfitTypeHeading,
    count: els.length,
    rects,
    sameRow: (Math.max(...tops) - Math.min(...tops)) <= 2,
    equalWidth: (Math.max(...widths) - Math.min(...widths)) <= 2,
    heightClose: (Math.max(...heights) - Math.min(...heights)) <= 2,
    heights,
    noHorizOverflow: overflow <= 1 && bodyOverflow <= 1 && barOverflow <= 1 && rects.every(r => r.overflowX <= 1),
    overflow, bodyOverflow, barOverflow, docW,
    dealIsAccent: deal.classList.contains('btn-accent'),
    typeIsGhost: typ.classList.contains('btn-ghost'),
    label: (document.getElementById('ideas-type-label') || {}).textContent || '',
    formality: window.formalityLevel,
    any: window.studioTypeAny,
    stored,
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


def open_ideas(page):
    page.locator("#section-ideas").click()
    page.wait_for_timeout(250)
    page.wait_for_selector("#panel-studio .studio-home-bar", state="visible")


def deal_stats(page):
    return page.evaluate(
        """() => {
          const cards = [...document.querySelectorAll('#panel-studio .option-card img, #panel-studio .options-grid img')];
          const srcs = cards.map(img => {
            const s = img.getAttribute('src') || '';
            const m = s.match(/assets\\/photos\\/[^/?#]+/);
            return m ? m[0] : s;
          }).filter(Boolean);
          const levels = srcs.map(s => (window.RENDER_FORMALITY && window.RENDER_FORMALITY[s]) || null);
          const known = levels.filter(v => typeof v === 'number');
          const avg = known.length ? known.reduce((a, b) => a + b, 0) / known.length : null;
          return {
            n: cards.length,
            known: known.length,
            levels: known,
            avg,
            formality: window.formalityLevel,
            any: window.studioTypeAny,
          };
        }"""
    )


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

            # ---- 390 and 402: four-across row, no overflow, dropdown works ----
            for vw, vh, dsf in ((390, 844, 2), (402, 874, 3)):
                name = f"{vw}x{vh}"
                ctx, page = new_page(vw, vh, dsf)
                home = nav_bbox(page)
                check(
                    f"{name}: build is .65",
                    home and home.get("build") == "2026-11-18.65",
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

                open_ideas(page)
                info = page.evaluate(ROW_JS)
                check(
                    f"{name}: no Outfit type heading or surface chips",
                    info and not info.get("outfitTypeHeading") and info.get("visibleSurfaceChips") == 0,
                    str(info),
                )
                check(
                    f"{name}: four controls in one row",
                    info and info.get("count") == 4 and info.get("sameRow"),
                    str(info),
                )
                check(
                    f"{name}: equal widths and consistent height",
                    info and info.get("equalWidth") and info.get("heightClose"),
                    str({"widths": [r["width"] for r in (info or {}).get("rects") or []], "heights": (info or {}).get("heights")}),
                )
                check(
                    f"{name}: no horizontal overflow",
                    info and info.get("noHorizOverflow"),
                    str({k: (info or {}).get(k) for k in ("overflow", "bodyOverflow", "barOverflow", "docW")}),
                )
                check(
                    f"{name}: Give me ideas stays the orange primary; type is outlined",
                    info and info.get("dealIsAccent") and info.get("typeIsGhost"),
                    str(info),
                )

                if vw == 390:
                    page.screenshot(
                        path=str(AUDIT / "ideas-390-build63.png"),
                        full_page=False,
                    )
                    print(f"  wrote {AUDIT / 'ideas-390-build63.png'}")

                # Dropdown: pick Business Casual (5), then Formal (6)
                page.locator("#ideas-type-btn").click()
                page.wait_for_selector("#ideas-type-menu", state="visible")
                page.locator('#ideas-type-menu [data-studio-type="5"]').click()
                page.wait_for_timeout(200)
                after5 = page.evaluate(ROW_JS)
                check(
                    f"{name}: dropdown sets Business Casual",
                    after5
                    and after5.get("label") == "Business Casual"
                    and after5.get("formality") == 5
                    and after5.get("any") is False
                    and after5.get("stored") == 5,
                    str(after5),
                )
                # Menu should close after a pick
                check(
                    f"{name}: type menu closes after a pick",
                    page.locator("#ideas-type-menu").is_hidden(),
                    "menu still open",
                )

                page.locator("#ideas-type-btn").click()
                page.wait_for_selector("#ideas-type-menu", state="visible")
                page.locator('#ideas-type-menu [data-studio-type="6"]').click()
                page.wait_for_timeout(200)
                page.locator("#studio-deal").click()
                page.wait_for_timeout(800)
                stats6 = deal_stats(page)
                engine6 = page.evaluate(
                    """() => ({
                      formality: window.formalityLevel,
                      any: window.studioTypeAny,
                      preferFormal: typeof formalityBandCost === 'function' && formalityBandCost(6) < formalityBandCost(1),
                      stored: (function () { try { return JSON.parse(localStorage.getItem('wardrobe.formality')); } catch (e) { return null; } })(),
                    })"""
                )
                check(
                    f"{name}: Formal deal keeps formality 6, stores it, and shows looks",
                    stats6 and stats6.get("formality") == 6 and stats6.get("any") is False and stats6.get("n", 0) >= 1
                    and engine6 and engine6.get("preferFormal") and engine6.get("stored") == 6,
                    f"stats={stats6} engine={engine6}",
                )

                # Re-deal at Swim/Pool: generation must read the new type, not a stale Formal.
                page.locator("#ideas-type-btn").click()
                page.wait_for_selector("#ideas-type-menu", state="visible")
                page.locator('#ideas-type-menu [data-studio-type="1"]').click()
                page.wait_for_timeout(200)
                page.locator("#studio-deal").click()
                page.wait_for_timeout(800)
                stats1 = deal_stats(page)
                engine1 = page.evaluate(
                    """() => ({
                      formality: window.formalityLevel,
                      any: window.studioTypeAny,
                      preferSwim: typeof formalityBandCost === 'function' && formalityBandCost(1) < formalityBandCost(6),
                      stored: (function () { try { return JSON.parse(localStorage.getItem('wardrobe.formality')); } catch (e) { return null; } })(),
                    })"""
                )
                check(
                    f"{name}: Swim deal uses the new type (formality 1, engine prefers swim)",
                    stats1 and stats1.get("formality") == 1 and stats1.get("n", 0) >= 1
                    and engine1 and engine1.get("preferSwim") and engine1.get("stored") == 1,
                    f"stats={stats1} engine={engine1}",
                )

                # Any keeps stored formality at the silent default 4
                page.locator("#ideas-type-btn").click()
                page.wait_for_selector("#ideas-type-menu", state="visible")
                page.locator("#ideas-type-menu [data-studio-type-any]").click()
                page.wait_for_timeout(200)
                any_info = page.evaluate(ROW_JS)
                check(
                    f"{name}: Any shows Any and stores formality 4",
                    any_info
                    and any_info.get("label") == "Any"
                    and any_info.get("any") is True
                    and any_info.get("formality") == 4
                    and any_info.get("stored") == 4,
                    str(any_info),
                )

                # Ideas nav still flush
                ideas_nav = nav_bbox(page)
                check(
                    f"{name}: Ideas bar stays flush with Home",
                    ideas_nav
                    and home
                    and nearly(ideas_nav["bottom"], home["bottom"])
                    and nearly(ideas_nav["top"], home["top"]),
                    f"home={home} ideas={ideas_nav}",
                )

                # Return to Home and re-check the .62 nav contract
                page.locator("#tab-today").click()
                page.wait_for_timeout(250)
                home2 = nav_bbox(page)
                check(
                    f"{name}: Home nav unchanged after Ideas",
                    home2
                    and nearly(home2["bottom"], vh)
                    and nearly(home2["height"], 68)
                    and home2["position"] in ("fixed", "absolute")
                    and nearly(home2["top"], home["top"]),
                    f"before={home} after={home2}",
                )
                ctx.close()

            # ---- 1280×800 desktop: row still holds, nothing breaks ----
            ctx, page = new_page(1280, 800, dsf=1, is_mobile=False)
            open_ideas(page)
            desk = page.evaluate(ROW_JS)
            check(
                "1280x800: build is .65",
                desk and desk.get("build") == "2026-11-18.65",
                str(desk and desk.get("build")),
            )
            check(
                "1280x800: four controls in one row, no overflow",
                desk and desk.get("count") == 4 and desk.get("sameRow") and desk.get("noHorizOverflow"),
                str(desk),
            )
            check(
                "1280x800: equal widths, consistent height, accent + outlined type",
                desk
                and desk.get("equalWidth")
                and desk.get("heightClose")
                and desk.get("dealIsAccent")
                and desk.get("typeIsGhost"),
                str({"widths": [r["width"] for r in (desk or {}).get("rects") or []], "heights": (desk or {}).get("heights")}),
            )
            page.locator("#ideas-type-btn").click()
            page.wait_for_selector("#ideas-type-menu", state="visible")
            page.locator('#ideas-type-menu [data-studio-type="5"]').click()
            page.wait_for_timeout(200)
            desk5 = page.evaluate(ROW_JS)
            check(
                "1280x800: dropdown sets Business Casual",
                desk5 and desk5.get("label") == "Business Casual" and desk5.get("formality") == 5,
                str(desk5),
            )
            page.screenshot(path=str(AUDIT / "ideas-1280x800-build63.png"), full_page=False)
            print(f"  wrote {AUDIT / 'ideas-1280x800-build63.png'}")
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
    print("All Ideas .63 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
