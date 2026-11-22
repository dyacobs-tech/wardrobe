"""Evening Sharp between Evening Casual and Evening Dressy; all-blue outfits take black or blue shoes; old pictures do not linger (.86.65).

David, 22 Nov 2026:
  "Create Evening Smart outfit type. It sits cleanly between Evening Casual and
   Evening Dressy, and it covers exactly what you listed: tucked button-downs
   with no blazer, untucked button-downs, knit tees with trousers or dark
   jeans, and tonal monochrome looks."
  "Rename nightttime's to evening casual evening dressy evening sharp"
  "For this classication, could include blazers with tee shirts under ONLY.
   Under blazer id only wear white or cream tee shirts, or dark navy if it was
   monochrome with blazer (my tech Giorgio blazer good example)"
  "All blue I'd prefer black shoes black belts. Or tonal matching blue shoes
   blue belt."
  "Rust tee is more like a light milk chocolate brown - pls fix"
  Later: "All these evening Casual looks are evening sharp!!!", then his photo
  of a "casual hibachi dinner" look (graphic tee, cream shorts, Vans) and "Yes,
  that split" (.86.68): Evening Casual and Evening Sharp never share an outfit.
"""
import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLOSET = [
    {"id": "bzT", "name": "Taupe Knit Blazer", "category": "Blazers", "colourName": "Taupe", "colourHex": "#82705e"},
    {"id": "bzN", "name": "Navy Knit Blazer", "category": "Blazers", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "wtee", "name": "White Merino Tee", "category": "Tees", "colourName": "White", "colourHex": "#f7f5ef"},
    {"id": "ntee", "name": "Navy Knit Tee", "category": "Tees", "colourName": "Navy", "colourHex": "#1f2a44"},
    {"id": "ztee", "name": "Zigzag Stripe Tee", "category": "Tees", "colourName": "White", "colourHex": "#f1ede4"},
    {"id": "gtee", "name": "Green Cotton Tee", "category": "Tees", "colourName": "Green", "colourHex": "#5b7a4f"},
    {"id": "oxf", "name": "Light Blue Oxford Shirt", "category": "Shirts", "colourName": "Light Blue", "colourHex": "#a9c2de"},
    {"id": "chino", "name": "Stone Cotton Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#c9b896"},
    {"id": "navyt", "name": "Navy Wool Trousers", "category": "Trousers", "colourName": "Navy", "colourHex": "#1e2846"},
    {"id": "dkj", "name": "Dark Indigo Jeans", "category": "Jeans", "colourName": "Indigo", "colourHex": "#22304f"},
    {"id": "ltj", "name": "Light Wash Jeans", "category": "Jeans", "colourName": "Light Blue", "colourHex": "#8aa8c4"},
    {"id": "sh", "name": "Stone Chino Shorts", "category": "Shorts", "colourName": "Stone", "colourHex": "#c9b896"},
    {"id": "lin", "name": "Yellow Linen Shirt", "category": "Shirts", "colourName": "Yellow", "colourHex": "#efe0a0"},
    {"id": "gtee2", "name": "Fliks Yellow Graphic Tee", "category": "Tees", "colourName": "Yellow", "colourHex": "#f0cf4a"},
    {"id": "vans", "name": "Vans Black and White Checkerboard Slip-On Sneakers", "category": "Shoes", "colourName": "Black/White", "colourHex": "#222222"},
    {"id": "brl", "name": "Dark Brown Suede Penny Loafers", "category": "Shoes", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "bkl", "name": "Black Leather Penny Loafers", "category": "Shoes", "colourName": "Black", "colourHex": "#111111"},
    {"id": "nvl", "name": "Navy Suede Loafers", "category": "Shoes", "colourName": "Navy", "colourHex": "#22304f"},
    {"id": "bbr", "name": "Dark Brown Suede Belt", "category": "Belts", "colourName": "Dark brown", "colourHex": "#4a2e1f"},
    {"id": "bbk", "name": "Black Leather Belt", "category": "Belts", "colourName": "Black", "colourHex": "#111111"},
    {"id": "bnv", "name": "Navy Suede Belt", "category": "Belts", "colourName": "Navy", "colourHex": "#22304f"},
]


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof onbodyRefresh === 'function' && typeof FORMALITY_LEVELS !== 'undefined'")
    out = page.evaluate("""closet => { const deck = WardrobeComposer.build(closet);
      const sharp = deck.combos.filter(c => c.mask & (1 << 4)).map(c => (c.l ? c.l.id + '+' : '') + c.t.id + '/' + c.b.id);
      const blue = deck.combos.filter(c => ['oxf', 'ntee'].includes(c.t.id) && ['navyt', 'dkj', 'ltj'].includes(c.b.id) && (!c.l || c.l.id === 'bzN')).map(c => c.s.id);
      const dealt = []; [2, 3, 4, 5].forEach(lv => deck.deal(30, { level: lv, temp: 72, recent: [], prefs: {}, exposure: {}, banned: {} }).forEach(o => {
        const ids = [o.top.id, o.bottom.id].concat(o.layer ? [o.layer.id] : []);
        if (ids.every(id => ['oxf', 'ntee', 'navyt', 'dkj', 'ltj', 'bzN'].includes(id))) dealt.push(o.shoes.id + '/' + (o.belt ? o.belt.id : '-')); }));
      const casual = deck.combos.filter(c => c.mask & (1 << 3)).map(c => (c.l ? c.l.id + '+' : '') + c.t.id + '/' + c.b.id + '/' + c.s.id);
      const both = deck.combos.filter(c => (c.mask & (1 << 3)) && (c.mask & (1 << 4))).length;
      return { casual: [...new Set(casual)], both, sharp: [...new Set(sharp)].sort(), blue: [...new Set(blue)], dealt: [...new Set(dealt)],
        names: FORMALITY_LEVELS.map(l => l.level + ':' + l.name) }; }""", CLOSET)

    sharp = out["sharp"]
    assert sharp, out
    # a blazer only over a plain white or cream tee, or a navy tee under the navy blazer
    blz = [s for s in sharp if "+" in s]
    assert blz and all(s.split("+")[1].split("/")[0] in ("wtee", "ntee") for s in blz), blz
    assert not any(s.startswith("bzT+ntee") for s in blz), blz
    # .86.66: the all-navy look, navy blazer over a navy tee with navy trousers
    assert "bzN+ntee/navyt" in sharp, blz
    assert not any("ztee" in s and "+" in s for s in sharp), sharp
    # never shorts, never light-wash jeans
    assert not any(s.endswith("/sh") or s.endswith("/ltj") for s in sharp), sharp
    # a button-down with no blazer is Evening Sharp
    assert any(s.startswith("oxf/") for s in sharp), sharp
    # all blue: black or blue shoes, never brown, and the belt follows the shoes
    assert out["blue"] and "brl" not in out["blue"], out["blue"]
    for d in out["dealt"]:
        shoe, belt = d.split("/")
        assert shoe in ("bkl", "nvl", "vans") and belt in ("-", {"bkl": "bbk", "nvl": "bnv", "vans": "bbk"}[shoe]), out["dealt"]   # the Vans read black
    # .86.68: the two evening levels never share an outfit; shorts and sneakers are Evening Casual's
    casual = out["casual"]
    assert out["both"] == 0, out["both"]
    assert any(c.startswith("gtee2/sh/vans") for c in casual), casual[:20]          # his hibachi look
    assert any(c.startswith("lin/") for c in casual) and not any(s.startswith("lin/") for s in sharp), (casual[:20], sharp)
    assert not any(c.startswith("oxf/") for c in casual), [c for c in casual if c.startswith("oxf/")][:5]   # a dress button-down is Sharp's
    assert not any(c.startswith(("bzN+", "bzT+")) for c in casual), casual[:20]
    # the names
    names = out["names"]
    assert "3:Evening Casual" in names and "4:Evening Sharp" in names and "5:Evening Dressy" in names, names
    assert not any("Nighttime" in n for n in names), names

    # a picture taken out of the list does not linger from an older copy
    page.evaluate("() => { ONBODY.map['stale|old|key'] = 'assets/onbody/gone.webp'; onbodyRefresh(); }")
    page.wait_for_function("() => !ONBODY.map['stale|old|key']", timeout=15000)
    assert not errors, errors
    ctx.close()
    return len(sharp)


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        n = run(browser)
        print("Confirmed: %d Evening Sharp outfits, blazers only over white/cream (or navy-on-navy) tees; all-blue in black or blue shoes; stale pictures dropped" % n)
        browser.close()
