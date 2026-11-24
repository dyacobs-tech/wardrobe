"""Every belt matches its shoes shade for shade: dark brown with dark brown, caramel with caramel (.87.09).

David, 24 Nov 2026: "Seeing tons of belts that DONT match shoes. Remember dark brown with dark brown. Caramel with
caramel. Etc... I have a match belt for ALL my shoes. Do better!!!!". The belt picker matched by colour family, and
every brown counted as one family, so his dark brown suede loafers were dealt the Tobacco Suede belt most of the time.
Browns now split into dark brown and caramel (tan, cognac, tobacco, rust, camel, greige, taupe); black, navy, grey and
green match their own; a beaded or woven belt counts by the colour of its leather. White and cream sneakers still take
any belt (his 21 Nov rule: "Plain belts should always match shoes unless I have beltless pants or white sneakers").
Checks, with his own 20 belts and 23 pairs of shoes: each pair is read as the right shade, and at every dress level
the belt dealt with it is in that shade, never another; his dark brown suede loafers never get the Tobacco Suede belt.
"""
import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
CLOSET = {
 "belts": [
  {
   "id": "b00",
   "name": "Black Braided Stretch Belt",
   "category": "Belts",
   "colourName": "Black",
   "colourHex": "#0f0e0f",
   "notes": "Braided elastic with black leather ends; silver buckle."
  },
  {
   "id": "b01",
   "name": "Black Textured Leather Belt",
   "category": "Belts",
   "colourName": "Black",
   "colourHex": "#222223",
   "notes": "Silver buckle."
  },
  {
   "id": "b02",
   "name": "Blue & Orange Beaded Belt",
   "category": "Belts",
   "colourName": "Blue",
   "colourHex": "#3f58a7",
   "notes": "Beaded zigzag pattern on dark leather; brass buckle."
  },
  {
   "id": "b03",
   "name": "Brown Leather Belt, Engraved Silver Buckle",
   "category": "Belts",
   "colourName": "Brown",
   "colourHex": "#663218",
   "notes": "Slim, with an engraved silver buckle, keeper and tip."
  },
  {
   "id": "b04",
   "name": "Dark Brown Pebbled Leather Belt",
   "category": "Belts",
   "colourName": "Dark Brown",
   "colourHex": "#3c2f2c",
   "notes": "Silver double-bar buckle."
  },
  {
   "id": "b05",
   "name": "Dark Brown Snakeskin-Pattern Belt",
   "category": "Belts",
   "colourName": "Dark Brown",
   "colourHex": "#37302d",
   "notes": "Glossy snakeskin-pattern leather, silver buckle."
  },
  {
   "id": "b06",
   "name": "Dark Grey Pebbled Leather Belt",
   "category": "Belts",
   "colourName": "Dark Grey",
   "colourHex": "#403c3a",
   "notes": "Silver buckle."
  },
  {
   "id": "b07",
   "name": "Grey Leather Polo Belt",
   "category": "Belts",
   "colourName": "Grey",
   "colourHex": "#524541",
   "notes": "Navy, red and cream stitched diamonds; silver buckle."
  },
  {
   "id": "b08",
   "name": "Navy Pebbled Leather Belt",
   "category": "Belts",
   "colourName": "Navy",
   "colourHex": "#393940",
   "notes": "Silver buckle."
  },
  {
   "id": "b09",
   "name": "Navy Scale-Embossed Leather Belt",
   "category": "Belts",
   "colourName": "Navy",
   "colourHex": "#313644",
   "notes": "Scale-embossed leather, silver buckle."
  },
  {
   "id": "b10",
   "name": "Navy Woven Stretch Belt",
   "category": "Belts",
   "colourName": "Navy",
   "colourHex": "#0b0b10",
   "notes": "Woven elastic with black leather ends; silver buckle."
  },
  {
   "id": "b11",
   "name": "Navy, Red & Tan Woven Polo Belt",
   "category": "Belts",
   "colourName": "Navy",
   "colourHex": "#1b1a25",
   "notes": "Woven diamond pattern with tan leather ends; silver buckle."
  },
  {
   "id": "b12",
   "name": "Orange, Blue & White Beaded Belt",
   "category": "Belts",
   "colourName": "Orange",
   "colourHex": "#e96521",
   "notes": "Beaded stripes on brown leather; brass buckle."
  },
  {
   "id": "b13",
   "name": "Patrick Gibbons Charcoal Alligator Belt",
   "category": "Belts",
   "colourName": "Charcoal",
   "colourHex": "#424143",
   "notes": "Alligator leather, silver buckle."
  },
  {
   "id": "b14",
   "name": "Patrick Gibbons Cognac Alligator Belt",
   "category": "Belts",
   "colourName": "Cognac",
   "colourHex": "#7c564b",
   "notes": "Alligator leather, silver buckle."
  },
  {
   "id": "b15",
   "name": "Patrick Gibbons Dark Brown Alligator Belt",
   "category": "Belts",
   "colourName": "Dark Brown",
   "colourHex": "#241915",
   "notes": "Alligator leather, silver buckle."
  },
  {
   "id": "b16",
   "name": "Patrick Gibbons Dark Green Alligator Belt",
   "category": "Belts",
   "colourName": "Dark Green",
   "colourHex": "#333635",
   "notes": "Alligator leather, silver buckle."
  },
  {
   "id": "b17",
   "name": "Tobacco Suede Belt",
   "category": "Belts",
   "colourName": "Tobacco",
   "colourHex": "#633213",
   "notes": "Silver buckle."
  },
  {
   "id": "b18",
   "name": "Velasca Brown Braided Leather Belt",
   "category": "Belts",
   "colourName": "Dark Brown",
   "colourHex": "#2a1a14",
   "notes": "Braided leather with a brass buckle."
  },
  {
   "id": "b19",
   "name": "White & Blue Beaded Belt",
   "category": "Belts",
   "colourName": "White",
   "colourHex": "#eee8dc",
   "notes": "Beaded diamond pattern on brown leather; brass buckle."
  }
 ],
 "shoes": [
  {
   "id": "s00",
   "name": "Baudoin & Lange Tan Suede Penny Espadrilles",
   "category": "Shoes",
   "colourName": "Tan",
   "colourHex": "#795936",
   "expect": "caramel"
  },
  {
   "id": "s01",
   "name": "Bottega Veneta Black and White Intrecciato Slip-On Sneakers",
   "category": "Shoes",
   "colourName": "Black/White",
   "colourHex": "#171409",
   "expect": "black"
  },
  {
   "id": "s02",
   "name": "Brunello Cucinelli Light Grey Suede Runner Sneakers",
   "category": "Shoes",
   "colourName": "Light Grey",
   "colourHex": "#c8c7c6",
   "expect": "grey"
  },
  {
   "id": "s03",
   "name": "Brunello Cucinelli Navy Pool Slides",
   "category": "Shoes",
   "colourName": "Navy",
   "colourHex": "#26304A",
   "expect": "navy"
  },
  {
   "id": "s04",
   "name": "Christian Dior Tan Suede Penny Loafers",
   "category": "Shoes",
   "colourName": "Tan",
   "colourHex": "#84653a",
   "expect": "caramel"
  },
  {
   "id": "s05",
   "name": "Common Projects White Leather Achilles Low Sneakers",
   "category": "Shoes",
   "colourName": "White",
   "colourHex": "#F4F2EC",
   "expect": "free"
  },
  {
   "id": "s06",
   "name": "D.A.T.E. Cream and Navy Retro Runner Sneakers",
   "category": "Shoes",
   "colourName": "Cream/Navy",
   "colourHex": "#090917",
   "expect": "free"
  },
  {
   "id": "s07",
   "name": "Edward Green Polperro Leather-Trimmed Suede Penny Loafers",
   "category": "Shoes",
   "colourName": "dark brown",
   "colourHex": "#4e2e22",
   "expect": "darkbrown"
  },
  {
   "id": "s08",
   "name": "Frescobol Carioca White and Navy Leather Pool Slides",
   "category": "Shoes",
   "colourName": "White",
   "colourHex": "#F4F2EC",
   "expect": "navy"
  },
  {
   "id": "s09",
   "name": "Giorgio Armani Light Grey Suede Whipstitch Slip-On Loafers",
   "category": "Shoes",
   "colourName": "Light Grey",
   "colourHex": "#a6948a",
   "expect": "grey"
  },
  {
   "id": "s10",
   "name": "Giorgio Armani Navy Leather Whipstitch Slip-On Loafers",
   "category": "Shoes",
   "colourName": "Navy",
   "colourHex": "#222b38",
   "expect": "navy"
  },
  {
   "id": "s11",
   "name": "Giorgio Armani Navy Suede Whipstitch Slip-On Loafers",
   "category": "Shoes",
   "colourName": "Navy",
   "colourHex": "#252a39",
   "expect": "navy"
  },
  {
   "id": "s12",
   "name": "Giorgio Armani Slate Grey Suede Whipstitch Slip-On Loafers",
   "category": "Shoes",
   "colourName": "Slate Grey",
   "colourHex": "#555659",
   "expect": "grey"
  },
  {
   "id": "s13",
   "name": "Giorgio Armani Taupe Leather Whipstitch Slip-On Loafers",
   "category": "Shoes",
   "colourName": "Taupe",
   "colourHex": "#735a47",
   "expect": "caramel"
  },
  {
   "id": "s14",
   "name": "Loro Piana Cream Multicolour Runner Sneakers",
   "category": "Shoes",
   "colourName": "Cream",
   "colourHex": "#e9e1d2",
   "expect": "free"
  },
  {
   "id": "s15",
   "name": "Prada Dark Brown Suede Boat Shoes",
   "category": "Shoes",
   "colourName": "Dark Brown",
   "colourHex": "#4a3834",
   "expect": "darkbrown"
  },
  {
   "id": "s16",
   "name": "Res Ipsa Cream Calf Hair Mules",
   "category": "Shoes",
   "colourName": "Cream",
   "colourHex": "#D9CDB8",
   "expect": "caramel"
  },
  {
   "id": "s17",
   "name": "TOMS Cream Canvas Slip-Ons",
   "category": "Shoes",
   "colourName": "Cream",
   "colourHex": "#d4cab9",
   "expect": "free"
  },
  {
   "id": "s18",
   "name": "Vans Black and White Checkerboard Slip-On Sneakers",
   "category": "Shoes",
   "colourName": "Black/White",
   "colourHex": "#171617",
   "expect": "black"
  },
  {
   "id": "s19",
   "name": "Vans Cream Canvas Authentic Sneakers",
   "category": "Shoes",
   "colourName": "Cream",
   "colourHex": "#EFE6CC",
   "expect": "free"
  },
  {
   "id": "s20",
   "name": "Vans Tan Suede Authentic Sneakers",
   "category": "Shoes",
   "colourName": "Tan",
   "colourHex": "#B9A383",
   "expect": "caramel"
  },
  {
   "id": "s21",
   "name": "Vans White and Grey Checkerboard Slip-On Sneakers",
   "category": "Shoes",
   "colourName": "White/Grey",
   "colourHex": "#d8d5d4",
   "expect": "free"
  },
  {
   "id": "s22",
   "name": "Velasca Brown Suede Venetian Slippers",
   "category": "Shoes",
   "colourName": "Brown",
   "colourHex": "#89573c",
   "expect": "caramel"
  }
 ]
}
OTHERS = [{"id": "t1", "name": "White Oxford Shirt", "category": "Shirts", "colourName": "White", "colourHex": "#f7f5ef"},
          {"id": "c1", "name": "Stone Cotton Chino", "category": "Trousers", "colourName": "Stone", "colourHex": "#c9b896"}]
items = CLOSET["belts"] + [{k: v for k, v in s.items() if k != "expect"} for s in CLOSET["shoes"]] + OTHERS

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and r.request.method == "GET" else r.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(items)) + ")")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__appRan850 === true && window.WardrobeComposer && WardrobeComposer.shadeOf8709", timeout=60000)
    got = page.evaluate("""(shoes) => {
      const C = WardrobeComposer, deck = C.build(wardrobeItems.filter(i => /^(b|s)\\d\\d$|^t1$|^c1$/.test(i.id)));
      const t = deck.tops.find(x => x.id === 't1'), bt = deck.bottoms.find(x => x.id === 'c1');
      return shoes.map(sh => { const s = deck.shoes.find(x => x.id === sh.id); const dealt = {};
        for (const lv of [1, 2, 3, 4, 5, 6]) for (let k = 0; k < 40; k++) {
          const b = C.beltFor(deck.belts, { t, b: bt, s, l: null, key: 'k' + k + s.id }, lv);
          const key = b ? b.name + '|' + b.shade8709 + '|' + (b.multi || b.casualBelt ? (b.shades8709 || []).join('/') : '') : '(none)';
          dealt[key] = (dealt[key] || 0) + 1; }
        return { name: sh.name, expect: sh.expect, shade: C.shadeOf8709(s.n), belts: deck.belts.length, dealt }; }); }""", CLOSET["shoes"])
    assert not errors, errors
    assert got[0]["belts"] == 20, got[0]["belts"]
    bad = []
    for g in got:
        if g["expect"] != "free":
            if g["shade"] != g["expect"]:
                bad.append(("read as the wrong shade", g["name"], g["shade"], g["expect"]))
            for k in g["dealt"]:
                name, shade, shades = k.split("|") if "|" in k else (k, "", "")
                if name == "(none)" or (shade != g["expect"] and g["expect"] not in shades.split("/")):
                    bad.append(("a belt of another shade", g["name"], g["expect"], k))
        else:
            assert "(none)" not in g["dealt"], g
    dark = [g for g in got if "Dark Brown Suede" in g["name"] or "Polperro" in g["name"]]
    assert dark and not any("Tobacco Suede Belt" in k for g in dark for k in g["dealt"]), dark
    assert not bad, (len(bad), bad[:12])
    browser.close()
print("Confirmed: each of %d pairs of shoes gets only belts in its own shade at every dress level (white and cream sneakers take any)" % len(got))
