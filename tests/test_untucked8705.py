"""Six pictured outfits with a shirt worn untucked are dealt at Evening Casual (.87.05).

David, 24 Nov 2026: "Evening casual should be untucked" (23 Nov), and on the list of pictures held out of Evening
Casual because their shirt counted as tucked: "Fix these". The yellow linen and denim shirt pictures show the shirt
untucked (four were already drawn that way and two were redrawn untucked), so the app now deals
them at Evening Casual untucked, while any other picture drawn with a tucked button-down stays out of Evening Casual.
"""
import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ITEMS = [{"id": "item-1794965180553-367368", "name": "Loro Piana Denim Shirt", "category": "Shirts", "colourName": "Denim Blue", "colourHex": "#838687"}, {"id": "item-1794965180554-529258", "name": "Brunello Cucinelli Yellow Linen Shirt", "category": "Shirts", "colourName": "Yellow", "colourHex": "#a58f6a"}, {"id": "item-1795089924131-247685", "name": "Common Projects White Leather Achilles Low Sneakers", "category": "Shoes", "colourName": "White", "colourHex": "#F4F2EC"}, {"id": "item-1795089924132-988772", "name": "Vans Tan Suede Authentic Sneakers", "category": "Shoes", "colourName": "Tan", "colourHex": "#B9A383"}, {"id": "item-1795089924133-225576", "name": "Vans Cream Canvas Authentic Sneakers", "category": "Shoes", "colourName": "Cream", "colourHex": "#EFE6CC"}, {"id": "item-1795296663307-996237", "name": "FRAME Dark Indigo Jeans", "category": "Jeans", "colourName": "Dark Indigo", "colourHex": "#172133"}, {"id": "item-1795317409064-924108", "name": "Loro Piana Cream Multicolour Runner Sneakers", "category": "Shoes", "colourName": "Cream", "colourHex": "#e9e1d2"}, {"id": "rcptbuy-1c3dyxl17", "name": "Levi's 517 Light Blue Cuffed Jeans", "category": "Jeans", "colourName": "Light blue", "colourHex": "#8ea4bd"}, {"id": "rcptbuy-1dnqhzg17", "name": "Levi's 517 Dark Indigo Jeans", "category": "Jeans", "colourName": "Dark indigo", "colourHex": "#2c3b5e"}, {"id": "rcptbuy-1fo09nv17", "name": "Proper Cloth Beige Non-Iron Stretch Chino", "category": "Trousers", "colourName": "beige", "colourHex": "#d8c6a5"}]
UNTUCKED = ["item-1794965180554-529258|item-1795089924131-247685|rcptbuy-1c3dyxl17", "item-1794965180554-529258|item-1795089924132-988772|item-1795296663307-996237", "item-1794965180554-529258|item-1795317409064-924108|rcptbuy-1dnqhzg17", "item-1794965180554-529258|item-1795089924133-225576|rcptbuy-1c3dyxl17", "item-1794965180554-529258|item-1795089924132-988772|rcptbuy-1dnqhzg17", "item-1794965180553-367368|item-1795089924131-247685|rcptbuy-1fo09nv17"]
# an outfit treated as pictured (passed as a picture key) with a tucked shirt and not on the untucked list stays out
CONTROL = "item-1794965180554-529258|item-1795089924131-247685|rcptbuy-1dnqhzg17"

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer")
    got = page.evaluate("""([items, keys, control]) => { const C = WardrobeComposer, rk = {};
      keys.concat([control]).forEach(k => rk[k] = 1);
      const deck = C.build(items, rk), at3 = deck.forLevel(3);
      const find = k => { const ids = k.split('|').sort().join('|'); return at3.find(c => c.ids.slice().sort().join('|') === ids); };
      return { shown: keys.map(k => { const c = find(k); return c ? { untucked: !c.tucked, prompt: c.tuckPrompt } : null; }), control: !!find(control) }; }""", [ITEMS, UNTUCKED, CONTROL])
    assert all(x and x["untucked"] for x in got["shown"]), ("an untucked picture is not dealt at Evening Casual, untucked", got)
    assert all("untucked" in x["prompt"] for x in got["shown"]), got
    assert not got["control"], ("an outfit with a tucked shirt that is not on the untucked list reached Evening Casual", got)
    browser.close()
print("Confirmed the 6 untucked yellow linen and denim shirt pictures are dealt at Evening Casual, and an outfit with a tucked shirt not on the list is not")
