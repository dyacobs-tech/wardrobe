"""Formal always has a tie, and Formal rotates through every blazer (.87.22).

David, 26 Nov 2026:
  "Formal looks should have TIES!!!! All formal should have ties... and why
   are all the blazers my red one? Formal looks can use all of the blazers!!!!!"
  Then: "MAKE MORE FORMAL LOOKS DO BETTER!!!!!"
"""
import collections
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLOSET = [
    {"id": "bzBurg", "name": "Burgundy Wool Blazer", "category": "Blazers", "colourName": "Burgundy", "colourHex": "#5e2129"},
    {"id": "bzNavyKnit", "name": "Navy Knit Blazer", "category": "Blazers", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "bzTaupeLinen", "name": "Taupe Linen Blazer", "category": "Blazers", "colourName": "Taupe", "colourHex": "#8a7358"},
    {"id": "bzNavyJersey", "name": "Navy Jersey Blazer", "category": "Blazers", "colourName": "Navy", "colourHex": "#1b2438"},
    {"id": "bzPlaid", "name": "Navy Plaid Blazer", "category": "Blazers", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "bzBlueLinen", "name": "Light Blue Linen Blazer", "category": "Blazers", "colourName": "Light Blue", "colourHex": "#9bb8d0"},
    {"id": "shLB", "name": "Light Blue Poplin Shirt", "category": "Shirts", "colourName": "Light Blue", "colourHex": "#a8c3d1"},
    {"id": "shNavy", "name": "Navy Poplin Shirt", "category": "Shirts", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "chBeige", "name": "Beige Stretch Cotton Chino", "category": "Trousers", "colourName": "Beige", "colourHex": "#cdbb98"},
    {"id": "chNavy", "name": "Dark Navy Cotton Chinos", "category": "Trousers", "colourName": "Navy", "colourHex": "#1e2846"},
    {"id": "chStone", "name": "Stone Non-Iron Stretch Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#b9ad98"},
    {"id": "loB", "name": "Baudoin & Lange Dark Brown Leather Tassel Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#3e2618"},
    {"id": "loBe", "name": "Belgian Shoes Brown Lizard Loafers", "category": "Shoes", "colourName": "Brown", "colourHex": "#7a4a2c"},
    {"id": "loBa", "name": "Balenciaga Black Leather Penny Loafers", "category": "Shoes", "colourName": "Black", "colourHex": "#111111"},
    {"id": "beltDB", "name": "Dark Brown Pebbled Leather Belt", "category": "Belts", "colourName": "Dark Brown", "colourHex": "#3e2618"},
    {"id": "beltBK", "name": "Black Textured Leather Belt", "category": "Belts", "colourName": "Black", "colourHex": "#111111"},
    {"id": "tiNavy", "name": "Dark Navy Knit Tie", "category": "Ties", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "tiBlue", "name": "Royal Blue Textured Knit Tie", "category": "Ties", "colourName": "Royal Blue", "colourHex": "#2a4f9a"},
    {"id": "tiChar", "name": "Charcoal Knit Tie", "category": "Ties", "colourName": "Charcoal", "colourHex": "#3c3c40"},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof WardrobeComposer.build === 'function'")
    out = page.evaluate("""closet => {
      const deck = WardrobeComposer.build(closet);
      const formalCombos = deck.combos.filter(c => c.mask & (1 << 6));
      const blazersIn = [...new Set(formalCombos.map(c => c.l && c.l.id).filter(Boolean))];
      const dealt = [];
      for (let k = 0; k < 8; k++) {
        deck.deal(12, { level: 6, temp: 70, recent: dealt.map(o => o.key), prefs: {}, exposure: {}, banned: {} }).forEach(o => {
          dealt.push({ key: o.key, layer: o.layer && o.layer.id, top: o.top.id, acc: o.acc && o.acc.id, accKind: o.acc && o.acc.kind, belt: o.belt && o.belt.id, bottom: o.bottom.id, shoes: o.shoes.id });
        });
      }
      const piece = id => closet.find(x => x.id === id);
      const empty = { id: 'no-tie', fwPieces: ['bzBurg','shLB','chBeige','loB'].map(piece) };
      const withTie = { id: 'with-tie', fwPieces: ['bzBurg','shLB','chBeige','loB','tiNavy'].map(piece) };
      const fit = (look) => (typeof lookFitsDress841 === 'function') ? lookFitsDress841(look, 6) : null;
      return { blazersIn, dealt, fitEmpty: fit(empty), fitTie: fit(withTie) };
    }""", CLOSET)
    assert not errors, errors
    # every Formal sport blazer, including knit, linen, jersey and plaid, can be Formal
    assert set(out["blazersIn"]) >= {"bzBurg", "bzNavyKnit", "bzTaupeLinen", "bzNavyJersey", "bzPlaid", "bzBlueLinen"}, out["blazersIn"]
    assert out["dealt"], "Formal dealt nothing"
    for o in out["dealt"]:
        assert o["accKind"] == "ties" and o["acc"], o
        assert o["layer"] in {"bzBurg", "bzNavyKnit", "bzTaupeLinen", "bzNavyJersey", "bzPlaid", "bzBlueLinen"}, o
    counts = collections.Counter(o["layer"] for o in out["dealt"])
    n_blaz = len({o["layer"] for o in out["dealt"]})
    assert n_blaz >= 5, counts
    # no single blazer over about 1/N, with a little slack for a short deal
    cap = max(1, int((len(out["dealt"]) / max(n_blaz, 1)) * 2 + 2))
    assert max(counts.values()) <= cap, (counts, cap, len(out["dealt"]))
    assert out["fitEmpty"] is False, out["fitEmpty"]
    assert out["fitTie"] is True, out["fitTie"]
    print("Confirmed: Formal dealt %d looks across %d blazers %s; every look has a tie; a Formal look without a tie is rejected" % (len(out["dealt"]), n_blaz, dict(counts)))
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        browser.close()
