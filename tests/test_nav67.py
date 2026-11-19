"""Build .67 nav contract, re-checked on .71:
every phone page's document is at least screen-tall,
and the bottom nav is flush and identical on short and long pages.

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_nav67.py
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
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")

PAGES = [
    ("home", ["#tab-today"]),
    ("closet-closet", ["#section-closet", "#tab-wardrobe"]),
    ("closet-watches", ["#section-closet", "#tab-watches"]),
    ("outfits", ["#section-ideas"]),
    ("shop-edit", ["#tab-find"]),
    ("calendar", ["#section-calendar"]),
    ("profile-info", ["#tab-profile", "#tab-pinfo"]),
    ("profile-location", ["#tab-profile", "#tab-plocation"]),
    ("profile-cloud", ["#tab-profile", "#tab-pcloud"]),
]

INSPECT = """() => {
  const nav = document.getElementById('bottombar');
  const r = nav.getBoundingClientRect();
  const cs = getComputedStyle(nav);
  const html = document.documentElement;
  const body = document.body;
  const sh = Math.max(html.scrollHeight, body.scrollHeight);
  const ch = html.clientHeight;
  const inner = window.innerHeight;
  const screenH = (window.screen && screen.height) || inner;
  return {
    build: window.WARDROBE_BUILD || null,
    chip: (document.getElementById('build-chip') || {}).textContent || '',
    navTop: r.top, navBottom: r.bottom, navHeight: r.height,
    position: cs.position, cssBottom: cs.bottom, transform: cs.transform,
    padBottom: cs.paddingBottom, boxShadow: cs.boxShadow,
    innerH: inner, screenH: screenH, clientH: ch, scrollH: sh,
    htmlMinH: getComputedStyle(html).minHeight,
    bodyMinH: getComputedStyle(body).minHeight,
    htmlH: getComputedStyle(html).height,
    bodyH: getComputedStyle(body).height,
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
    httpd, url = start_static_server()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for vw, vh, dsf in ((375, 812, 2), (390, 844, 2), (402, 874, 3), (430, 932, 2)):
                tag = f"{vw}x{vh}"
                ctx = browser.new_context(
                    viewport={"width": vw, "height": vh},
                    device_scale_factor=dsf,
                    is_mobile=True,
                    has_touch=True,
                    service_workers="block",
                )
                ctx.route(BLOCK, lambda route: route.abort())
                page = ctx.new_page()
                page.goto(url, wait_until="load")
                page.wait_for_timeout(250)
                baseline = None
                short_over = []
                for slug, clicks in PAGES:
                    for sel in clicks:
                        loc = page.locator(sel)
                        if loc.count():
                            loc.first.click()
                            page.wait_for_timeout(180)
                    page.wait_for_timeout(80)
                    info = page.evaluate(INSPECT)
                    check(
                        f"{tag} {slug}: build is .71",
                        info and info.get("build") == "2026-11-19.78.8a",
                        str(info and info.get("build")),
                    )
                    check(
                        f"{tag} {slug}: scrollHeight >= innerHeight and screen.height",
                        info
                        and info["scrollH"] + 1 >= info["innerH"]
                        and info["scrollH"] + 1 >= info["screenH"],
                        f"scrollH={info['scrollH']} innerH={info['innerH']} screenH={info['screenH']} clientH={info['clientH']}",
                    )
                    check(
                        f"{tag} {slug}: nav is fixed, flush, normal safe-area padding, no fill shadow",
                        info
                        and info["position"] == "fixed"
                        and nearly(info["navBottom"], vh)
                        and nearly(info["navHeight"], 68)
                        and info["transform"] in ("none", "matrix(1, 0, 0, 1, 0, 0)")
                        and info["padBottom"] in ("0px",)
                        and (not info["boxShadow"] or info["boxShadow"] == "none"),
                        str({k: info[k] for k in ("navTop", "navBottom", "navHeight", "position", "padBottom", "boxShadow", "cssBottom")}),
                    )
                    if baseline is None:
                        baseline = info
                        check(
                            f"{tag}: Home has no build-chip",
                            not (info.get("chip") or ""),
                            repr(info.get("chip")),
                        )
                    else:
                        check(
                            f"{tag} {slug}: nav matches Home",
                            nearly(info["navTop"], baseline["navTop"])
                            and nearly(info["navBottom"], baseline["navBottom"])
                            and nearly(info["navHeight"], baseline["navHeight"]),
                            f"home={baseline['navTop']}/{baseline['navBottom']}/{baseline['navHeight']} now={info['navTop']}/{info['navBottom']}/{info['navHeight']}",
                        )
                    # Short pages (Home, Calendar, My Inspo) must not grow a
                    # large empty scroll; a hair is ok, tens of px of
                    # min-height slop is not.
                    if slug in ("home", "calendar", "ideas-myinspo", "profile-location"):
                        over = info["scrollH"] - info["innerH"]
                        if over > 8:
                            short_over.append(f"{slug} +{over}px")
                    # Reset scroll so the next page isn't measured mid-scroll
                    page.evaluate("() => { document.documentElement.style.scrollBehavior='auto'; window.scrollTo(0,0); }")
                check(
                    f"{tag}: short pages have no large empty scroll",
                    not short_over,
                    "; ".join(short_over),
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
    print("\nAll .71 nav/document-height checks passed (nav contract unchanged from .67).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
