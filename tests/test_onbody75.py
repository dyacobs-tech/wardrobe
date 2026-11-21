"""Build .75.1: David's on-body renders replace the flat-lay wherever an
outfit with a render is shown, and the flat-lay falls back to real photos.

Headless WebKit, iPhone size, all *.workers.dev traffic aborted.

1. assets/onbody/manifest.json is valid; every entry's file exists; the
   page knows every render synchronously at boot (ONBODY_SEED).
2. Home outfit of the day, with a closet whose pieces have renders, is
   dealt as a rendered outfit: #today-collage holds img[data-onbody] from
   assets/onbody/, it loads, and every piece is his own (non-seed) item.
3. Outfits > Mine: the "From your closet" feed shows on-body renders.
4. A closet with no rendered outfits falls back to a flat-lay of real
   photos: no on-body image and no colour-swatch cells.
5. The service worker caches renders cache-first in wardrobe-onbody-v3,
   kept across builds; the manifest is not in that cache.

Usage: PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 python tests/test_onbody75.py [base_url]
"""
from __future__ import annotations

import base64
import json
import random
import struct
import sys
import zlib
from pathlib import Path

from playwright.sync_api import sync_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))  # noqa: E402
from buildinfo import CURRENT_BUILD

ROOT = Path(__file__).resolve().parents[1]
BUILD = CURRENT_BUILD
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18975/"


def png_uri(seed: int) -> str:
    rnd = random.Random(seed)
    rgb = (rnd.randint(40, 220), rnd.randint(40, 220), rnd.randint(40, 220))
    w = h = 24
    raw = b"".join(b"\x00" + bytes(max(0, min(255, c + rnd.randint(-30, 30))) for _ in range(w) for c in rgb) for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


def items_with_photos(path: Path, prefix: str = "") -> list:
    items = json.loads(path.read_text())
    return [dict(i, id=prefix + i["id"], photo=png_uri(n), addedISO="2026-11-17") for n, i in enumerate(items)]


def seed(items) -> str:
    return ("(() => { if (!sessionStorage.getItem('seeded')) { localStorage.clear(); sessionStorage.setItem('seeded','1');"
            " localStorage.setItem('wardrobe.items', %s);"
            " localStorage.setItem('wardrobe.todaySource', JSON.stringify('wardrobe'));"
            " localStorage.setItem('wardrobe.formality', JSON.stringify(4)); } })();" % json.dumps(json.dumps(items)))


FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def main():
    man = json.loads((ROOT / "assets/onbody/manifest.json").read_text())
    files = [e["f"] for e in man["r"]]
    check(man.get("v") == 1 and len(man["r"]) == man.get("count") and len(man["r"]) >= 300, "manifest v1 with %d renders" % len(man["r"]))
    check(all((ROOT / "assets/onbody" / f).exists() for f in files), "every manifest file exists")
    check(all(e["k"] == "|".join(sorted(e["k"].split("|"))) for e in man["r"]), "keys are sorted composer keys")
    size = sum((ROOT / "assets/onbody" / f).stat().st_size for f in files)
    # Renders are cached on the phone only as they are viewed (sw.js
    # ONBODY_CACHE), never precached, so this budget guards the published
    # site, not the device. ~25 KB per render here, plus ~135 KB for its
    # cut-out and zoom copies: 40 MB is ~1,600 renders and keeps the whole
    # site well under the Pages size limit (checked below).
    check(size < 40 * 1024 * 1024, "render pool is %.1f MB (< 40 MB)" % (size / 1048576))
    # every cut-out has its zoom copy (Home prefetches it) and a placeholder
    cut = json.loads((ROOT / "assets/onbody-cut/manifest.json").read_text())["map"]
    lqm = json.loads((ROOT / "assets/onbody-cut/lq.json").read_text())["lq"]
    no_hq = [f for f in cut if not (ROOT / "assets/onbody-cut-hq" / f).exists()]
    no_lq = [f for f in cut if f[:-5] not in lqm]
    check(not no_hq, "every cut-out has a zoom copy (%d missing: %s)" % (len(no_hq), no_hq[:4]))
    check(not no_lq, "every cut-out has a placeholder (%d missing: %s)" % (len(no_lq), no_lq[:4]))
    site = sum(f.stat().st_size for f in (ROOT / "assets").rglob("*") if f.is_file())
    check(site < 900 * 1024 * 1024, "published assets are %.0f MB (< 900 MB)" % (site / 1048576))

    rendered = items_with_photos(ROOT / "tests/fixture_onbody.json")
    plain = items_with_photos(ROOT / "tests/fixture_closet83.json", prefix="x")
    errors = []
    with sync_playwright() as p:
        b = p.webkit.launch()

        def ctx_for(items):
            c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            c.route("**/*.workers.dev/**", lambda r: r.abort())
            c.add_init_script(seed(items))
            pg = c.new_page()
            pg.on("pageerror", lambda e: errors.append(str(e)))
            return c, pg

        # 1-3: rendered closet
        c, pg = ctx_for(rendered)
        pg.goto(BASE, wait_until="load")
        pg.wait_for_timeout(2500)
        # WebKit on CI can still be hydrating the hero's pieces at 2.5 s
        try:
            pg.wait_for_function("() => typeof todayLook !== 'undefined' && todayLook && (todayLook.fwPieces || []).length >= 3", timeout=10000)
        except Exception:
            pass
        allowed = pg.evaluate("""rows => rows.filter(e => !onbodyFileBanned(e.f) &&
          !onbodyKeyBanned866(e.k)).map(e => [e.k, 'assets/onbody/' + e.f])""", man["r"])
        mapped = pg.evaluate("Object.entries(onbodyKeys())")
        check(dict(mapped) == dict(allowed) and len(allowed) >= 300,
              "all %d eligible outfit photos are available" % len(allowed))
        home = pg.evaluate("""() => {
          const c = document.getElementById('today-collage');
          /* .78.2c: the Home hero is the render itself (#today-img), no collage */
          const im0 = document.getElementById('today-img'); const im = im0 && !im0.hidden && /\/onbody\//.test(im0.getAttribute('data-render') || im0.getAttribute('src') || '') ? im0 : null;
          const ids = (todayLook && todayLook.fwPieces || []).map(p => p.id);
          /* .84: built-in library pieces (his tees, polos) are his clothes; what
             must not appear is a piece that is not in his closet at all */
          const notMine = ids.filter(i => !(typeof closetItemById === 'function' && closetItemById(i))).length;
          return { src: im ? (im.getAttribute('data-render') || im.getAttribute('src')) : null, ok: im ? (im.complete && im.naturalWidth > 0) : false,
                   key: todayLook && todayLook.composerKey, ids, seed: notMine,
                   sw: c ? c.querySelectorAll('.fl-swatch').length : -1 };
        }""")
        check(bool(home["src"]) and home["src"].startswith("assets/onbody/"), "Home OOTD shows an on-body render (%s)" % home["src"])
        check(home["ok"], "the Home render loads")
        check(home["seed"] == 0 and len(home["ids"]) >= 3, "Home OOTD uses only pieces in his closet (%d pieces, %d not in it: %s)" % (len(home["ids"]), home["seed"], home["key"]))
        check(home["sw"] == 0, "no swatch cells on Home")
        pg.click("#section-ideas")
        pg.wait_for_timeout(300)
        pg.wait_for_selector("#cf-grid .mine-avatar")
        mine = pg.evaluate("""() => { const g = document.getElementById('cf-grid'); if (!g) return [0,0,0];
          return [g.querySelectorAll('.cf-card').length, g.querySelectorAll('.cf-card img[data-onbody]').length, g.querySelectorAll('.fl-swatch').length]; }""")
        check(mine[0] > 0 and mine[1] > 0, "Outfits > Mine shows on-body renders (%d of %d cards)" % (mine[1], mine[0]))
        check(mine[2] == 0, "no swatch cells in Mine")
        # 5: service worker caches renders (reload once so the SW controls the page)
        pg.wait_for_timeout(1500)
        pg.reload(wait_until="load")
        pg.wait_for_timeout(3000)
        sw = pg.evaluate("""async () => {
          const ctl = !!navigator.serviceWorker.controller;
          const has = await caches.has('wardrobe-onbody-v3');
          let webp = 0, man = 0;
          if (has) { const k = await (await caches.open('wardrobe-onbody-v3')).keys();
            webp = k.filter(r => /\/assets\/onbody(?:-cut)?\//.test(r.url) && r.url.endsWith('.webp')).length;
            man = k.filter(r => r.url.endsWith('manifest.json')).length; }
          return { ctl, has, webp, man };
        }""")
        check(sw["ctl"] and sw["has"] and sw["webp"] > 0, "SW caches renders in wardrobe-onbody-v3 (%d)" % sw["webp"])
        check(sw["man"] == 0, "manifest is not cache-first")
        swsrc = (ROOT / "sw.js").read_text()
        check("ONBODY_CACHE" in swsrc and "keep = [SHELL_CACHE, PHOTO_CACHE, ASSET_CACHE, ONBODY_CACHE" in swsrc, "render cache survives activate")
        c.close()

        # An unmatched closet opens on the explicit empty state.
        c, pg = ctx_for(plain)
        pg.goto(BASE, wait_until="load")
        pg.wait_for_selector('#today-hero.hero-empty861 .hero-empty861-box')
        check(pg.locator("#today-collage .fl-cell").count() == 0 and
              pg.locator("#today-hero [data-he861-level]").is_visible(),
              "an unmatched dress level offers another level without a misleading portrait")
        c.close()
        b.close()
    check(not errors, "no page errors %s" % errors[:3])
    print("ALL PASS" if not FAILS else "%d FAIL" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
