"""Next keeps dealing fresh outfits under the icon weights, and the old burgundy-blazer drawings stay hidden (.87.31).

David, 24 Nov 2026: "My red jacket isn't fucking paisley!!!!" The nightly audit of 28 Nov saw an old drawing of
his plain Dolce & Gabbana burgundy blazer, drawn with a pattern, on Home at Formal. The 28 old drawings of that
blazer with no high-res redraw are hidden; it has 64 redraws.

The same audit found Next coming back to the same few outfits since .87.29, when the icon weights began to rank
Home's looks: on his closet, 4 to 7 different pictures in 30 taps at Nighttime Dressy and Formal, where .87.28 gave
about 25. A look shown in the last 60 deals now goes behind the ones he has not seen; the weights still order the rest.
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent
BLAZER = "item-1794964266128-402564"   # Dolce & Gabbana Burgundy Blazer


def hidden_drawings():
    src = (ROOT / "src/app.html").read_text()
    hidden = set(re.findall(r'"([0-9a-f]{16}\.webp)"', re.search(r"var ONBODY_BURGUNDY8731 = (\{.*?\});", src).group(1)))
    man = json.loads((ROOT / "assets/onbody/manifest.json").read_text())["r"]
    hi = json.loads((ROOT / "assets/onbody-hires/manifest.json").read_text())["r"]
    hk = {e["k"] for e in hi}
    ho = {e.get("onbody") for e in hi}
    old = {e["f"] for e in man if BLAZER in e["k"] and e["k"] not in hk and e["f"] not in ho}
    assert old and old <= hidden, ("an old burgundy-blazer drawing with no redraw is not hidden", sorted(old - hidden)[:5])
    redraws = sum(1 for e in hi if BLAZER in e["k"])
    assert redraws >= 40, ("too few high-res redraws of the blazer to hide the old ones", redraws)
    return len(old), redraws, man


def run(browser, man):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and r.request.method == "GET" else r.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ")")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => typeof composerLooks === 'function' && window.iconWeights81 && typeof onbodyKeys === 'function' && onbodyKeys() && HIRES.ready", timeout=30000)
    # none of the hidden drawings can reach a screen
    leaks = page.evaluate("""rows => { const keys = onbodyKeys() || {};
      return rows.filter(e => e.k.indexOf('%s') !== -1).filter(e => onbodyFileBanned(e.f) && Object.values(keys).some(v => String(v).endsWith('/' + e.f))).map(e => e.f); }""" % BLAZER, man)
    assert not leaks, ("a hidden burgundy-blazer drawing is still dealable", leaks)
    # under the icon weights, each deal leads with an outfit not shown in the last few deals
    got = page.evaluate("""() => { const out = [];
      for (const lv of [2, 4, 5]) {
        const keys = [];
        for (let i = 0; i < 10; i++) {
          const ls = composerLooks({ slot: 'rot8731', count: 6, level: lv, temp: 70 }) || [];
          if (!ls.length) break;
          keys.push(ls[0].composerKey); composerMarkSeen([ls[0]]);
        }
        out.push({ lv, n: keys.length, distinct: new Set(keys).size });
      }
      return out; }""")
    for g in got:
        if g["n"] >= 5:
            assert g["distinct"] >= g["n"] - 1, ("Next keeps coming back to the same outfits under the icon weights", got)
    assert any(g["n"] >= 5 for g in got), ("no dress level dealt enough to check", got)
    assert not errors, errors
    ctx.close()
    return got


n_old, n_redraws, man = hidden_drawings()
with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        b = engine.launch()
        got = run(b, man)
        b.close()
print("Confirmed: the %d old burgundy-blazer drawings stay hidden (%d high-res redraws of the blazer); ten deals in a row lead with %s"
      % (n_old, n_redraws, ", ".join("%d different outfits of %d at level %d" % (g["distinct"], g["n"], g["lv"]) for g in got)))
