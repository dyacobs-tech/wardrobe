"""Build .78.1 — the Add-many review batch survives a reload (IndexedDB),
and /identify gets the photo's palette + his brand list.

Headless WebKit, iPhone size, every *.workers.dev call intercepted
(/identify is a local MOCK built from the recorded live answers; sync
aborted). Closet: the 63-piece on-body fixture.

  1. 5 photos -> each /identify body carries palette (hexes, most pixels
     first) and brands (his, incl. Kiton + two-word Loro Piana).
  2. Two answered with a server-snapped hex (meta.rules) -> that hex is
     kept as is; three left in flight.
  3. An edit + the batch are in IndexedDB; a reload restores all 5 cards
     in order with the edit, done rows stay done, in-flight rows are read
     again.
  4. × removes that row from IndexedDB.
  5. Add all files the 4 and empties the store; another reload shows no
     batch, no resume button, and no duplicate pieces.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_src = (Path(__file__).resolve().parent / "test_edit77.py").read_text()
_g: dict = {"__file__": str(Path(__file__).resolve().parent / "test_edit77.py")}
exec(compile(_src.split("\ndef main():")[0], "test_edit77_helpers", "exec"), _g)
png_uri, wait_js, start_server, CLOSET, TRY = (_g[k] for k in ("png_uri", "wait_js", "start_server", "CLOSET", "TRY"))

HERE = Path(__file__).resolve().parent
BUILD = "2026-11-19.80.3"
REC = json.loads((HERE / "fixtures78/identify_recorded.json").read_text())
KEYS = list(REC["answers"].keys())
fails: list[str] = []
IDB = """() => new Promise(res => { const rq = indexedDB.open('wardrobe-bulk', 1);
  rq.onupgradeneeded = () => rq.result.createObjectStore('rows', {keyPath: 'rid'});
  rq.onsuccess = () => { const g = rq.result.transaction('rows', 'readonly').objectStore('rows').getAll();
    g.onsuccess = () => res(g.result.sort((a, b) => a.ord - b.ord).map(r => ({rid: r.rid, status: r.status, name: r.name, photo: (r.photo || '').slice(0, 23)}))); }; })"""


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:400]))
    if not ok:
        fails.append(name)


def main():
    from playwright.sync_api import sync_playwright
    items = [dict(i, photo=png_uri(n), addedISO="2026-11-17") for n, i in enumerate(CLOSET)]
    httpd, base = start_server()
    seen = {"bodies": [], "held": [], "answer": True}

    def answer(r, body):
        img = body.get("image", "")
        # which photo? match by arrival order of distinct images
        if img not in seen.setdefault("imgs", []):
            seen["imgs"].append(img)
        k = KEYS[seen["imgs"].index(img) % len(KEYS)]
        a = json.loads(json.dumps(REC["answers"][k]))
        a["colourHex"] = (body.get("palette") or ["#123456"])[0]
        a["meta"] = dict(a.get("meta") or {}, rules=["hex-snap"])
        r.fulfill(status=200, content_type="application/json", body=json.dumps(a))

    def route(r):
        u = r.request.url
        if u.startswith(TRY + "/health"):
            return r.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "identify": {"configured": True, "model": "m"}}))
        if u.startswith(TRY + "/identify") and r.request.method == "POST":
            body = json.loads(r.request.post_data)
            seen["bodies"].append(body)
            if seen["answer"] and len([b for b in seen["bodies"]]) <= 2:
                return answer(r, body)
            if seen["answer"] == "all":
                return answer(r, body)
            seen["held"].append(r)
            return
        return r.abort()

    seed = ("(() => { if (sessionStorage.getItem('seeded781')) return; localStorage.clear(); sessionStorage.setItem('seeded781','1');"
            " localStorage.setItem('wardrobe.items', %s); localStorage.setItem('wardrobe.todaySource', JSON.stringify('wardrobe'));"
            " localStorage.setItem('wardrobe-theme', 'light');"
            " localStorage.setItem('wardrobe.sync', JSON.stringify({key:'%s', acct:'test781', last:0, snap:{}, st:{}, tomb:{}, dirty:{}, status:'x', lastOk:0}));"
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
        pg.wait_for_timeout(2000)
        check("build string", pg.evaluate("window.WARDROBE_BUILD") == BUILD, pg.evaluate("window.WARDROBE_BUILD"))
        check("store ready, empty at start", pg.evaluate("bulkRestored()") and pg.evaluate(IDB) == [] and not pg.locator("#bulk-resume").is_visible())
        n0 = pg.evaluate("wardrobeItems.length")
        brands = pg.evaluate("bulkBrands()")
        check("his brands derived (Kiton, Loro Piana)", "Kiton" in brands and "Loro Piana" in brands and "Loro" not in brands, brands[:40])

        pg.evaluate("switchTab('add')"); pg.wait_for_timeout(300)
        pg.set_input_files("#bulk-photos", [str(HERE / "fixtures78" / (k + ".jpg")) for k in KEYS])
        wait_js(pg, "document.querySelectorAll('#bulk-grid .bulk-card').length === 5", 8000)
        wait_js(pg, "bulkState().filter(r => r.status === 'done').length === 2", 12000)
        pg.wait_for_timeout(800)
        bd = seen["bodies"]
        check("3 reads in flight / 2 done", len(bd) == 5 and len(seen["held"]) == 3, (len(bd), len(seen["held"])))
        check("palette sent: hexes, most pixels first", all(isinstance(x.get("palette"), list) and 1 <= len(x["palette"]) <= 6 and all(str(h).startswith("#") and len(h) == 7 for h in x["palette"]) for x in bd), [x.get("palette") for x in bd[:2]])
        check("brands sent with every photo", all(x.get("brands") == brands for x in bd), [len(x.get("brands") or []) for x in bd])
        st = pg.evaluate("bulkState()")
        done = [r for r in st if r["status"] == "done"]
        check("server-snapped hex kept as is", len(done) == 2 and all(r["colourHex"] == r["modelHex"] for r in done), done)
        pg.locator("#bulk-grid .bulk-card").nth(0).locator("[data-bk-f=name]").fill("Edited Olive Polo")
        pg.wait_for_timeout(500)
        before = pg.evaluate(IDB)
        check("batch mirrored to IndexedDB (5, with the edit)", len(before) == 5 and before[0]["name"] == "Edited Olive Polo" and all(r["photo"].startswith("data:image/jpeg") for r in before), before)

        # ---------- reload ----------
        for h in seen["held"]:
            try:
                h.abort()
            except Exception:
                pass
        seen["held"].clear(); nb = len(seen["bodies"])
        seen["answer"] = "all"
        pg.reload(wait_until="load")
        ok = wait_js(pg, "window.bulkRestored && bulkRestored() && document.querySelectorAll('#bulk-grid .bulk-card').length === 5", 8000)
        check("reload restores all 5 cards", ok, pg.evaluate("document.querySelectorAll('#bulk-grid .bulk-card').length"))
        wait_js(pg, "bulkState().every(r => r.status === 'done' || r.status === 'manual')", 12000)
        st2 = pg.evaluate("bulkState()")
        check("same rows, same order, edit kept", [r["rid"] for r in st2] == [r["rid"] for r in before] and st2[0]["name"] == "Edited Olive Polo", [(r["rid"], r["name"]) for r in st2])
        check("in-flight rows read again, done rows not", len(seen["bodies"]) - nb == 3, len(seen["bodies"]) - nb)
        pg.evaluate("switchTab('add')"); pg.wait_for_timeout(300)
        check("resume button shows the restored batch", pg.locator("#bulk-resume").is_visible() and "5" in pg.inner_text("#bulk-resume"), pg.inner_text("#bulk-resume"))
        pg.click("#bulk-resume"); pg.wait_for_timeout(300)

        # ---------- × ----------
        gone = st2[4]["rid"]
        pg.locator("#bulk-grid .bulk-card").nth(4).locator("[data-bulk-drop]").click()
        pg.wait_for_timeout(400)
        after_x = pg.evaluate(IDB)
        check("× removes the row from IndexedDB", len(after_x) == 4 and gone not in [r["rid"] for r in after_x], after_x)

        # ---------- Add all ----------
        pg.click("#bulk-add-all"); pg.wait_for_timeout(700)
        check("Add all filed 4 pieces", pg.evaluate("wardrobeItems.filter(i => i.addedVia === 'bulk').length") == 4)
        check("store empty after Add all", pg.evaluate(IDB) == [], pg.evaluate(IDB))
        pg.reload(wait_until="load")
        wait_js(pg, "window.bulkRestored && bulkRestored()", 8000)
        pg.wait_for_timeout(600)
        pg.evaluate("switchTab('add')"); pg.wait_for_timeout(300)
        check("no batch after reload, no resume button", pg.evaluate("bulkState().length") == 0 and not pg.locator("#bulk-resume").is_visible(), [pg.evaluate("(() => { const e = document.getElementById('bulk-resume'); return [getComputedStyle(e).display, e.getBoundingClientRect().height, document.querySelectorAll('#bulk-resume').length]; })()"), pg.evaluate("[document.getElementById('bulk-resume').hidden, document.getElementById('bulk-resume').textContent, currentTab]")])
        check("no duplicates after reload", pg.evaluate("wardrobeItems.length") == n0 + 4 and pg.evaluate("wardrobeItems.filter(i => i.addedVia === 'bulk').length") == 4)
        check("no page errors", not errors, errors[:3])
        b.close()
    httpd.shutdown()
    print("\nALL PASS" if not fails else "\nFAILED: " + ", ".join(fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
