"""Shoe rotation in the outfit engine (.87.13).

David, 24 Nov 2026, approving the audit's fix after his Edward Green Polperro came up in about one Evening Dressy look
in four (and earlier, 23 Nov: "appears my velasca slippers in every picture '!!!!! Where are my other shoes??????"):
no single shoe in more than 15% of the looks at a dress level, a repeat window of 8 looks, the favourite-brand lift
halved, and his shoes that were never dealt brought in where the level fits.
Checks (fixture closet, the outfits drawn on him, 60 Home deals per level at 62°F and 78°F): at every level with at
least 7 shoes to choose from, no shoe is worn more than 3 times in any 20 looks in a row, and no shoe takes more
than 15% of the 60; the shoes of a look are not dealt again in the next look when other shoes fit.
"""
import collections
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent
MAN = json.loads((ROOT / "assets/onbody/manifest.json").read_text())

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and r.request.method == "GET" else r.abort())
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof onbodyFileBanned === 'function'", timeout=120000)
    res = page.evaluate("""([items, man]) => {
      const C = window.WardrobeComposer;
      const rk = {};
      man.r.forEach(e => { if (!onbodyFileBanned(e.f) && !onbodyKeyBanned866(e.k)) rk[e.k] = 'assets/onbody/' + e.f; });
      const deck = C.build(items, rk);
      const out = {};
      for (const L of [1, 2, 3, 4, 5, 6]) for (const T of [62, 78]) {
        let recent = [], exp = {}, seq = [], seed = 777;
        const rng = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
        for (let i = 0; i < 60; i++) {
          const o = deck.deal(1, { level: L, temp: T, recent: recent.slice(-200), exposure: exp, rng: rng, onlyKeys: rk, strictKeys: true });
          if (!o.length) break;
          seq.push(o[0].shoes.id); recent.push(o[0].key); o[0].ids.forEach(id => exp[id] = (exp[id] || 0) + 1);
        }
        const shoesAtLevel = new Set(deck.forLevel(L).filter(c => rk[c.key]).map(c => c.s.id));
        out[L + '_' + T] = { seq: seq, shoes: shoesAtLevel.size };
      }
      return out;
    }""", [photographed_closet(), MAN])
    browser.close()

checked = 0
for k, v in res.items():
    seq, n = v["seq"], len(v["seq"])
    if v["shoes"] < 7 or n < 20:
        continue
    checked += 1
    win = max(collections.Counter(seq[i:i + 20]).most_common(1)[0][1] for i in range(0, n - 19))
    top = collections.Counter(seq).most_common(1)[0][1]
    back2back = sum(1 for i in range(1, n) if seq[i] == seq[i - 1])
    assert win <= 3, (k, "a shoe is worn %d times in 20 looks" % win)
    assert top <= 0.15 * n + 1e-9, (k, "a shoe takes %d of %d looks" % (top, n))
    assert back2back == 0, (k, "the same shoes in two looks in a row", back2back)
assert checked >= 4, ("too few levels had 7 shoes to check", {k: v["shoes"] for k, v in res.items()})
print("Confirmed: %d level/temperature runs, no shoe over 3 in 20 looks or over 15%% of 60, never twice in a row" % checked)
