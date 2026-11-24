"""Build .80.34: Wardrobe Rules.

Parser, seed rules, engine enforcement (50 generated looks violate
zero enforced rules), Profile → Wardrobe Rules UI, light/dark 390
screenshots.

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_rules8034.py
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E402
from buildinfo import CURRENT_BUILD

ROOT = Path(__file__).resolve().parents[1]
BUILD = CURRENT_BUILD
FIXTURE_PHOTO = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
FIXTURE = json.loads((Path(__file__).resolve().parent / "fixture_closet83.json").read_text())
# Extra pieces so dress-tee / casual-tee rules have something to apply to.
EXTRA = [
    {"id": "wr-dress-tee", "name": "White Dress T-Shirt", "category": "Tees", "colourName": "White", "colourHex": "#f4f1ea"},
    {"id": "wr-casual-tee", "name": "Olive Casual T-Shirt", "category": "Tees", "colourName": "Olive", "colourHex": "#6b7a4a"},
]
CLOSET = FIXTURE + EXTRA
BLOCK = re.compile(r"https?://[^/]*workers\.dev/.*")
OUT = Path(os.environ.get("AUDIT_OUT") or "/workspace/wardrobe-audit/wardrobe-rules")
STANDALONE_INIT = """
Object.defineProperty(window.navigator, 'standalone', { get: () => true, configurable: true });
if (window.matchMedia) {
  const orig = window.matchMedia.bind(window);
  window.matchMedia = (q) => String(q).includes('display-mode: standalone')
    ? { matches: true, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, onchange: null, dispatchEvent() { return false; } }
    : orig(q);
}
"""

PARSER_CASES = [
    ("Under a blazer or sport coat, shirts, polos and knits are tucked; casual T-shirts may be untucked.",
     True, "shirts, polos and knits must be tucked under blazers or sport coats", "casual T-shirts may be untucked under blazers"),
    ("Dress T-shirts are always tucked.", True, "dress T-shirts must be tucked", None),
    ("Flannel shirts are never tucked.", True, "flannel shirts must never be tucked", None),
    ("Never wear brown shoes with black trousers", True, "never pair brown shoes with black trousers", None),
    ("No blazers on weekends", True, "no blazers or sport coats on weekends", None),
    ("Always pair a knit with trousers", True, "always pair knits with trousers", None),
    ("No orange", True, "no orange pieces", None),
    ("I like things that feel like Sunday morning in Positano", False, "Saved as a note — not yet enforced.", None),
    ("Flannels never tucked", True, "flannel shirts must never be tucked", None),
    ("Never tuck flannel shirts", True, "flannel shirts must never be tucked", None),
    ("Dress t shirts always tucked", True, "dress T-shirts must be tucked", None),
]


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
    OUT.mkdir(parents=True, exist_ok=True)
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
                "items": [dict(i, addedISO="2026-11-17", photo=FIXTURE_PHOTO) for i in CLOSET],
                "todaySource": "wardrobe",
                "formality": 4,
            }
            ctx.add_init_script(
                "(() => { const S = %s; for (const k in S) localStorage.setItem('wardrobe.' + k, JSON.stringify(S[k])); })();"
                % json.dumps(seed)
            )
            ctx.route(BLOCK, lambda r: r.abort())
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url, wait_until="load")
            page.wait_for_timeout(1800)

            check("build is current", str(page.evaluate("window.WARDROBE_BUILD") or "") == BUILD, page.evaluate("window.WARDROBE_BUILD"))
            check("WardrobeRules present", page.evaluate("!!(window.WardrobeRules && WardrobeRules.parse)"))

            for text, parsed, needle, needle2 in PARSER_CASES:
                got = page.evaluate("t => window.WardrobeRules.parse(t)", text)
                ok = got.get("parsed") is parsed and needle in (got.get("understood") or "")
                if needle2:
                    ok = ok and needle2 in (got.get("understood") or "")
                check("parse: " + text[:48], ok, got.get("understood"))

            seeds = page.evaluate("""() => ({
              n: (wardrobeRules || []).length,
              ids: (wardrobeRules || []).map(r => r.id),
              enabled: (wardrobeRules || []).every(r => r.enabled !== false),
              parsed: (wardrobeRules || []).every(r => r.parsed),
              texts: (wardrobeRules || []).map(r => r.understood),
              stored: !!localStorage.getItem('wardrobe.wardrobeRules'),
              inKeys: (typeof DATA_KEYS !== 'undefined') && DATA_KEYS.indexOf('wardrobeRules') !== -1
            })""")
            # .86.31+: a fresh profile gets the 3 built-in rules plus David's added rules
            EXPECT = 3 + 5
            check("seed rules on a fresh profile", seeds["n"] == EXPECT and seeds["parsed"] and seeds["enabled"], seeds)
            check("seed ids are stable", set(seeds["ids"]) == {"seed-tuck-blazer", "seed-tuck-dress-tee", "seed-tuck-flannel", "dj-sweater-over-shirt-70", "dj-eleventy-no-sweater", "dj-eleventy-untucked", "dj-malibu-tees-only", "dj-untucked-with-shorts"}, seeds["ids"])
            check("seed rules stored for backup", seeds["stored"] and seeds["inKeys"])
            check("blazer seed understood", any("shirts, polos and knits must be tucked under blazers" in t for t in seeds["texts"]), seeds["texts"][:1])

            # Engine: 50 generated looks violate zero enforced rules; tuck flags match the rules.
            eng = page.evaluate(
                """(items) => {
              const R = window.WardrobeRules;
              const C = window.WardrobeComposer;
              if (!R || !C) return { ok: false };
              R.setActive(R.seedRules());
              const deck = C.build(items);
              const looks = deck.deal(50, { level: null, dow: 3 });
              const violations = [];
              const tuckMismatches = [];
              looks.forEach((o, i) => {
                const chk = R.check(o, { dow: 3 });
                if (!chk.ok) violations.push({ i, key: o.key, why: chk.violations.map(v => v.reason) });
                const flag = (o.tucked !== undefined && o.tucked !== null) ? o.tucked : o.tuck;
                const expect = R.applyTuck(flag, o.top, o.layer);
                if (expect !== null && expect !== undefined && flag !== expect) tuckMismatches.push({ i, key: o.key, tucked: flag, expect });
              });
              // Known violations must be rejected
              const shirt = items.find(i => /Oxford Shirt/i.test(i.name));
              const flannel = items.find(i => /Flannel/i.test(i.name));
              const dress = items.find(i => /Dress T-Shirt/i.test(i.name));
              const blazer = items.find(i => /Navy.*Blazer|Navy Jersey Blazer|Maker06/i.test(i.name)) || items.find(i => i.category === 'Blazers');
              const trousers = items.find(i => i.category === 'Trousers');
              const shoes = items.find(i => i.category === 'Shoes' && !shoeIsCasual866(i));
              if (!shoes) throw new Error('Tuck checks need dress shoes that may be worn with a blazer');
              const cases = {
                shirtUntucked: shirt && blazer && !R.lookAllowed({ t: Object.assign({role:'top', kind:'shirt'}, shirt), b: trousers, s: shoes, l: Object.assign({role:'layer', kind:'blazer'}, blazer), tucked: false }),
                flannelTucked: flannel && !R.lookAllowed({ t: flannel, b: trousers, s: shoes, tucked: true }),
                dressUntucked: dress && !R.lookAllowed({ t: dress, b: trousers, s: shoes, tucked: false }),
                shirtTuckedOk: shirt && blazer && R.lookAllowed({ t: Object.assign({role:'top', kind:'shirt'}, shirt), b: trousers, s: shoes, l: Object.assign({role:'layer', kind:'blazer'}, blazer), tucked: true }),
                noteNotEnforced: (() => {
                  const note = R.makeRule('I like things that feel like Sunday morning in Positano');
                  const prev = R.getActive();
                  R.setActive(prev.concat([note]));
                  const ok = R.lookAllowed({ t: shirt, b: trousers, s: shoes, tucked: true });
                  R.setActive(prev);
                  return !!note && !note.parsed && ok;
                })()
              };
              return { ok: true, dealt: looks.length, violations, tuckMismatches, cases, combos: deck.combos.length };
            }""",
                CLOSET,
            )
            check("engine ran", eng.get("ok"), eng)
            check("50 looks dealt", eng.get("dealt") == 50, eng.get("dealt"))
            check("50 generated looks violate zero enforced rules", not eng.get("violations"), eng.get("violations")[:5] if eng.get("violations") else "")
            check("tuck flags match the rules", not eng.get("tuckMismatches"), eng.get("tuckMismatches")[:5] if eng.get("tuckMismatches") else "")
            cases = eng.get("cases") or {}
            check("untucked shirt under a blazer is rejected", cases.get("shirtUntucked"))
            check("tucked flannel is rejected", cases.get("flannelTucked"))
            check("untucked dress T-shirt is rejected", cases.get("dressUntucked"))
            check("tucked shirt under a blazer is allowed", cases.get("shirtTuckedOk"))
            check("unparsed note is kept and not enforced", cases.get("noteNotEnforced"))

            # UI: Profile → Wardrobe Rules
            page.locator("#tab-profile").click()
            page.wait_for_timeout(400)
            check("rules entry is on Profile", page.locator("#rules-entry").is_visible())
            page.locator("#rules-entry").click()
            page.wait_for_timeout(500)
            check("Rules sub-page opens", page.evaluate("currentTab") == "prules" and page.locator("#panel-prules").is_visible())
            check("page heading is centred Wardrobe Rules", page.locator("#prules-title").is_visible())
            cards = page.locator(".rule-card")
            check("seed rules are listed", cards.count() == EXPECT, cards.count())
            check("each rule shows its interpretation", page.evaluate("""() => {
              const cards = [...document.querySelectorAll('.rule-card')];
              return cards.length === 8 && cards.every(c => {
                const u = c.querySelector('.rule-understood');
                return u && /Understood as:/.test(u.textContent || '');
              });
            }"""))

            # Overflow at the asked widths (reuse this page at 390 first).
            def overflow_ok():
                return page.evaluate("""() => {
                  const doc = document.scrollingElement || document.documentElement;
                  return { sw: doc.scrollWidth, iw: window.innerWidth, cut: doc.scrollWidth > window.innerWidth + 1 };
                }""")

            ov = overflow_ok()
            check("nothing cut off at 390", not ov["cut"], ov)

            OUT.mkdir(parents=True, exist_ok=True)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(150)
            page.screenshot(path=str(OUT / "rules-390-light.png"), full_page=False)
            page.locator(".rule-card").first.screenshot(path=str(OUT / "rules-interpretation-390-light.png"))
            page.evaluate("typeof applyTheme === 'function' && applyTheme('dark')")
            page.wait_for_timeout(300)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(150)
            page.screenshot(path=str(OUT / "rules-390-dark.png"), full_page=False)
            page.locator(".rule-card").first.screenshot(path=str(OUT / "rules-interpretation-390-dark.png"))
            page.evaluate("typeof applyTheme === 'function' && applyTheme('light')")
            page.wait_for_timeout(200)

            # Add, toggle, edit, delete a note-style rule and a parsed one
            page.fill("#rule-input", "No blazers on weekends")
            page.wait_for_timeout(150)
            prev = page.locator("#rule-preview")
            check("live preview parses a new rule", "Understood as:" in (prev.inner_text() if prev.is_visible() else ""))
            page.locator("#rule-add").click()
            page.wait_for_timeout(250)
            check("adding a rule lists it", page.locator(".rule-card").count() == EXPECT + 1)
            page.fill("#rule-input", "Keep the Italian attitude")
            page.locator("#rule-add").click()
            page.wait_for_timeout(250)
            check("unparsed rule is saved as a note", page.evaluate("""() => {
              const cards = [...document.querySelectorAll('.rule-card')];
              const last = cards[cards.length - 1];
              const u = last && last.querySelector('.rule-understood');
              return !!(u && u.classList.contains('is-note') && /Saved as a note/.test(u.textContent || ''));
            }"""))
            # Toggle the first off
            page.locator(".rule-card").first.locator('[data-rule-act="toggle"]').click()
            page.wait_for_timeout(200)
            check("a rule can be switched off", page.evaluate("wardrobeRules[0].enabled === false") and "is-off" in (page.locator(".rule-card").first.get_attribute("class") or ""))
            page.locator(".rule-card").first.locator('[data-rule-act="toggle"]').click()
            page.wait_for_timeout(200)
            # Edit the weekend rule
            weekend = page.locator(".rule-card").nth(3)
            weekend.locator('[data-rule-act="edit"]').click()
            page.wait_for_timeout(150)
            page.locator(".rule-edit-box").fill("No shorts in winter")
            weekend.locator('[data-rule-act="save-edit"]').click()
            page.wait_for_timeout(250)
            check("a rule can be edited", page.evaluate("wardrobeRules.some(r => r.text === 'No shorts in winter' && /winter/.test(r.understood || ''))"))
            # Delete the note
            before = page.locator(".rule-card").count()
            page.locator(".rule-card").last.locator('[data-rule-act="delete"]').click()
            page.wait_for_timeout(200)
            check("a rule can be deleted", page.locator(".rule-card").count() == before - 1)

            # Overflow at other widths (desktop 1440 and the other phone sizes)
            for w, h in ((375, 812), (430, 932), (1440, 900)):
                page.set_viewport_size({"width": w, "height": h})
                page.wait_for_timeout(200)
                ovw = overflow_ok()
                check(f"nothing cut off at {w}", not ovw["cut"], ovw)

            check("no JS errors", not errors, errors[:3])
            ctx.close()
            browser.close()
    finally:
        httpd.shutdown()
    print(f"{sum(results)}/{len(results)} passed")
    print("screenshots:", ", ".join(sorted(p.name for p in OUT.glob("*.png"))))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
