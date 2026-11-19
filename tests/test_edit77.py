"""Build .77 — Ask, Inspo · On you, accessory slots, Save look -> Outfits, pairsWith.

Headless WebKit, iPhone size. Every *.workers.dev call is intercepted:
sync is aborted, /ask, /ask/catalog, /health and /tryon are local
MOCKS (never production). Closet: his 63 rendered pieces.

  1. The Edit has four centred tabs: Saved / Searches / Build / Ask.
  2. Ask: suggestion chips first time; a question shows on the right
     and typing dots while waiting; the answer, a swipe deck of cards
     (brand, name, price, colour dot, why, Owns thumbnails); ☆ stars
     it into Saved (star: true, liked); 👎 hides it with Hidden · Undo
     (disliked); the next ask sends closet, history, liked, disliked;
     Build this look lays ownedIds + skuIds on the Build board; a 429
     shows the server's message; offline disables send; the thread
     survives a reload; /health configured:false hides the tab.
  3. Build: Belt and Sunglasses slots (accessories), empty = None,
     catalogue belts cycle in; See it on me sends no accessory.
  4. Save look: all his pieces -> a saved look in Outfits > Mine;
     with shop pieces -> Outfits > Inspo > On you.
  5. Inspo > On you: the 16 QA-passed on-body renders with Shop links,
     Build this look; assets/inspo/manifest.json is re-read at launch.
  6. Catalogue pairsWith differ per SKU and pair across slots.
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
BUILD = "2026-11-19.79.1"
TRY = "https://wardrobe-tryon.dyacobs.workers.dev"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
CLOSET = json.loads((HERE / "fixture_onbody.json").read_text())
CAT = json.loads((ROOT / "assets/edit-catalog.json").read_text())["products"]
MAN = json.loads((ROOT / "assets/inspo/manifest.json").read_text())
fails: list[str] = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:400]))
    if not ok:
        fails.append(name)


def png_uri(n):
    import random, struct, zlib
    rnd = random.Random(n)
    rgb = (rnd.randint(40, 220), rnd.randint(40, 220), rnd.randint(40, 220))
    raw = b"".join(b"\x00" + bytes(c for _ in range(16) for c in rgb) for _ in range(16))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


def wait_js(pg, expr, ms=10000):
    for _ in range(ms // 100):
        if pg.evaluate("() => !!(" + expr + ")"):
            return True
        pg.wait_for_timeout(100)
    return False


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


def server_card(e):
    return {"sku": e["sku"], "brand": e["brand"], "name": e["name"], "cat": e.get("cat"), "subcat": e.get("subcat", e.get("cat")),
            "price": e["price"], "priceDisplay": "$%s" % format(int(e["price"]), ","), "currency": "USD", "retailer": e.get("retailer", ""),
            "url": e["url"], "imgUrl": "https://example.com/x.jpg", "colourName": e.get("colour", ""), "hex": e.get("hex", "#555555")}


def main():
    items = [dict(i, photo=png_uri(n), addedISO="2026-11-17") for n, i in enumerate(CLOSET)]
    by_cat = {}
    for e in CAT:
        by_cat.setdefault(e.get("cat"), []).append(e)
    trousers = by_cat.get("trousers", [])[:5]
    polo = next(i for i in CLOSET if i["category"] == "Polos")
    shoe = next(i for i in CLOSET if i["category"] == "Shoes")
    httpd, base = start_server()
    seen = {"asks": [], "mode": "ok", "health": True, "posts": [], "manifest": None}

    def ask_reply():
        picks = [{"sku": e["sku"], "why": "Picks up the olive without matching it.", "pairsWith": [polo["id"], shoe["id"]], "product": server_card(e)} for e in trousers]
        return ({
                "answer": "My top pick is the %s %s — it sits quietly under your Kiton polo." % (trousers[0]["brand"], trousers[0]["name"]),
                "picks": picks, "outfit": {"ownedIds": [polo["id"], shoe["id"]], "skuIds": [trousers[0]["sku"]]},
                "meta": {"fallback": False, "remaining": 190}})

    def route(r):
        u = r.request.url
        if u.startswith(TRY + "/health"):
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "ask": {"configured": seen["health"], "model": "m"}}))
        if u.startswith(TRY + "/ask/catalog"):
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"version": "v1", "count": len(CAT), "items": [server_card(e) for e in CAT[:40]]}))
        if u.startswith(TRY + "/ask") and r.request.method == "POST":
            body = json.loads(r.request.post_data)
            seen["asks"].append({"body": body, "auth": r.request.headers.get("authorization", "")})
            if seen["mode"] == "cap":
                return r.fulfill(status=429, content_type="application/json", body=json.dumps({"error": "daily_cap", "message": "That's 200 asks today — back tomorrow."}))
            if seen["mode"] == "hold":
                seen["held"] = r
                return
            return r.fulfill(status=200, content_type="application/json", body=json.dumps(ask_reply()))

        if u.startswith(TRY + "/tryon") and r.request.method == "POST":
            body = json.loads(r.request.post_data)
            seen["posts"].append(body)
            return r.fulfill(status=202, content_type="application/json", body=json.dumps({"id": "%032x" % len(seen["posts"]), "status": "running", "step": 1, "steps": 1}))
        if u.startswith(TRY + "/tryon/"):
            jid = u.rsplit("/", 1)[1]
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"id": jid, "status": "done", "step": 1, "steps": 1, "resultUrl": TRY + "/r/" + jid + ".jpg"}))
        if u.startswith(TRY + "/r/"):
            return r.fulfill(status=200, content_type="image/png", body=PNG)
        return r.abort()

    seed = ("(() => { if (sessionStorage.getItem('seeded77')) return; localStorage.clear(); sessionStorage.setItem('seeded77','1');"
            " localStorage.setItem('wardrobe.items', %s); localStorage.setItem('wardrobe.todaySource', JSON.stringify('wardrobe'));"
            " localStorage.setItem('wardrobe-theme', 'light');"
            " localStorage.setItem('wardrobe.sync', JSON.stringify({key:'%s', acct:'test77', last:0, snap:{}, st:{}, tomb:{}, dirty:{}, status:'x', lastOk:0}));"
            " })();" % (json.dumps(json.dumps(items)), "b" * 48))

    with sync_playwright() as p:
        b = p.webkit.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
        ctx.add_init_script(seed)
        ctx.route("**/*.workers.dev/**", route)

        def man_route(r):
            if seen["manifest"] is None:
                return r.continue_()
            return r.fulfill(status=200, content_type="application/json", body=json.dumps(seen["manifest"]))
        ctx.route("**/assets/inspo/manifest.json*", man_route)
        errors = []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base, wait_until="load")
        pg.wait_for_timeout(2200)
        check("build string", pg.evaluate("window.WARDROBE_BUILD") == BUILD, pg.evaluate("window.WARDROBE_BUILD"))

        # 1. four tabs
        pg.click("#tab-find"); pg.wait_for_timeout(500)
        tabs = pg.evaluate("""() => [...document.querySelectorAll('#panel-find .edit-tabs .chip')].filter(b => !b.hidden).map(b => { const r = b.getBoundingClientRect(); return { t: b.textContent.replace(/\\d+/g,'').trim(), l: r.left, r: r.right, top: r.top }; })""")
        check("four tabs Saved/Searches/Build/Ask (+ Price pill, .78.4)", [t["t"] for t in tabs][:4] == ["Saved", "Searches", "Build", "Ask"] and len(tabs) == 5, tabs)
        if len(tabs) == 5:
            mid = (tabs[0]["l"] + tabs[-1]["r"]) / 2
            check("tabs centred on one row", abs(mid - 195) <= 2 and len({round(t["top"]) for t in tabs}) == 1 and tabs[0]["l"] >= 8 and tabs[-1]["r"] <= 382, tabs)

        # 2. Ask
        pg.click("#edit-tab-ask"); pg.wait_for_timeout(400)
        check("Ask view open", pg.locator("#edit-v-ask").is_visible())
        sugs = pg.locator("#ask-sugs .chip").all_inner_texts()
        check("three suggestion chips first time", len(sugs) == 3, sugs)
        check("send disabled when empty", pg.locator("#ask-send").is_disabled())
        pg.fill("#ask-q", "what trousers go with my Kiton dark olive polo for a Palm Beach dinner")
        check("send enabled with text", not pg.locator("#ask-send").is_disabled())
        seen["mode"] = "hold"
        pg.click("#ask-send"); pg.wait_for_timeout(400)
        qb = pg.evaluate("(() => { const q = document.querySelector('#ask-thread .ask-q'); if (!q) return null; const r = q.getBoundingClientRect(); return [r.left, r.right]; })()")
        check("question bubble on the right", qb and qb[1] > 360 and qb[0] > 40, qb)
        check("typing dots while waiting", pg.locator("#ask-thread .ask-dots").count() == 1)
        check("chips go after first ask", pg.locator("#ask-sugs .chip").count() == 0)
        check("input stays usable while waiting", pg.locator("#ask-q").is_editable())
        seen["mode"] = "ok"
        seen["held"].fulfill(status=200, content_type="application/json", body=json.dumps(ask_reply()))
        pg.wait_for_selector("#ask-thread .ask-card", timeout=10000)
        a = seen["asks"][-1]
        bd = a["body"]
        check("Bearer key sent", a["auth"] == "Bearer " + "b" * 48)
        check("closet sent without photos", len(bd["closet"]) >= len(CLOSET) and all(set(c) == {"id", "name", "cat", "color", "hex"} for c in bd["closet"]), bd["closet"][:1])
        check("first ask has empty history/liked/disliked", bd["history"] == [] and bd["liked"] == [] and bd["disliked"] == [])
        ans = pg.inner_text("#ask-thread .ask-a")
        check("answer text in the serif", "My top pick" in ans and "serif" in pg.evaluate("getComputedStyle(document.querySelector('#ask-thread .ask-a')).fontFamily").lower() or "Cormorant" in pg.evaluate("getComputedStyle(document.querySelector('#ask-thread .ask-a')).fontFamily"), pg.evaluate("getComputedStyle(document.querySelector('#ask-thread .ask-a')).fontFamily"))
        n_cards = pg.locator("#ask-thread .ask-card").count()
        check("deck shows every pick", n_cards == len(trousers), n_cards)
        deck = pg.evaluate("(() => { const d = document.querySelector('.ask-deck'), c = d.querySelector('.ask-card'); return { sw: d.scrollWidth, cw: d.clientWidth, w: c.getBoundingClientRect().width, snap: getComputedStyle(d).scrollSnapType }; })()")
        check("swipe deck: ~80% cards, scroll-snap", deck["sw"] > deck["cw"] and 0.7 * 390 <= deck["w"] <= 0.86 * 390 and "x" in deck["snap"], deck)
        c0 = pg.locator("#ask-thread .ask-card").first
        check("card: brand, name, price, dot, why, owns", c0.locator(".edit-kick").inner_text().strip() != "" and "$" in c0.locator(".ask-pr").inner_text()
              and c0.locator(".ask-dot").count() == 1 and "olive" in c0.locator(".ask-why").inner_text() and c0.locator(".ask-owns button").count() == 2, c0.inner_text()[:300])
        check("local catalogue image used", "assets/editimg/" in (c0.locator(".ask-ph img").get_attribute("src") or ""), c0.locator(".ask-ph img").get_attribute("src"))
        check("Ask card in the shared card style (.78.8): icon row + photo opens the product sheet", c0.evaluate("e => e.classList.contains('vp-ask')") and c0.locator("[data-vp-act=wish]").count() == 1 and c0.locator("[data-vp-act=onme]").count() == 1)
        c0.locator(".ask-ph").click(); pg.wait_for_timeout(300)
        check("product sheet from an Ask card", pg.locator("#vp-sheet").is_visible() and pg.locator("#vp-sheet .vp-sh-buy").count() == 1)
        pg.click("#vp-sheet-close"); pg.wait_for_timeout(200)
        check("Shop opens the product", (c0.locator("a.edit-onme").get_attribute("href") or "").startswith("http") and c0.locator("a.edit-onme").get_attribute("target") == "_blank")
        # star
        sku0 = c0.get_attribute("data-ask-sku")
        c0.locator("[data-ask-star]").click(); pg.wait_for_timeout(250)
        check("star pressed", c0.locator("[data-ask-star]").get_attribute("aria-pressed") == "true")
        st = pg.evaluate("askState()")
        check("star -> liked", st["liked"][:1] == [sku0], st["liked"])
        prod0 = next(e for e in CAT if e["sku"] == sku0)
        check("star -> saved in The Edit with star", pg.evaluate("u => (shopWishlist || []).some(w => w.url === u)", prod0["url"])
              and pg.evaluate("u => editMeta.some(m => m.p && m.p.url === u && m.star === true)", prod0["url"]))
        # thumbs down
        c1 = pg.locator("#ask-thread .ask-card").nth(1)
        sku1 = c1.get_attribute("data-ask-sku")
        c1.locator("[data-ask-down]").click(); pg.wait_for_timeout(500)
        check("thumbs-down hides the card", pg.locator('#ask-thread .ask-card[data-ask-sku="%s"]' % sku1).count() == 0)
        check("Hidden · Undo toast", pg.locator("#undo-toast").is_visible() and "Hidden" in pg.inner_text("#undo-msg"))
        check("thumbs-down -> disliked", pg.evaluate("askState().disliked")[:1] == [sku1])
        pg.click("#undo-btn"); pg.wait_for_timeout(300)
        check("undo brings it back", pg.locator('#ask-thread .ask-card[data-ask-sku="%s"]' % sku1).count() == 1 and sku1 not in pg.evaluate("askState().disliked"))
        pg.locator('#ask-thread .ask-card[data-ask-sku="%s"] [data-ask-down]' % sku1).click(); pg.wait_for_timeout(500)
        pg.wait_for_timeout(4300)
        check("toast gone after ~4 s", not pg.locator("#undo-toast").is_visible())
        # add to build
        c2 = pg.locator("#ask-thread .ask-card").nth(1)
        sku2 = c2.get_attribute("data-ask-sku")
        c2.locator("[data-ask-add]").click(); pg.wait_for_timeout(250)
        check("Add to Build: button says In Build", "In Build" in c2.locator("[data-ask-add]").inner_text())
        url2 = next(e for e in CAT if e["sku"] == sku2)["url"]
        check("Add to Build: piece in its slot", pg.evaluate("u => { const b = editBoardState(); return !!(b.bottom && b.bottom.t === 'p' && b.bottom.p.url === u); }", url2))
        # follow-up carries history + prefs
        pg.fill("#ask-q", "cheaper option?"); pg.press("#ask-q", "Enter")
        wait_js(pg, "document.querySelectorAll('#ask-thread .ask-turn').length === 2 && !document.querySelector('#ask-thread .ask-dots')")
        bd = seen["asks"][-1]["body"]
        check("follow-up sends history (answer + picks)", len(bd["history"]) == 2 and bd["history"][0]["role"] == "user" and "Picks:" in bd["history"][1]["content"] and "$" in bd["history"][1]["content"], bd["history"])
        check("follow-up sends liked + disliked", bd["liked"] == [sku0] and bd["disliked"] == [sku1], (bd["liked"], bd["disliked"]))
        check("disliked never shown again", pg.locator('#ask-thread .ask-card[data-ask-sku="%s"]' % sku1).count() == 0)
        # build this look
        pg.locator("#ask-thread [data-ask-build]").last.click(); pg.wait_for_timeout(600)
        check("Build this look opens Build", pg.locator("#edit-v-build").is_visible())
        bs = pg.evaluate("editBoardState()")
        check("board: his polo + shoes + the pick", bs.get("top", {}) and bs["top"].get("id") == polo["id"] and bs.get("shoes", {}).get("id") == shoe["id"]
              and bs.get("bottom", {}).get("t") == "p" and bs["bottom"]["p"]["url"] == trousers[0]["url"], bs)
        check("See it on me ready", pg.locator("#edit-see").is_visible())
        # reload keeps the thread
        pg.reload(wait_until="load"); pg.wait_for_timeout(2000)
        pg.click("#tab-find"); pg.wait_for_timeout(300); pg.click("#edit-tab-ask"); pg.wait_for_timeout(300)
        check("thread survives reload", pg.locator("#ask-thread .ask-turn").count() == 2 and pg.evaluate("JSON.parse(localStorage.getItem('wardrobe.ask.thread')).length") == 2)
        check("catalogue cached", pg.evaluate("!!(JSON.parse(localStorage.getItem('wardrobe.ask.catalog') || 'null') || {}).items"))
        # 429
        seen["mode"] = "cap"
        pg.fill("#ask-q", "more?"); pg.press("#ask-q", "Enter")
        wait_js(pg, "document.querySelectorAll('#ask-thread .ask-turn').length === 3 && !document.querySelector('#ask-thread .ask-dots')")
        check("429 shows the server message", "back tomorrow" in pg.locator("#ask-thread .ask-turn").last.inner_text())
        seen["mode"] = "ok"
        # offline
        ctx.set_offline(True); pg.wait_for_timeout(200)
        pg.fill("#ask-q", "anything"); pg.wait_for_timeout(100)
        check("offline: send disabled", pg.locator("#ask-send").is_disabled())
        ctx.set_offline(False); pg.wait_for_timeout(200)
        pg.fill("#ask-q", "")
        fr = pg.evaluate("(() => { const f = document.getElementById('ask-form').getBoundingClientRect(), b = document.getElementById('bottombar').getBoundingClientRect(); return [f.bottom, b.top]; })()")
        check("input sits above the bottom nav", fr[0] <= fr[1] + 1, fr)
        check("Ask has no i icons / helper text", pg.locator("#edit-v-ask .info-btn, #edit-v-ask .page-info-row, #edit-v-ask .meta").count() == 0)

        # 3. accessories in Build
        pg.click("#edit-tab-build"); pg.wait_for_timeout(400)
        slots = pg.eval_on_selector_all("#edit-board [data-edit-slot]", "e => e.map(x => x.getAttribute('data-edit-slot'))")
        check("Belt and Sunglasses slots", "belt" in slots and "eyewear" in slots, slots)
        check("Accessories heading", "Accessories" in pg.inner_text("#edit-board"))
        check("empty accessory = None", "None" in pg.inner_text('[data-edit-slot="belt"]'), pg.inner_text('[data-edit-slot="belt"]'))
        pg.click('[data-edit-step="1"][data-slot="belt"]'); pg.wait_for_timeout(200)
        pg.click('[data-edit-step="1"][data-slot="eyewear"]'); pg.wait_for_timeout(200)
        bs = pg.evaluate("editBoardState()")
        check("catalogue belt + sunglasses cycle in", (bs.get("belt") or {}).get("t") == "p" and (bs.get("eyewear") or {}).get("t") == "p", (bs.get("belt"), bs.get("eyewear")))
        check("accessories listed in To buy", pg.locator("#edit-buy-out a.edit-buy").count() >= 3)
        n0 = len(seen["posts"])
        pg.click("#edit-see"); pg.wait_for_selector("#edit-onme-img", timeout=15000)
        slots_sent = [i["slot"] for i in seen["posts"][-1]["items"]] if len(seen["posts"]) > n0 else []
        check("See it on me sends no accessory", slots_sent and not any(s in ("belt", "eyewear", "tie", "accessory") for s in slots_sent), slots_sent)
        # 4. Save look with shop pieces -> Inspo
        pg.click("#edit-save-look"); pg.wait_for_timeout(300)
        lk = pg.evaluate("editBuiltLooks()[0]")
        check("build with shop pieces -> home inspo", lk and lk["home"] == "inspo", lk and lk.get("home"))
        # all his own -> Mine
        pg.evaluate("""(ids) => editLoadOutfit(ids, [])""", [polo["id"], shoe["id"], next(i for i in CLOSET if i["category"] == "Trousers")["id"]])
        pg.wait_for_timeout(300)
        nsl = pg.evaluate("savedLooks.length")
        pg.click("#edit-see"); pg.wait_for_selector("#edit-onme-img", timeout=15000)
        pg.click("#edit-save-look"); pg.wait_for_timeout(300)
        check("all-owned build -> saved look in Outfits", pg.evaluate("savedLooks.length") == nsl + 1 and pg.evaluate("savedLooks[0].id").startswith("look-e77-"))
        check("it lives in Mine", pg.evaluate("typeof savedLookHome !== 'function' || savedLookHome(savedLooks[0]) === 'outfits'"), pg.evaluate("typeof savedLookHome === 'function' ? savedLookHome(savedLooks[0]) : '?'"))
        pg.click("#edit-save-look"); pg.wait_for_timeout(300)
        check("saving twice keeps one", pg.evaluate("savedLooks.length") == nsl + 1)
        pg.click("#section-ideas"); pg.wait_for_timeout(500)
        if pg.locator("#outfits-mine").count():
            pg.click("#outfits-mine"); pg.wait_for_timeout(400)
        check("shows in Outfits > Mine", pg.evaluate("(id => !!document.querySelector('#outfits-mine-view [data-look-id=\"' + id + '\"], #outfits-mine-view [data-id=\"' + id + '\"]') || document.getElementById('outfits-mine-view').innerHTML.indexOf(id) !== -1)", pg.evaluate("savedLooks[0].id")))

        # 5. Inspo > On you
        pg.click("#outfits-inspo"); pg.wait_for_timeout(600)
        check("Inspo opens on On you", pg.locator("#panel-onyou").is_visible() and pg.get_attribute('[data-inspo-view="onyou"]', "aria-pressed") == "true")
        nlooks = pg.locator("#panel-onyou [data-ion-look]").count()
        check("every manifest on-body inspo render shown (%d)" % MAN["count"], nlooks == MAN["count"] >= 16, nlooks)
        check("your shop build shows there too", pg.locator("#panel-onyou [data-ion-build]").count() >= 1)
        f0 = pg.locator("#panel-onyou [data-ion-look]").first
        check("render is the webp", (f0.locator(".ion-fig img").get_attribute("src") or "").startswith("assets/inspo/") and pg.evaluate("(() => { const i = document.querySelector('#panel-onyou [data-ion-look] .ion-fig img'); return i.complete && i.naturalWidth > 0; })()"))
        shops = pg.eval_on_selector_all("#panel-onyou [data-ion-look] .ion-shop a, #panel-onyou [data-ion-look] .vp-card a[data-vp-act=buy]", "e => e.map(x => x.href)")
        check("shop-the-missing-pieces links", len(shops) >= 16 and all(h.startswith("http") for h in shops), len(shops))
        check("his pieces shown", pg.locator("#panel-onyou [data-ion-look] .ion-own span").count() >= 10)
        f0.locator("[data-ion-build-look]").click(); pg.wait_for_timeout(600)
        bs = pg.evaluate("editBoardState()")
        l0 = MAN["looks"][0]
        check("Build this look from Inspo fills the board", pg.locator("#edit-v-build").is_visible() and any((v or {}).get("t") == "p" and v["p"]["url"] == l0["shop"][0]["url"] for v in bs.values()), bs)
        # manifest re-read
        extra = json.loads(json.dumps(MAN)); extra["looks"].append(dict(MAN["looks"][0], id="inspo-zz"))
        seen["manifest"] = extra
        pg.reload(wait_until="load"); pg.wait_for_timeout(2200)
        pg.click("#section-ideas"); pg.wait_for_timeout(300); pg.click("#outfits-inspo"); pg.wait_for_timeout(600)
        check("manifest re-read at launch (+1 look)", pg.locator("#panel-onyou [data-ion-look]").count() == MAN["count"] + 1, pg.locator("#panel-onyou [data-ion-look]").count())
        check("no i icons on Inspo", pg.locator("#panel-onyou .info-btn").count() == 0)

        # 6. pairsWith
        pairs = [tuple(e.get("pairs") or []) for e in CAT]
        check("pairsWith differ per SKU", len(set(pairs)) >= 0.8 * len(CAT), len(set(pairs)))
        cl = {i["id"]: i["category"] for i in json.loads(Path("/workspace/wardrobe-audit/build-75/fixture_live83.json").read_text())} if Path("/workspace/wardrobe-audit/build-75/fixture_live83.json").exists() else {}
        if cl:
            tr = [e for e in CAT if e.get("cat") == "trousers"]
            bad = [e["sku"] for e in tr if any(cl.get(x) in ("Trousers", "Jeans", "Shorts") for x in e.get("pairs", []))]
            check("trousers never pair with his trousers", not bad, bad[:5])

        # 7. /health configured:false hides Ask
        seen["health"] = False
        pg.reload(wait_until="load"); pg.wait_for_timeout(2200)
        pg.click("#tab-find"); pg.wait_for_timeout(300)
        check("Ask hidden when not configured", not pg.locator("#edit-tab-ask").is_visible())
        check("no page errors", not errors, errors)
        b.close()
    httpd.shutdown()
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


main()
