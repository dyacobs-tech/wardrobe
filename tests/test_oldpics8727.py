"""The old pictures that have a high-res redraw are gone, and the app never asks for one (.87.27).

David, 27 Nov 2026, on the published site being about 28% over GitHub's 1 GB limit: "Do 2" (the
second option offered: remove the old pictures of him that now have a high-res replacement).

2,436 files (98.8 MB) were removed: for each of 812 redrawn outfits, the old drawing in
assets/onbody/ and its two cut-outs in assets/onbody-cut/ and assets/onbody-cut-hq/.

Three places in the app still reached for an old picture and were changed:
  * Home at start-up showed the old drawing until the high-res list arrived. The list is now kept on
    the phone and read first, and Home waits for it instead of painting an old drawing.
  * The full-screen outfit view used the old path for an outfit kept from before the redraws.
  * The start-up preload fetched the old cut-out.
Any picture that still fails on an old path is swapped for its high-res redraw.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from oldpics import OLD_DIRS, is_redrawn, redrawn, stem_of
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent
OLD_RE = r"assets/(onbody|onbody-cut|onbody-cut-hq)/([0-9a-f]{8,})\.(webp|png)"


def files_on_disk():
    rows = json.loads((ROOT / "assets/onbody/manifest.json").read_text())["r"]
    both, neither, kept = [], [], 0
    for e in rows:
        st = stem_of(e["f"])
        have = [(ROOT / d / (st + ".webp")).is_file() for d in OLD_DIRS]
        if is_redrawn(st):
            if any(have):
                both.append(st)
        else:
            kept += 1
            if not all(have):
                neither.append(st)
    assert not both, ("an outfit has a high-res redraw and still carries its old pictures", len(both), both[:5])
    assert not neither, ("an outfit has no high-res redraw and its old picture is missing", neither[:5])
    cut = json.loads((ROOT / "assets/onbody-cut/manifest.json").read_text())["map"]
    assert cut, "the cut-out list is empty"
    gone = [k for k, v in cut.items() if not (ROOT / v).is_file()]
    assert not gone, ("the cut-out list names files that are not there", gone[:5])
    assert not [k for k in cut if is_redrawn(k)], "the cut-out list still names a redrawn outfit"
    # nothing left over in the old folders that no list names
    listed = {stem_of(e["f"]) for e in rows}
    for d in OLD_DIRS:
        stray = [p.name for p in (ROOT / d).glob("*.webp") if p.stem in redrawn() and is_redrawn(p.stem)]
        assert not stray, ("old picture of a redrawn outfit left in " + d, stray[:5])
    return kept, len(rows) - kept, len(listed)


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    asked, missing = [], []

    def route(r):
        req = r.request
        if not (req.url.startswith(URL) and req.method == "GET"):
            return r.abort()
        if req.url.split("?")[0].endswith("assets/onbody-hires/manifest.json"):
            # the high-res list arrives late, as on a slow connection
            ctx_page.wait_for_timeout(1200)
        return r.continue_()

    ctx.route("**/*", route)
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");" +
                        "localStorage.setItem('wardrobe.formality','2')")
    page = ctx.new_page()
    global ctx_page
    ctx_page = page
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    import re
    page.on("request", lambda q: asked.append(q.url) if re.search(OLD_RE, q.url) else None)
    page.on("response", lambda p: missing.append(p.url) if p.status >= 400 and "/assets/" in p.url else None)

    hero = """() => { const i = document.getElementById('today-img'); return { src: i.getAttribute('src') || '', ok: !i.hidden && i.complete && i.naturalWidth > 1,
      ready: typeof HIRES !== 'undefined' && HIRES.ready, saved: !!localStorage.getItem('wardrobe.hires') }; }"""
    shown = "() => { const i = document.getElementById('today-img'); return !i.hidden && i.complete && i.naturalWidth > 1 && /assets\\/onbody(-hires|-cut)\\//.test(i.getAttribute('src') || ''); }"

    # first open: nothing saved on the phone, the list is late; Home waits and then shows a picture
    page.goto(URL, wait_until="load")
    page.wait_for_function(shown, timeout=30000)
    first = page.evaluate(hero)
    assert first["ready"] and first["saved"], ("the high-res list was not kept on the phone", first)

    # second open: the list on the phone is used at once, so Home's picture is there before the network list returns
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function(shown, timeout=30000)
    second = page.evaluate(hero)
    assert second["ok"], second

    # Next a few times, then the full-screen outfit view
    for _ in range(4):
        page.evaluate("() => document.getElementById('today-next').click()")
        page.wait_for_timeout(900)
    page.wait_for_function(shown, timeout=15000)
    # an outfit kept from before the redraws still names its old picture: the outfit view must show the redraw
    old_named = page.evaluate("""() => { const k = Object.keys(HIRES.map).filter(k => HIRES.map[k].onbody && todayLook && k === (typeof hiresKeyOfLook === 'function' ? hiresKeyOfLook(todayLook) : ''))[0];
      if (!k) return null; todayLook.fwRender = 'assets/onbody/' + HIRES.map[k].onbody; return HIRES.map[k].full; }""")
    page.evaluate("() => document.getElementById('today-img').click()")
    page.wait_for_function("() => { const i = document.getElementById('ov-img'); return i && i.complete && i.naturalWidth > 1; }", timeout=15000)
    ov = page.evaluate("() => document.getElementById('ov-img').getAttribute('src')")
    assert "/onbody-hires/" in ov or "/onbody-cut" in ov, ("the outfit view is not showing a redraw or a cut-out", ov)
    if old_named:
        assert ov == old_named, ("an outfit that names its old picture did not get its high-res redraw in the outfit view", ov, old_named)

    # the safety net: a picture that fails on an old path becomes its high-res redraw
    stem = next(s for s in sorted(redrawn()) if is_redrawn(s))
    page.evaluate("s => { const i = document.createElement('img'); i.id = 'net8727'; i.style.width = '80px'; i.src = 'assets/onbody/' + s + '.webp'; document.body.appendChild(i); }", stem)
    page.wait_for_function("() => { const i = document.getElementById('net8727'); return /onbody-hires\\//.test(i.getAttribute('src') || '') && i.complete && i.naturalWidth > 1; }", timeout=15000)
    net = [u for u in missing if stem in u]
    assert len(net) == 1, ("the safety-net check should fail exactly once on the old path", net)

    # apart from that deliberate one, the app never asked for the old picture of a redrawn outfit, and nothing was missing
    bad = [u.split("/assets/")[1] for u in asked if is_redrawn(re.search(OLD_RE, u).group(2)) and stem not in u]
    assert not bad, ("the app asked for the old picture of a redrawn outfit", bad[:6])
    gone = [u.split("/assets/")[1] for u in missing if stem not in u]
    assert not gone, ("pictures failed to load", gone[:6])
    assert not errors, errors
    ctx.close()
    return first["src"][-34:], second["src"][-34:], ov[-34:]


kept_n, redrawn_n, listed_n = files_on_disk()
with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        got = run(browser)
        browser.close()
print("Confirmed: %d outfits keep their old picture and %d have only the high-res redraw; Home, Next, the outfit view and a late "
      "high-res list never ask for a removed picture; a failed old path swaps to its redraw" % (kept_n, redrawn_n))
