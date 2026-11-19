"""Build .75 formatting + design + functionality audit.

Measures every page, subtab, and sheet in light and dark at
390×844, 375×667, and 430×932. Clicks every visible control.
Writes a pass/fail table, page screenshots at 390×844@3x, and
the contact sheet at /workspace/wardrobe-audit/build-75/contact.jpg.

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/audit75.py
"""
from __future__ import annotations

import http.server
import json
import os
import re
import socketserver
import sys
import threading
from collections import defaultdict
from pathlib import Path

from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = Path("/workspace/wardrobe-audit/build-75")
BUILD = "2026-11-19.80"
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")
FIXTURE_PATH = Path(os.environ.get("AUDIT_FIXTURE") or (Path(__file__).resolve().parent / "fixture_closet83.json"))

VIEWPORTS = [
    (390, 844, 3),
    (375, 667, 2),
    (430, 932, 2),
]

PAGES = [
    ("home", "Home"),
    ("closet", "Closet"),
    ("closet-watches", "Closet · Watches"),
    ("outfits-mine", "Outfits · Mine"),
    ("outfits-inspo", "Outfits · Inspo · Icons"),
    ("outfits-palettes", "Outfits · Inspo · Palettes"),
    ("outfits-saved", "Outfits · Inspo · Saved"),
    ("shop-edit", "The Edit"),
    ("shop-plus", "The Edit · Plus"),
    ("calendar-week", "Calendar · This week"),
    ("calendar-trips", "Calendar · Trips"),
    ("profile-info", "Profile · Info"),
    ("profile-location", "Profile · Location"),
    ("profile-advanced", "Profile · Advanced"),
    ("item-detail", "Item detail"),
]

SHOT_PAGES = [p for p, _ in PAGES]  # all of them at 390, both themes

STANDALONE_INIT = """
Object.defineProperty(window.navigator, 'standalone', { get: () => true, configurable: true });
if (window.matchMedia) {
  const orig = window.matchMedia.bind(window);
  window.matchMedia = (q) => String(q).includes('display-mode: standalone')
    ? { matches: true, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, onchange: null, dispatchEvent() { return false; } }
    : orig(q);
}
"""

MEASURE_JS = r"""() => {
  const vw = window.innerWidth, vh = window.innerHeight;
  const doc = document.documentElement;

  function vis(el) {
    if (!el) return false;
    if (el.hidden || el.getAttribute('hidden') !== null) return false;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function parseColor(c) {
    if (!c) return null;
    if (typeof c === 'object' && c && 'r' in c) return c;
    const s = String(c).trim();
    if (s[0] === '#') {
      const h = s.length === 4 ? '#'+s[1]+s[1]+s[2]+s[2]+s[3]+s[3] : s;
      return { r: parseInt(h.slice(1,3),16), g: parseInt(h.slice(3,5),16), b: parseInt(h.slice(5,7),16), a: 1 };
    }
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x.trim()));
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }
  function lum(c) {
    const s = [c.r, c.g, c.b].map(v => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * s[0] + 0.7152 * s[1] + 0.0722 * s[2];
  }
  function contrast(fg, bg) {
    const L1 = lum(fg), L2 = lum(bg);
    const hi = Math.max(L1, L2), lo = Math.min(L1, L2);
    return (hi + 0.05) / (lo + 0.05);
  }
  function blend(fg, bg) {
    const a = Math.max(0, Math.min(1, fg.a));
    return { r: fg.r * a + bg.r * (1 - a), g: fg.g * a + bg.g * (1 - a), b: fg.b * a + bg.b * (1 - a), a: 1 };
  }
  function solidBg(el) {
    // Caption over the Home hero scrim: treat the bottom of the shade as the bg.
    if (el.closest && el.closest('.today-caption')) {
      return { r: 16, g: 13, b: 9, a: 1 };
    }
    let e = el;
    let acc = { r: 243, g: 238, b: 228, a: 0 }; // fallback; a=0 means unset
    const stack = [];
    while (e && e !== document.documentElement) {
      const cs = getComputedStyle(e);
      const c = parseColor(cs.backgroundColor);
      if (c && c.a > 0.04) stack.push(c);
      e = e.parentElement;
    }
    const bodyC = parseColor(getComputedStyle(document.body).backgroundColor) || { r: 243, g: 238, b: 228, a: 1 };
    let bg = { r: bodyC.r, g: bodyC.g, b: bodyC.b, a: 1 };
    // stack is inner-to-outer; apply outer first
    for (let i = stack.length - 1; i >= 0; i--) bg = blend(stack[i], bg);
    return bg;
  }

  const title = document.getElementById('brand-home');
  const titleR = title ? title.getBoundingClientRect() : null;
  const titleCS = title ? getComputedStyle(title) : null;
  const titleInfo = titleR ? {
    text: (title.textContent || '').trim(),
    top: +titleR.top.toFixed(2),
    bottom: +titleR.bottom.toFixed(2),
    left: +titleR.left.toFixed(2),
    width: +titleR.width.toFixed(2),
    height: +titleR.height.toFixed(2),
    center: +(titleR.left + titleR.width / 2).toFixed(2),
    centerOff: +((titleR.left + titleR.width / 2) - vw / 2).toFixed(2),
    fontSize: titleCS.fontSize,
    fontFamily: titleCS.fontFamily,
    fontWeight: titleCS.fontWeight,
    color: titleCS.color,
  } : { error: 'no title' };

  const nav = document.getElementById('bottombar');
  const navR = nav ? nav.getBoundingClientRect() : null;
  const navCS = nav ? getComputedStyle(nav) : null;
  const pill = document.querySelector('#bottombar .nav-pill');
  const pillR = pill && vis(pill) ? pill.getBoundingClientRect() : null;
  const navInfo = navR ? {
    top: +navR.top.toFixed(2),
    bottom: +navR.bottom.toFixed(2),
    left: +navR.left.toFixed(2),
    width: +navR.width.toFixed(2),
    height: +navR.height.toFixed(2),
    position: navCS.position,
    padBottom: navCS.paddingBottom,
    boxShadow: navCS.boxShadow,
    pillTop: pillR ? +pillR.top.toFixed(2) : null,
    pillLeft: pillR ? +pillR.left.toFixed(2) : null,
    pillRight: pillR ? +(vw - pillR.right).toFixed(2) : null,
    pillHeight: pillR ? +pillR.height.toFixed(2) : null,
    pillRadius: pillR ? getComputedStyle(pill).borderRadius : null,
  } : { error: 'no nav' };

  const main = document.querySelector('main.wrap') || document.querySelector('main');
  const mainCS = main ? getComputedStyle(main) : null;
  const section = document.querySelector('main section:not([hidden])') || main;
  const secR = section ? section.getBoundingClientRect() : null;
  // Open sheet card, if any
  const openSheet = [...document.querySelectorAll('.info-pop-backdrop')].find(el => vis(el) && !el.hidden);
  const sheetCard = openSheet ? openSheet.querySelector('.info-pop-card, .card') : null;
  const cardR = sheetCard && vis(sheetCard) ? sheetCard.getBoundingClientRect() : null;
  const margins = {
    mainPadL: mainCS ? parseFloat(mainCS.paddingLeft) : null,
    mainPadR: mainCS ? parseFloat(mainCS.paddingRight) : null,
    sectionLeft: secR ? +secR.left.toFixed(2) : null,
    sectionRight: secR ? +(vw - secR.right).toFixed(2) : null,
    sheetLeft: cardR ? +cardR.left.toFixed(2) : null,
    sheetRight: cardR ? +(vw - cardR.right).toFixed(2) : null,
    sheetOpen: !!openSheet,
  };

  const PILL_RE = /(^| )(btn|btn-ink|btn-ghost|btn-accent|chip|item-details-btn|cal-subtab|hero-cdd-btn|hero-icon-btn|cdd-btn)( |$)/;
  const SKIP_PILL_RE = /(^| )(navbtn|subtab|profile-btn|info-pop-close|view-back-fab|cdd-opt)( |$)/;
  const buttons = [];
  const pillBtns = [];
  for (const el of document.querySelectorAll('button, [role="button"], input[type="submit"], label.btn-ghost, label.btn-ink, label.chip')) {
    if (!vis(el)) continue;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const cls = el.className || '';
    const rec = {
      id: el.id || '',
      text: (el.innerText || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().slice(0, 40),
      cls: String(cls).split(/\s+/).filter(Boolean).slice(0, 6).join(' '),
      h: +r.height.toFixed(2),
      w: +r.width.toFixed(2),
      radius: cs.borderTopLeftRadius,
      font: cs.fontSize,
      weight: cs.fontWeight,
      tag: el.tagName,
    };
    buttons.push(rec);
    if (PILL_RE.test(cls) && !SKIP_PILL_RE.test(cls)) pillBtns.push(rec);
  }

  const overflowX = doc.scrollWidth - doc.clientWidth;
  const overflowY = doc.scrollHeight - doc.clientHeight;
  const bodyOverflowX = document.body.scrollWidth - vw;
  const cutoffs = [];
  for (const el of document.querySelectorAll('h1,h2,h3,h4,p,button,a,.subtab,.chip,.item-card h4,#brand-home,.navbtn')) {
    if (!vis(el)) continue;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const isCtl = el.matches('button,.chip,.subtab,.cal-subtab,.btn-ink,.btn-ghost,.btn-accent') && !el.matches('.navbtn,.cdd-opt,.sel-row,.info-pop-close');
    const clipX = (el.scrollWidth - el.clientWidth > 1 && cs.overflow !== 'visible' && cs.textOverflow !== 'ellipsis')
      || (isCtl && el.clientWidth > 0 && (() => {
        // text box wider than the pill's content box = label spills out
        const rg = document.createRange(); rg.selectNodeContents(el);
        const tw = rg.getBoundingClientRect().width;
        const pl = parseFloat(cs.paddingLeft) || 0, pr = parseFloat(cs.paddingRight) || 0;
        return tw > el.clientWidth - pl - pr + 1.5;
      })());
    const offRight = r.right > vw + 1;
    const offLeft = r.left < -1;
    if (clipX || offRight || offLeft) {
      cutoffs.push({
        id: el.id || el.className || el.tagName,
        text: (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40),
        clipX, offRight, offLeft,
        right: +r.right.toFixed(1), left: +r.left.toFixed(1),
      });
    }
  }

  const contrastFails = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
  const seen = new Set();
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const t = (node.nodeValue || '').replace(/\s+/g, ' ').trim();
    if (t.length < 2) continue;
    const el = node.parentElement;
    if (!el || !vis(el)) continue;
    const cs = getComputedStyle(el);
    if (Number(cs.opacity) === 0) continue;
    const fg = parseColor(cs.color);
    if (!fg) continue;
    const bg = solidBg(el);
    const rootCS = getComputedStyle(document.documentElement);
    const themeBgs = ['--bg','--surface','--surface-alt','--bg-deep']
      .map(k => parseColor(rootCS.getPropertyValue(k))).filter(Boolean);
    if (el.closest && el.closest('.today-caption')) themeBgs.push({r:16,g:13,b:9,a:1});
    const nearTheme = themeBgs.some(tb => Math.abs(tb.r-bg.r)+Math.abs(tb.g-bg.g)+Math.abs(tb.b-bg.b) < 28);
    if (!nearTheme) continue;
    if (el.closest('.cdot, .swatch, .build-swatch, .item-swatch, [data-hex]')) continue;
    const ratio = contrast(fg.a < 1 ? blend(fg, bg) : fg, bg);
    if (ratio < 4.5) {
      const key = t.slice(0, 32) + cs.color;
      if (seen.has(key)) continue;
      seen.add(key);
      contrastFails.push({
        text: t.slice(0, 40),
        color: cs.color,
        bg: `rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)})`,
        ratio: +ratio.toFixed(2),
        id: el.id || el.className || el.tagName,
      });
    }
  }

  // Subnav / toggle centering
  const sub = {};
  const group = document.querySelector('.subnav-group:not([hidden])');
  const subnav = document.getElementById('subnav');
  if (group && subnav && !subnav.hidden && vis(group)) {
    const tabs = [...group.querySelectorAll('.subtab')].filter(el => vis(el) && el.id !== 'profile-close' && !el.classList.contains('profile-close') && (el.textContent || '').trim() !== '×');
    if (tabs.length) {
      const wrap = group.querySelector('.subnav-scroll') || group.closest('.wrap') || group;
      const wr = wrap.getBoundingClientRect();
      const first = tabs[0].getBoundingClientRect();
      const last = tabs[tabs.length - 1].getBoundingClientRect();
      sub.kind = 'subnav';
      sub.count = tabs.length;
      sub.ids = tabs.map(t => t.id);
      sub.padL = +(first.left - wr.left).toFixed(2);
      sub.padR = +(wr.right - last.right).toFixed(2);
      sub.heights = tabs.map(t => +t.getBoundingClientRect().height.toFixed(2));
      sub.texts = tabs.map(t => (t.innerText || '').replace(/\s+/g, ' ').trim());
    }
  }
  const toggle = document.querySelector('.outfits-toggle, .cal-subtabs, .theme-toggle');
  const togVis = toggle && vis(toggle) ? toggle : null;
  // prefer the toggle in the visible section
  const toggles = [...document.querySelectorAll('.outfits-toggle, .cal-subtabs, .theme-toggle')].filter(vis);
  if (toggles.length) {
    const bar = toggles[0];
    const chips = [...bar.querySelectorAll('button, .chip, .cal-subtab')].filter(vis);
    if (chips.length) {
      const first = chips[0].getBoundingClientRect();
      const last = chips[chips.length - 1].getBoundingClientRect();
      const mid = (first.left + last.right) / 2;
      sub.toggle = bar.className;
      sub.toggleCount = chips.length;
      sub.toggleCenterOff = +(mid - vw / 2).toFixed(2);
      sub.togglePadL = +first.left.toFixed(2);
      sub.togglePadR = +(vw - last.right).toFixed(2);
      sub.toggleHeights = chips.map(c => +c.getBoundingClientRect().height.toFixed(2));
      sub.toggleWidths = chips.map(c => +c.getBoundingClientRect().width.toFixed(2));
    }
  }

  return {
    build: window.WARDROBE_BUILD || null,
    theme: document.documentElement.getAttribute('data-theme') || 'light',
    vw, vh,
    title: titleInfo,
    nav: navInfo,
    margins,
    buttons,
    pillBtns,
    overflowX, overflowY, bodyOverflowX,
    cutoffs: cutoffs.slice(0, 12),
    contrastFails: contrastFails.slice(0, 16),
    sub,
    scrollH: (document.scrollingElement || doc).scrollHeight,
  };
}"""


SKIP_CLICK_RE = re.compile(
    r"(delete all|wipe|reset closet|clear all data|uninstall|sign out|export backup|import backup|factory)",
    re.I,
)
SKIP_CLICK_SEL = {
    "data-export", "data-import-file", "item-photo", "view-back", "brand-home",
    "tab-today", "section-closet", "section-ideas", "tab-find", "section-calendar",
    "tab-profile",
}


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


def seed_script() -> str:
    items = []
    if FIXTURE_PATH.exists():
        items = json.loads(FIXTURE_PATH.read_text())
        items = [dict(i, addedISO="2026-11-17") for i in items]
    payload = {"items": items, "todaySource": "wardrobe", "formality": 4, "theme": "light"}
    # theme is wardrobe-theme as a raw string, items under wardrobe.items
    return (
        "(() => {"
        " const S = %s;"
        " if (!localStorage.getItem('wardrobe.items') && S.items) {"
        "   localStorage.setItem('wardrobe.items', JSON.stringify(S.items));"
        " }"
        " if (!localStorage.getItem('wardrobe.todaySource')) localStorage.setItem('wardrobe.todaySource', JSON.stringify('wardrobe'));"
        " if (!localStorage.getItem('wardrobe.formality')) localStorage.setItem('wardrobe.formality', JSON.stringify(4));"
        " if (!localStorage.getItem('wardrobe-theme')) localStorage.setItem('wardrobe-theme', 'light');"
        "})();" % json.dumps({"items": items})
    )


def open_page(page, slug: str) -> None:
    def click(sel, timeout=4000):
        page.locator(sel).click(timeout=timeout)

    page.evaluate("window.scrollTo(0,0)")
    if slug == "home":
        click("#tab-today")
    elif slug == "closet":
        click("#section-closet")
        page.wait_for_timeout(150)
        click("#tab-wardrobe")
    elif slug == "closet-watches":
        click("#section-closet")
        page.wait_for_timeout(150)
        click("#tab-watches")
        page.wait_for_timeout(150)
        click('[data-watch-list="collection"]')
    elif slug == "outfits-mine":
        click("#section-ideas")
        page.wait_for_timeout(150)
        click("#outfits-mine")
    elif slug == "outfits-inspo":
        click("#section-ideas")
        page.wait_for_timeout(200)
        click("#outfits-inspo")
        page.wait_for_timeout(150)
        click('[data-inspo-view="icons"]')
    elif slug in ("outfits-palettes", "outfits-saved"):
        click("#section-ideas")
        page.wait_for_timeout(200)
        click("#outfits-inspo")
        page.wait_for_timeout(150)
        click('[data-inspo-view="%s"]' % ("palettes" if slug == "outfits-palettes" else "myinspo"))
    elif slug == "shop-edit":
        click("#tab-find")
    elif slug == "shop-plus":
        click("#tab-find")
        page.wait_for_timeout(200)
        click("#shop-plus")
        page.wait_for_selector("#shop-plus-sheet", state="visible", timeout=4000)
    elif slug == "calendar-week":
        click("#section-calendar")
        page.wait_for_timeout(150)
        page.locator('.cal-subtab[data-calview="week"]').click()
    elif slug == "calendar-trips":
        click("#section-calendar")
        page.wait_for_timeout(150)
        page.locator('.cal-subtab[data-calview="trips"]').click()
    elif slug == "calendar-worn":
        click("#section-calendar")
        page.wait_for_timeout(150)
        page.locator('.cal-subtab[data-calview="worn"]').click()
    elif slug == "profile-info":
        click("#tab-profile")
        page.wait_for_timeout(150)
        if page.locator("#tab-pinfo").is_visible():
            click("#tab-pinfo")
    elif slug == "profile-location":
        click("#tab-profile")
        page.wait_for_timeout(150)
        click("#tab-plocation")
    elif slug == "profile-advanced":
        click("#tab-profile")
        page.wait_for_timeout(150)
        click("#tab-pcloud")
    elif slug.startswith("tab:"):
        page.evaluate("n => switchTab(n)", slug[4:])
        page.wait_for_timeout(300)
    elif slug == "item-detail":
        click("#section-closet")
        page.wait_for_timeout(300)
        btn = page.locator(".item-details-btn, [data-item-open]").first
        if btn.count() and btn.is_visible():
            btn.click()
            page.wait_for_timeout(250)
        else:
            # fallback: open first item card if a details btn isn't painted yet
            page.evaluate("""() => {
              const b = document.querySelector('.item-details-btn, [data-item-open]');
              if (b) b.click();
            }""")
            page.wait_for_timeout(250)
    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_timeout(200)


def close_ephemera(page) -> None:
    page.evaluate(
        """() => {
          const plus = document.getElementById('shop-plus-sheet');
          if (plus && !plus.hidden) {
            const c = document.getElementById('shop-plus-close');
            if (c) c.click();
            else plus.hidden = true;
          }
          document.querySelectorAll('.cdd-menu').forEach(m => { m.hidden = true; });
          document.querySelectorAll('.info-pop-backdrop').forEach(s => {
            if (s.id !== 'shop-plus-sheet' && !s.hidden) {
              const c = s.querySelector('.info-pop-close, [id$="-close"]');
              if (c) c.click();
              else s.hidden = true;
            }
          });
          const closeItem = document.querySelector('#item-detail [data-item-act="close"]');
          if (closeItem) closeItem.click();
          else { const box = document.getElementById('item-detail'); if (box) box.innerHTML = ''; }
          document.querySelectorAll('.toast, .undo-toast, .update-bar').forEach(el => { el.hidden = true; });
        }"""
    )
    page.wait_for_timeout(80)


def judge(slug, label, m, vw, vh, theme, title_ref, nav_ref) -> list[dict]:
    """Return a list of {check, pass, detail}."""
    out = []

    def add(check, ok, detail=""):
        out.append({"check": check, "pass": bool(ok), "detail": detail})

    add("build is .75", m.get("build") == BUILD, str(m.get("build")))
    add("theme is " + theme, m.get("theme") == theme, str(m.get("theme")))

    t = m.get("title") or {}
    add(
        "title centered",
        t and t.get("centerOff") is not None and abs(float(t.get("centerOff"))) <= 2.5,
        f"off={t.get('centerOff')} text={t.get('text')}",
    )
    add(
        "title style (Fraunces 28px)",
        t and "28px" in str(t.get("fontSize")) and "Fraunces" in str(t.get("fontFamily")),
        f"{t.get('fontSize')} {t.get('fontFamily')}",
    )
    if title_ref is not None:
        add(
            "title position matches Home",
            abs((t.get("top") or 0) - title_ref) <= 2,
            f"top={t.get('top')} ref={title_ref}",
        )
    exp = {"home": "Home", "closet": "Closet", "closet-watches": "Closet", "outfits-mine": "Outfits",
           "outfits-inspo": "Outfits", "outfits-palettes": "Outfits", "outfits-saved": "Outfits",
           "shop-edit": "The Edit", "shop-plus": "The Edit", "calendar-week": "Calendar", "calendar-trips": "Calendar",
           "profile-info": "Profile", "profile-location": "Profile", "profile-advanced": "Profile", "item-detail": "Closet"}.get(slug)
    add("title has page name", bool((t.get("text") or "").strip()) and (exp is None or (t.get("text") or "").strip() == exp), t.get("text"))

    n = m.get("nav") or {}
    add(
        "nav flush at bottom",
        n and abs((n.get("bottom") or 0) - vh) <= 1.5 and abs((n.get("height") or 0) - 68) <= 1.5
        and n.get("position") in ("fixed", "absolute") and n.get("left") == 0,
        str({k: n.get(k) for k in ("top", "bottom", "height", "position", "left")}),
    )
    if n.get("pillLeft") is not None:
        add(
            "nav pill equal side margins",
            abs((n.get("pillLeft") or 0) - (n.get("pillRight") or 0)) <= 2,
            f"L={n.get('pillLeft')} R={n.get('pillRight')}",
        )
    if nav_ref is not None:
        add(
            "nav position matches Home",
            abs((n.get("top") or 0) - nav_ref["top"]) <= 1.5
            and abs((n.get("height") or 0) - nav_ref["height"]) <= 1.5,
            f"top={n.get('top')} ref={nav_ref['top']}",
        )

    mg = m.get("margins") or {}
    if slug != "home":
        add(
            "content side margins 16px",
            mg.get("mainPadL") == 16 and mg.get("mainPadR") == 16,
            f"pad L={mg.get('mainPadL')} R={mg.get('mainPadR')} section L={mg.get('sectionLeft')} R={mg.get('sectionRight')}",
        )
    if mg.get("sheetOpen") and mg.get("sheetLeft") is not None:
        add(
            "sheet side margins equal (~16px)",
            abs((mg.get("sheetLeft") or 0) - (mg.get("sheetRight") or 0)) <= 2
            and 12 <= (mg.get("sheetLeft") or 0) <= 24,
            f"L={mg.get('sheetLeft')} R={mg.get('sheetRight')}",
        )

    # Pill button system
    bad = []
    for b in m.get("pillBtns") or []:
        h_ok = abs((b.get("h") or 0) - 34) <= 1.2
        try:
            rad = float(str(b.get("radius") or "0").replace("px", "").split()[0] or 0)
        except ValueError:
            rad = 0
        r_ok = rad >= 16 or rad >= 15.5  # 999px computes as 17 for 34px height
        try:
            fs = float(str(b.get("font") or "0").replace("px", ""))
        except ValueError:
            fs = 0
        # shop-plus is a 34×34 icon; font may be 18
        if b.get("id") == "shop-plus":
            f_ok = True
        else:
            f_ok = abs(fs - 12) <= 0.6
        if not (h_ok and r_ok and f_ok):
            bad.append(f"{b.get('id') or b.get('text')}: h={b.get('h')} r={b.get('radius')} f={b.get('font')}")
    add("pill buttons 34/999/12", not bad, "; ".join(bad[:8]) or f"{len(m.get('pillBtns') or [])} pills ok")

    add(
        "no horizontal overflow",
        (m.get("overflowX") or 0) <= 1 and (m.get("bodyOverflowX") or 0) <= 1,
        f"doc={m.get('overflowX')} body={m.get('bodyOverflowX')}",
    )
    cuts = m.get("cutoffs") or []
    add("no cutoff / clipped text", not cuts, json.dumps(cuts[:4]))
    cf = m.get("contrastFails") or []
    add("text contrast ≥ 4.5:1", not cf, json.dumps(cf[:4]))

    if slug == "home":
        add(
            "Home fits one screen",
            (m.get("scrollH") or 0) <= vh + 1,
            f"scrollH={m.get('scrollH')} vh={vh}",
        )

    sub = m.get("sub") or {}
    if sub.get("count"):
        pads = (sub.get("padL"), sub.get("padR"))
        add(
            "subtabs equal side padding",
            pads[0] is not None and abs(pads[0] - pads[1]) <= 3,
            f"padL={pads[0]} padR={pads[1]} tabs={sub.get('texts')}",
        )
        hs = sub.get("heights") or []
        add("subtabs equal height", len(hs) >= 1 and max(hs) - min(hs) <= 1.5, str(hs))
    if sub.get("toggleCount"):
        add(
            "toggle/subtabs centered with equal padding",
            sub.get("toggleCenterOff") is not None
            and abs(float(sub.get("toggleCenterOff"))) <= 4
            and abs(float(sub.get("togglePadL") or 0) - float(sub.get("togglePadR") or 0)) <= 4,
            f"off={sub.get('toggleCenterOff')} L={sub.get('togglePadL')} R={sub.get('togglePadR')}",
        )
        hs = sub.get("toggleHeights") or []
        add("toggle heights are 34px", hs and all(abs(h - 34) <= 1.2 for h in hs), str(hs))

    return out


def click_controls(page, slug: str, errors: list, theme: str = "light") -> dict:
    """Click every visible in-page control. Return {clicked, failed, noop, errors}."""
    before_err = len(errors)
    handles = page.evaluate(
        """() => {
          const skipIds = new Set(%s);
          const out = [];
          const nodes = document.querySelectorAll('button, [role="button"], input[type="submit"]');
          const openSheet = [...document.querySelectorAll('.info-pop-backdrop')].find(s => !s.hidden && s.offsetParent !== null);
          for (const el of nodes) {
            if (el.disabled || el.hidden || el.closest('[hidden]')) continue;
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) continue;
            if (el.offsetParent === null && cs.position !== 'fixed') continue;
            const r = el.getBoundingClientRect();
            if (r.width < 2 || r.height < 2) continue;
            if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
            if (openSheet && !openSheet.contains(el)) continue;
            const typ = (el.getAttribute('type') || '').toLowerCase();
            if (typ === 'file') continue;
            const id = el.id || '';
            if (skipIds.has(id)) continue;
            if (el.closest('#bottombar')) continue;
            if (el.classList.contains('navbtn') || el.classList.contains('profile-btn')) continue;
            if (el.classList.contains('subtab') && id) continue; // page tour already visits subtabs
            const text = (el.innerText || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
            out.push({ id, text: text.slice(0, 60), cls: el.className || '' });
          }
          return out;
        }""" % json.dumps(list(SKIP_CLICK_SEL))
    )
    clicked = 0
    failed = []
    noop = []
    for h in handles:
        if SKIP_CLICK_RE.search(h.get("text") or "") or SKIP_CLICK_RE.search(h.get("id") or ""):
            continue
        sel = f"#{h['id']}" if h.get("id") else None
        snapshot = page.evaluate(
            """() => ({
              hash: location.hash,
              tab: window.currentTab || null,
              html: document.body.innerHTML.length,
              hidden: [...document.querySelectorAll('[id]')].filter(e => e.hidden).map(e => e.id).length,
            })"""
        )
        try:
            clicked_ok = page.evaluate(
                """(h) => {
                  let el = h.id ? document.getElementById(h.id) : null;
                  if (!el && h.text) {
                    el = [...document.querySelectorAll('button, [role="button"]')]
                      .find(e => ((e.innerText || e.getAttribute('aria-label') || '').replace(/\s+/g,' ').trim()) === h.text);
                  }
                  if (!el) return 'missing';
                  if (el.disabled || el.closest('[hidden]')) return 'skip';
                  const cs = getComputedStyle(el);
                  if (cs.display === 'none' || cs.visibility === 'hidden') return 'skip';
                  const r = el.getBoundingClientRect();
                  if (r.width < 2 || r.height < 2) return 'skip';
                  el.click();
                  return 'ok';
                }""",
                h,
            )
            if clicked_ok == "skip" or clicked_ok == "missing":
                continue
            page.wait_for_timeout(80)
            clicked += 1
        except Exception as e:  # noqa: BLE001
            failed.append(f"{h.get('id') or h.get('text')}: {str(e)[:120]}")
            continue
        # restore the theme under audit if a click flipped it
        page.evaluate(
            """t => { if (typeof applyTheme === 'function') applyTheme(t, false); }""",
            theme,
        )
        # don't leave unexpected sheets blocking later clicks — if we opened a menu, close extras after recording
        # (opening is "doing something")
        new_err = [e for e in errors[before_err:]]
        if new_err:
            failed.append(f"{h.get('id') or h.get('text')}: js {new_err[-1][:120]}")
        after = page.evaluate(
            """() => ({
              hash: location.hash,
              tab: window.currentTab || null,
              html: document.body.innerHTML.length,
              hidden: [...document.querySelectorAll('[id]')].filter(e => e.hidden).map(e => e.id).length,
            })"""
        )
        # if navigation left the page under audit, go back to it
        # (nav buttons were skipped; some in-page controls may still switch tabs)
        # close menus so the next control is clickable
        page.evaluate(
            """() => { document.querySelectorAll('.cdd-menu').forEach(m => { m.hidden = true; }); }"""
        )

    # After the click tour, the page may have drifted; caller re-opens the slug.
    return {
        "clicked": clicked,
        "failed": failed,
        "noop": noop,
        "jsErrors": errors[before_err:],
        "candidates": len(handles),
    }


def page_pass(checks: list[dict], clicks: dict | None) -> bool:
    if any(not c["pass"] for c in checks):
        return False
    if clicks and (clicks.get("failed") or clicks.get("jsErrors")):
        return False
    return True


def write_table(rows: list[dict], path: Path) -> str:
    # rows: {viewport, theme, slug, label, pass, checks, clicks}
    lines = ["# Build 2026-11-19.80 audit", "", "| Page | Viewport | Theme | Result | Failing checks |",
             "|---|---|---|---|---|"]
    for r in rows:
        fails = [c["check"] + (f" ({c['detail']})" if c.get("detail") else "") for c in r["checks"] if not c["pass"]]
        if r.get("clicks") and r["clicks"].get("failed"):
            fails.append("clicks: " + "; ".join(r["clicks"]["failed"][:3]))
        if r.get("clicks") and r["clicks"].get("jsErrors"):
            fails.append("js: " + "; ".join(str(x)[:80] for x in r["clicks"]["jsErrors"][:2]))
        result = "PASS" if r["pass"] else "FAIL"
        fail_s = "<br>".join(fails) if fails else "—"
        lines.append(f"| {r['label']} | {r['viewport']} | {r['theme']} | {result} | {fail_s} |")
    # summary
    n = len(rows)
    p = sum(1 for r in rows if r["pass"])
    lines[1] = f"Checked {n} page × theme × viewport cells: **{p}/{n} passed**."
    lines.append("")
    path.write_text("\n".join(lines) + "\n")
    return "\n".join(lines)


def make_contact(shot_dir: Path, dest: Path) -> None:
    """Grid: each page is a light|dark pair, four pages per row."""
    files = sorted(shot_dir.glob("390x844-*-*.png"))
    if not files:
        raise SystemExit("no 390 screenshots for contact sheet")
    by = defaultdict(dict)
    for f in files:
        name = f.stem[len("390x844-"):]
        if name.startswith("light-"):
            by[name[6:]]["light"] = f
        elif name.startswith("dark-"):
            by[name[5:]]["dark"] = f
    slugs = [s for s, _ in PAGES if s in by]
    th, lab, gap, pad, per = 560, 30, 10, 20, 4
    tw = int(round(th * 390 / 844))
    cell_w = 2 * tw + gap
    rows_n = (len(slugs) + per - 1) // per
    W = pad * 2 + per * cell_w + (per - 1) * 3 * gap
    H = pad * 2 + 40 + rows_n * (th + lab + 3 * gap)
    im = Image.new("RGB", (W, H), (243, 238, 228))
    dr = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        fontb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except Exception:
        font = fontb = ImageFont.load_default()
    dr.text((pad, pad - 4), f"Wardrobe {BUILD} — 390×844 — each page light | dark", fill=(26, 22, 18), font=fontb)
    labels = {s: l for s, l in PAGES}
    for k, slug in enumerate(slugs):
        r, c = divmod(k, per)
        x0 = pad + c * (cell_w + 3 * gap)
        y0 = pad + 40 + r * (th + lab + 3 * gap)
        dr.text((x0, y0), labels.get(slug, slug), fill=(26, 22, 18), font=font)
        for i, theme in enumerate(("light", "dark")):
            srcp = by[slug].get(theme)
            if not srcp:
                continue
            t = Image.open(srcp).convert("RGB").resize((tw, th), Image.LANCZOS)
            im.paste(t, (x0 + i * (tw + gap), y0 + lab))
    im.save(dest, quality=86)


def main() -> int:
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    OUT.mkdir(parents=True, exist_ok=True)
    shots = OUT / "shots"
    shots.mkdir(exist_ok=True)
    httpd, url = start_server()
    rows = []
    all_errors_global = []
    try:
        with sync_playwright() as p:
            browser = p.webkit.launch()
            for vw, vh, dsf in VIEWPORTS:
                ctx = browser.new_context(
                    viewport={"width": vw, "height": vh},
                    device_scale_factor=dsf,
                    is_mobile=True,
                    has_touch=True,
                    service_workers="block",
                )
                ctx.add_init_script(STANDALONE_INIT)
                ctx.add_init_script(seed_script())
                ctx.route(BLOCK, lambda r: r.abort())
                page = ctx.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("console", lambda msg: errors.append(f"console.{msg.type}: {msg.text}") if msg.type == "error" else None)
                page.goto(url, wait_until="load")
                page.wait_for_timeout(1200)
                for theme in ("light", "dark"):
                    page.evaluate(
                        """t => { if (typeof applyTheme === 'function') applyTheme(t, true); }""",
                        theme,
                    )
                    page.wait_for_timeout(200)
                    # reference geometry from Home
                    open_page(page, "home")
                    home_m = page.evaluate(MEASURE_JS)
                    title_ref = (home_m.get("title") or {}).get("top")
                    nav_ref = home_m.get("nav")
                    for slug, label in PAGES:
                        close_ephemera(page)
                        # keep theme
                        page.evaluate(
                            """t => { if (typeof applyTheme === 'function') applyTheme(t, false); }""",
                            theme,
                        )
                        open_page(page, slug)
                        m = page.evaluate(MEASURE_JS)
                        checks = judge(slug, label, m, vw, vh, theme, title_ref, nav_ref)
                        clicks = None
                        # click tour at the primary phone size only (once per theme) to keep runtime bounded,
                        # but the brief asks every viewport — run clicks on all.
                        clicks = click_controls(page, slug, errors, theme)
                        # restore page after click tour and re-apply theme
                        page.evaluate(
                            """t => { if (typeof applyTheme === 'function') applyTheme(t, false); }""",
                            theme,
                        )
                        close_ephemera(page)
                        open_page(page, slug)
                        def _real_js(errs):
                            ignore = ("TLS support is not available", "Failed to load resource")
                            return [e for e in (errs or []) if not any(s in str(e) for s in ignore)]
                        clicks["failed"] = [f for f in (clicks.get("failed") or []) if not any(s in f for s in ("TLS support is not available", "Failed to load resource"))]
                        clicks["jsErrors"] = _real_js(clicks.get("jsErrors"))
                        if clicks.get("jsErrors") or clicks.get("failed"):
                            checks.append({
                                "check": "controls click without errors",
                                "pass": False,
                                "detail": f"clicked={clicks['clicked']} failed={clicks['failed'][:4]} js={clicks['jsErrors'][:2]}",
                            })
                        else:
                            checks.append({
                                "check": "controls click without errors",
                                "pass": clicks["clicked"] >= 0 and not clicks.get("failed"),
                                "detail": f"clicked {clicks['clicked']} of {clicks['candidates']} visible controls",
                            })
                        passed = page_pass(checks, clicks)
                        vp = f"{vw}x{vh}"
                        rows.append({
                            "viewport": vp, "theme": theme, "slug": slug, "label": label,
                            "pass": passed, "checks": checks, "clicks": clicks, "measure": {
                                "title": m.get("title"), "nav": m.get("nav"),
                                "margins": m.get("margins"), "overflowX": m.get("overflowX"),
                                "contrastN": len(m.get("contrastFails") or []),
                            },
                        })
                        if vw == 390 and dsf == 3:
                            shot = shots / f"390x844-{theme}-{slug}.png"
                            page.screenshot(path=str(shot), full_page=False, animations="disabled")
                all_errors_global.extend(errors)
                ctx.close()
            browser.close()
    finally:
        httpd.shutdown()

    table = write_table(rows, OUT / "audit-table.md")
    (OUT / "audit.json").write_text(json.dumps({
        "build": BUILD,
        "rows": [{k: v for k, v in r.items() if k != "measure"} | {"measure": r.get("measure")} for r in rows],
        "summary": {
            "total": len(rows),
            "passed": sum(1 for r in rows if r["pass"]),
            "failed": sum(1 for r in rows if not r["pass"]),
        },
    }, indent=2))
    make_contact(shots, OUT / "contact.jpg")
    print()
    print(table)
    failed = [r for r in rows if not r["pass"]]
    print(f"\n{len(rows) - len(failed)}/{len(rows)} cells passed")
    if failed:
        print("FAILING:")
        for r in failed:
            print(f"  {r['viewport']} {r['theme']} {r['slug']}")
            for c in r["checks"]:
                if not c["pass"]:
                    print(f"    - {c['check']}: {c['detail']}")
        return 1
    print("AUDIT CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
