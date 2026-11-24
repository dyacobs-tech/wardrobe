"""Ask DONNA is back in Shop, answered by the assistant, and its page is laid out cleanly (.86.82).

David, 23 Nov 2026: "Let's integrate muse / Claude / chatgpt though", then "yes deploy the assistant" and
"also make sure formatting of thAT PAGE IS DIALED!!!!". Checks: the tab is there, an answer shows as readable
text with compact product cards (two to a screen), and the question box sits above the bottom bar, not under it.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
from pathlib import Path
cat = json.loads((Path(__file__).resolve().parents[1] / "assets/edit-catalog.json").read_text())["products"]
prods = [c for c in cat if c["cat"] in ("trousers", "shoes")][:4]
ANSWER = {"answer": "Go Evening Sharp tonight: your navy knit tee, the stone chinos and the dark brown tassel loafers.",
          "picks": [{"sku": p["sku"], "why": "Pairs with your navy tee.", "pairsWith": [],
                     "product": {k: p.get(k) for k in ("sku", "brand", "name", "price", "priceDisplay", "url", "img", "cat", "colour", "hex", "retailer")}} for p in prods],
          "meta": {"model": "openai:test", "fallback": False}}

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")

    def route(r):
        u = r.request.url
        if u.startswith(URL):
            return r.continue_()
        if u.endswith("/ask") and r.request.method == "POST":
            return r.fulfill(status=200, content_type="application/json", body=json.dumps(ANSWER))
        return r.abort()
    ctx.route("**/*", route)
    ctx.add_init_script("localStorage.setItem('wardrobe.items',%s)" % json.dumps(json.dumps(photographed_closet())))
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => typeof window.editShow === 'function'")
    page.locator("#tab-find").first.dispatch_event("click")
    page.wait_for_timeout(800)
    page.evaluate("() => { SY.key = 'a'.repeat(48); }")
    page.locator("#edit-tab-askdonna").click()
    page.wait_for_timeout(500)
    page.fill("#ask-q", "What should I wear to dinner tonight?")
    page.locator("#ask-send").click()
    page.wait_for_selector("#ask-thread .ask-card", timeout=10000)
    page.wait_for_timeout(800)
    m = page.evaluate("""() => {
      const a = document.querySelector('#ask-thread .ask-a'), c = document.querySelector('#ask-thread .ask-card');
      const f = document.getElementById('ask-form').getBoundingClientRect(), bar = document.getElementById('bottombar');
      const barTop = bar ? bar.getBoundingClientRect().top : innerHeight;
      return { font: parseFloat(getComputedStyle(a).fontSize), card: c.getBoundingClientRect().width, vw: innerWidth,
               formBottom: f.bottom, barTop, cardH: c.getBoundingClientRect().height };
    }""")
    assert 15 <= m["font"] <= 18, m
    assert m["card"] <= m["vw"] * 0.52, ("product cards too wide", m)
    assert m["cardH"] <= 460, ("product cards too tall", m)
    assert m["formBottom"] <= m["barTop"] + 1, ("question box hidden behind the bottom bar", m)
    browser.close()
print("Confirmed Ask DONNA: tab in Shop, readable answer, two cards to a screen, question box above the bottom bar")
