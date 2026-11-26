"""The Edit has an Inspo page of new outfit concepts drawn on him; an icon's page has a closet-only choice (.86.58).

David, 22 Nov 2026:
  "We need to be able to create new outfit concepts (DOESNT HAVE TO BE
   SHOPPABLE) and if I like the designs of the concepts we can try and find
   the items for sale."
  "it creates new outfit concepts (six at a time) and lets me create six
   more, I can save down"
  "outfits inspired by icons and my style engine. Also using approved color
   pallets"
  About concepts drawn from his own garments in other colours: "I HATE this
   idea pls delete all of these!!!!!"
  Asked whether concepts drawn on his avatar are the right direction: "Yes".
  Asked whether an icon's page should also have a closet-only view: "Both".
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");localStorage.setItem('wardrobe.formality','5')")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => window.__appRan850 === true && typeof switchTab === 'function'", timeout=60000)

    # the library: every concept has a picture file, garments with colours, a level he uses, and a source
    lib = page.evaluate("() => INSPO_CONCEPTS")
    assert len(lib) >= 50, len(lib)
    for c in lib:
        assert os.path.exists(os.path.join(ROOT, "assets", "inspo-concepts", c["id"] + ".webp")), c["id"]
        assert c["level"] in (2, 3, 5, 6) and c["source"] in ("icon", "palette", "engine") and c["title"], c
        roles = [p["role"] for p in c["pieces"]]
        assert "top" in roles and "bottom" in roles and "shoes" in roles and all(p["hex"].startswith("#") and p["name"] for p in c["pieces"]), c
        names = " ".join(p["name"].lower() for p in c["pieces"])
        # his rules: Formal has a tie; a blazer never meets sneakers; nothing is a women's piece
        if c["level"] == 6:
            assert "tie" in roles, c
        if any(w in names for w in ("blazer", "suit jacket")):
            assert not any(w in names for w in ("sneaker", "slip-on", "plimsoll", "trainer")), c
        assert not any(w in names for w in ("skirt", "blouse", "gown", "high heel", "women")), c
    assert {c["level"] for c in lib} == {2, 3, 5, 6}

    page.evaluate("() => switchTab('inspo')")
    page.wait_for_function("() => document.querySelectorAll('[data-ins-seg]').length === 3")
    assert page.evaluate("() => [...document.querySelectorAll('[data-ins-seg]')].map(b => b.textContent)") == ["Icons", "Inspo", "Dress me"]
    seg = page.evaluate("() => { const b = [...document.querySelectorAll('[data-ins-seg]')].map(x => x.getBoundingClientRect()); return b.every(r => Math.abs(r.top - b[0].top) < 2); }")
    assert seg, "the three tabs are not on one line"
    page.evaluate("() => document.querySelector('[data-ins-seg=\"ideas\"]').click()")
    page.wait_for_function("() => document.querySelectorAll('#ins-ideas858 .cx-card858').length === 6")
    first = page.evaluate("""() => ({ ids: inspoShown858().map(c => c.id), levels: [...new Set(inspoShown858().map(c => c.level))],
      imgs: [...document.querySelectorAll('#ins-ideas858 .cx-card858 img')].map(i => i.getAttribute('src')), prices: /\\$\\d/.test(document.getElementById('ins-ideas858').textContent),
      feeds: !!document.querySelector('#outfits-inspo-view') && document.querySelector('#outfits-inspo-view').offsetParent !== null, tinted: document.querySelectorAll('#ins-ideas858 [class*="cx-g8"], #ins-ideas858 [style*="mask-image"]').length })""")
    assert first["levels"] == [5] and len(set(first["ids"])) == 6, first
    assert all(s.startswith("assets/inspo-concepts-hires/") or s.startswith("assets/inspo-concepts/cx-") for s in first["imgs"]) and not first["prices"] and not first["feeds"] and first["tinted"] == 0, first
    page.wait_for_function("() => [...document.querySelectorAll('#ins-ideas858 .cx-card858 img')].slice(0, 2).every(i => i.complete && i.naturalWidth > 100)", timeout=20000)

    # six more are six different ones
    page.evaluate("() => document.querySelector('[data-cx858-more]').click()")
    second = page.evaluate("() => inspoShown858().map(c => c.id)")
    assert len(second) == 6 and not set(second) & set(first["ids"]), (first["ids"], second)

    # open one, keep it, shop the look
    page.evaluate("() => document.querySelector('[data-cx858-open]').click()")
    sheet = page.evaluate("() => ({ open: !document.getElementById('cx-sheet858').hidden, pieces: document.querySelectorAll('#cx-sheet858 .cx-list858 li').length, title: document.getElementById('cx-title858').textContent })")
    assert sheet["open"] and sheet["pieces"] >= 3, sheet
    cream = page.evaluate("""() => {
      const card = document.querySelector('#cx-sheet858 .cx-sheet858');
      const img = document.querySelector('#cx-sheet858 .cx-big858');
      const head = document.querySelector('#cx-sheet858 .principles-head');
      return {
        card: card ? getComputedStyle(card).backgroundColor : null,
        img: img ? getComputedStyle(img).backgroundColor : null,
        head: head ? getComputedStyle(head).backgroundColor : null
      };
    }""")
    cream_ok = "rgb(246, 242, 234)"
    assert cream["card"] == cream_ok and cream["img"] == cream_ok and cream["head"] == cream_ok, ("concept sheet card, header and photo are not the same cream #F6F2EA", cream)
    page.evaluate("() => document.querySelector('[data-cx858-sheetlike]').click()")
    kept = page.evaluate("() => savedLooks.filter(l => l.concept).map(l => ({ t: l.title, v: l.verdict, img: l.img, n: l.swatches.length }))")
    assert len(kept) == 1 and kept[0]["v"] == "like" and kept[0]["t"] == sheet["title"] and (kept[0]["img"].startswith("assets/inspo-concepts-hires/") or kept[0]["img"].startswith("assets/inspo-concepts/")) and kept[0]["n"] >= 3, kept
    page.evaluate("() => document.querySelector('[data-cx858-find]').click()")
    shop = page.evaluate("() => ({ open: !document.getElementById('find-sheet').hidden, rows: document.querySelectorAll('#find-sheet-pieces [data-find-sheet-piece]').length, face: document.querySelectorAll('#find-sheet-pieces .find-sheet-photo').length })")
    assert shop["open"] and shop["rows"] >= 3 and shop["face"] == 0, shop
    page.evaluate("() => document.getElementById('find-sheet-close').click()")

    # the kept concept is in Liked > Looks with its picture of him, and is not a palette
    page.evaluate("() => switchTab('liked')")
    page.wait_for_function("() => document.querySelector('#lk-liked841 .cx-fig858')")
    liked = page.evaluate("() => ({ titles: [...document.querySelectorAll('#lk-liked841 .lk-card841 .oc-title')].map(t => t.textContent), palettes: approvedPalettes853().length })")
    assert sheet["title"] in liked["titles"] and liked["palettes"] == 0, liked

    # a different level shows that level's concepts
    page.evaluate("() => { setFormality(2); switchTab('inspo'); document.querySelector('[data-ins-seg=\"ideas\"]').click(); }")
    page.wait_for_function("() => inspoShown858().length && inspoShown858().every(c => c.level === 2)")

    # an icon's page offers Mine: closet outfits, on him, no prices; without an icon it is not offered
    page.evaluate("() => { setFormality(3); document.querySelector('[data-ins-seg=\"icons\"]').click(); }")
    page.wait_for_function("() => document.querySelector('[data-ins-feed=\"mine\"]')")
    assert page.evaluate("() => document.querySelector('[data-ins-feed=\"mine\"]').hidden") is True
    page.evaluate("() => document.querySelector('[data-ins-icon]').click()")
    page.wait_for_function("() => !document.querySelector('[data-ins-feed=\"mine\"]').hidden")
    # .87.10: Mix (new pieces mixed with his closet, not drawn on him) is back next to New + mine (David, 24 Nov 2026)
    assert page.evaluate("() => [...document.querySelectorAll('[data-ins-feed]')].filter(b => !b.hidden).map(b => b.textContent)") == ["Mine", "New + mine", "Mix", "All new"]
    page.evaluate("() => document.querySelector('[data-ins-feed=\"mine\"]').click()")
    # waited for and measured in one step: the level change above re-deals the grid ~300ms later, and on a busy
    # machine a separate measure could land in that re-deal and count 0 cards (24 Nov 2026, full local runs)
    mine = page.wait_for_function("""() => { const cards = [...document.querySelectorAll('#cf-grid .cf-card:not(.en-skel)')].filter(c => c.offsetParent);
      if (cards.length < 2) return false;
      return { n: cards.length, priced: cards.filter(c => /\\$\\d/.test(c.textContent)).length, onHim: cards.filter(c => c.querySelector('img[data-onbody], .mine-avatar')).length,
               products: [...document.querySelectorAll('#en-grid-withmine .cf-card, #en-grid-allnew .cf-card')].filter(c => c.offsetParent).length, tab: currentTab }; }""", timeout=30000).json_value()
    assert mine["tab"] == "inspo" and mine["n"] >= 2 and mine["priced"] == 0 and mine["onHim"] == mine["n"] and mine["products"] == 0, mine
    page.evaluate("() => document.querySelector('[data-ins-clear]').click()")
    page.wait_for_function("() => document.querySelector('[data-ins-feed=\"mine\"]').hidden && document.querySelector('[data-ins-feed=\"withmine\"]').getAttribute('aria-pressed') === 'true'")
    assert not errors, errors
    ctx.close()
    return len(lib), mine["n"]


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        n, mine = run(browser)
        print("Confirmed: %d concepts with pictures and garments; Inspo shows six for the level, six more are new; like keeps one in Liked; Shop the look lists its garments; an icon's page offers Mine (%d closet outfits on him)" % (n, mine))
        browser.close()
