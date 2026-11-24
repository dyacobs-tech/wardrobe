"""Evening Casual is untucked; Evening Sharp is either way (.87.00, .87.02).

David, 23 Nov 2026, on tucking a button-down: "Actually no. Evening casual should be untucked. Evening sharp either
tucked or untucked". So no outfit whose top is tucked in is dealt at Evening Casual (level 3). An outfit that fits
Evening Casual is worn untucked (his linen, chambray and denim button-downs keep their Evening Casual outfits; .87.00
dropped them instead, which emptied Evening Casual of those shirts); a picture already drawn tucked leaves Evening
Casual. Evening Sharp (level 4) is left as it was (its dress shirts are dealt tucked in).
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
COUNT = """() => { const C = WardrobeComposer, out = {};
  [["all", C.build(wardrobeItems)], ["drawn", C.build(wardrobeItems, onbodyKeys())], ["only3", C.build(wardrobeItems, null, 3)]].forEach(([name, deck]) =>
    [3, 4].forEach(L => { const cs = deck.forLevel(L); out[name + L] = { n: cs.length, tucked: cs.filter(c => c.tucked).length,
      tuckedShirts: cs.filter(c => c.tucked && c.t.kind === 'shirt').length, untuckedShirts: cs.filter(c => !c.tucked && c.t.kind === 'shirt').length,
      untuckedButtonDowns: cs.filter(c => !c.tucked && c.t.kind === 'shirt' && !c.t.casualShirt && !c.t.overshirt).length }; }));
  return out; }"""

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items',%s)" % json.dumps(json.dumps(photographed_closet())))
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.WardrobeComposer && typeof onbodyKeys === 'function' && Object.keys(onbodyKeys() || {}).length > 0", timeout=60000)
    c = page.evaluate(COUNT)
    for name in ("all", "drawn", "only3"):
        assert c[name + "3"]["n"] > 0, ("no Evening Casual outfits at all", name, c)
        assert c[name + "3"]["tucked"] == 0, ("a tucked outfit at Evening Casual", name, c[name + "3"])
    assert c["all3"]["untuckedShirts"] > 0, ("Evening Casual lost its untucked shirts", c["all3"])
    # button-downs the app would tuck elsewhere (linen, chambray, denim) are still dealt at Evening Casual, untucked
    assert c["all3"]["untuckedButtonDowns"] > 0, ("Evening Casual lost its button-downs instead of untucking them", c["all3"])
    # Evening Sharp is unchanged: its button-downs are still dealt tucked in
    assert c["all4"]["tuckedShirts"] > 0, ("Evening Sharp lost its tucked shirts", c["all4"])
    browser.close()
print("Confirmed Evening Casual deals nothing tucked in, and Evening Sharp keeps its tucked shirts: %s" % json.dumps({k: v["n"] for k, v in c.items()}))
