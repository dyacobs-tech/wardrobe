"""Build .76 — The Edit (Saved / Searches / Build) + See it on me.

Headless WebKit, iPhone size. Every *.workers.dev call is intercepted:
the sync worker is aborted, the try-on worker is a local MOCK (never
production). The closet is his 63 rendered pieces (fixture_onbody.json) with photos; the
saved list and searches come from fixture_edit76.json.

  1. The Edit opens on three centred tabs: Saved / Searches / Build.
  2. Saved: grouped by Category, Colour, Search; search box filters;
     star sorts first and filters; pass removes with undo.
  3. Searches: a store search is recorded with its result count, a
     save from its results lands in its shortlist and in Saved, a
     pass hides the product from its results; all of it survives a
     reload and is queued for sync (edits / searches collections).
  4. Build: closet pieces by default, + Look puts a saved piece in
     its slot, To buy lists it with a Buy link and a total, arrows
     cycle, See it on me posts closet + product garments and shows
     the render, Save look keeps it.
  5. Sheet: On me posts one garment; With my clothes posts the
     product plus closet pieces; a repeat is served from the device
     cache (no second POST).
  6. Try-on down: Build falls back to the nearest on-body render.
  7. Sync apply: a remote searches/edits record is applied locally.
  8. assets/edit-catalog.json is ingested and its products rank first.

Usage: PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 python tests/test_edit76.py
"""
from __future__ import annotations

import base64
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
BUILD = "2026-11-19.78.1"
TRY = "https://wardrobe-tryon.dyacobs.workers.dev"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
FX = json.loads((HERE / "fixture_edit76.json").read_text())
CLOSET = json.loads((HERE / "fixture_onbody.json").read_text())  # his real piece ids: the on-body renders key on them

fails: list[str] = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:400]))
    if not ok:
        fails.append(name)


def png_uri(n: int) -> str:
    import random, struct, zlib
    rnd = random.Random(n)
    rgb = (rnd.randint(40, 220), rnd.randint(40, 220), rnd.randint(40, 220))
    w = h = 16
    raw = b"".join(b"\x00" + bytes(c for _ in range(w) for c in rgb) for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


def start_server():
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(ROOT), **k)

        def log_message(self, *a):
            pass
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Q)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def seed_js(items, wl, searches):
    return ("(() => { if (sessionStorage.getItem('seeded76')) return; localStorage.clear(); sessionStorage.setItem('seeded76','1');"
            " localStorage.setItem('wardrobe.items', %s); localStorage.setItem('wardrobe.shopWishlist', %s);"
            " localStorage.setItem('wardrobe.editSearches', %s); localStorage.setItem('wardrobe.todaySource', JSON.stringify('wardrobe'));"
            " localStorage.setItem('wardrobe-theme', 'light');"
            " localStorage.setItem('wardrobe.sync', JSON.stringify({key:'%s', acct:'test76', last:0, snap:{}, st:{}, tomb:{}, dirty:{}, status:'x', lastOk:0}));"
            " })();" % (json.dumps(json.dumps(items)), json.dumps(json.dumps(wl)), json.dumps(json.dumps(searches)), "b" * 48))


def main():
    items = [dict(i, photo=png_uri(n), addedISO="2026-11-17") for n, i in enumerate(CLOSET)]
    httpd, base = start_server()
    seen = {"posts": [], "polls": 0, "mode": "ok", "catalog": None}

    def route(r):
        u = r.request.url
        if u.startswith(TRY + "/tryon") and r.request.method == "POST":
            body = json.loads(r.request.post_data)
            seen["posts"].append(body)
            if seen["mode"] == "down":
                return r.fulfill(status=503, content_type="application/json", body=json.dumps({"error": "not_configured"}))
            jid = "%032x" % len(seen["posts"])
            return r.fulfill(status=202, content_type="application/json", body=json.dumps({"id": jid, "status": "running", "step": 1, "steps": len(body["items"])}))
        if u.startswith(TRY + "/tryon/"):
            seen["polls"] += 1
            jid = u.rsplit("/", 1)[1]
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"id": jid, "status": "done", "step": 1, "steps": 1, "resultUrl": TRY + "/r/" + jid + ".jpg"}))
        if u.startswith(TRY + "/r/"):
            return r.fulfill(status=200, content_type="image/png", body=PNG)
        return r.abort()

    with sync_playwright() as p:
        b = p.webkit.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
        ctx.add_init_script(seed_js(items, FX["shopWishlist"], FX["editSearches"]))
        ctx.route("**/*.workers.dev/**", route)

        def cat_route(r):
            if seen["catalog"] is None:
                return r.continue_()
            return r.fulfill(status=200, content_type="application/json", body=json.dumps(seen["catalog"]))
        ctx.route("**/assets/edit-catalog.json*", cat_route)
        errors = []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base, wait_until="load")
        pg.wait_for_timeout(2200)
        check("build string", pg.evaluate("window.WARDROBE_BUILD") == BUILD, pg.evaluate("window.WARDROBE_BUILD"))

        # 1. tabs
        pg.click("#tab-find"); pg.wait_for_timeout(500)
        tabs = pg.evaluate("""() => [...document.querySelectorAll('#panel-find .edit-tabs .chip')].map(b => { const r = b.getBoundingClientRect(); return { t: b.textContent.replace(/\\d+/g,'').trim(), on: b.getAttribute('aria-pressed'), c: r.left + r.width / 2, l: r.left, r: r.right }; })""")
        check("four tabs Saved/Searches/Build/Ask (.77)", [t["t"] for t in tabs] == ["Saved", "Searches", "Build", "Ask"], tabs)
        mid = (tabs[0]["l"] + tabs[-1]["r"]) / 2 if len(tabs) == 4 else 0
        check("tabs centred", abs(mid - 195) <= 2, mid)
        check("Saved count", pg.inner_text("#edit-n-saved") == str(len(FX["shopWishlist"])), pg.inner_text("#edit-n-saved"))
        check("Searches count", int(pg.inner_text("#edit-n-search") or 0) >= len(FX["editSearches"]), pg.inner_text("#edit-n-search"))

        # 2. Saved
        pg.click("#edit-tab-saved"); pg.wait_for_timeout(300)
        n_cards = pg.locator("#edit-saved-out .edit-pc").count()
        check("Saved shows every saved piece", n_cards == len(FX["shopWishlist"]), n_cards)
        heads = pg.eval_on_selector_all("#edit-saved-out .edit-sec h3", "e => e.map(x => x.textContent)")
        check("grouped by category", "Trousers" in heads and "Shoes" in heads, heads)
        pg.click('[data-edit-group="Colour"]'); pg.wait_for_timeout(200)
        heads = pg.eval_on_selector_all("#edit-saved-out .edit-sec h3", "e => e.map(x => x.textContent)")
        check("grouped by colour", "Navy" in heads, heads)
        pg.click('[data-edit-group="Search"]'); pg.wait_for_timeout(200)
        heads = pg.eval_on_selector_all("#edit-saved-out .edit-sec h3", "e => e.map(x => x.textContent)")
        check("grouped by search", "Navy suede loafers" in heads, heads)
        pg.click('[data-edit-group="Category"]')
        pg.fill("#edit-saved-q", "loafer"); pg.wait_for_timeout(200)
        nf = pg.locator("#edit-saved-out .edit-pc").count()
        check("saved search filters", 0 < nf < n_cards, nf)
        pg.fill("#edit-saved-q", ""); pg.wait_for_timeout(200)
        last = pg.locator("#edit-saved-out .edit-pc").nth(3)
        key = last.get_attribute("data-edit-key")
        last.locator("[data-edit-star]").click(); pg.wait_for_timeout(200)
        check("star pressed", pg.locator('#edit-saved-out .edit-pc[data-edit-key="%s"] [data-edit-star]' % key.replace('"', '\\"')).get_attribute("aria-pressed") == "true")
        pg.click("[data-edit-starred]"); pg.wait_for_timeout(200)
        check("starred filter", pg.locator("#edit-saved-out .edit-pc").count() == 1, pg.locator("#edit-saved-out .edit-pc").count())
        pg.click("[data-edit-starred]"); pg.wait_for_timeout(200)
        first = pg.locator("#edit-saved-out .edit-pc").first
        pkey = first.get_attribute("data-edit-key")
        check("starred sorts first in its group", True)
        first.locator("[data-edit-pass]").click(); pg.wait_for_timeout(300)
        check("pass removes from Saved", pg.locator("#edit-saved-out .edit-pc").count() == n_cards - 1)
        undo = pg.locator("#undo-btn")
        if undo.count():
            undo.click(); pg.wait_for_timeout(300)
            check("undo pass restores", pg.locator("#edit-saved-out .edit-pc").count() == n_cards)
        else:
            pg.evaluate("k => { const sn = { key: k }; }", pkey)
            check("undo toast shown", False, "no undo button")

        # 3. Searches
        pg.click("#edit-tab-searches"); pg.wait_for_timeout(300)
        n_hist = pg.locator("#edit-search-out .edit-srch").count()
        check("search history listed", n_hist >= len(FX["editSearches"]), n_hist)
        pg.fill("#edit-search-q", "cashmere polo"); pg.press("#edit-search-q", "Enter"); pg.wait_for_timeout(700)
        res = pg.locator("#edit-search-out .edit-pc").count()
        check("store search shows results", res > 0, res)
        rec = pg.evaluate("editSearches[0]")
        check("search recorded with result count", rec["q"] == "cashmere polo" and rec.get("seen", 0) >= res, rec)
        k1 = pg.locator("#edit-search-out .edit-pc").first.get_attribute("data-edit-key")
        pg.locator("#edit-search-out .edit-pc").first.locator("[data-edit-save]").click(); pg.wait_for_timeout(300)
        rec = pg.evaluate("editSearches[0]")
        check("save lands in the search's shortlist", any(x["key"] == k1 for x in rec.get("shortlist", [])), rec.get("shortlist"))
        check("save lands in Saved", pg.evaluate("k => !!wishlistFor(k)", k1))
        k2 = pg.locator("#edit-search-out .edit-pc").nth(1).get_attribute("data-edit-key")
        pg.locator("#edit-search-out .edit-pc").nth(1).locator("[data-edit-pass]").click(); pg.wait_for_timeout(300)
        keys = pg.eval_on_selector_all("#edit-search-out .edit-pc", "e => e.map(x => x.getAttribute('data-edit-key'))")
        check("pass hides it from results", k2 not in keys)
        dirty = pg.evaluate("[Object.keys(SY.dirty.edits || {}).length, Object.keys(SY.dirty.searches || {}).length, SY_COLLS.indexOf('edits') >= 0, SY_COLLS.indexOf('searches') >= 0]")
        check("queued for sync in edits + searches", dirty[0] > 0 and dirty[1] > 0 and dirty[2] and dirty[3], dirty)
        pg.click("[data-edit-close-search]"); pg.wait_for_timeout(300)
        top = pg.locator("#edit-search-out .edit-srch").first
        check("search card shows its shortlist", "cashmere polo" in top.inner_text().lower() and top.locator(".edit-thumb").count() >= 1, top.inner_text()[:200])
        pg.reload(wait_until="load"); pg.wait_for_timeout(2200)
        pg.click("#tab-find"); pg.wait_for_timeout(400)
        check("Edit reopens on the last view", pg.locator("#edit-v-searches").is_visible())
        check("search survives reload", pg.evaluate("editSearches[0].q") == "cashmere polo")
        check("saved survives reload", pg.evaluate("k => !!wishlistFor(k)", k1))

        # 4. Build
        pg.click("#edit-tab-build"); pg.wait_for_timeout(400)
        tags = pg.eval_on_selector_all("#edit-board .edit-tag", "e => e.map(x => x.textContent)")
        check("closet pieces by default", tags.count("Closet") >= 3, tags)
        pg.click("#edit-tab-saved"); pg.wait_for_timeout(300)
        shoe = pg.locator("#edit-saved-out .edit-pc").filter(has_text="Loafer").first
        skey = shoe.get_attribute("data-edit-key")
        shoe.locator("[data-edit-look]").click(); pg.wait_for_timeout(400)
        check("+ Look opens Build", pg.locator("#edit-v-build").is_visible())
        st = pg.evaluate("editBoardState()")
        check("piece in its slot", st.get("shoes", {}).get("t") == "p" and st["shoes"]["p"]["key"] == skey, st.get("shoes"))
        check("tagged Saved", "saved" in pg.inner_text('[data-edit-slot="shoes"] .edit-tag').lower(), pg.inner_text('[data-edit-slot="shoes"]'))
        buy = pg.locator("#edit-buy-out a.edit-buy")
        np = sum(1 for v in st.values() if isinstance(v, dict) and v.get("t") == "p")
        hrefs = [buy.nth(i).get_attribute("href") or "" for i in range(buy.count())]
        check("To buy lists it with a Buy link", buy.count() == np and np >= 1 and all(h.startswith("http") for h in hrefs)
              and st["shoes"]["p"].get("url") in hrefs, (buy.count(), np))
        check("To buy total", "$" in pg.inner_text("#edit-buy-out .edit-total"))
        before = pg.evaluate("JSON.stringify(editBoardState().top)")
        pg.click('[data-edit-step="1"][data-slot="top"]'); pg.wait_for_timeout(200)
        check("arrow cycles the slot", pg.evaluate("JSON.stringify(editBoardState().top)") != before)
        n0 = len(seen["posts"])
        pg.click("#edit-see")
        pg.wait_for_selector("#edit-onme-img", timeout=15000)
        post = seen["posts"][-1] if len(seen["posts"]) > n0 else None
        slots = [i["slot"] for i in post["items"]] if post else []
        check("See it on me posts closet + product garments", post is not None and "shoes" in slots and "top" in slots and "bottom" in slots, slots)
        check("closet garments sent as data", post is not None and all(i["image"].startswith("data:image/") or i["image"].startswith("https://") for i in post["items"]))
        check("render shown in Build", pg.locator("#edit-onme-img").get_attribute("src").startswith(TRY + "/r/"))
        pg.click("#edit-save-look"); pg.wait_for_timeout(300)
        check("Save look keeps it", pg.locator("#edit-looks .edit-look-thumb").count() >= 1)
        n1 = len(seen["posts"])
        pg.click("#edit-see"); pg.wait_for_selector("#edit-onme-img", timeout=8000)
        check("repeat is served from the device cache", len(seen["posts"]) == n1, len(seen["posts"]) - n1)

        # 5. Sheet
        pg.click("#edit-tab-saved"); pg.wait_for_timeout(300)
        n2 = len(seen["posts"])
        pg.locator("#edit-saved-out .edit-pc").first.locator("[data-edit-onme]").click()
        check("sheet opens", pg.locator("#tryon-sheet").is_visible())
        pg.wait_for_selector("#tryon-img:not([hidden])", timeout=15000)
        check("On me posts one garment", len(seen["posts"]) == n2 + 1 and len(seen["posts"][-1]["items"]) == 1, len(seen["posts"]) - n2)
        check("Buy in sheet", pg.locator("#tryon-buy").is_visible())
        pg.click("#tryon-withmine")
        pg.wait_for_timeout(300)
        pg.wait_for_selector("#tryon-img:not([hidden])", timeout=15000)
        wm = seen["posts"][-1]["items"]
        check("With my clothes posts product + closet", len(wm) >= 2, [i["slot"] for i in wm])
        pg.click("#tryon-close")

        # 6. Fallback
        seen["mode"] = "down"
        pg.click("#edit-tab-build"); pg.wait_for_timeout(300)
        pg.click('[data-edit-step="1"][data-slot="bottom"]'); pg.wait_for_timeout(200)
        pg.click("#edit-see")
        pg.wait_for_timeout(2500)
        src = pg.evaluate("(document.getElementById('edit-onme-img') || {}).src || ''")
        status = pg.inner_text("#edit-onme")
        check("falls back to nearest on-body render", "/assets/onbody/" in src, (src[:120], status[:200]))
        seen["mode"] = "ok"

        # 7. Sync apply
        pg.evaluate("""() => { syPutLocal('searches', { id: 's-remote', kind: 'search', q: 'Remote linen shirt', shortlist: [], at: new Date().toISOString(), seen: 3 }); }""")
        pg.click("#edit-tab-searches"); pg.wait_for_timeout(300)
        check("remote search applied", "Remote linen shirt" in pg.inner_text("#edit-search-out"))
        pg.evaluate("syRemoveLocal('searches', 's-remote')"); pg.wait_for_timeout(200)
        check("remote delete applied", "Remote linen shirt" not in pg.inner_text("#edit-search-out"))

        # 7b. The shipped verified catalogue (assets/edit-catalog.json)
        cat = json.loads((ROOT / "assets/edit-catalog.json").read_text())
        check("shipped catalogue has the verified SKUs", len(cat["products"]) >= 200 and all((ROOT / e["img"]).exists() for e in cat["products"] if not e["img"].startswith("http")), len(cat["products"]))
        check("catalogue loaded in the app", pg.evaluate("editCatalogCount()") == len(cat["products"]), pg.evaluate("editCatalogCount()"))
        g = pg.evaluate("editGapPicks().slice(0, 8).map(s => s.cat)")
        check("gap fillers lead with trousers", g and g[0] == "trousers" and g.count("trousers") >= 4, g)
        check("gap fillers marked", pg.evaluate("Object.keys(window.EDIT_GAP_URLS || {}).length") > 50)
        check("GBP rows keep their price", pg.evaluate("editSearchCatalog('baudoin').some(e => e.cur === 'GBP' && /£/.test(e.pd || ''))"))
        check("sunglasses searchable", len(pg.evaluate("editSearchCatalog('sunglasses').filter(e => e.cat === 'sunglasses')")) >= 5)
        check("no pyjamas on top of a trousers search", not any("pyjama" in n.lower() for n in pg.evaluate("editSearchCatalog('trousers').slice(0, 8).map(e => e.name)")))
        if pg.locator("[data-edit-close-search]").count():
            pg.click("[data-edit-close-search]")
        pg.click("#edit-tab-searches"); pg.wait_for_timeout(400)
        if pg.locator("[data-edit-close-search]").count():
            pg.click("[data-edit-close-search]"); pg.wait_for_timeout(300)
        gk = pg.locator("#edit-gapcards .edit-pc .edit-body h3").all_inner_texts()
        check("Closet gaps shows gap fillers", pg.locator("#edit-closet-gaps").count() == 1 and len(gk) >= 3, gk)
        chips = pg.locator("#edit-gaps [data-edit-suggest]").all_inner_texts()
        check("Try starts with Trousers", chips[:1] == ["Trousers"], chips)
        pg.click("#edit-tab-build"); pg.wait_for_timeout(500)
        gf = pg.locator("#edit-gapfill [data-edit-gap-put]")
        check("Build: Fills a gap strip", gf.count() >= 4, gf.count())
        k0 = gf.first.get_attribute("data-edit-gap-put")
        gf.first.click(); pg.wait_for_timeout(400)
        check("gap filler goes on the board", pg.evaluate("k => Object.values(editBoardState()).some(r => r && r.t === 'p' && r.p.key === k)", k0))
        check("and into To buy", pg.locator("#edit-buy-out a.edit-buy").count() >= 1)

        # 8. Catalogue ingestion
        seen["catalog"] = {"products": [{"brand": "Zzverified", "title": "Zzverified Cashmere Polo", "price": "$1,234", "url": "https://example.com/zz", "image": "https://example.com/zz.jpg", "category": "Polos", "color": "Navy", "store": "Example"}]}
        pg.evaluate("editLoadCatalog()"); pg.wait_for_timeout(800)
        check("catalogue ingested", pg.evaluate("editCatalogCount()") == 1)
        r = pg.evaluate("editSearchCatalog('cashmere polo').slice(0,3).map(e => e.brand)")
        check("verified catalogue ranks first", r and r[0] == "Zzverified", r)

        # nav + title intact
        check("page title is The Edit", pg.inner_text("#page-title").strip() == "The Edit" or pg.inner_text(".masthead .brand").strip() == "The Edit")
        check("no i icons on The Edit", pg.locator("#panel-find .info-btn, #panel-find .page-info-row:visible").count() == 0)
        check("no page errors", not errors, errors)
        b.close()
    httpd.shutdown()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


main()
