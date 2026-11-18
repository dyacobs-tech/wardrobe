"""Full UI sweep for build .64.

Visits every top-level page and sub-tab at 375×812, 390×844, 430×932
and 1280×800. Records clipped tabs, horizontal overflow, overlaps,
inconsistent bottom-nav geometry, content under the nav, and console
errors. Writes screenshots and a 390 contact sheet under
/workspace/wardrobe-audit/sweep64/.

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/sweep64.py
"""
from __future__ import annotations

import http.server
import json
import os
import re
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path("/workspace/wardrobe-audit/sweep64")
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")

# (filename slug, click path). First click is a section/nav control;
# optional second is a subtab.
PAGES = [
    ("home", ["#tab-today"]),
    ("closet-closet", ["#section-closet", "#tab-wardrobe"]),
    ("closet-outfits", ["#section-closet", "#tab-looks"]),
    ("closet-watches", ["#section-closet", "#tab-watches"]),
    ("closet-today", ["#section-closet", "#tab-wearing"]),
    ("ideas-ideas", ["#section-ideas", "#tab-studio"]),
    ("ideas-outfits", ["#section-ideas", "#tab-outfitideas"]),
    ("ideas-icons", ["#section-ideas", "#tab-icons"]),
    ("ideas-palettes", ["#section-ideas", "#tab-palettes"]),
    ("ideas-myinspo", ["#section-ideas", "#tab-myinspo"]),
    ("shop-look", ["#tab-find", "#tab-shopmain"]),
    ("shop-brands", ["#tab-find", "#tab-brands"]),
    ("shop-sale", ["#tab-find", "#tab-sale"]),
    ("shop-wishlist", ["#tab-find", "#tab-shopwish"]),
    ("shop-purchased", ["#tab-find", "#tab-purchased"]),
    ("shop-receipts", ["#tab-find", "#tab-receipts"]),
    ("shop-search", ["#tab-find", "#tab-search"]),
    ("calendar", ["#section-calendar"]),
    ("profile-info", ["#tab-profile", "#tab-pinfo"]),
    ("profile-location", ["#tab-profile", "#tab-plocation"]),
    ("profile-cloud", ["#tab-profile", "#tab-pcloud"]),
]

VIEWPORTS = [
    (375, 812, 2, True),
    (390, 844, 2, True),
    (430, 932, 2, True),
    (1280, 800, 1, False),
]

INSPECT_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const vh = window.innerHeight;
  const issues = [];
  const nav = document.getElementById('bottombar');
  const navR = nav ? nav.getBoundingClientRect() : null;
  const navInfo = navR ? {
    top: navR.top, bottom: navR.bottom, height: navR.height,
    left: navR.left, right: navR.right,
    position: getComputedStyle(nav).position,
    transform: getComputedStyle(nav).transform,
  } : null;

  const docOverflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  const bodyOverflow = document.body.scrollWidth - document.body.clientWidth;
  if (docOverflow > 1) issues.push({kind: 'page-overflow', detail: 'documentElement +' + docOverflow});
  if (bodyOverflow > 1) issues.push({kind: 'page-overflow', detail: 'body +' + bodyOverflow});

  // Subnav tabs
  const subnav = document.getElementById('subnav');
  if (subnav && !subnav.hidden) {
    const group = subnav.querySelector('.subnav-group:not([hidden])');
    if (group) {
      const tabs = [...group.querySelectorAll('.subtab')].filter(t => t.id !== 'profile-close');
      if (tabs.length) {
        const tops = tabs.map(t => t.getBoundingClientRect().top);
        if (Math.max(...tops) - Math.min(...tops) > 3) {
          issues.push({kind: 'subnav-wrap', detail: group.id + ' tabs not on one row'});
        }
      }
      const active = group.querySelector('.subtab[aria-selected="true"]');
      if (active) {
        const r = active.getBoundingClientRect();
        if (r.left < -0.5 || r.right > vw + 0.5) {
          issues.push({kind: 'clipped-tab', detail: active.id + ' ' + Math.round(r.left) + '-' + Math.round(r.right) + ' vw=' + vw});
        }
      }
      const close = document.getElementById('profile-close');
      if (close && group.id === 'subnav-me') {
        const r = close.getBoundingClientRect();
        if (r.left < -0.5 || r.right > vw + 0.5) {
          issues.push({kind: 'clipped-tab', detail: 'profile-close cut off'});
        }
        const last = tabs[tabs.length - 1];
        if (last) {
          const lr = last.getBoundingClientRect();
          if (r.left < lr.right - 1) issues.push({kind: 'overlap', detail: 'profile × overlaps last tab'});
        }
      }
    }
  }

  function isVisible(el) {
    if (!el || el.nodeType !== 1) return false;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    if (r.bottom < 0 || r.top > vh || r.right < 0 || r.left > vw) return false;
    return true;
  }
  function isIntentionalScroll(el) {
    let n = el;
    while (n && n !== document.body && n !== document.documentElement) {
      const cs = getComputedStyle(n);
      const ox = cs.overflowX;
      if (ox === 'auto' || ox === 'scroll') return true;
      if (n.classList && (n.classList.contains('subnav-group') || n.classList.contains('subnav-scroll') || n.classList.contains('fb-chips'))) return true;
      n = n.parentElement;
    }
    return false;
  }
  function isChromeWrap(el) {
    return !!(el.closest && el.closest('.subnav, .navstack, .masthead, #bottombar'));
  }
  function isEllipsisClip(el) {
    const cs = getComputedStyle(el);
    return cs.textOverflow === 'ellipsis' || cs.webkitLineClamp && cs.webkitLineClamp !== 'none';
  }

  const seen = new Set();
  const walk = document.body.querySelectorAll('*');
  for (const el of walk) {
    if (!isVisible(el)) continue;
    // Horizontal overflow of the element's own content (clipped text/controls)
    if (!isIntentionalScroll(el) && !isChromeWrap(el) && !isEllipsisClip(el) && el.scrollWidth > el.clientWidth + 2) {
      const cs = getComputedStyle(el);
      // Only flag if the overflow is actually clipped or spills the page
      const r = el.getBoundingClientRect();
      const clips = (cs.overflowX === 'hidden' || cs.overflow === 'hidden') && (el.scrollWidth - el.clientWidth) > 4;
      const spills = r.right > vw + 1;
      if (clips || spills) {
        const key = (el.id || el.className || el.tagName).toString().slice(0, 80) + '@' + Math.round(r.top);
        if (!seen.has(key)) {
          seen.add(key);
          issues.push({
            kind: clips ? 'clipped-content' : 'h-overflow',
            detail: (el.id ? '#' + el.id : el.tagName + '.' + (el.className||'').toString().split(' ')[0]) +
                    ' sw=' + el.scrollWidth + ' cw=' + el.clientWidth + ' right=' + Math.round(r.right)
          });
        }
      }
    }
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1.5 && !isIntentionalScroll(el) && !isChromeWrap(el) && !el.closest('#bottombar')) {
      const key = 'spill:' + (el.id || el.className || el.tagName).toString().slice(0, 80);
      if (!seen.has(key)) {
        seen.add(key);
        issues.push({kind: 'h-overflow', detail: (el.id ? '#'+el.id : el.tagName) + ' extends to ' + Math.round(r.right) + ' of ' + vw});
      }
    }
  }

  // Content hidden behind the bottom nav (phone fixed bar only).
  // A card that merely peeks under the bar mid-scroll is fine if the
  // page can still scroll it fully above the bar. Only flag controls
  // that would remain covered even at maximum scroll.
  if (navR && getComputedStyle(nav).position === 'fixed' && navR.top < vh - 10 && navR.bottom > navR.top) {
    const hits = [];
    const scrollMax = Math.max(0, Math.max(document.documentElement.scrollHeight, document.body.scrollHeight) - vh);
    const candidates = document.querySelectorAll('main button, main a, main input, main select, main textarea, main [role="button"]');
    for (const el of candidates) {
      if (!isVisible(el)) continue;
      if (el.closest('#bottombar') || el.closest('.subnav') || el.closest('.masthead')) continue;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      const overlapH = Math.min(r.bottom, navR.top + navR.height) - Math.max(r.top, navR.top);
      if (overlapH > 8 && r.left < navR.right && r.right > navR.left) {
        const pos = cs.position;
        const bottomAtEnd = (pos === 'fixed' || pos === 'sticky') ? r.bottom : (r.bottom - scrollMax);
        if (bottomAtEnd > navR.top + 8) {
          hits.push((el.id ? '#'+el.id : el.tagName) + ' overlap ' + Math.round(overlapH) + 'px');
          if (hits.length >= 5) break;
        }
      }
    }
    if (hits.length) issues.push({kind: 'under-nav', detail: hits.join('; ')});
    // Bar should be flush with the viewport bottom on phone-sized layouts
    // (desktop restyles it to a top nav).
  }

  // Calendar week-strip count badges must never cover MON/TUE labels
  document.querySelectorAll('.wp-day').forEach(day => {
    const badge = day.querySelector('.wp-worn-count');
    const dow = day.querySelector('.wp-dow');
    if (!badge || !dow) return;
    const a = badge.getBoundingClientRect();
    const b = dow.getBoundingClientRect();
    const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (ox > 1 && oy > 1) {
      issues.push({kind: 'badge-overlap', detail: (dow.textContent||'').trim() + ' covered by count badge'});
    }
    if (dow.scrollWidth > dow.clientWidth + 1) {
      issues.push({kind: 'clipped-label', detail: 'day label clipped: ' + (dow.textContent||'').trim()});
    }
  });

  return {
    nav: navInfo,
    issues,
    title: document.title,
    hiddenSubnav: !!(subnav && subnav.hidden),
    shift: getComputedStyle(document.documentElement).getPropertyValue('--bb-shift').trim(),
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
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    OUT.mkdir(parents=True, exist_ok=True)
    httpd, url = start_static_server()
    all_issues: list[dict] = []
    shots_390: list[tuple[str, Path]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for vw, vh, dsf, is_mobile in VIEWPORTS:
                tag = f"{vw}x{vh}"
                ctx = browser.new_context(
                    viewport={"width": vw, "height": vh},
                    device_scale_factor=dsf,
                    is_mobile=is_mobile,
                    has_touch=is_mobile,
                    service_workers="block",
                )
                ctx.route(BLOCK, lambda route: route.abort())
                page = ctx.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
                page.on(
                    "console",
                    lambda m: errors.append(f"console.{m.type}: {m.text}")
                    if m.type == "error"
                    and "workers.dev" not in m.text
                    and "ERR_FAILED" not in m.text
                    and not m.text.startswith("Failed to load resource")
                    else None,
                )
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("load")
                page.wait_for_timeout(300)

                baseline_nav = None
                for slug, clicks in PAGES:
                    for sel in clicks:
                        loc = page.locator(sel)
                        if loc.count():
                            loc.first.click()
                            page.wait_for_timeout(180)
                    page.wait_for_timeout(120)
                    if slug == "calendar":
                        page.evaluate(
                            """() => {
                              function iso(d) {
                                var m = d.getMonth()+1, day = d.getDate();
                                return d.getFullYear() + '-' + (m<10?'0':'')+m + '-' + (day<10?'0':'')+day;
                              }
                              if (typeof planMonday !== 'function' || typeof wornLog === 'undefined') return;
                              var mon = planMonday(0);
                              var tue = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate()+1, 12);
                              var monIso = iso(mon), tueIso = iso(tue);
                              ['sweep-mon-0','sweep-mon-1'].forEach(function(id,i){
                                if (!wornLog.some(function(e){return e.id===id;}))
                                  wornLog.push({id:id, date:monIso, title:'Mon '+i, img:''});
                              });
                              ['sweep-tue-0','sweep-tue-1','sweep-tue-2'].forEach(function(id,i){
                                if (!wornLog.some(function(e){return e.id===id;}))
                                  wornLog.push({id:id, date:tueIso, title:'Tue '+i, img:''});
                              });
                              if (typeof store !== 'undefined') store.set('wornLog', wornLog);
                              if (typeof renderWeekPlan === 'function') renderWeekPlan();
                            }"""
                        )
                        page.wait_for_timeout(150)
                    info = page.evaluate(INSPECT_JS)
                    nav = info.get("nav")
                    if vw <= 899:
                        if baseline_nav is None:
                            baseline_nav = nav
                        elif nav and baseline_nav:
                            if not (
                                nearly(nav["top"], baseline_nav["top"])
                                and nearly(nav["bottom"], baseline_nav["bottom"])
                                and nearly(nav["height"], baseline_nav["height"])
                            ):
                                info["issues"].append({
                                    "kind": "nav-mismatch",
                                    "detail": f"nav {nav} != home/baseline {baseline_nav}",
                                })
                        if nav and not nearly(nav["bottom"], vh):
                            info["issues"].append({
                                "kind": "nav-lift",
                                "detail": f"bottom {nav['bottom']} vs vh {vh} height {nav['height']}",
                            })
                    # console errors accumulated so far for this context — attribute new ones to this page
                    # (we snapshot and clear? keep a cursor)
                    shot = OUT / f"{tag}-{slug}.png"
                    page.screenshot(path=str(shot), full_page=False)
                    if vw == 390:
                        shots_390.append((slug, shot))
                    page_errors = list(errors)
                    errors.clear()
                    for err in page_errors:
                        info["issues"].append({"kind": "console", "detail": err})
                    for iss in info["issues"]:
                        rec = {"viewport": tag, "page": slug, **iss}
                        all_issues.append(rec)
                        print(f"  ISSUE {tag} {slug}: {iss['kind']} — {iss['detail']}")
                    if not info["issues"]:
                        print(f"  ok {tag} {slug}")

                ctx.close()
            browser.close()
    finally:
        httpd.shutdown()

    # Contact sheet of 390 shots
    try:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            import sys
            sys.path.insert(0, "/usr/local/lib/python3.13/dist-packages")
            from PIL import Image, ImageDraw, ImageFont
        if shots_390:
            cols = 4
            thumbs = []
            label_h = 22
            tw, th = 195, 422
            for slug, path in shots_390:
                im = Image.open(path).convert("RGB")
                im = im.resize((tw, th), Image.Resampling.LANCZOS)
                thumbs.append((slug, im))
            rows = (len(thumbs) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * tw + 8, rows * (th + label_h) + 8), (28, 24, 18))
            draw = ImageDraw.Draw(sheet)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
            except Exception:
                font = ImageFont.load_default()
            for i, (slug, im) in enumerate(thumbs):
                r, c = divmod(i, cols)
                x, y = 4 + c * tw, 4 + r * (th + label_h)
                sheet.paste(im, (x, y + label_h))
                draw.text((x + 4, y + 4), slug, fill=(240, 230, 210), font=font)
            sheet_path = OUT / "contact-sheet-390.png"
            sheet.save(sheet_path, "PNG")
            print(f"wrote {sheet_path} ({sheet.size[0]}x{sheet.size[1]})")
    except Exception as e:
        print("contact sheet failed:", e)

    report = OUT / "issues.json"
    report.write_text(json.dumps(all_issues, indent=2), encoding="utf-8")
    print()
    print(f"{len(all_issues)} issue(s) across the sweep.")
    by_kind: dict[str, int] = {}
    for iss in all_issues:
        by_kind[iss["kind"]] = by_kind.get(iss["kind"], 0) + 1
    for k, n in sorted(by_kind.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3d} {k}")
    print(f"wrote {report}")
    return 0 if not all_issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
