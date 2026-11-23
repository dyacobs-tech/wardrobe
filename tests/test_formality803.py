"""Build .80.34: formality levels and tuck rules.

Engine (fixture_closet83.json, 74°F):
  * Casual and Smart Casual deals never include a blazer or suit
  * Evening Dressy (level 5) always wears a blazer (.86.34)
  * Formal / Black Tie deals are tailored
  * Flannel shirts are never tucked, with or without a layer
  * T-shirts, dress tees included, are untucked, even under a blazer (.86.83; David, 22 Nov 2026:
    "Untucked under blazer.")
  * Other shirts, polos and knits under a blazer are tucked
  * 26 existing on-body renders that break those tuck rules are excluded

UI (WebKit standalone 390×844, local server, workers.dev blocked):
  * Picking Casual on the Home type menu sets and stores formality 3
    and immediately re-deals a look with no blazer

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_formality803.py
"""
from __future__ import annotations

import http.server
import json
import os
import re
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wardrobe_fixture import garments_for_all_levels, photographed_closet
from buildinfo import CURRENT_BUILD  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BUILD = CURRENT_BUILD
FIXTURE_PHOTO = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
FIXTURE = json.loads((Path(__file__).resolve().parent / "fixture_closet83.json").read_text())
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")
STANDALONE_INIT = """
Object.defineProperty(window.navigator, 'standalone', { get: () => true, configurable: true });
if (window.matchMedia) {
  const orig = window.matchMedia.bind(window);
  window.matchMedia = (q) => String(q).includes('display-mode: standalone')
    ? { matches: true, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, onchange: null, dispatchEvent() { return false; } }
    : orig(q);
}
"""

ENGINE_JS = """(items) => {
  const C = window.WardrobeComposer;
  const out = { ok: !!C && typeof C.tuckOf === 'function' };
  if (!C) return out;
  const deck = C.build(items);
  const blazerOf = (o) => !!(o.layer && ['blazer', 'suit', 'dinner'].includes(o.layer.kind));
  out.rates = {};
  for (let L = 1; L <= 7; L++) {
    let n = 0, b = 0, recent = [], exposure = {};
    for (let i = 0; i < 50; i++) {
      const batch = deck.deal(1, { level: L, temp: 74, recent, exposure });
      if (!batch.length) break;
      const o = batch[0];
      n++; if (blazerOf(o)) b++;
      recent.push(o.key);
      o.ids.forEach(id => { exposure[id] = (exposure[id] || 0) + 1; });
    }
    out.rates[L] = { n, blazers: b, rate: n ? b / n : 0 };
  }
  const flan = deck.tops.filter(t => /flannel/i.test(t.n))[0];
  const blaz = deck.layerOpts.filter(l => l && l.kind === 'blazer')[0];
  const shirt = deck.tops.filter(t => t.kind === 'shirt' && !/flannel/i.test(t.n) && !t.casualShirt)[0];
  const knit = deck.tops.filter(t => t.kind === 'knit')[0];
  const polo = deck.tops.filter(t => t.kind === 'polo')[0];
  const dressTee = C.profile({ id: 'dt', name: 'Sunspel Mercerised Silk Dress Tee', category: 'Tees', colourName: 'Navy', colourHex: '#1a1f3c' });
  const casualTee = C.profile({ id: 'ct', name: 'White Cotton Crew-Neck Tee', category: 'Tees', colourName: 'White', colourHex: '#f5f5f2' });
  out.tuck = {
    flannelAlone: C.tuckOf(flan, null),
    flannelBlazer: C.tuckOf(flan, blaz),
    flannelPrompt: C.tuckPromptOf(flan, blaz, false),
    dressShirtBlazer: C.tuckOf(shirt, blaz),
    knitBlazer: C.tuckOf(knit, blaz),
    poloBlazer: C.tuckOf(polo, blaz),
    dressTeeFlag: !!dressTee.dressTee,
    dressTeeAlone: C.tuckOf(dressTee, null),
    dressTeeBlazer: C.tuckOf(dressTee, blaz),
    casualTeeFlag: !!casualTee.dressTee,
    casualTeeAlone: C.tuckOf(casualTee, null),
    casualTeeBlazer: C.tuckOf(casualTee, blaz)
  };
  let badFlan = 0, badBlazer = 0;
  deck.combos.forEach(c => {
    if (/flannel/i.test(c.t.n) && c.tuck) badFlan++;
    if (c.l && (c.l.kind === 'blazer' || c.l.kind === 'suit') && !/flannel/i.test(c.t.n)
        && (c.t.kind === 'shirt' || c.t.kind === 'polo' || c.t.kind === 'knit') && !c.tuck) badBlazer++;
  });
  out.comboIntegrity = { badFlan, badBlazer, n: deck.combos.length };
  out.excludeCount = window.ONBODY_TUCK_EXCLUDE_COUNT;
  const banned = Object.keys(window.ONBODY_TUCK_EXCLUDE || {});
  out.bannedFiles = banned.length;
  let stillMapped = 0, srcHit = 0;
  Object.keys(window.ONBODY && window.ONBODY.map || {}).forEach(k => {
    const f = (window.ONBODY.map[k] || '').split('/').pop();
    if (window.ONBODY_TUCK_EXCLUDE && window.ONBODY_TUCK_EXCLUDE[f]) stillMapped++;
  });
  banned.forEach(f => {
    const k = Object.keys((window.ONBODY && window.ONBODY.map) || {}).find(id => (window.ONBODY.map[id] || '').split('/').pop() === f);
    if (typeof onbodySrc === 'function' && onbodySrc(k || f)) srcHit++;
  });
  const keys = typeof onbodyKeys === 'function' ? onbodyKeys() : null;
  let keysHit = 0;
  if (keys) Object.keys(keys).forEach(k => { if (banned.indexOf((keys[k] || '').split('/').pop()) !== -1) keysHit++; });
  out.exclude = { stillMapped, srcHit, keysHit, keys: keys ? Object.keys(keys).length : 0 };
  return out;
}"""


def start_server():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(ROOT), **k)

        def log_message(self, *a):
            pass

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Quiet)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def main() -> int:
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    results = []

    def check(name, ok, detail=""):
        results.append(bool(ok))
        print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail != "" else ""))

    httpd, url = start_server()
    try:
        with sync_playwright() as p:
            browser = p.webkit.launch()
            ctx = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                service_workers="block",
            )
            ctx.add_init_script(STANDALONE_INIT)
            seed = {
                "items": photographed_closet(),
                "todaySource": "wardrobe",
                "formality": 5,
            }
            ctx.add_init_script(
                "(() => { if (localStorage.getItem('wardrobe.items')) return; const S = %s;"
                " for (const k in S) localStorage.setItem('wardrobe.' + k, JSON.stringify(S[k])); })();"
                % json.dumps(seed)
            )
            ctx.route(BLOCK, lambda r: r.abort())
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url, wait_until="load")
            page.wait_for_timeout(2000)
            check("build is current", page.evaluate("window.WARDROBE_BUILD") == BUILD, page.evaluate("window.WARDROBE_BUILD"))

            # Weather at Palm Beach 74°F if the live weather is not in yet
            page.evaluate(
                """() => { if (typeof currentWeather !== 'undefined') {
                  currentWeather = Object.assign({}, currentWeather || {}, { temp: 74, label: 'Clear', rain: 0 });
                } }"""
            )
            eng = page.evaluate(ENGINE_JS, FIXTURE + garments_for_all_levels())
            check("composer and tuck helpers present", eng.get("ok"), str(eng.get("ok")))
            rates = eng.get("rates") or {}
            for L in (1, 2, 3, 4):
                r = rates.get(str(L)) or rates.get(L) or {}
                check(
                    f"50 deals at level {L} have no blazers",
                    r.get("n") == 50 and r.get("blazers") == 0,
                    r,
                )
            r5 = rates.get("5") or rates.get(5) or {}
            # .86.34 (David): level 5 is Evening Dressy, always a blazer
            check(
                "50 Evening Dressy deals all wear a blazer",
                r5.get("n") == 50 and r5.get("blazers") == 50,
                r5,
            )
            for L in (6, 7):
                r = rates.get(str(L)) or rates.get(L) or {}
                check(
                    f"50 deals at level {L} are all tailored",
                    r.get("n") == 50 and r.get("blazers") == 50,
                    r,
                )

            tk = eng.get("tuck") or {}
            check("flannel alone is untucked", tk.get("flannelAlone") is False, tk)
            check("flannel under a blazer is untucked", tk.get("flannelBlazer") is False, tk)
            check(
                "flannel prompt says untucked",
                "untucked" in (tk.get("flannelPrompt") or ""),
                tk.get("flannelPrompt"),
            )
            check("dress shirt under a blazer is tucked", tk.get("dressShirtBlazer") is True, tk)
            check("knit under a blazer is tucked", tk.get("knitBlazer") is True, tk)
            check("polo under a blazer is tucked", tk.get("poloBlazer") is True, tk)
            # .86.83: David, 22 Nov 2026, of T-shirts under a blazer: "Untucked under blazer." Every tee is untucked now.
            check("dress T-shirt is flagged and untucked (David: \"Untucked under blazer.\")", tk.get("dressTeeFlag") and tk.get("dressTeeAlone") is False and tk.get("dressTeeBlazer") is False, tk)
            check("casual T-shirt may be untucked under a blazer", (not tk.get("casualTeeFlag")) and tk.get("casualTeeAlone") is False and tk.get("casualTeeBlazer") is False, tk)
            ci = eng.get("comboIntegrity") or {}
            check("no fixture combo breaks the tuck rules", ci.get("badFlan") == 0 and ci.get("badBlazer") == 0, ci)

            check("26 on-body renders are listed for exclusion", eng.get("excludeCount") == 26 and eng.get("bannedFiles") == 26, (eng.get("excludeCount"), eng.get("bannedFiles")))
            ex = eng.get("exclude") or {}
            check("excluded renders are not in onbodyKeys or onbodySrc", ex.get("stillMapped") == 0 and ex.get("srcHit") == 0 and ex.get("keysHit") == 0, ex)

            # UI: start on Business Casual (seeded 5), switch to Casual, look re-deals without a blazer
            before = page.evaluate(
                """() => ({
                  formality: window.formalityLevel,
                  label: (document.getElementById('today-type-label') || {}).textContent,
                  title: todayLook && todayLook.title,
                  key: todayLook && todayLook.composerKey,
                  pieces: ((todayLook && todayLook.fwPieces) || []).map(p => p.category + '|' + p.name)
                })"""
            )
            page.locator("#today-type-btn").click()
            page.wait_for_selector("#today-type-row", state="visible")
            page.locator('#today-type-row [data-studio-type="3"]').click()
            page.wait_for_timeout(600)
            after = page.evaluate(
                """() => {
                  let stored = null;
                  try { stored = JSON.parse(localStorage.getItem('wardrobe.formality')); } catch (e) { stored = localStorage.getItem('wardrobe.formality'); }
                  const pieces = ((todayLook && todayLook.fwPieces) || []);
                  const blazer = pieces.some(p => p.category === 'Blazers' || p.category === 'Suits' || /blazer|sport\\s*coat/i.test(p.name || ''));
                  return {
                    formality: window.formalityLevel,
                    stored,
                    label: (document.getElementById('today-type-label') || {}).textContent,
                    title: todayLook && todayLook.title,
                    key: todayLook && todayLook.composerKey,
                    blazer,
                    menuHidden: document.getElementById('today-type-row').hidden
                  };
                }"""
            )
            check(
                "Evening Casual pick sets and stores formality 3",
                after.get("formality") == 3 and after.get("stored") == 3 and after.get("label") == "Evening Casual",
                after,
            )
            check("type menu closes after the pick", after.get("menuHidden") is True, after)
            check(
                "Casual re-deal is a new look with no blazer",
                after.get("key") and after.get("key") != before.get("key") and after.get("blazer") is False,
                {"before": before, "after": after},
            )
            check("no page errors", not errors, errors)
            browser.close()
    finally:
        httpd.shutdown()

    failed = results.count(False)
    print(f"{sum(results)} passed, {failed} failed, of {len(results)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
