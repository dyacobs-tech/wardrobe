"""A top is untucked, or tucked with a belt: pictures drawn tucked with no belt are hidden (.87.34).

David, 28 Nov 2026, on a Home picture of a white pocket tee tucked into dark indigo jeans under a navy blazer,
no belt: "wtf!!!!!!! Untucked or WITH belt!!!!!!"

Every high-res picture was checked by eye. 193 show a top tucked in with no belt (tees under open overshirts and
blazers, shirts into chinos and jeans, Formal shirt-and-tie looks) and are hidden until they are redrawn. Tucked
with a belt is allowed and stays. His 17 Nov Go-to was one of them; it is redrawn untucked, with the old picture
removed, so he keeps every Go-to.
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent
OLD_GOTO = "6409c0b9a3a55aa1"

src = (ROOT / "src/app.html").read_text()
hidden = set(re.findall(r'"([0-9a-f]{16})"', re.search(r"var HIRES_NOBELT8734 = (\{.*?\});", src).group(1)))
man = json.loads((ROOT / "assets/onbody-hires/manifest.json").read_text())["r"]
stems = {Path(e["full"]).stem: e for e in man}
assert len(hidden) == 193 and hidden <= set(stems), ("the hidden no-belt pictures must be real entries", len(hidden), sorted(hidden - set(stems))[:5])
assert not [s for s in hidden if stems[s].get("goto")], "a Go-to is hidden instead of redrawn"
# the 17 Nov Go-to is the redraw, and the old tucked picture is gone
g17 = [e for e in man if e.get("goto") == "2026-11-17"]
assert len(g17) == 1 and OLD_GOTO not in g17[0]["full"], g17
for kind in ("card", "full"):
    assert (ROOT / g17[0][kind]).is_file(), g17[0][kind]
    assert not (ROOT / ("assets/onbody-hires/%s/%s.jpg" % (kind, OLD_GOTO))).exists(), "the old tucked Go-to picture is still there"
assert OLD_GOTO not in stems


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and r.request.method == "GET" else r.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => typeof HIRES !== 'undefined' && HIRES.ready", timeout=30000)
    got = page.evaluate("""stems => { const st = e => String(e.full || e.card || '').replace(/^.*\\//, '').replace(/\\.[a-z]+$/i, '');
      const v = Object.values(HIRES.map); return { shown: v.filter(e => stems.includes(st(e))).length, total: v.length,
        g17: v.filter(e => e.goto === '2026-11-17').map(st) }; }""", sorted(hidden))
    assert got["shown"] == 0, ("a picture tucked with no belt is still in use", got)
    assert got["g17"] == [Path(g17[0]["full"]).stem], ("the redrawn 17 Nov Go-to is not in use", got)
    assert not errors, errors
    ctx.close()
    return got


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        b = engine.launch()
        got = run(b)
        b.close()
print("Confirmed: the %d pictures tucked with no belt are hidden (%d high-res pictures still in use); the 17 Nov Go-to is the untucked redraw" % (len(hidden), got["total"]))
