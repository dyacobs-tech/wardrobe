"""The Edit at Pool / Beach settles: no button rebuilt every frame, so iPhone taps work (.86.97).

David, 24 Nov 2026: "Cannot engage with any buttons. Once I click the edit, it shows the screen, but none of the buttons
navigate anywhere. And then the rest of the app freezes and I can't scroll to different pages. I have to close the app."
Cause: at Pool / Beach the New + mine feed holds few outfits, its end-of-feed marker stayed in range, and the feed
re-checked it every frame, rebuilding the "Show ideas not drawn on you yet" button 60 times a second. iPhone Safari
treats a tap during which a new clickable element appears as a hover and never sends the click.
Checks, at every dress level: once The Edit has settled, nothing clickable is inserted and the page hardly changes.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
COUNT = """() => new Promise(done => {
  let added = 0, clickable = 0, attrs = 0;
  const mo = new MutationObserver(ms => { for (const m of ms) {
    if (m.type === 'attributes') { if (m.target.getClientRects && m.target.getClientRects().length) attrs++; continue; }
    /* only what appears on screen counts: the app also builds its hidden pages in spare moments after start-up */
    m.addedNodes.forEach(n => { if (n.nodeType !== 1 || !n.isConnected || !n.getClientRects().length) return; added++; if (n.matches('button, a, [role=button]') || n.querySelector('button, a, [role=button]')) clickable++; });
  } });
  mo.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['hidden', 'class'] });
  setTimeout(() => { mo.disconnect(); done({ added, clickable, attrs }); }, 3000);
})"""

with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        for level in (1, 2, 3, 4, 5, 6, 7):
            ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
            ctx.add_init_script("localStorage.setItem('wardrobe.items',%s);localStorage.setItem('wardrobe.formality','%d');localStorage.setItem('wardrobe.dressLevels838','[%d]')" % (json.dumps(json.dumps(photographed_closet())), level, level))
            page = ctx.new_page()
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_function("() => typeof window.editShow === 'function'")
            page.wait_for_timeout(1500)
            page.locator("#section-inspo").first.dispatch_event("click")
            page.wait_for_timeout(5000)     # let the feed fill and settle
            for where in ("top", "bottom"):
                if where == "bottom":
                    page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
                    page.wait_for_timeout(2500)
                got = page.evaluate(COUNT)
                assert got["clickable"] <= 2 and got["added"] <= 20, (engine.name, "level", level, where, "The Edit keeps rebuilding itself", got)
            ctx.close()
        browser.close()
print("Confirmed The Edit settles at every dress level: nothing clickable is rebuilt once it has drawn")
