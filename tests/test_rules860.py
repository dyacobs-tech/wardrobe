"""Ties only with white or light blue shirts; wide-leg trousers only with tees; a belt whenever there are belt loops (.86.60).

David, 22 Nov 2026:
  "Create a rule I only wear white or light blue shirts with ties. EVER."
  "Inspo can include faint striped shirts with ties but base color has to be a
   light blue shade or white. All black with black tie could work. Or all
   navy navy tie etc...."
  "The WIDE linen pants should ONLY be worn with t shirts."
  "EVERY pant w belt loops should always have a belt - in outfit"
  On the pool outfits: "Son of these color combos are awful" and "Why are all
  these with brown tee? Not other tees?"
"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLOSET = [
    {"id": "bzN", "name": "Navy Blazer", "category": "Blazers", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "bzB", "name": "Black Blazer", "category": "Blazers", "colourName": "Black", "colourHex": "#141416"},
    {"id": "white", "name": "White Poplin Shirt", "category": "Shirts", "colourName": "White", "colourHex": "#f7f7f5"},
    {"id": "lbstripe", "name": "Light Blue Bengal Stripe Shirt", "category": "Shirts", "colourName": "Light Blue", "colourHex": "#b4cbe0"},
    {"id": "pink", "name": "Pink Poplin Shirt", "category": "Shirts", "colourName": "Pink", "colourHex": "#e2a9b0"},
    {"id": "blue", "name": "Blue Poplin Shirt", "category": "Shirts", "colourName": "Blue", "colourHex": "#3e6aa8"},
    {"id": "lbcheck", "name": "Light Blue Check Shirt", "category": "Shirts", "colourName": "Light Blue", "colourHex": "#b4cbe0"},
    {"id": "black", "name": "Black Poplin Shirt", "category": "Shirts", "colourName": "Black", "colourHex": "#141416"},
    {"id": "tee", "name": "White Tee", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "ntee", "name": "Navy Tee", "category": "Tees", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "chino", "name": "Beige Stretch Cotton Chino", "category": "Trousers", "colourName": "Beige", "colourHex": "#cdbb98"},
    {"id": "wool", "name": "Black Wool Trousers", "category": "Trousers", "colourName": "Black", "colourHex": "#151517"},
    {"id": "jeans", "name": "Indigo Jeans", "category": "Jeans", "colourName": "Indigo", "colourHex": "#2c3e63"},
    {"id": "wide", "name": "Isaia White Wide-Leg Linen Trousers", "category": "Trousers", "colourName": "White", "colourHex": "#f2efe8"},
    {"id": "eg", "name": "Edward Green Dark Brown Suede Penny Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "bal", "name": "Balenciaga Black Leather Penny Loafers", "category": "Shoes", "colourName": "Black", "colourHex": "#111111"},
    {"id": "snk", "name": "White Leather Sneakers", "category": "Shoes", "colourName": "White", "colourHex": "#f5f5f0"},
    {"id": "bbr", "name": "Dark Brown Suede Belt", "category": "Belts", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "bbk", "name": "Black Leather Belt", "category": "Belts", "colourName": "Black", "colourHex": "#111111"},
    {"id": "tiN", "name": "Navy Knit Tie", "category": "Ties", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "tiB", "name": "Black Silk Tie", "category": "Ties", "colourName": "Black", "colourHex": "#121214"},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof WardrobeComposer.build === 'function'")
    out = page.evaluate("""closet => { const deck = WardrobeComposer.build(closet);
      const formal = deck.combos.filter(c => c.mask & (1 << 6)).map(c => c.t.id + '/' + (c.l ? c.l.id : '-'));
      const wide = deck.combos.filter(c => c.b.id === 'wide').map(c => c.t.id + '/' + (c.l ? c.l.id : '-'));
      const dealt = []; let noBelt = 0, loops = 0;
      [2, 3, 5, 6].forEach(lv => deck.deal(40, { level: lv, temp: 70, recent: [], prefs: {}, exposure: {}, banned: {} }).forEach(o => {
        if (lv === 6) dealt.push(o.top.id + '/' + (o.acc ? o.acc.id : 'none'));
        if (!o.bottom.beltless && o.bottom.kind !== 'swim') { loops++; if (!o.belt) noBelt++; } }));
      return { formal: [...new Set(formal)].sort(), wide: [...new Set(wide)].sort(), dealt: [...new Set(dealt)].sort(), loops, noBelt }; }""", CLOSET)

    # ties go only on a white or light blue shirt (a faint stripe is fine, a check is not),
    # or tonal: a black shirt under a black blazer
    shirts = {f.split("/")[0] for f in out["formal"]}
    assert shirts and shirts <= {"white", "lbstripe", "black"}, out["formal"]
    assert {"white", "lbstripe"} <= shirts, out["formal"]
    assert all(f == "black/bzB" for f in out["formal"] if f.startswith("black/")), out["formal"]
    for d in out["dealt"]:
        top, tie = d.split("/")
        assert tie != "none", d
        if top == "black":
            assert tie == "tiB", d       # all black takes the black tie
    # wide-leg linen trousers: a tee and nothing over it
    assert out["wide"] and all(w.split("/")[0] in ("tee", "ntee") and w.endswith("/-") for w in out["wide"]), out["wide"]
    # a belt on every outfit whose trousers have belt loops
    assert out["loops"] > 20 and out["noBelt"] == 0, out

    # the shipped Formal pictures: each has a tie, and none has a shirt that cannot take one
    # (the keys name closet ids, so this reads the file list of what was removed)
    man = json.load(open(os.path.join(ROOT, "assets", "onbody", "manifest.json")))
    files = {e["f"] for e in man["r"]}
    for f in ("b6f935ac7ac6f480", "a3df17689d036028", "1b441c9b92641b24", "087c53c9afdfc646", "582e08a5a13b832c",
              "c88c951126da147c", "8fcb4a3a6a84d85b", "4ef4510277e0905e", "d91f68ef408a9e03", "650043a805412c85"):
        assert f + ".webp" not in files, f

    # Inspo: a tie only with a white or light blue shirt, or a tonal black or navy outfit
    src = open(os.path.join(ROOT, "src", "app.html"), encoding="utf-8").read()
    lib = json.loads(re.search(r"/\*INSPO_CONCEPTS_BEGIN\*/(.*?)/\*INSPO_CONCEPTS_END\*/", src, re.S).group(1))
    tonal = 0
    for c in lib:
        ps = {p["role"]: p for p in c["pieces"]}
        if "tie" not in ps:
            continue
        col = ps["top"]["colour"].lower()
        if col in ("black", "navy"):
            assert ps["tie"]["colour"].lower() == col and ps.get("layer", {}).get("colour", "").lower() == col, c["id"]
            tonal += 1
        else:
            assert re.search(r"white|light blue|pale blue", col), (c["id"], col)
    assert tonal >= 2, tonal
    # .86.67 (David: "EVERY pant w belt loops should always have a belt - in outfit"): every concept whose
    # trousers have belt loops lists a belt, and every redrawn concept picture is shipped
    for c in lib:
        ps = {p["role"]: p for p in c["pieces"]}
        b = ps["bottom"]["name"].lower()
        if not any(w in b for w in ("short", "drawstring", "gurkha", "swim")):
            assert "belt" in ps, c["id"]
        if c.get("img"):
            assert os.path.exists(os.path.join(ROOT, "assets", "inspo-concepts", c["img"] + ".webp")), c["img"]
    assert not errors, errors
    ctx.close()
    print("Confirmed: ties only on white/light blue (or tonal) shirts; wide-leg with tees only; a belt on %d outfits with belt loops" % out["loops"])


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        browser.close()
