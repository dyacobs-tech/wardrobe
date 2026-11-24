"""Dress me never cuts his arms off at the frame edge (.87.06).

David, 24 Nov 2026: "Issue with all arm cut off sleeves wrong pls fix" and "did you audit the fucking images????!".
Every picture of him is scaled (up to 15%) so he stands the same height on every screen. On The Edit > Dress me the
figure's frame clips at its edge and the picture filled the frame's whole width, so in a scaled-up picture both arms
were cut by a straight line at the frame edge (up to 5px at a phone's width; 20 of the 810 shown pictures). The
picture now takes 88% of the frame's width.
Checks, at two phone widths: the pictures that need the most room once scaled (worked out from every shown picture's
drawing and feet.json, not a fixed list) are put in the Dress me frame one by one, and both arms stay inside it.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from wardrobe_fixture import photographed_closet  # noqa: E402

src = (ROOT / "src/app.html").read_text()
seed = json.loads(re.search(r"var ONBODY_SEED = (\{.*?\});\n", src).group(1))
hidden = set(re.findall(r'"([0-9a-f]{16})\.webp"', "".join(re.findall(r"var ONBODY_(?:TUCK_EXCLUDE|REJECTED859|TEELONG879|AUDIT883) = \{.*?\};", src))))
feet = json.loads((ROOT / "assets/onbody-cut/feet.json").read_text())["feet"]


def need(stem):
    """px (of 362) his arms would reach past the picture's own edge once the app shifts and scales it"""
    f = feet[stem]
    fig = 1200 - f[0] - f[2]
    k = max(0.9, min(1.15, 1106 / fig))
    a = np.asarray(Image.open(ROOT / "assets/onbody-cut" / (stem + ".webp")).convert("RGBA"))[..., 3] >= 128
    cols = np.where(a.any(0))[0]
    left = 181 + k * (cols.min() - f[1] - 181)
    right = 181 + k * (cols.max() + 1 - f[1] - 181)
    return max(-left, right - 362)


shown = [e["f"][:-5] for e in seed["r"] if e["f"][:-5] not in hidden and e["f"][:-5] in feet]
ranked = sorted(shown, key=need, reverse=True)
RISK = ranked[:6]
assert need(RISK[0]) > 2, ("the riskiest picture no longer reaches past its edge; pick a harder case", RISK[0], need(RISK[0]))

MEASURE = """async (src) => {
  const img = document.querySelector('.dm-av841 img');
  img.removeAttribute('data-h874'); img.style.scale = ''; img.style.translate = '';
  img.src = src;
  await img.decode();
  window.heightAll874();
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
  const g = c.getContext('2d'); g.drawImage(img, 0, 0);
  const d = g.getImageData(0, 0, c.width, c.height).data;
  let L = c.width, R = -1;
  for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) if (d[(y * c.width + x) * 4 + 3] >= 128) { if (x < L) L = x; if (x > R) R = x; }
  const r = img.getBoundingClientRect(), ax = r.width / img.offsetWidth;
  const cw = img.clientWidth, ch = img.clientHeight, f = Math.min(cw / img.naturalWidth, ch / img.naturalHeight);
  const offX = (cw - img.naturalWidth * f) / 2;
  const fr = img.parentElement, fb = fr.getBoundingClientRect();
  const frameL = fb.left + fr.clientLeft, frameR = frameL + fr.clientWidth;
  return { scale: img.style.scale, armL: r.left + ax * (offX + L * f), armR: r.left + ax * (offX + (R + 1) * f), frameL, frameR };
}"""

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for width in (402, 375):
        ctx = browser.new_context(viewport={"width": width, "height": 874}, device_scale_factor=1, is_mobile=True, has_touch=True, service_workers="block")
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and r.request.method == "GET" else r.abort())
        ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ")")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL, wait_until="load")
        page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function' && window.heroFeet801 && window.heroFeet801() && window.heightAll874", timeout=60000)
        page.evaluate("() => document.querySelector('#bottombar [data-section=\"inspo\"]').click()")
        page.wait_for_timeout(500)
        page.evaluate("() => document.querySelector('[data-ins-seg=\"dress\"]').click()")
        page.wait_for_selector(".dm-av841 img", timeout=15000)
        page.wait_for_timeout(1500)   # the height script starts 600ms after boot
        scaled = 0
        for stem in RISK:
            m = page.evaluate(MEASURE, "assets/onbody-cut/%s.webp" % stem)
            scaled += bool(m["scale"])
            assert m["armL"] >= m["frameL"] + 0.5 and m["armR"] <= m["frameR"] - 0.5, ("an arm is cut off at the Dress me frame edge", width, stem, round(need(stem), 1), m)
        assert scaled >= 4, ("the app did not scale the test pictures, so the check proves nothing", width, scaled)
        assert not errors, errors
        ctx.close()
    browser.close()
print("Confirmed at 402 and 375px: the %d pictures that need the most room (up to %.1fpx past their own edge once scaled) keep both arms inside the Dress me frame" % (len(RISK), need(RISK[0])))
