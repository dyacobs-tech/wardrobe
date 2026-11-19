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
5. The service worker caches renders cache-first in wardrobe-onbody-v1,
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

ROOT = Path(__file__).resolve().parents[1]
BUILD = "2026-11-19.78.5"
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
    check(size < 12 * 1024 * 1024, "render pool is %.1f MB (< 12 MB)" % (size / 1048576))

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
        n = pg.evaluate("Object.keys(ONBODY.map).length")
        check(n >= len(man["r"]), "page knows %d renders at boot" % n)
        home = pg.evaluate("""() => {
          const c = document.getElementById('today-collage');
          /* .78.2c: the Home hero is the render itself (#today-img), no collage */
          const im0 = document.getElementById('today-img'); const im = im0 && !im0.hidden && /\/onbody\//.test(im0.getAttribute('src') || '') ? im0 : null;
          const ids = (todayLook && todayLook.fwPieces || []).map(p => p.id);
          return { src: im ? im.getAttribute('src') : null, ok: im ? (im.complete && im.naturalWidth > 0) : false,
                   key: todayLook && todayLook.composerKey, ids, seed: ids.filter(i => String(i).indexOf('seed-') === 0).length,
                   sw: c ? c.querySelectorAll('.fl-swatch').length : -1 };
        }""")
        check(bool(home["src"]) and home["src"].startswith("assets/onbody/"), "Home OOTD shows an on-body render (%s)" % home["src"])
        check(home["ok"], "the Home render loads")
        check(home["seed"] == 0 and len(home["ids"]) >= 3, "Home OOTD uses only his own pieces")
        check(home["sw"] == 0, "no swatch cells on Home")
        pg.click("#section-ideas")
        pg.wait_for_timeout(300)
        pg.click("#outfits-mine")
        pg.wait_for_timeout(1500)
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
          const has = await caches.has('wardrobe-onbody-v1');
          let webp = 0, man = 0;
          if (has) { const k = await (await caches.open('wardrobe-onbody-v1')).keys();
            webp = k.filter(r => r.url.includes('/assets/onbody/') && r.url.endsWith('.webp')).length;
            man = k.filter(r => r.url.endsWith('manifest.json')).length; }
          return { ctl, has, webp, man };
        }""")
        check(sw["ctl"] and sw["has"] and sw["webp"] > 0, "SW caches renders in wardrobe-onbody-v1 (%d)" % sw["webp"])
        check(sw["man"] == 0, "manifest is not cache-first")
        swsrc = (ROOT / "sw.js").read_text()
        check("ONBODY_CACHE" in swsrc and "keep = [SHELL_CACHE, PHOTO_CACHE, ASSET_CACHE, ONBODY_CACHE]" in swsrc, "render cache survives activate")
        c.close()

        # 4: no renders for this closet -> photo flat-lay
        c, pg = ctx_for(plain)
        pg.goto(BASE, wait_until="load")
        pg.wait_for_timeout(2500)
        fl = pg.evaluate("""() => { const c = document.getElementById('today-collage'), im = document.getElementById('today-img');
          return { tiles: c && !c.hidden ? c.querySelectorAll('.fl-cell').length : 0, img: !!(im && !im.hidden && im.getAttribute('src')), ob: /\/onbody\//.test(im.getAttribute('src') || '') }; }""")
        check(fl["tiles"] == 0 and fl["img"] and not fl["ob"], "fallback: no render, so the hero shows a photo, never a tile grid (%s)" % fl)
        c.close()
        b.close()
    check(not errors, "no page errors %s" % errors[:3])
    print("ALL PASS" if not FAILS else "%d FAIL" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
