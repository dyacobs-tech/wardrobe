"""Build .62 bottom-nav geometry: cold load into Home, Home vs Closet,
390×844 / 402×874, simulated 34px bottom safe area, WebKit iPhone
15/16 Pro descriptors when available.

Never talks to the production sync worker.
Usage (from the repo root):

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_nav62.py
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
INSET_CSS = """
:root { --bb-h: calc(68px + 34px) !important; }
#bottombar.bottombar, .bottombar {
  padding-bottom: 34px !important;
  height: var(--bb-h) !important;
}
body { padding-bottom: var(--bb-h) !important; }
"""
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")


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


def bbox(page):
    return page.evaluate(
        """() => {
          const el = document.getElementById('bottombar');
          if (!el) return null;
          const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el);
          const slot = document.getElementById('bottombar-slot');
          const scs = slot ? getComputedStyle(slot) : null;
          return {
            top: r.top, bottom: r.bottom, height: r.height,
            position: cs.position, paddingBottom: cs.paddingBottom,
            cssBottom: cs.bottom, transform: cs.transform,
            innerH: window.innerHeight,
            vvH: window.visualViewport ? visualViewport.height : null,
            build: window.WARDROBE_BUILD || null,
            slotPosition: scs ? scs.position : null,
            slotHeight: scs ? scs.height : null,
          };
        }"""
    )


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
            def run_viewport(browser, name, vw, vh, dsf=3, inset=0, engine="chromium"):
                ctx_kw = dict(
                    viewport={"width": vw, "height": vh},
                    device_scale_factor=dsf,
                    is_mobile=True,
                    has_touch=True,
                    service_workers="block",
                )
                ctx = browser.new_context(**ctx_kw)
                ctx.route(BLOCK, lambda route: route.abort())
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded")
                if inset:
                    page.add_style_tag(content=INSET_CSS)
                page.wait_for_load_state("load")
                page.wait_for_timeout(250)
                home = bbox(page)
                expected_h = 68 + inset
                check(
                    f"{name}: build is .71",
                    home and home.get("build") == "2026-11-19.79.1",
                    str(home and home.get("build")),
                )
                anchored = home and (
                    home["position"] == "fixed"
                    or (home["position"] == "absolute" and home.get("slotPosition") == "fixed")
                )
                check(
                    f"{name}: bar is fixed, or absolute inside the fixed 100lvh slot, on Home cold load",
                    anchored,
                    str(home),
                )
                check(
                    f"{name}: bar bottom is flush with the {vh}px viewport on Home",
                    home and nearly(home["bottom"], vh) and nearly(home["height"], expected_h),
                    str(home),
                )
                check(
                    f"{name}: bar has no transform on Home",
                    home and (home["transform"] in ("none", "matrix(1, 0, 0, 1, 0, 0)")),
                    str(home and home["transform"]),
                )
                # Closet
                page.locator("#section-closet").click()
                page.wait_for_timeout(250)
                closet = bbox(page)
                check(
                    f"{name}: Home and Closet bar tops match",
                    home and closet and nearly(home["top"], closet["top"]) and nearly(home["bottom"], closet["bottom"]),
                    f"home={home} closet={closet}",
                )
                # Diagnostic on Profile → Cloud & backup
                page.locator("#tab-today").click()
                page.wait_for_timeout(150)
                # Profile is the masthead button, then Cloud & backup subtab
                prof = page.locator(".profile-btn, #tab-profile, [data-tab='pinfo'], [data-tab='pcloud']").first
                # Open profile via the masthead profile button if present
                pbtn = page.locator(".profile-btn")
                if pbtn.count():
                    pbtn.first.click()
                    page.wait_for_timeout(200)
                pcloud = page.locator("#tab-pcloud")
                if pcloud.count():
                    pcloud.first.click()
                    page.wait_for_timeout(250)
                diag = page.evaluate(
                    """() => {
                      const el = document.getElementById('nav-diag');
                      const st = document.getElementById('build-stamp');
                      const cs = el ? getComputedStyle(el) : null;
                      return {
                        stamp: st ? st.textContent : null,
                        stampDisplay: st ? getComputedStyle(st).display : null,
                        diag: el ? el.textContent : null,
                        diagHiddenAttr: !!(el && el.hidden),
                        diagDisplay: cs ? cs.display : null,
                        diagVisible: !!(el && cs && cs.display !== 'none' && cs.visibility !== 'hidden' && (el.offsetWidth || el.offsetHeight)),
                        pcloudShown: !!(document.getElementById('panel-pcloud') && !document.getElementById('panel-pcloud').hidden),
                      };
                    }"""
                )
                check(
                    f"{name}: Cloud & backup shows build stamp .71",
                    diag and "2026-11-19.79.1" in (diag.get("stamp") or ""),
                    str(diag),
                )
                check(
                    f"{name}: Cloud & backup build stamp is visible",
                    diag and diag.get("stampDisplay") not in (None, "none"),
                    str(diag),
                )
                check(
                    f"{name}: diagnostic line is hidden",
                    diag and (diag.get("diagHiddenAttr") or diag.get("diagDisplay") == "none") and not diag.get("diagVisible"),
                    str(diag),
                )
                # Screenshot bottoms for the report
                out = Path("/tmp/wardrobe-nav62")
                out.mkdir(parents=True, exist_ok=True)
                page.locator("#tab-today").click()
                page.wait_for_timeout(200)
                page.screenshot(path=str(out / f"{engine}-{name}-home.png"), full_page=False)
                page.locator("#section-closet").click()
                page.wait_for_timeout(200)
                page.screenshot(path=str(out / f"{engine}-{name}-closet.png"), full_page=False)
                ctx.close()
                return home, closet

            # Chromium viewports
            chrome = p.chromium.launch(channel="chrome") if False else p.chromium.launch()
            try:
                run_viewport(chrome, "390x844", 390, 844, dsf=2, inset=0)
                run_viewport(chrome, "390x844-inset34", 390, 844, dsf=2, inset=34)
                run_viewport(chrome, "402x874", 402, 874, dsf=3, inset=0)
                run_viewport(chrome, "402x874-inset34", 402, 874, dsf=3, inset=34)
            finally:
                chrome.close()

            # WebKit + iPhone device descriptors
            try:
                webkit = p.webkit.launch()
            except Exception as e:
                check("webkit launches", False, str(e))
                webkit = None
            if webkit:
                try:
                    devices = p.devices
                    for label, key, fallback in (
                        ("iphone15pro", "iPhone 15 Pro", {"viewport": {"width": 393, "height": 852}, "device_scale_factor": 3}),
                        ("iphone16pro", "iPhone 16 Pro", {"viewport": {"width": 402, "height": 874}, "device_scale_factor": 3}),
                    ):
                        dev = devices.get(key)
                        if dev:
                            ctx_kw = {k: v for k, v in dev.items() if k != "default_browser_type"}
                        else:
                            print(f"  (no Playwright device '{key}', using fallback viewport)")
                            ctx_kw = dict(
                                viewport=fallback["viewport"],
                                device_scale_factor=fallback["device_scale_factor"],
                                is_mobile=True,
                                has_touch=True,
                            )
                        ctx_kw["service_workers"] = "block"
                        ctx = webkit.new_context(**ctx_kw)
                        ctx.route(BLOCK, lambda route: route.abort())
                        page = ctx.new_page()
                        page.goto(url, wait_until="domcontentloaded")
                        page.add_style_tag(content=INSET_CSS)
                        page.wait_for_load_state("load")
                        page.wait_for_timeout(300)
                        vw = page.viewport_size["width"]
                        vh = page.viewport_size["height"]
                        home = bbox(page)
                        check(
                            f"webkit {label}+inset34: bar flush at bottom of {vh}px Home",
                            home and nearly(home["bottom"], vh) and nearly(home["height"], 102) and home["position"] in ("fixed", "absolute") and (home["position"]=="fixed" or home.get("slotPosition")=="fixed"),
                            str(home) + f" vh={vh}",
                        )
                        page.locator("#section-closet").click()
                        page.wait_for_timeout(250)
                        closet = bbox(page)
                        check(
                            f"webkit {label}+inset34: Home and Closet tops match",
                            home and closet and nearly(home["top"], closet["top"]),
                            f"home={home} closet={closet}",
                        )
                        out = Path("/tmp/wardrobe-nav62")
                        page.screenshot(path=str(out / f"webkit-{label}-closet.png"), full_page=False)
                        page.locator("#tab-today").click()
                        page.wait_for_timeout(200)
                        page.screenshot(path=str(out / f"webkit-{label}-home.png"), full_page=False)
                        ctx.close()
                finally:
                    webkit.close()
    finally:
        try:
            httpd.shutdown()
        except Exception:
            pass

    print()
    if failures:
        print(f"{len(failures)} failed:")
        for f in failures:
            print(" -", f)
        return 1
    print("All .62 nav checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
