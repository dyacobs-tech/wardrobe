"""The look page, the full-screen view and Calendar show his clean cut-out, not the studio drawing (.87.08).

David, 24 Nov 2026, with a screenshot of a look page showing his picture inside its grey studio box: "wtf is this
quality looks like shit!!!!". Home, Looks and the outfit view show the cut-out of each picture on the app's own
background; the look page, the full-screen view and the Calendar week still showed the raw drawing with its grey
studio backdrop. They now show the cut-out too (the sharp copy where the picture is big, the small copy in Calendar).
Checks: a look whose picture is one of his drawings opens on the look page with the sharp cut-out; the full-screen
view opened with the raw drawing shows the sharp cut-out on the light ground; Calendar thumbnails ask for the small
cut-out; a picture that is not one of his drawings is left as it is.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

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
    got = page.evaluate("""raw => {
      openLookLayer({ id: 'look-test-8708', title: 'Test look', img: raw, source: 'built', swatches: [] });
      const im = document.querySelector('#look-layer-body .look-media img');
      const out = { layer: im ? im.getAttribute('src') : null, pop: im ? im.getAttribute('data-popout') : null };
      closeLookLayer();
      openPopout(raw, 'Test');
      const pe = document.getElementById('photo-popout');
      out.popout = document.getElementById('popout-img').getAttribute('src');
      out.light = pe.classList.contains('popout-cut8708') && getComputedStyle(pe).backgroundColor;
      closePopout();
      out.thumb = cleanPic8708(raw, true);
      out.other = cleanPic8708('assets/photos/2f6757ee2dbc.jpg');
      return out; }""", raw)
    assert got["layer"] and got["layer"].endswith("onbody-cut-hq/" + stem), ("the look page shows the studio drawing", got)
    assert got["popout"].endswith("onbody-cut-hq/" + stem), ("the full-screen view shows the studio drawing", got)
    assert got["light"] == "rgb(246, 242, 234)", ("the full-screen view is not on the light ground", got)
    assert got["thumb"].endswith("onbody-cut/" + stem), ("Calendar would show the studio drawing", got)
    assert got["other"] == "assets/photos/2f6757ee2dbc.jpg", got
    assert not errors, errors
    browser.close()
print("Confirmed the look page, the full-screen view and Calendar show the cut-out of %s, not the studio drawing" % stem)
