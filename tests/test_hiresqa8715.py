"""Picture QA for the cream high-res avatar on Dress me, the look page,
the full-screen view and the Looks grid (.87.15).

David, 26 Nov 2026, forwarding Claude's preview pass: Dress me placed the
new picture low, with a blank band above his head; the full-screen view had
black bars above and below the cream picture; the look page picture sat in
a slightly different cream box from the card around it; the Looks grid mixed
new and old cards. The Edit > New + mine still uses a separate on-body set
that has no hires copy yet and is reported, not redrawn (credits at reserve).
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
CREAM = "rgb(246, 242, 234)"


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and r.request.method == "GET" else r.abort())
    ctx.add_init_script(
        "localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");"
        "localStorage.setItem('wardrobe.formality','5');"
    )
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && window.HIRES && HIRES.ready && window.cleanPic8708", timeout=60000)

    # Looks grid at Evening Dressy: every on-body card with a hires copy must use it
    page.locator("#section-ideas").tap()
    page.wait_for_function("() => document.querySelectorAll('#cf-grid .mine-avatar').length >= 4", timeout=60000)
    page.wait_for_timeout(400)
    grid = page.evaluate("""() => [...document.querySelectorAll('#cf-grid article, #cf-grid .cf-card')].map((card, i) => {
      const btn = card.querySelector('[data-cf-open]');
      const img = card.querySelector('.mine-avatar, img[data-onbody]');
      const src = img ? (img.getAttribute('src') || '') : '';
      const look = (btn && window.__cfLooks81) ? __cfLooks81()[Number(btn.dataset.cfOpen)] : null;
      const hi = (look && typeof hiresForLook === 'function') ? (hiresForLook(look, 'card') || '') : '';
      return { i, src, hi, missed: !!(hi && src && src !== hi) };
    })""")
    missed = [c for c in grid if c["missed"]]
    assert grid and len(grid) >= 4, grid
    assert not missed, ("Looks grid still shows an old picture when a hires copy exists", missed)

    # Look page + full-screen: same cream, no dark letterbox
    raw = page.evaluate("() => { const k = Object.keys(ONBODY.map)[0]; return ONBODY.map[k]; }")
    got = page.evaluate("""raw => {
      openLookLayer({ id: 'look-test-8715', title: 'Test look', img: raw, source: 'built', swatches: [] });
      const im = document.querySelector('#look-layer-body .look-media img');
      const card = document.querySelector('#look-layer-body .look-card');
      const out = {
        layerBg: im ? getComputedStyle(im).backgroundColor : null,
        cardBg: card ? getComputedStyle(card).backgroundColor : null
      };
      closeLookLayer();
      openPopout(raw, 'Test');
      const pe = document.getElementById('photo-popout');
      out.popBg = pe ? getComputedStyle(pe).backgroundColor : null;
      out.popClass = pe ? pe.classList.contains('popout-cut8708') : false;
      closePopout();
      return out;
    }""", raw)
    assert got["layerBg"] == CREAM and got["cardBg"] == CREAM, ("look page picture and card are not the same cream", got)
    assert got["popClass"] and got["popBg"] == CREAM, ("full-screen view is not cream #F6F2EA edge to edge", got)

    # Dress me: hires figure fills the 9:16 frame, head near the top
    page.locator("#section-inspo").tap()
    page.wait_for_timeout(600)
    page.evaluate("""() => { const b = document.querySelector('[data-ins-seg="dress"]'); if (b) b.click(); }""")
    page.wait_for_function("() => document.querySelector('.dm-av841 img') && document.querySelector('.dm-av841 img').naturalWidth > 20", timeout=30000)
    dress = page.evaluate("""() => {
      const frame = document.querySelector('.dm-av841');
      const img = document.querySelector('.dm-av841 img');
      const fr = frame.getBoundingClientRect(), ir = img.getBoundingClientRect();
      return {
        src: img.getAttribute('src') || '',
        ar: fr.width / fr.height,
        bandAbove: ir.top - fr.top,
        bandBelow: fr.bottom - ir.bottom,
        widthPct: img.clientWidth / frame.clientWidth,
        bg: getComputedStyle(frame).backgroundColor
      };
    }""")
    assert "onbody-hires" in dress["src"], ("Dress me is not using a hires cream picture", dress)
    assert abs(dress["ar"] - 9 / 16) < 0.05, ("Dress me frame is not 9:16", dress)
    assert dress["bandAbove"] <= 8, ("Dress me still leaves a blank band above his head", dress)
    assert dress["widthPct"] > 0.95, ("Dress me hires picture does not fill the frame width", dress)
    assert dress["bg"] == CREAM, ("Dress me frame is not cream", dress)

    assert not errors, errors
    browser.close()

print("Confirmed Dress me fills its 9:16 cream frame, the look page and card are the same cream, the full-screen view is cream edge to edge, and the Looks grid does not keep an old picture when a hires copy exists")
