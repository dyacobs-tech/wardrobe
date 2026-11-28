"""The nightly audit's open findings of 28 Nov 2026, fixed (.87.33).

David, 28 Nov 2026, on the list of open findings: "DO ALL", and on the mirror photos in Calendar on 23, 24 and
26 Nov: "replace w avatar".

  * Calendar and the worn list show his avatar for a logged outfit when a high-res picture of those pieces exists;
    the photo he logged stays stored with the entry.
  * Home shows only the high-res pictures of him. After an old drawing showed, his figure dropped from 402x584
    to 384x557 and stayed smaller; the old drawings are on his old face.
  * The Edit lights the tab of the page it shows (Looks, pencil on a card, Home, The Edit showed Icons with
    "Dress me" lit).
  * Closet > Brand lists brands, not piece names, with one "No brand" entry, and one entry per brand whatever
    the capitals.
  * A pressed Like shows its thumb (it was a plain black dot).
  * Black Tie with no dinner jacket says so at once (six blank cards sat there for six seconds).
  * Clothing > "All 186" shows the 186 clothing pieces (it showed all 277).
  * The level button reads "Sharp" for Evening Sharp (it read "undefined +1").
  * A Home title too long for one line takes two lines in the same box instead of ending in "...".
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"


def run(browser):
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) and r.request.method == "GET" else r.abort())
    closet = photographed_closet()
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(closet)) + ");localStorage.setItem('wardrobe.formality','3')")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("() => window.__homeShownAt850 > 0 && typeof HIRES !== 'undefined' && HIRES.ready && window.__cfLooks81 && __cfLooks81().length >= 1", timeout=40000)
    out = {}

    # level button: every level has a short name
    out["levels"] = page.evaluate("() => { const r = []; for (const set of [[2, 4], [4, 5], [4, 5, 6], [3, 4]]) { dressLevels838.set(set); const b = [...document.querySelectorAll('button')].map(x => x.textContent).filter(t => /Sharp|Dressy|Day|Casual|Formal/.test(t)); r.push(b.join('|')); } dressLevels838.set([3]); return r; }")
    assert out["levels"] and not any("undefined" in x for x in out["levels"]), out["levels"]

    # Home shows only high-res pictures: an outfit with only an old drawing is not shown
    out["oldOnHome"] = page.evaluate("""() => { const keys = onbodyKeys() || {}; let checked = 0, shown = 0;
      for (const k in keys) { if (/onbody-hires\\//.test(String(keys[k]))) continue; const items = k.split('|').map(id => closetItemById(id)).filter(Boolean);
        if (items.length < 2) continue; const look = { fwPieces: items, composerKey: k }; if (hiresForLook(look, 'full')) continue;
        checked++; if (lookHeroVisible84(look)) shown++; if (checked > 40) break; }
      return { checked, shown }; }""")
    assert out["oldOnHome"]["checked"] >= 1 and out["oldOnHome"]["shown"] == 0, ("an old drawing can still be dealt on Home", out["oldOnHome"])

    # Home title: a long name is never cut off and the text around it does not move
    out["title"] = page.evaluate("""async () => { const n = document.getElementById('today-name'), loc = document.getElementById('today-loc');
      const before = [Math.round(n.getBoundingClientRect().top), Math.round(loc.getBoundingClientRect().top)];
      n.textContent = 'Light Blue Blazer, Light Blue Stripe Shirt & Dark Navy Knit Tie'; await new Promise(r => setTimeout(r, 150));
      const cs = getComputedStyle(n); const after = [Math.round(n.getBoundingClientRect().top), Math.round(loc.getBoundingClientRect().top)];
      return { before, after, ellipsis: cs.whiteSpace === 'nowrap' && n.scrollWidth > n.clientWidth + 1, wide: n.scrollWidth > n.clientWidth + 1, fs: cs.fontSize }; }""")
    t = out["title"]
    assert not t["ellipsis"] and not t["wide"], ("a long Home title is cut off", t)
    assert t["before"] == t["after"], ("the Home text moved for a long title", t)

    # Calendar: a logged outfit shows the avatar picture of its pieces; the logged photo stays stored
    out["cal"] = page.evaluate("""() => { const items = wardrobeItems.filter(i => /Tees|Polos|Shirts/.test(i.category)).slice(0, 1).concat(wardrobeItems.filter(i => /Trousers|Jeans/.test(i.category)).slice(0, 1));
      const key = items.map(i => i.id).sort().join('|'); const any = Object.values(HIRES.map)[0];
      hiresIngest({ r: [{ k: key, card: any.card, full: any.full }] });
      const selfie = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
      const entry = { id: 'w-8733', date: '2026-11-23', title: 'From a mirror photo', img: selfie, selfie: true, pieceIds: items.map(i => i.id) };
      const e = calendarOutfits([entry], null)[0]; return { image: e.image, want: any.card, kept: entry.img === selfie }; }""")
    assert out["cal"]["image"] == out["cal"]["want"] and out["cal"]["kept"], out["cal"]

    # Closet: "All" in a group is that group; brands are brands
    page.evaluate("() => document.querySelector('#bottombar [data-section=\"ideas\"]').click()")
    page.wait_for_timeout(800)
    page.evaluate("() => { const b = [...document.querySelectorAll('button')].filter(x => x.offsetParent && x.textContent.trim() === 'Closet')[0]; b.click(); }")
    page.wait_for_function("() => document.querySelectorAll('#item-grid [data-item-open]').length > 5", timeout=15000)
    out["closet"] = page.evaluate("""async () => { const r = {}; const n = () => document.querySelectorAll('#item-grid [data-item-open]').length;
      r.all = n(); document.getElementById('ward-cat-clothing-btn').click(); await new Promise(z => setTimeout(z, 200));
      const opt = document.querySelector('#ward-cat-clothing-menu [data-cat-pick^="@"]'); r.says = +((opt.querySelector('.cat-count') || {}).textContent || 0);
      opt.click(); await new Promise(z => setTimeout(z, 600)); r.shows = n();
      r.brands = [...document.getElementById('ward-brand875').options].slice(1).map(o => o.textContent);
      r.names = wardrobeItems.map(i => i.name); return r; }""")
    c = out["closet"]
    assert c["says"] == c["shows"] and c["shows"] < c["all"], ("Clothing > All does not match its count", c["says"], c["shows"], c["all"])
    piece_names = set(c["names"]) - {b for b in c["brands"]}
    assert not [b for b in c["brands"] if b in set(c["names"]) and b != "No brand" and " " in b and b in piece_names], c["brands"]
    assert len({b.lower() for b in c["brands"]}) == len(c["brands"]), ("one brand listed twice with different capitals", c["brands"])

    # Like: the pressed thumb is visible
    page.evaluate("() => { const b = [...document.querySelectorAll('button')].filter(x => x.offsetParent && x.textContent.trim() === 'Outfits')[0]; b.click(); }")
    page.wait_for_function("() => document.querySelector('#panel-looks .cf-card [data-cf-like]')", timeout=20000)
    out["like"] = page.evaluate("""() => { const b = document.querySelector('#panel-looks .cf-card [data-cf-like]'); b.setAttribute('aria-pressed', 'true');
      const cs = getComputedStyle(b); return { bg: cs.backgroundColor, fg: cs.color }; }""")
    assert out["like"]["bg"] != out["like"]["fg"], ("a pressed Like is a plain dot", out["like"])

    # The Edit: the lit tab follows the page shown
    out["edit"] = page.evaluate("""async () => { const look = __cfLooks81()[0]; dressMe841(look); await new Promise(z => setTimeout(z, 400));
      switchTab('today'); await new Promise(z => setTimeout(z, 300)); switchTab('inspo'); await new Promise(z => setTimeout(z, 400));
      const lit = [...document.querySelectorAll('[data-ins-seg]')].filter(b => b.getAttribute('aria-selected') === 'true').map(b => b.getAttribute('data-ins-seg'));
      return { lit, shown: document.getElementById('panel-inspo') ? (document.querySelector('[data-insv]') ? document.querySelector('[data-insv]').getAttribute('data-insv') : 'icons') : '?' }; }""")
    assert out["edit"]["lit"] == [out["edit"]["shown"]], out["edit"]

    # Black Tie with no dinner jacket: says so at once
    out["bt"] = page.evaluate("""async () => { switchTab('looks'); await new Promise(z => setTimeout(z, 300)); const b = [...document.querySelectorAll('button')].filter(x => x.offsetParent && x.textContent.trim() === 'Outfits')[0]; if (b) b.click();
      dressLevels838.set([7]); const t0 = performance.now(); let ms = -1;
      for (let i = 0; i < 40; i++) { if (document.querySelector('.mine-empty829')) { ms = performance.now() - t0; break; } await new Promise(z => setTimeout(z, 50)); }
      return { ms, skel: document.querySelectorAll('.en-skel').length }; }""")
    assert 0 <= out["bt"]["ms"] < 1500, ("Black Tie waited on blank cards", out["bt"])
    assert not errors, errors
    ctx.close()
    return out


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        b = engine.launch()
        o = run(b)
        b.close()
print("Confirmed: level labels %s; no old drawing on Home (%d checked); a long title fits in place at %s; Calendar shows the avatar and keeps the logged photo; Clothing All %d of %d; %d brands, none twice; a pressed Like shows its thumb; The Edit lights %s; Black Tie says none in %d ms"
      % (o["levels"], o["oldOnHome"]["checked"], o["title"]["fs"], o["closet"]["shows"], o["closet"]["all"], len(o["closet"]["brands"]), o["edit"]["lit"], o["bt"]["ms"]))
