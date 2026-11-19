"""Build .72 — computed styles are consistent across pages.

Every dropdown (Closet pills, Ideas source segments, native selects),
primary/secondary button, chip, text input and card uses the shared
design tokens. Closet's 34px / 999px-radius / 12px pill is canonical.
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
BUILD = "2026-11-19.78.2b"
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")
PAGES = [
    ("home", ["#tab-today"]),
    ("closet-closet", ["#section-closet", "#tab-wardrobe"]),
    ("closet-watches", ["#section-closet", "#tab-watches"]),
    ("outfits-mine", ["#section-ideas", "#outfits-mine"]),
    ("outfits-inspo", ["#section-ideas", "#outfits-inspo"]),
    ("shop-edit", ["#tab-find"]),
    ("calendar", ["#section-calendar"]),
    ("profile-info", ["#tab-profile", "#tab-pinfo"]),
    ("profile-location", ["#tab-profile", "#tab-plocation"]),
]
STANDALONE_INIT = """
Object.defineProperty(window.navigator, 'standalone', { get: () => true, configurable: true });
if (window.matchMedia) {
  const orig = window.matchMedia.bind(window);
  window.matchMedia = (q) => {
    if (String(q).includes('display-mode: standalone')) {
      return { matches: true, media: q, addListener() {}, removeListener() {},
        addEventListener() {}, removeEventListener() {}, onchange: null,
        dispatchEvent() { return false; } };
    }
    return orig(q);
  };
}
"""
COLLECT_JS = """() => {
  const visible = (sel) => [...document.querySelectorAll(sel)].filter((el) => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && !el.hidden
      && r.width > 0 && r.height > 0;
  });
  const pick = (el) => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      id: el.id || '',
      cls: (typeof el.className === 'string' ? el.className : '').slice(0, 80),
      h: Math.round(r.height * 10) / 10,
      radius: cs.borderRadius,
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      fontFamily: cs.fontFamily.split(',')[0].replace(/['\"]/g, '').trim(),
      borderW: cs.borderTopWidth,
      borderStyle: cs.borderTopStyle,
      borderColor: cs.borderTopColor,
      padding: cs.padding,
      color: cs.color,
      bg: cs.backgroundColor,
    };
  };
  return {
    build: window.WARDROBE_BUILD || null,
    closetPill: visible('.closet-cat-btn, .closet-add-btn').map(pick),
    cdd: visible('.cdd-btn:not(.hero-cdd-btn):not(.hero-corner-btn)').map(pick),
    sourceSeg: visible('.source-seg button, #ideas-source-seg button').map(pick),
    select: visible('select').map(pick),
    primary: visible('.btn-accent, .btn-ink').map(pick),
    secondary: visible('.btn-ghost').map(pick),
    chip: visible('.chip').map(pick),
    input: visible('input[type=text], input[type=search], input[type=url], input:not([type])').map(pick),
    card: visible('.card, .sale-card, .item-card, .find-card, .data-card, .link-card, #link-card').map(pick),
    title: visible('h2, h3, .fav-head, .item-card h4').slice(0, 6).map(pick),
    infoBtns: visible('.info-btn, .info-pop-backdrop, #info-pop, #icons-info-pop').length,
  };
}"""


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


def key_geom(s):
    return (round(s["h"]), s["radius"].split()[0] if s["radius"] else s["radius"], s["fontSize"])


def unique(rows, proj):
    seen = {}
    for slug, item in rows:
        k = proj(item)
        seen.setdefault(k, []).append(f"{slug}:{item.get('id') or item.get('cls')}")
    return seen


def assert_one(kind, rows, proj, msg=None):
    if not rows:
        raise AssertionError(f"{kind}: no samples collected")
    seen = unique(rows, proj)
    if len(seen) != 1:
        detail = "\n".join(f"  {k} -> {v[:8]}" for k, v in seen.items())
        raise AssertionError(msg or f"{kind} has {len(seen)} variants:\n{detail}")


def test_design_tokens_consistent():
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    httpd, url = start_server()
    records = []
    try:
        with sync_playwright() as p:
            browser = p.webkit.launch()
            ctx = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                service_workers="block",
            )
            ctx.add_init_script(STANDALONE_INIT)
            ctx.route(BLOCK, lambda route: route.abort())
            page = ctx.new_page()
            page.goto(url, wait_until="load")
            page.wait_for_timeout(250)
            for slug, clicks in PAGES:
                for sel in clicks:
                    page.locator(sel).click()
                    page.wait_for_timeout(160)
                info = page.evaluate(COLLECT_JS)
                info["slug"] = slug
                records.append(info)
            ctx.close()
            browser.close()
    finally:
        httpd.shutdown()

    builds = {r["build"] for r in records}
    assert builds == {BUILD}, f"build stamp {builds}"
    assert all(r["infoBtns"] == 0 for r in records), "info buttons / help popovers still present"

    def gather(kind):
        out = []
        for r in records:
            for item in r.get(kind) or []:
                out.append((r["slug"], item))
        return out

    pills = gather("closetPill") + gather("cdd") + gather("sourceSeg") + gather("select")
    # Canonical Closet pill geometry
    assert_one(
        "dropdowns",
        pills,
        lambda s: (round(s["h"]), s["radius"].split()[0], s["fontSize"]),
        "dropdowns/selects/Ideas segments must all match the Closet 34px / 999px / 12px pill",
    )
    # Confirm canonical numbers
    sample = pills[0][1]
    assert round(sample["h"]) == 34, f"canonical height {sample['h']}, expected 34"
    assert sample["radius"].split()[0] == "999px", f"canonical radius {sample['radius']}, expected 999px"
    assert sample["fontSize"] == "12px", f"canonical font {sample['fontSize']}, expected 12px"

    prim = gather("primary")
    sec = gather("secondary")
    assert_one("primary buttons", prim, lambda s: (round(s["h"]), s["radius"].split()[0], s["fontSize"]))
    assert_one("secondary buttons", sec, lambda s: (round(s["h"]), s["radius"].split()[0], s["fontSize"]))
    # Primary and secondary share geometry with the pill
    p0, s0 = prim[0][1], sec[0][1]
    assert (round(p0["h"]), p0["radius"].split()[0], p0["fontSize"]) == (34, "999px", "12px")
    assert (round(s0["h"]), s0["radius"].split()[0], s0["fontSize"]) == (34, "999px", "12px")

    chips = gather("chip")
    assert_one("chips", chips, lambda s: (round(s["h"]), s["radius"].split()[0], s["fontSize"]))
    c0 = chips[0][1]
    assert (round(c0["h"]), c0["radius"].split()[0], c0["fontSize"]) == (34, "999px", "12px")

    inputs = gather("input")
    assert_one("inputs", inputs, lambda s: (round(s["h"]), s["radius"].split()[0], s["fontSize"]))
    i0 = inputs[0][1]
    assert round(i0["h"]) == 34, f"input height {i0['h']}"
    assert i0["radius"].split()[0] == "999px", f"input radius {i0['radius']}"
    assert i0["fontSize"] == "16px", f"input font {i0['fontSize']}"

    cards = gather("card")
    assert_one("card radius", cards, lambda s: (s["radius"].split()[0], s["borderStyle"], s["borderW"]))
    k0 = cards[0][1]
    assert k0["radius"].split()[0] == "16px", f"card radius {k0['radius']}"
    assert k0["borderStyle"] == "solid" and k0["borderW"] == "1px", f"card border {k0['borderW']} {k0['borderStyle']}"

    titles = [item for slug, item in gather("title") if item["fontFamily"] and "masthead" not in item["cls"] and item["cls"] != "brand" and "page-title" not in item["cls"] and "item-name" not in item["cls"]]
    # Build .75: Closet product-card names (.item-name) are the Vesper 15px card style, not section titles.
    # Section / card titles are Fraunces 20px / 600; the masthead wordmark
    # and the large #page-title are excluded from the 20px check.
    display = [t for t in titles if any(n in t["fontFamily"] for n in ("Fraunces", "Libre", "Times", "Georgia"))]
    if display:
        sizes = {t["fontSize"] for t in display}
        weights = {t["fontWeight"] for t in display}
        assert sizes == {"20px"}, f"title sizes {sizes}"
        assert "600" in weights or "bold" in {str(w) for w in weights}, f"title weights {weights}"


if __name__ == "__main__":
    test_design_tokens_consistent()
    print("test_design72 ok")
