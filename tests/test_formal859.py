"""Formal: dress loafers only, and every Formal look is pictured wearing its tie; rejected pictures stay out (.86.59).

David, 22 Nov 2026:
  "Formal looks should be DRESS loafers only not sneakers w white soles - all
   outfit should have TIES."
  On Home pictures: "Sneaker fucked up"; "I look fat head is messed up images
  messed up".
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLOSET = [
    {"id": "bz1", "name": "Burgundy Blazer", "category": "Blazers", "colourName": "Burgundy", "colourHex": "#5e2129"},
    {"id": "sh1", "name": "Light Blue Shirt", "category": "Shirts", "colourName": "Light Blue", "colourHex": "#a8c3d1"},
    {"id": "ch1", "name": "Beige Stretch Cotton Chino", "category": "Trousers", "colourName": "Beige", "colourHex": "#cdbb98"},
    {"id": "eg", "name": "Edward Green Dark Brown Suede Penny Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "bal", "name": "Balenciaga Black Leather Penny Loafers", "category": "Shoes", "colourName": "Black", "colourHex": "#111111"},
    {"id": "dior", "name": "Christian Dior Tan Suede Penny Loafers", "category": "Shoes", "colourName": "Tan", "colourHex": "#84653a"},
    {"id": "arm", "name": "Giorgio Armani Cream Woven Leather Loafers", "category": "Shoes", "colourName": "Cream", "colourHex": "#e9e1d2"},
    {"id": "camo", "name": "Belgian Shoes Camo Pony-Hair Loafers", "category": "Shoes", "colourName": "Camo", "colourHex": "#6b6f3f"},
    {"id": "vel", "name": "Vibi Venezia Tan Velvet Furlane Slippers", "category": "Shoes", "colourName": "Tan", "colourHex": "#b08455"},
    {"id": "esp", "name": "Baudoin & Lange Tan Suede Penny Espadrilles", "category": "Shoes", "colourName": "Tan", "colourHex": "#795936"},
    {"id": "ti1", "name": "Navy Knit Tie", "category": "Ties", "colourName": "Navy", "colourHex": "#1f2a44"},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof onbodyForLook === 'function'")
    out = page.evaluate("""closet => { const deck = WardrobeComposer.build(closet);
      const formal = deck.combos.filter(c => c.mask & (1 << 6)).map(c => c.s.id);
      const dressy = deck.combos.filter(c => c.mask & (1 << 5)).map(c => c.s.id);
      // pictures: the outfit without a tie, and the same outfit with the tie
      const core = ['bz1', 'sh1', 'ch1', 'eg'].sort().join('|'), withTie = ['bz1', 'sh1', 'ch1', 'eg', 'ti1'].sort().join('|');
      ONBODY.map[core] = 'assets/onbody/notie.webp';
      const piece = id => { const i = closet.find(x => x.id === id); return { id, name: i.name, category: i.category }; };
      const formalLook = { composerKey: core, fwPieces: ['bz1', 'sh1', 'ch1', 'eg', 'ti1'].map(piece) };
      const dressyLook = { composerKey: core, fwPieces: ['bz1', 'sh1', 'ch1', 'eg'].map(piece) };
      const before = { formal: onbodyForLook(formalLook), dressy: onbodyForLook(dressyLook) };
      ONBODY.map[withTie] = 'assets/onbody/tie.webp';
      const after = { formal: onbodyForLook(formalLook), dressy: onbodyForLook(dressyLook) };
      delete ONBODY.map[core]; delete ONBODY.map[withTie];
      return { formal: [...new Set(formal)].sort(), dressy: [...new Set(dressy)].sort(), before, after,
        banned: ['c1c3225a0867efce.webp', 'ed7969a72e937a88.webp', '4529bac87ec41ac7.webp', '9f5bc4066c18d16a.webp'].map(f => onbodyFileBanned('assets/onbody/' + f)) }; }""", CLOSET)
    # dress loafers only at Formal
    # .86.72 (David, 22 Nov 2026: "Formal loafers should be dark brown boudain lange all Belgians. Balenciaga."):
    # the Edward Greens leave Formal; the camo Belgians are allowed but this closet deals them nothing
    assert "eg" not in out["formal"] and "bal" in out["formal"] and set(out["formal"]) <= {"bal", "camo"}, out["formal"]
    # the rule is Formal's: Evening Dressy still takes the other shoes it took before
    assert "dior" in out["dressy"], out["dressy"]
    # a Formal look (it carries a tie) never shows a picture without the tie; it shows the one with it
    assert out["before"] == {"formal": None, "dressy": "assets/onbody/notie.webp"}, out["before"]
    assert out["after"] == {"formal": "assets/onbody/tie.webp", "dressy": "assets/onbody/notie.webp"}, out["after"]
    # the three pictures he rejected
    assert out["banned"] == [True, True, True, True], out["banned"]   # .86.64: "Awful!!!!!! I'm fat and picture distorted"
    # every Formal picture shipped is keyed with a tie that is in its outfit
    # (.86.79: found by outfit, not file name; pictures get new names when they are redrawn, e.g. with his watch)
    FORMAL_KEYS = ["item-1794964266126-146676|item-1794971947771-183364|item-1795293967786-460785|rcptbuy-1pv7csr17|rcptbuy-99ztz517", "item-1794964266126-146676|item-1794965887185-931158|item-1795293967786-460785|rcptbuy-1pv7csr17|rcptbuy-99ztz517", "item-1794964266128-402564|item-1794971947773-858227|item-1795293967787-731268|rcptbuy-1jnn02517|seed-edwardgreen-darkbrown-loafers", "item-1794964266128-402564|item-1794971947771-183364|item-1795293967790-528874|rcptbuy-1fo09nv17|seed-edwardgreen-darkbrown-loafers", "item-1794965887185-931158|item-1795293967787-731268|rcptbuy-99ztz517|seed-baudoin-brown-leather-loafers|seed-loropiana-oatmeal-blazer", "item-1794971947771-183364|item-1795293967787-731268|item-1795308710457-402402|seed-edwardgreen-darkbrown-loafers|seed-loropiana-oatmeal-blazer", "item-1794971947771-183364|item-1795293967790-528874|item-1795311782862-318558|seed-belgian-brown-lizard-loafers|seed-loropiana-oatmeal-blazer", "item-1794964266126-146676|item-1794965887185-931158|item-1795293967789-356683|rcptbuy-gwrgm217|seed-belgian-brown-lizard-loafers"]
    shipped = page.evaluate("""keys => fetch('assets/onbody/manifest.json').then(r => r.json()).then(m => m.r.filter(e => keys.includes(e.k)).map(e => e.k.split('|').length))""", FORMAL_KEYS)
    assert len(shipped) == 8 and all(n == 5 for n in shipped), shipped
    assert not errors, errors
    print("Confirmed: Formal deals only dress loafers %s; a Formal look shows only a picture with its tie; 8 tie pictures shipped; 3 rejected pictures out" % out["formal"])
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        browser.close()
