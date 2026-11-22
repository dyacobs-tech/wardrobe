"""Liked never shows colour bands; thumbs sit in the middle; Go-to's opens at once (.86.49).

David, 22 Nov 2026:
  "Liked section has color swatches makes NO sense pls fix this now"
  "Liked looks still showing palettes"
  "Thumbs up and down still off centered"
  "you haven't fixed the placement of the thumbs in the icons!!!!!!"
  "Click on go-tos is super slow!!!!"
  "GO-TOs still loading still SO slow"

An old liked look has a list of colours and no pieces. Its card shows the
pieces from his closet that the look names (the same piece by name, or the
same kind of garment in the same colour). A look where that fails is listed
by name under the cards. No card is ever a stack of colour bands.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL)
              and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," +
                        json.dumps(json.dumps(photographed_closet())) + ");" +
                        "localStorage.setItem('wardrobe.formality','2')")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.locator("#section-ideas").tap()
    page.wait_for_function("() => window.__cfLooks81 && __cfLooks81().length >= 2")

    made = page.evaluate("""() => {
      const pick = re => wardrobeItems.filter(i => re.test(i.category) && i.photo && /^#[0-9a-f]{6}$/i.test(i.colourHex || ''));
      const tops = pick(/^(Polos|Tees|Shirts)$/), bots = pick(/^(Trousers|Jeans)$/), shoes = pick(/^Shoes$/);
      if (tops.length < 2 || bots.length < 2 || !shoes.length) return { ok: false };
      const noun = { Polos: 'Knit polo', Tees: 'Tee', Shirts: 'Shirt', Trousers: 'Trousers', Jeans: 'Jeans' };
      // 1: names his pieces outright
      savedLooks.push({ id: 'old-named', title: 'Named pieces', img: 'assets/photos/113a3f5b339f.webp', verdict: 'like', likedAt: 5,
        swatches: [tops[0], bots[0], shoes[0]].map(i => ({ name: i.colourName || '', hex: i.colourHex, role: i.name })) });
      // 2: names a kind of garment and a colour he owns; the pocket square is not a garment and is left out
      savedLooks.push({ id: 'old-colour', title: 'Same kind same colour', img: 'assets/photos/113a3f5b339f.webp', verdict: 'like', likedAt: 4,
        swatches: [{ name: 'x', hex: tops[1].colourHex, role: noun[tops[1].category] }, { name: 'y', hex: bots[1].colourHex, role: noun[bots[1].category] },
                   { name: 'z', hex: '#ff00ff', role: 'Silk pocket square' }] });
      // 3: a colour he does not own in that garment
      savedLooks.push({ id: 'old-none', title: 'Racing Green & Stone', img: 'assets/photos/113a3f5b339f.webp', source: 'combo', verdict: 'like', likedAt: 3,
        swatches: [{ name: 'Magenta', hex: '#ff00c8', role: 'Crew-neck knit' }, { name: 'Lime', hex: '#39ff14', role: 'Chinos' }, { name: 'Brown', hex: '#7c4226', role: 'Suede loafers' }] });
      return { ok: true, top0: tops[0].id, kind1: tops[1].category };
    }""")
    assert made["ok"], made
    page.evaluate("() => window.scrollTo(0, 0)")
    page.locator('#panel-looks [data-lk-go="liked"]').tap()
    page.wait_for_function("() => document.querySelectorAll('#lk-liked841 .lk-card841').length >= 2")
    liked = page.evaluate("""() => {
      const host = document.getElementById('lk-liked841');
      const cards = [...host.querySelectorAll('.lk-card841')].map(c => { const m = c.querySelector('.cf-media');
        return { title: c.querySelector('.oc-title').textContent, imgs: m.querySelectorAll('img').length,
                 bands: m.querySelectorAll('[class*="lk-sw"], .fl-swatch').length,
                 painted: [...m.querySelectorAll('span')].filter(s => s.style && s.style.background && !s.querySelector('img')).length }; });
      const list = [...host.querySelectorAll('.lk-nopic849 .lk-np849')].map(r => ({ title: r.querySelector('.lk-npt849').textContent, open: r.querySelector('[data-l841-open]') != null, unlike: r.querySelector('[data-l841-unlike]') != null }));
      return { cards, list, summary: (host.querySelector('.lk-nopic849 > summary') || {}).textContent || '', anyBand: host.querySelectorAll('.lk-sw843, .lk-swb843').length }; }""")
    by = {c["title"]: c for c in liked["cards"]}
    assert liked["anyBand"] == 0, liked
    assert all(c["bands"] == 0 and c["painted"] == 0 and c["imgs"] >= 1 for c in liked["cards"]), liked
    assert "Named pieces" in by and by["Named pieces"]["imgs"] >= 2, liked
    assert "Same kind same colour" in by and by["Same kind same colour"]["imgs"] >= 2, liked
    assert "Racing Green & Stone" not in by, liked
    assert [r["title"] for r in liked["list"]] == ["Racing Green & Stone"] and liked["list"][0]["open"] and liked["list"][0]["unlike"], liked
    assert liked["summary"].startswith("1 older liked look without a picture"), liked
    # the matcher itself: exact names give those pieces; an unowned colour gives nothing
    m = page.evaluate("""() => ({ named: (likedClosetPieces849(savedLooks.find(l => l.id === 'old-named')) || []).map(i => i.id),
      none: likedClosetPieces849(savedLooks.find(l => l.id === 'old-none')) })""")
    assert m["named"][0] == made["top0"] and len(m["named"]) == 3 and m["none"] is None, m
    # unliking from the list keeps the look (a dislike or unlike never deletes) and empties the list
    page.evaluate("() => document.querySelector('.lk-nopic849').setAttribute('open', '')")
    page.locator(".lk-nopic849 [data-l841-unlike]").tap()
    page.wait_for_function("() => !document.querySelector('.lk-nopic849')")
    assert page.evaluate("() => savedLooks.some(l => l.id === 'old-none')"), "unliking removed the look"

    # thumbs: the icon is its own size and laid out in the middle of its circle (it was a 44px strip pinned left)
    def thumbs(sel):
        return page.evaluate("""sel => [...document.querySelectorAll(sel)].filter(b => b.offsetParent).slice(0, 6).map(b => {
          const cs = getComputedStyle(b), bf = getComputedStyle(b, '::before'), r = b.getBoundingClientRect();
          return { w: r.width, h: r.height, pos: bf.position, bw: parseFloat(bf.width), bh: parseFloat(bf.height), tf: bf.transform, flex: /flex/.test(cs.display), jc: cs.justifyContent, ai: cs.alignItems, fs: cs.fontSize }; })""", sel)
    seen = 0
    for sel, go in (("#lk-liked841 [data-cf-like]", None), ("#panel-looks #cf-grid [data-cf-like], #panel-looks #cf-grid [data-cf-dislike]", "looks"), ("#panel-today .thumb-btn", "today")):
        if go:
            page.evaluate("t => switchTab(t)", go)
            page.wait_for_timeout(700)
        for t in thumbs(sel):
            seen += 1
            assert t["pos"] == "static" and t["tf"] == "none", (sel, t)
            assert t["bw"] == t["bh"] and 10 <= t["bw"] <= 24 and t["bw"] < t["w"], (sel, t)
            assert t["flex"] and t["jc"] == "center" and t["ai"] == "center" and t["fs"] == "0px", (sel, t)
    assert seen >= 3, seen

    # Go-to's: opening it never builds the deck of every outfit in the closet, and paints quickly
    page.evaluate("""() => { const l = __cfLooks81()[0]; recordWorn({ date: localTodayISO(), title: l.title, img: '', pieces: [], pieceIds: (l.fwPieces || []).map(p => p.id || p.itemId) }); switchTab('looks'); }""")
    took = page.evaluate("""() => { const t0 = performance.now(); switchTab('gotos'); return { ms: performance.now() - t0, cards: document.querySelectorAll('.lk-goto843').length,
      deck: !!(typeof composerDeckCache !== 'undefined' && composerDeckCache.lk841) }; }""")
    assert took["cards"] >= 1 and not took["deck"], took
    assert took["ms"] < 1500, took
    assert not errors, errors
    print("Confirmed: Liked shows pieces, never colour bands (%d cards, 1 listed by name); %d thumbs centred; Go-to's opened in %d ms without building the deck" % (len(liked["cards"]), seen, took["ms"]))
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        browser.close()
