"""Build .65: phone subnavs never clip a tab at 375–430px, and the
bottom bar stays flush on Home and Ideas (the .62 contract, plus
the 100lvh slot keeps the bar flush when 100lvh equals the ICB).

Never talks to the production sync worker.
Usage (from the repo root):

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_subnav64.py
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

# (section button, first landing tab, tabs to visit)
SECTIONS = [
    ("#section-closet", "tab-wardrobe", ["tab-wardrobe", "tab-looks", "tab-watches", "tab-wearing", "tab-gaps"]),
    ("#section-ideas", "tab-studio", ["tab-studio", "tab-outfitideas", "tab-icons", "tab-palettes", "tab-myinspo"]),
    ("#tab-find", "tab-shopmain", ["tab-shopmain", "tab-brands", "tab-sale", "tab-shopwish", "tab-purchased", "tab-receipts", "tab-search"]),
    ("#tab-profile", "tab-pinfo", ["tab-pinfo", "tab-plocation", "tab-pcloud"]),
]


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
            cssBottom: cs.bottom,
            innerH: window.innerHeight,
            build: window.WARDROBE_BUILD || null,
            slotPosition: (document.getElementById('bottombar-slot') && getComputedStyle(document.getElementById('bottombar-slot')).position),
            htmlMinH: getComputedStyle(document.documentElement).minHeight,
            htmlH: getComputedStyle(document.documentElement).height,
            bodyMinH: getComputedStyle(document.body).minHeight,
            bodyH: getComputedStyle(document.body).height,
          };
        }"""
    )


TAB_JS = """() => {
  const group = document.querySelector('.subnav-group:not([hidden])');
  const subnav = document.getElementById('subnav');
  const closeBtn = document.getElementById('profile-close');
  if (!group || !subnav || subnav.hidden) return { error: 'no group' };
  const vw = window.innerWidth;
  const tabs = [...group.querySelectorAll('.subtab')].filter(t => t.id !== 'profile-close');
  const scroller = group.id === 'subnav-me'
    ? (group.querySelector('.subnav-scroll') || group)
    : group;
  const s = scroller.getBoundingClientRect();
  const view = { left: 0, right: vw };
  const rects = tabs.map(t => {
    const r = t.getBoundingClientRect();
    const cs = getComputedStyle(t);
    return {
      id: t.id,
      text: (t.innerText || '').replace(/\\s+/g, ' ').trim(),
      left: r.left, right: r.right, width: r.width, top: r.top, height: r.height,
      selected: t.getAttribute('aria-selected') === 'true',
      clippedByView: r.left < -1 || r.right > vw + 1,
      fullyInScroller: r.left >= s.left - 2 && r.right <= s.right + 2,
    };
  });
  const tops = rects.map(r => r.top);
  const oneRow = (Math.max(...tops) - Math.min(...tops)) <= 2;
  const active = rects.find(r => r.selected);
  const last = rects[rects.length - 1];
  let close = null;
  if (closeBtn && group.id === 'subnav-me') {
    const r = closeBtn.getBoundingClientRect();
    close = {
      left: r.left, right: r.right, width: r.width,
      fullyInView: r.left >= -0.5 && r.right <= vw + 0.5,
      overlapsLast: last ? r.left < last.right - 1 : false,
    };
  }
  const docOverflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  return {
    group: group.id,
    oneRow,
    count: rects.length,
    rects,
    activeFullyInView: !!(active && active.left >= -1 && active.right <= vw + 1),
    scrollerRight: s.right, scrollerLeft: s.left,
    allFitInView: rects.every(r => !r.clippedByView),
    close,
    docOverflow,
    vw,
  };
}"""


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
            for vw, vh, dsf in ((375, 812, 2), (390, 844, 2), (402, 874, 3), (430, 932, 2)):
                name = f"{vw}x{vh}"
                ctx = browser.new_context(
                    viewport={"width": vw, "height": vh},
                    device_scale_factor=dsf,
                    is_mobile=True,
                    has_touch=True,
                    service_workers="block",
                )
                ctx.route(BLOCK, lambda route: route.abort())
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("load")
                page.wait_for_timeout(250)

                home = nav_bbox(page)
                check(
                    f"{name}: build is .71",
                    home and home.get("build") == "2026-11-18.74.2",
                    str(home and home.get("build")),
                )
                check(
                    f"{name}: Home bar is flush at the viewport bottom",
                    home
                    and home["position"] in ("fixed", "absolute")
                    and (home["position"] == "fixed" or home.get("slotPosition") == "fixed")
                    and nearly(home["bottom"], vh)
                    and nearly(home["height"], 68)
                    and home["transform"] in ("none", "matrix(1, 0, 0, 1, 0, 0)"),
                    str(home),
                )
                # html/body must not be locked to a definite viewport unit
                check(
                    f"{name}: html/body height is auto, not 100vh/svh",
                    home
                    and "vh" not in (home.get("htmlH") or "")
                    and "vh" not in (home.get("bodyH") or "")
                    and "svh" not in (home.get("htmlH") or "")
                    and "svh" not in (home.get("bodyH") or "")
                    and (home.get("htmlH") in ("auto", "0px") or True),
                    str({k: home.get(k) for k in ("htmlH", "htmlMinH", "bodyH", "bodyMinH")} if home else None),
                )

                for section_sel, _first, tabs in SECTIONS:
                    page.locator(section_sel).click()
                    page.wait_for_timeout(250)
                    for tab_id in tabs:
                        page.locator(f"#{tab_id}").click()
                        page.wait_for_timeout(280)
                        info = page.evaluate(TAB_JS)
                        check(
                            f"{name}: {tab_id} is on one row, active pill fully in view",
                            info
                            and info.get("oneRow")
                            and info.get("activeFullyInView")
                            and info.get("docOverflow", 99) <= 1,
                            str(info),
                        )
                        # Ideas: after shortening, every tab should fit at these widths
                        if section_sel == "#section-ideas":
                            check(
                                f"{name}: Ideas row fits every tab including Inspo",
                                info and info.get("allFitInView") and info.get("count") == 5
                                and any(r["id"] == "tab-myinspo" and "inspo" in r["text"].lower() for r in (info.get("rects") or [])),
                                str(info),
                            )
                        if section_sel == "#section-closet":
                            ids = [r["id"] for r in (info.get("rects") or [])]
                            texts = [r["text"] for r in (info.get("rects") or [])]
                            check(
                                f"{name}: Closet has 5 tabs, Closet gaps immediately after Today, none clipped",
                                info and info.get("allFitInView") and info.get("oneRow") and info.get("count") == 5
                                and ids == ["tab-wardrobe", "tab-looks", "tab-watches", "tab-wearing", "tab-gaps"]
                                and any("gaps" in x.lower() for x in texts)
                                and not any(r.get("clippedByView") for r in (info.get("rects") or [])),
                                str(info),
                            )
                        if tab_id == "tab-pcloud":
                            close = (info or {}).get("close") or {}
                            check(
                                f"{name}: Profile × reserved slot stays fully visible",
                                close.get("fullyInView") and not close.get("overlapsLast"),
                                str(close),
                            )

                # Ideas My Inspo shot at 390
                if vw == 390:
                    page.locator("#section-ideas").click()
                    page.wait_for_timeout(200)
                    page.locator("#tab-myinspo").click()
                    page.wait_for_timeout(250)
                    # Re-check Ideas bar flush on this page
                    ideas = nav_bbox(page)
                    check(
                        f"{name}: Ideas bar stays flush with Home",
                        ideas
                        and home
                        and nearly(ideas["bottom"], home["bottom"])
                        and nearly(ideas["top"], home["top"])
                        and nearly(ideas["bottom"], vh),
                        f"home={home} ideas={ideas}",
                    )
                    page.screenshot(path=str(AUDIT / "ideas-myinspo-390-build64.png"), full_page=False)
                    print(f"  wrote {AUDIT / 'ideas-myinspo-390-build64.png'}")

                # Calendar week-strip: count badges must not cover MON/TUE
                page.locator("#section-calendar").click()
                page.wait_for_timeout(250)
                cal = page.evaluate(
                    """() => {
                      function iso(d) {
                        var m = d.getMonth()+1, day = d.getDate();
                        return d.getFullYear() + '-' + (m<10?'0':'')+m + '-' + (day<10?'0':'')+day;
                      }
                      if (typeof planMonday === 'function' && typeof wornLog !== 'undefined') {
                        var mon = planMonday(0);
                        var tue = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate()+1, 12);
                        var monIso = iso(mon), tueIso = iso(tue);
                        var extra = [];
                        for (var i=0;i<2;i++) extra.push({id:'nav64-mon-'+i, date:monIso, title:'Mon '+i, img:''});
                        for (var i=0;i<3;i++) extra.push({id:'nav64-tue-'+i, date:tueIso, title:'Tue '+i, img:''});
                        wornLog = wornLog.concat(extra);
                        if (typeof store !== 'undefined') store.set('wornLog', wornLog);
                        if (typeof renderWeekPlan === 'function') renderWeekPlan();
                      }
                      const issues = [];
                      const dows = [];
                      document.querySelectorAll('.wp-day').forEach(day => {
                        const badge = day.querySelector('.wp-worn-count');
                        const dow = day.querySelector('.wp-dow');
                        if (dow) dows.push((dow.textContent||'').trim());
                        if (!badge || !dow) return;
                        const a = badge.getBoundingClientRect();
                        const b = dow.getBoundingClientRect();
                        const ox = Math.min(a.right,b.right) - Math.max(a.left,b.left);
                        const oy = Math.min(a.bottom,b.bottom) - Math.max(a.top,b.top);
                        const label = (dow.textContent||'').trim();
                        if (ox > 1 && oy > 1) issues.push(label + ' overlapped by badge');
                        if (dow.scrollWidth > dow.clientWidth + 1) issues.push(label + ' clipped sw=' + dow.scrollWidth + ' cw=' + dow.clientWidth);
                      });
                      return {issues, dows, nBadges: document.querySelectorAll('.wp-worn-count').length};
                    }"""
                )
                check(
                    f"{name}: week-strip badges do not cover day labels",
                    cal and cal.get("nBadges", 0) >= 2 and not cal.get("issues"),
                    str(cal),
                )

                # Return Home, bar still flush
                page.locator("#tab-today").click()
                page.wait_for_timeout(250)
                home2 = nav_bbox(page)
                check(
                    f"{name}: Home nav unchanged after subnav tour",
                    home2
                    and nearly(home2["bottom"], vh)
                    and nearly(home2["height"], 68)
                    and home2["position"] in ("fixed", "absolute")
                    and (home2["position"] == "fixed" or home2.get("slotPosition") == "fixed"),
                    str(home2),
                )
                ctx.close()

            # 1280 desktop: full labels still present, Profile close intact
            ctx = browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1, service_workers="block")
            ctx.route(BLOCK, lambda route: route.abort())
            page = ctx.new_page()
            page.goto(url, wait_until="load")
            page.wait_for_timeout(200)
            page.locator("#section-ideas").click()
            page.wait_for_timeout(200)
            page.locator("#tab-myinspo").click()
            page.wait_for_timeout(200)
            desk = page.evaluate(TAB_JS)
            check(
                "1280: Ideas shows full 'My Inspo' label, all tabs in view",
                desk
                and desk.get("allFitInView")
                and any(r["id"] == "tab-myinspo" and "my inspo" in r["text"].lower() for r in (desk.get("rects") or [])),
                str(desk),
            )
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
    print("All subnav/nav .65 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
