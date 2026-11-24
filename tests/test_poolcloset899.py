"""At Pool / Beach, The Edit shows outfits from David's own closet only; no pieces for sale (.86.99).

David, 24 Nov 2026: "I don't care about Inspo pool looks. Maybe we remove this section for the edit. I only really
care about pool looks with my existing wardrobe with what I own. Just to have as a fun feature. If we can't fix this,
that is and it becomes an issue. I don't want this holding back the actual app."
Checks, in Chromium and WebKit:
  1. With Pool / Beach the only dress level, The Edit shows his closet outfits under "Pool looks from your closet":
     New + mine, All new and the price filter are hidden, no card for sale is on screen, and no shop deal is asked for.
  2. Once drawn it settles (nothing clickable rebuilt), and real taps on the bottom bar move between pages.
  3. Changing to Daytime while The Edit is open brings New + mine back; Pool + Daytime deals shop looks for Daytime only.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
COUNT = """() => new Promise(done => {
  let added = 0, clickable = 0;
  const mo = new MutationObserver(ms => { for (const m of ms) m.addedNodes.forEach(n => {
    if (n.nodeType !== 1 || !n.isConnected || !n.getClientRects().length) return; added++;
    if (n.matches('button, a, [role=button]') || n.querySelector('button, a, [role=button]')) clickable++; }); });
  mo.observe(document.body, { subtree: true, childList: true });
  setTimeout(() => { mo.disconnect(); done({ added, clickable }); }, 3000);
})"""
STATE = """() => ({ insf: document.documentElement.getAttribute('data-insf'), title: (document.getElementById('ins-title841') || {}).textContent,
  choices: [...document.querySelectorAll('[data-ins-feed]')].filter(b => b.offsetParent).map(b => b.textContent),
  filter: !!(document.querySelector('.ins-filter841') || {}).offsetParent,
  closet: [...document.querySelectorAll('#outfits-mine-view .cf-grid > *')].filter(e => e.offsetParent && e.getBoundingClientRect().height > 40).length,
  shop: [...document.querySelectorAll('#outfits-inspo-view .en-card')].filter(e => e.offsetParent).length })"""
# every deal message the page sends to its outfit worker
SPY = """(() => { const P = Worker.prototype.postMessage; window.__deals899 = [];
  Worker.prototype.postMessage = function (m) { try { if (m && m.type === 'deal') window.__deals899.push({ feed: m.feed, level: m.level, levels: m.levels }); } catch (e) {} return P.apply(this, arguments); }; })()"""


def tap(page, name):
    xy = page.evaluate("""n => { const el = [...document.querySelectorAll('#bottombar button')].find(x => x.textContent.trim().startsWith(n));
      if (!el) return null; const r = el.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }""", name)
    page.touchscreen.tap(xy[0], xy[1])
    page.wait_for_timeout(1200)
    return page.evaluate("() => currentTab")


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
        ctx.add_init_script(SPY)
        ctx.add_init_script("localStorage.setItem('wardrobe.items',%s);localStorage.setItem('wardrobe.formality','1');localStorage.setItem('wardrobe.dressLevels838','[1]')" % json.dumps(json.dumps(photographed_closet())))
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_function("() => typeof window.editShow === 'function' && typeof window.poolOnly899 === 'function'")
        page.wait_for_timeout(1500)
        page.locator("#section-inspo").first.dispatch_event("click")
        page.wait_for_function("() => document.querySelectorAll('#outfits-mine-view .cf-grid > *').length > 0", timeout=30000)
        page.wait_for_timeout(4000)
        st = page.evaluate(STATE)
        assert st["insf"] == "mine" and st["title"] == "Pool looks from your closet", (engine.name, "The Edit at Pool is not his closet", st)
        assert not st["choices"] and not st["filter"], (engine.name, "shop choices still offered at Pool", st)
        assert st["closet"] >= 1 and st["shop"] == 0, (engine.name, "Pool shows pieces for sale or no closet outfits", st)
        pool_deals = [d for d in page.evaluate("() => window.__deals899") if d["feed"] != "mine"]
        assert not pool_deals, (engine.name, "shop looks dealt at Pool only", pool_deals[:3])
        got = page.evaluate(COUNT)
        assert got["clickable"] <= 2 and got["added"] <= 20, (engine.name, "The Edit at Pool keeps rebuilding itself", got)
        for name, tab in (("Looks", "looks"), ("Shop", "find"), ("The Edit", "inspo")):
            now = tap(page, name)
            assert now == tab, (engine.name, "a real tap on", name, "did not move", now)
        # Daytime while The Edit is open: the shop feeds come back
        page.evaluate("() => { window.__deals899.length = 0; setFormality(2); window.dressLevels838.set([2]); }")
        page.wait_for_timeout(3000)
        st = page.evaluate(STATE)
        assert st["insf"] is None and "New + mine" in st["choices"] and st["title"] == "Ideas for you", (engine.name, "Daytime did not bring the shop feeds back", st)
        # Pool + Daytime: shop looks are dealt for Daytime only
        page.evaluate("() => { window.__deals899.length = 0; window.dressLevels838.set([1, 2]); }")
        page.wait_for_function("() => window.__deals899.some(d => d.feed !== 'mine')", timeout=20000)
        shop = [d for d in page.evaluate("() => window.__deals899") if d["feed"] != "mine"]
        assert all(d["level"] != 1 and 1 not in (d["levels"] or []) for d in shop), (engine.name, "a shop deal at Pool / Beach", shop[:3])
        ctx.close()
        browser.close()
print("Confirmed The Edit at Pool / Beach shows only his closet, settles, takes real taps, and the shop feeds skip Pool")
