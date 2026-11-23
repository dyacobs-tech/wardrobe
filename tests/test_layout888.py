"""Pages end clear of the bottom bar, the + never sits on a card title, the Profile tabs fit (audit, fix 9, .86.88).

From the audit David asked to have fixed ("Just start going through ALL of these in order"), against his formatting
rule (22 Nov 2026: "Want formatting to be DIALED!!!! Make sure all pages for viewing are correct in formatting and
buttons are smushed or hidden!!!!"):
- the last button of Closet · Add, Profile · Info and Advanced and Shop · Build ended at, or under, the bar;
- the floating + covered an outfit card's title on Looks;
- Info / Location / Rules / Advanced ran 10px past the row on a 402px phone ("Advanced" cut at the edge).
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

CLICK = """(sel) => { const e = document.querySelector(sel); if (!e) return false; e.click(); return true; }"""
LAST = """() => new Promise(done => { const se = document.scrollingElement; se.scrollTop = se.scrollHeight;
  setTimeout(() => { const bar = document.getElementById('bottombar').getBoundingClientRect().top; let low = 0;
    [...document.querySelectorAll('main section[role=tabpanel]')].filter(s => s.offsetParent).forEach(p =>
      p.querySelectorAll('button,input,a,p,h3,img,.card').forEach(e => { if (!e.offsetParent) return; const b = e.getBoundingClientRect();
        if (b.height > 0 && b.bottom > low) low = b.bottom; }));
    done(Math.round(bar - low)); }, 400); })"""


def ctx_for(browser, w, h):
    ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items',%s)" % json.dumps(json.dumps(photographed_closet())))
    return ctx


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for w, h in ((402, 874), (375, 667)):
        ctx = ctx_for(browser, w, h)
        page = ctx.new_page()
        for name, steps in (("Closet · Add", ["#section-ideas", "[data-lk-go=wardrobe]", "#closet-add-entry"]),
                            ("Profile · Advanced", ["#tab-pcloud"]), ("Profile · Info", ["#tab-pinfo"])):
            page.goto(URL, wait_until="load")
            page.wait_for_timeout(1200)
            if name.startswith("Profile"):
                page.evaluate("() => switchTab('pinfo')")
                page.wait_for_timeout(400)
            for s in steps:
                page.evaluate(CLICK, s)
                page.wait_for_timeout(700)
            clear = page.evaluate(LAST)
            assert clear >= 12, (w, name, "ends %dpx from the bottom bar" % clear)
        # the four Profile tabs fit on the row
        fit = page.evaluate("() => { const s = document.querySelector('#subnav-me .subnav-scroll'); return [s.scrollWidth, s.clientWidth]; }")
        assert fit[0] <= fit[1] + 1, (w, "Profile tabs run past the row", fit)
        ctx.close()

    # the + is never on a card title on Looks
    ctx = ctx_for(browser, 390, 844)
    page = ctx.new_page()
    page.goto(URL, wait_until="load")
    page.wait_for_timeout(1200)
    page.evaluate(CLICK, "#section-ideas")
    page.wait_for_function("() => document.querySelectorAll('#panel-looks .oc-title').length >= 4", timeout=30000)
    page.wait_for_timeout(1200)
    hits = page.evaluate("""() => { const f = document.getElementById('pv-fab'); if (!f || !f.offsetParent) return [];
      const r = f.getBoundingClientRect(); if (getComputedStyle(f).opacity === '0') return [];
      return [...document.querySelectorAll('#panel-looks .oc-title')].filter(e => { const b = e.getBoundingClientRect();
        return b.width && b.right > r.left && b.left < r.right && b.bottom > r.top && b.top < r.bottom; }).map(e => e.textContent.trim()); }""")
    assert not hits, ("the + covers a card title", hits)
    browser.close()
print("Confirmed pages end clear of the bottom bar, the Profile tabs fit at 375 and 402, and the + keeps off card titles")
