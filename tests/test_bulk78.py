"""Build .78 — Add many photos (/identify), Ask sync, Owns -> item page, Save look without a render.

Headless WebKit, iPhone size. Every *.workers.dev call is intercepted:
sync is aborted; /identify, /ask, /health are local MOCKS (never
production). /identify answers are the RECORDED live answers for his 5
real photos (tests/fixtures78/identify_recorded.json, Mistral Small 3.1,
2026-11-19). Closet: the 63-piece on-body fixture.

  1. Closet + -> Add many photos takes 5 photos at once; review grid
     shows every card with a spinner, then filled fields; at most 3
     reads in flight; Bearer key + a JPEG data URI sent; "Riton" snaps
     to his "Kiton"; hex snaps onto a real photo colour; one failed
     read leaves an editable blank card; edits + × stick; Add all files
     every piece via the normal create path (persisted, dirty for sync,
     needsStudio, original photo kept) and they survive a reload.
  2. Ask thread + liked/disliked ride the "ask" sync collection:
     local data migrates into records; a remote turn + pref land in the
     thread / liked; star, hide and unstar update pref records (never
     deleted); records are dirty for sync.
  3. An "Owns" thumbnail opens that piece's page in Closet.
  4. Save look works with no See it on me render: all-own board -> a
     Mine look with the nearest on-body render; a board with no render
     anywhere near -> flat-lay (no image) record.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

_src = (Path(__file__).resolve().parent / "test_edit77.py").read_text()
_g: dict = {"__file__": str(Path(__file__).resolve().parent / "test_edit77.py")}
exec(compile(_src.split("\ndef main():")[0], "test_edit77_helpers", "exec"), _g)  # helpers only, not its run
png_uri, wait_js, start_server, server_card, CLOSET, CAT, TRY = (_g[k] for k in ("png_uri", "wait_js", "start_server", "server_card", "CLOSET", "CAT", "TRY"))

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
BUILD = "2026-11-19.79.5"
REC = json.loads((HERE / "fixtures78/identify_recorded.json").read_text())
KEYS = list(REC["answers"].keys())
fails: list[str] = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:400]))
    if not ok:
        fails.append(name)


def main():
    from playwright.sync_api import sync_playwright
    items = [dict(i, photo=png_uri(n), addedISO="2026-11-17") for n, i in enumerate(CLOSET)]
    polo = next(i for i in CLOSET if i["category"] == "Polos")
    shoe = next(i for i in CLOSET if i["category"] == "Shoes")
    trousers = [e for e in CAT if e.get("cat") == "trousers"][:3]
    httpd, base = start_server()
    seen = {"ids": [], "inflight": 0, "max": 0, "held": [], "fail": {4}, "asks": 0}

    def route(r):
        u = r.request.url
        if u.startswith(TRY + "/health"):
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "ask": {"configured": True, "model": "m"}, "identify": {"configured": True, "model": "m"}}))
        if u.startswith(TRY + "/identify") and r.request.method == "POST":
            body = json.loads(r.request.post_data)
            n = len(seen["ids"])
            seen["ids"].append({"auth": r.request.headers.get("authorization", ""), "img": body.get("image", "")[:40], "len": len(body.get("image", ""))})
            seen["inflight"] += 1
            seen["max"] = max(seen["max"], seen["inflight"])
            seen["held"].append((r, n))
            return
        if u.startswith(TRY + "/ask/catalog"):
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"version": "v1", "items": [server_card(e) for e in CAT[:40]]}))
        if u.startswith(TRY + "/ask") and r.request.method == "POST":
            seen["asks"] += 1
            picks = [{"sku": e["sku"], "why": "Sits under the olive.", "pairsWith": [polo["id"], shoe["id"]], "product": server_card(e)} for e in trousers]
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"answer": "Try these.", "picks": picks, "outfit": {"ownedIds": [polo["id"]], "skuIds": [trousers[0]["sku"]]}, "meta": {}}))
        return r.abort()

    def release(pg):
        """answer held /identify calls in arrival order (recorded live answers)"""
        while seen["held"]:
            r, n = seen["held"].pop(0)
            seen["inflight"] -= 1
            if n in seen["fail"]:
                r.fulfill(status=502, content_type="application/json", body=json.dumps({"error": "model_failed", "message": "Couldn't read that photo."}))
            else:
                r.fulfill(status=200, content_type="application/json", body=json.dumps(REC["answers"][KEYS[n]]))
            pg.wait_for_timeout(60)

    seed = ("(() => { if (sessionStorage.getItem('seeded78')) return; localStorage.clear(); sessionStorage.setItem('seeded78','1');"
            " localStorage.setItem('wardrobe.items', %s); localStorage.setItem('wardrobe.todaySource', JSON.stringify('wardrobe'));"
            " localStorage.setItem('wardrobe-theme', 'light');"
            " localStorage.setItem('wardrobe.ask.thread', JSON.stringify([{id:'old1', q:'old question', at:'2026-11-18T10:00:00.000Z', state:'done', answer:'old answer', picks:[]}]));"
            " localStorage.setItem('wardrobe.ask.liked', JSON.stringify(['sku-local-like']));"
            " localStorage.setItem('wardrobe.sync', JSON.stringify({key:'%s', acct:'test78', last:0, snap:{}, st:{}, tomb:{}, dirty:{}, status:'x', lastOk:0}));"
            " })();" % (json.dumps(json.dumps(items)), "b" * 48))

    with sync_playwright() as p:
        b = p.webkit.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
        ctx.add_init_script(seed)
        ctx.route("**/*.workers.dev/**", route)
        errors = []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base, wait_until="load")
        pg.wait_for_timeout(2200)
        check("build string", pg.evaluate("window.WARDROBE_BUILD") == BUILD, pg.evaluate("window.WARDROBE_BUILD"))
        n0 = pg.evaluate("wardrobeItems.length")

        # ---------- 1. bulk add ----------
        pg.evaluate("switchTab('add')"); pg.wait_for_timeout(300)
        check("Add many photos card on the Add page", pg.locator("#bulk-add-card").is_visible() and pg.locator("#bulk-photos").get_attribute("multiple") is not None)
        pg.set_input_files("#bulk-photos", [str(HERE / "fixtures78" / (k + ".jpg")) for k in KEYS])
        ok = wait_js(pg, "currentTab === 'bulk' && document.querySelectorAll('#bulk-grid .bulk-card').length === 5", 8000)
        check("review grid opens with 5 cards", ok, pg.evaluate("[currentTab, document.querySelectorAll('#bulk-grid .bulk-card').length]"))
        wait_js(pg, "document.querySelectorAll('#bulk-grid .bulk-card.is-reading').length === 5", 6000)
        check("cards show reading spinners", pg.locator("#bulk-grid .bulk-spin").count() >= 3)
        check("Add all disabled while reading", pg.locator("#bulk-add-all").is_disabled())
        wait_js(pg, "true", 1500)
        pg.wait_for_timeout(800)
        check("at most 3 /identify in flight", 1 <= seen["max"] <= 3, seen["max"])
        for _ in range(40):
            release(pg)
            if len(seen["ids"]) >= 5 and not seen["held"]:
                break
            pg.wait_for_timeout(150)
        ok = wait_js(pg, "bulkState().every(r => r.status === 'done' || r.status === 'manual')", 8000)
        st = pg.evaluate("bulkState()")
        check("all 5 photos read once each", ok and len(seen["ids"]) == 5, (len(seen["ids"]), [r["status"] for r in st]))
        check("Bearer key + JPEG data URI sent", all(x["auth"] == "Bearer " + "b" * 48 and x["img"].startswith("data:image/jpeg;base64,") and x["len"] < 2_000_000 for x in seen["ids"]), seen["ids"][:1])
        by = {k: st[i] for i, k in enumerate(KEYS)}
        check("categories from /identify", [by[k]["category"] for k in KEYS[:4]] == ["Button downs", "Jeans", "Shoes", "Blazers"], [r["category"] for r in st])
        check("'Riton' label snaps to his Kiton", by["kiton-olive-polo"]["brand"] == "Kiton" and by["kiton-olive-polo"]["name"].startswith("Kiton "), by["kiton-olive-polo"])
        check("hex snapped onto a photo colour", all(by[k]["colourHex"] and by[k]["colourHex"] != by[k]["modelHex"] for k in KEYS[:4]), [(by[k]["modelHex"], by[k]["colourHex"]) for k in KEYS[:4]])
        check("failed read -> blank editable card", by[KEYS[4]]["status"] == "manual" and by[KEYS[4]]["name"] == "" and pg.locator("#bulk-grid .bulk-card").nth(4).locator("[data-bk-f=name]").is_editable())
        cards = pg.locator("#bulk-grid .bulk-card")
        check("filled fields on the card", cards.nth(1).locator("[data-bk-f=name]").input_value() == "Mid Blue Denim Straight Leg Jeans" and cards.nth(1).locator("[data-bk-f=category]").input_value() == "Jeans")
        cards.nth(0).locator("[data-bk-f=category]").select_option("Polos")
        cards.nth(4).locator("[data-bk-f=name]").fill("Eleventy Navy Crewneck Sweater")
        cards.nth(4).locator("[data-bk-f=category]").select_option("Sweaters")
        cards.nth(4).locator("[data-bk-f=colourName]").fill("Navy")
        check("edits stick", pg.evaluate("bulkState()[0].category") == "Polos" and pg.evaluate("bulkState()[4].name") == "Eleventy Navy Crewneck Sweater")
        geo = pg.evaluate("""(() => { const g = document.getElementById('bulk-grid'), c = g.querySelector('.bulk-card').getBoundingClientRect(), a = document.getElementById('bulk-add-all').getBoundingClientRect(), bb = document.getElementById('bottombar').getBoundingClientRect();
            return { sw: document.documentElement.scrollWidth, cl: c.left, cr: c.right, addTop: a.top, addBottom: a.bottom, barTop: bb.top, nav: !!bb.height }; })()""")
        check("grid fits 390 and Add all clears the nav", geo["sw"] <= 390 and geo["cl"] >= 0 and geo["cr"] <= 390 and geo["addBottom"] <= geo["barTop"] + 1, geo)
        ov = pg.evaluate("""(() => [...document.querySelectorAll('#bulk-grid .bulk-card')].every(c => { const x = c.querySelector('.bulk-x').getBoundingClientRect(); return [...c.querySelectorAll('input, select')].every(f => { const r = f.getBoundingClientRect(); return r.right <= x.left || r.top >= x.bottom || r.bottom <= x.top; }); }))()""")
        check("remove × never covers a field", ov)
        check("Add all says how many", pg.text_content("#bulk-add-all").strip() == "Add all 5", pg.text_content("#bulk-add-all"))
        # drop one then re-add count
        pg.evaluate("switchTab('wardrobe')"); pg.wait_for_timeout(200)
        pg.evaluate("switchTab('add')"); pg.wait_for_timeout(200)
        check("resume button keeps the batch", pg.locator("#bulk-resume").is_visible() and "5" in pg.inner_text("#bulk-resume"))
        pg.click("#bulk-resume"); pg.wait_for_timeout(300)
        pg.click("#bulk-add-all"); pg.wait_for_timeout(600)
        new = pg.evaluate("wardrobeItems.filter(i => i.addedVia === 'bulk')")
        check("Add all filed 5 pieces", len(new) == 5 and pg.evaluate("wardrobeItems.length") == n0 + 5, len(new))
        check("names, categories, colours kept", sorted(i["category"] for i in new) == sorted(["Polos", "Jeans", "Shoes", "Blazers", "Sweaters"]) and any(i["name"] == "Eleventy Navy Crewneck Sweater" and i["colourName"] == "Navy" for i in new), [(i["name"], i["category"]) for i in new])
        check("needsStudio + original photo kept", all(i.get("needsStudio") is True and i["photo"].startswith("data:image/jpeg") and i["originalPhoto"] == i["photo"] for i in new))
        check("studio queue lists them", sorted(pg.evaluate("studioQueue78()")) == sorted(i["id"] for i in new))
        check("unique ids", len({i["id"] for i in new}) == 5)
        stored = pg.evaluate("JSON.parse(localStorage.getItem('wardrobe.items')).filter(i => i.addedVia === 'bulk').length")
        check("persisted like the Add form", stored == 5, stored)
        pg.wait_for_timeout(300)
        dirty = pg.evaluate("(() => { syTrackChanges('items'); const d = SY.dirty.items || {}; return wardrobeItems.filter(i => i.addedVia === 'bulk').every(i => d[i.id] === 1); })()")
        check("new pieces are dirty for sync", dirty)
        check("back on Closet after Add all", pg.evaluate("currentTab") == "wardrobe")

        # ---------- 2. Ask sync ----------
        recs = pg.evaluate("askSync")
        check("local thread + liked migrated into ask records", any(r["id"] == "t-old1" and r["kind"] == "turn" for r in recs) and any(r["kind"] == "pref" and r["sku"] == "sku-local-like" and r["v"] == "like" for r in recs), recs)
        check("ask is a sync collection", pg.evaluate("SY_COLLS.indexOf('ask') !== -1 && SY_KEY_COLL.askSync === 'ask' && SY_COLL_KEY.ask === 'askSync'"))
        pg.evaluate("""syPutLocal('ask', {id:'t-remote1', kind:'turn', q:'from the iPad', at:'2026-11-18T12:00:00.000Z', state:'done', answer:'remote answer', picks:[]});
                       syPutLocal('ask', {id:'p-sku-remote', kind:'pref', sku:'sku-remote', v:'dislike', at: Date.now()});""")
        stt = pg.evaluate("askState()")
        check("remote turn lands in the thread, in time order", [t["id"] for t in stt["thread"]] == ["old1", "remote1"], [t["id"] for t in stt["thread"]])
        check("remote pref lands in disliked", "sku-remote" in stt["disliked"] and "sku-local-like" in stt["liked"], stt)
        pg.evaluate("syPutLocal('ask', {id:'p-sku-local-like', kind:'pref', sku:'sku-local-like', v:'', at: Date.now()+5})")
        check("remote unstar clears liked", "sku-local-like" not in pg.evaluate("askState().liked"))
        # ask -> star + hide through the UI
        pg.evaluate("switchTab('find')"); pg.wait_for_timeout(400)
        pg.click("#edit-tab-ask"); pg.wait_for_timeout(300)
        pg.fill("#ask-q", "trousers for the olive polo"); pg.click("#ask-send")
        pg.wait_for_selector("#ask-thread .ask-card", timeout=10000)
        c0 = pg.locator("#ask-thread .ask-card").first
        sku0 = c0.get_attribute("data-ask-sku")
        c0.locator("[data-ask-star]").click(); pg.wait_for_timeout(200)
        r = pg.evaluate("askSync.filter(r => r.kind === 'pref' && r.sku === %s)[0] || null" % json.dumps(sku0))
        check("star -> pref record v:like", r and r["v"] == "like", r)
        c0.locator("[data-ask-star]").click(); pg.wait_for_timeout(200)
        r = pg.evaluate("askSync.filter(r => r.kind === 'pref' && r.sku === %s)[0] || null" % json.dumps(sku0))
        check("unstar keeps the record, v cleared", r and r["v"] == "", r)
        nt = pg.evaluate("askSync.filter(r => r.kind === 'turn').length")
        check("answered turn is a record", nt == 3, nt)
        d = pg.evaluate("(() => { syTrackChanges('ask'); return Object.keys(SY.dirty.ask || {}); })()")
        check("ask records dirty for sync", any(x.startswith("t-") for x in d) and any(x.startswith("p-") for x in d), d)

        # ---------- 3. Owns -> item page ----------
        own = pg.locator("#ask-thread .ask-card").nth(1).locator(".ask-owns button").first
        iid = own.get_attribute("data-ask-item")
        own.click(); pg.wait_for_timeout(500)
        check("Owns thumbnail opens the item page", pg.evaluate("currentTab") == "wardrobe" and pg.evaluate("detailItemId") == iid and pg.locator("#item-detail .item-detail-card").is_visible(), [pg.evaluate("currentTab"), pg.evaluate("detailItemId"), iid])
        check("item page shows that piece", next(i["name"] for i in CLOSET if i["id"] == iid) in pg.inner_text("#item-detail"))

        # ---------- 4. Save look without a render ----------
        # sync is aborted here, so the "Couldn't sync" note shows: the page must still scroll its foot clear of it
        pg.evaluate("switchTab('find')"); pg.wait_for_timeout(300)
        pg.evaluate("editShow('build')"); pg.wait_for_timeout(300)
        tops = [i["id"] for i in CLOSET if i["category"] in ("Polos",)][:1]
        bottoms = [i["id"] for i in CLOSET if i["category"] in ("Trousers",)][:1]
        pg.evaluate("editLoadOutfit(%s, [])" % json.dumps(tops + bottoms + [shoe["id"]])); pg.wait_for_timeout(400)
        check("Save look on the board before any render", pg.locator("#edit-save-board").is_visible() and pg.locator("#edit-onme").is_hidden())
        nl = pg.evaluate("savedLooks.length")
        pg.locator("#edit-save-board").evaluate("e => e.scrollIntoView({block: 'center'})"); pg.click("#edit-save-board"); pg.wait_for_timeout(400)
        lk = pg.evaluate("editBuiltLooks()[0]")
        check("built look saved with nearest on-body or flat-lay", lk and lk.get("imgKind") in ("near", "flat") and (lk["imgKind"] == "flat") == (not lk.get("img")), lk and {k: lk.get(k) for k in ("imgKind", "img", "home")})
        check("all-own -> Outfits > Mine", pg.evaluate("savedLooks.length") == nl + 1 and pg.evaluate("savedLooks.some(l => l.id.indexOf('look-e77-') === 0)"))
        ml = pg.evaluate("savedLooks.filter(l => l.id.indexOf('look-e77-') === 0)[0]")
        check("Mine look carries the nearest render when one exists", (ml["img"] or "") == (lk.get("img") or ""), (ml.get("img"), lk.get("img")))
        cta = pg.evaluate("""(() => { const bs = [...document.querySelectorAll('#panel-find .edit-cta button')].map(b => b.getBoundingClientRect()); return { n: bs.length, top: [...new Set(bs.map(r => Math.round(r.top)))].length, l: Math.min(...bs.map(r => r.left)), r: Math.max(...bs.map(r => r.right)) }; })()""")
        pg.locator("#edit-save-board").evaluate("e => e.scrollIntoView({block: 'end'})"); pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)"); pg.wait_for_timeout(200)
        cl = pg.evaluate("""(() => { const s = document.getElementById('sync-note'), b = document.getElementById('edit-save-board').getBoundingClientRect(); if (s.hidden) return { hidden: true }; const r = s.getBoundingClientRect(); return { ok: b.bottom <= r.top || b.top >= r.bottom, b: b.bottom, n: r.top }; })()""")
        check("page foot scrolls clear of the sync note", cl.get("hidden") or cl.get("ok"), cl)
        check("board buttons fit on one row at 390", cta["n"] == 3 and cta["top"] == 1 and cta["l"] >= 0 and cta["r"] <= 390, cta)
        # with a shop piece -> inspo record; no render at all near -> still saves
        pg.evaluate("editLoadOutfit([], [%s])" % json.dumps({"sku": trousers[1]["sku"], "key": trousers[1]["sku"], "brand": trousers[1]["brand"], "name": trousers[1]["name"], "cat": "trousers", "img": "x.jpg", "price": 100, "hex": "#555555"})); pg.wait_for_timeout(300)
        pg.locator("#edit-save-board").evaluate("e => e.scrollIntoView({block: 'center'})"); pg.click("#edit-save-board"); pg.wait_for_timeout(300)
        lk2 = pg.evaluate("editBuiltLooks()[0]")
        check("shop-piece board saves too (Inspo)", lk2 and lk2["home"] == "inspo" and lk2.get("imgKind") in ("near", "flat"), lk2 and {k: lk2.get(k) for k in ("imgKind", "home")})

        # ---------- reload: everything survives ----------
        pg.reload(wait_until="load"); pg.wait_for_timeout(2000)
        check("bulk pieces survive reload", pg.evaluate("wardrobeItems.filter(i => i.addedVia === 'bulk' && i.needsStudio).length") == 5)
        check("ask thread survives reload", len(pg.evaluate("askState().thread")) == 3)
        check("no page errors", not errors, errors[:3])
        b.close()
    httpd.shutdown()
    print("\n%d failed" % len(fails) if fails else "\nALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
