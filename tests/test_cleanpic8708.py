"""Look page, full-screen view and Calendar use the high-res studio redraw
when one exists (.87.14), otherwise the clean cut-out (.87.08).

David, 24 Nov 2026, with a screenshot of a look page showing an old drawing
inside its grey studio box: "wtf is this quality looks like shit!!!!". The
look page, full-screen view and Calendar were switched to the cut-out. The
.87.14 high-res studio redraws (assets/onbody-hires) are the approved
picture for those surfaces when a look has one; looks not yet redrawn still
use the sharp cut-out on the light ground. A picture that is not one of his
drawings is left as it is.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and r.request.method == "GET" else r.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ")")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && window.cleanPic8708 && window.ONBODY && ONBODY.map && Object.keys(ONBODY.map).length > 100", timeout=60000)
    raw = page.evaluate("() => { const k = Object.keys(ONBODY.map)[0]; return ONBODY.map[k]; }")
    assert "/onbody/" in raw, raw
    stem = raw.split("/")[-1]
    base = Path(stem).stem
    # .87.21: a go-to drawn on his avatar has no older library picture, so its entry names no "onbody" file
    hires = {Path(e["onbody"]).stem for e in json.loads((ROOT / "assets/onbody-hires/manifest.json").read_text())["r"] if e.get("onbody")}
    got = page.evaluate("""raw => {
      openLookLayer({ id: 'look-test-8708', title: 'Test look', img: raw, source: 'built', swatches: [] });
      const im = document.querySelector('#look-layer-body .look-media img');
      const card = document.querySelector('#look-layer-body .look-card');
      const pane = im && im.closest('.pane');
      const out = { layer: im ? im.getAttribute('src') : null, pop: im ? im.getAttribute('data-popout') : null,
        layerBg: im ? getComputedStyle(im).backgroundColor : null,
        paneBg: pane ? getComputedStyle(pane).backgroundColor : null,
        cardBg: card ? getComputedStyle(card).backgroundColor : null };
      closeLookLayer();
      openPopout(raw, 'Test');
      const pe = document.getElementById('photo-popout');
      out.popout = document.getElementById('popout-img').getAttribute('src');
      out.light = pe.classList.contains('popout-cut8708') && getComputedStyle(pe).backgroundColor;
      closePopout();
      out.thumb = cleanPic8708(raw, true);
      out.other = cleanPic8708('assets/photos/2f6757ee2dbc.jpg');
      return out; }""", raw)
    assert got["light"] == "rgb(246, 242, 234)", ("the full-screen view is not cream #F6F2EA edge to edge", got)
    if base in hires:
        assert got["layer"] and got["layer"].endswith("onbody-hires/full/" + base + ".jpg"), ("the look page should show the high-res studio redraw", got)
        assert got["popout"].endswith("onbody-hires/full/" + base + ".jpg"), ("the full-screen view should show the high-res studio redraw", got)
        assert got["thumb"].endswith("onbody-hires/card/" + base + ".jpg"), ("Calendar should show the high-res card", got)
        assert got.get("layerBg") == "rgb(246, 242, 234)" and got.get("cardBg") == "rgb(246, 242, 234)", ("the look page picture and the card around it must be the same cream", got)
    else:
        assert got["layer"] and got["layer"].endswith("onbody-cut-hq/" + stem), ("the look page shows the studio drawing", got)
        assert got["popout"].endswith("onbody-cut-hq/" + stem), ("the full-screen view shows the studio drawing", got)
        assert got["thumb"].endswith("onbody-cut/" + stem), ("Calendar would show the studio drawing", got)
    assert got["other"] == "assets/photos/2f6757ee2dbc.jpg", got
    assert not errors, errors
    browser.close()
if base in hires:
    print("Confirmed the look page, the full-screen view and Calendar show the high-res studio redraw of %s" % stem)
else:
    print("Confirmed the look page, the full-screen view and Calendar show the cut-out of %s, not the studio drawing" % stem)
