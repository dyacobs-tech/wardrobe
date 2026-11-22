"""Go-to's show him wearing the outfit AND its pieces (.86.43).

David (21 Nov): "Go-tos should be on my avatar AND the swatches."
A worn outfit that has an on-body render shows the avatar with its piece
photos beside it; one without a render shows its pieces alone.
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

    # he wore a rendered outfit, and one that has no render (two loose pieces)
    worn = page.evaluate("""() => {
      const l = __cfLooks81()[0];
      const ids = (l.fwPieces || []).map(p => p.id || p.itemId);
      recordWorn({ date: localTodayISO(), title: l.title, img: '', pieces: [], pieceIds: ids });
      const tops = wardrobeItems.filter(i => /Shirts|Polos|Tees/.test(i.category)), bots = wardrobeItems.filter(i => /Trousers|Jeans/.test(i.category));
      let loose = null;
      for (const t of tops) { for (const b of bots) { const k = [t.id, b.id]; if (!onbodyForLook({ fwPieces: [t, b], composerKey: k.slice().sort().join('|') })) { loose = k; break; } } if (loose) break; }
      if (loose) recordWorn({ date: '2026-11-01', title: 'Loose pair', img: '', pieces: [], pieceIds: loose });
      return { n: ids.length, loose: !!loose };
    }""")
    assert worn["n"] >= 3, worn
    page.locator('#panel-looks [data-lk-go="gotos"]').tap()
    page.wait_for_function("() => document.querySelectorAll('.lk-goto843').length >= 1")
    cards = page.evaluate("""() => [...document.querySelectorAll('.lk-goto843')].map(c => ({
      avatar: !!c.querySelector('.onbody-split .ob-figure img[data-onbody]'),
      pieces: c.querySelectorAll('.onbody-split .ob-pieces .fl-cell img').length,
      flat: c.querySelectorAll('.flatlay:not(.onbody-split) .fl-cell').length,
      fig: (() => { const f = c.querySelector('.ob-figure'); if (!f) return 0; return Math.round(f.getBoundingClientRect().height); })() }))""")
    first = cards[0]
    assert first["avatar"] and first["pieces"] >= 3 and first["fig"] > 150, cards
    if worn["loose"]:
        assert any((not c["avatar"]) and c["flat"] >= 2 for c in cards), cards
    # .86.45 (David: "Go-tos should be on my avatar too remember!!!"): an outfit he logged carries its own picture
    # of him wearing it. With no library render the go-to shows that picture beside its pieces: the backdrop-free
    # file when the entry names one, the saved picture when that file cannot load, and never a camera selfie.
    px = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    made = page.evaluate("""px => {
      const tops = wardrobeItems.filter(i => /Shirts|Polos|Tees/.test(i.category)), bots = wardrobeItems.filter(i => /Trousers|Jeans/.test(i.category));
      const have = {}; window.gotoEntries841().forEach(g => { have[g.key] = 1; });
      const pairs = [];
      for (const t of tops) { for (const b of bots) { const k = [t.id, b.id].sort().join('|'); if (have[k] || onbodyForLook({ fwPieces: [t, b], composerKey: k })) continue; pairs.push([t.id, b.id]); have[k] = 1; break; } if (pairs.length >= 3) break; }
      if (pairs.length < 3) return { n: pairs.length };
      wornLog.push({ id: 'worn-cut', date: '2026-10-03', title: 'Has a cut-out', img: px, selfie: false, cut: 'assets/worn/selfie-1794868007730.webp', pieces: [], pieceIds: pairs[0] });
      wornLog.push({ id: 'worn-nocut', date: '2026-10-02', title: 'Cut-out missing', img: px, selfie: false, cut: 'assets/worn/not-there.webp', pieces: [], pieceIds: pairs[1] });
      wornLog.push({ id: 'worn-selfie', date: '2026-10-01', title: 'A camera selfie', img: px, selfie: true, pieces: [], pieceIds: pairs[2] });
      return { n: 3 };
    }""", px)
    assert made["n"] == 3, made
    page.evaluate("() => { document.querySelector('#panel-looks [data-lk-go=\"liked\"]').click(); document.querySelector('#panel-looks [data-lk-go=\"gotos\"]').click(); }")
    page.wait_for_function("""() => { const by = {}; document.querySelectorAll('.lk-goto843').forEach(c => { by[c.querySelector('.oc-title').textContent] = c; });
      const a = by['Has a cut-out'], b = by['Cut-out missing']; if (!a || !b) return false;
      const ia = a.querySelector('.ob-figure img[data-worn845]'), ib = b.querySelector('.ob-figure img[data-worn845]');
      return ia && ia.complete && ia.naturalWidth > 0 && ib && ib.complete && ib.naturalWidth > 0 && ib.getAttribute('src').indexOf('data:') === 0; }""", timeout=15000)
    wornc = page.evaluate("""() => { const by = {}; document.querySelectorAll('.lk-goto843').forEach(c => { by[c.querySelector('.oc-title').textContent] = c; });
      const f = t => { const c = by[t]; const i = c && c.querySelector('.ob-figure img[data-worn845]'); return { card: !!c, src: i ? i.getAttribute('src').slice(0, 44) : null, pieces: c ? c.querySelectorAll('.fl-cell').length : 0, fig: i ? Math.round(i.getBoundingClientRect().height) : 0 }; };
      return { cut: f('Has a cut-out'), back: f('Cut-out missing'), selfie: f('A camera selfie') }; }""")
    assert wornc["cut"]["src"] == "assets/worn/selfie-1794868007730.webp" and wornc["cut"]["pieces"] >= 2 and wornc["cut"]["fig"] > 150, wornc
    assert wornc["back"]["src"].startswith("data:image/png") and wornc["back"]["pieces"] >= 2, wornc
    assert wornc["selfie"]["card"] and wornc["selfie"]["src"] is None and wornc["selfie"]["pieces"] >= 2, wornc

    # Liked: a photo look (no pieces, no render) shows its colours and what each is, never a lone watch;
    # a liked rendered outfit shows the whole avatar inside its box
    page.evaluate("""() => {
      savedLooks.push({ id: 'look-photo-1', title: 'Racing Green & Stone', img: 'assets/photos/113a3f5b339f.webp', source: 'combo', verdict: 'like', likedAt: 2,
        swatches: [{ name: 'Diamine Green', hex: '#1d5c43', role: 'Crew-neck knit' }, { name: 'Ecru', hex: '#d8c9a8', role: 'Chinos' }, { name: 'Brown', hex: '#7c4226', role: 'Suede loafers' }] });
      const l = Object.assign({}, __cfLooks81()[0], { id: 'look-rendered-1', verdict: 'like', likedAt: 3 }); savedLooks.push(l);
    }""")
    page.evaluate("() => window.scrollTo(0, 0)")
    page.locator('#panel-looks [data-lk-go="liked"]').tap()
    page.wait_for_function("() => document.querySelectorAll('#lk-liked841 .lk-card841').length >= 2")
    liked = page.evaluate("""() => [...document.querySelectorAll('#lk-liked841 .lk-card841')].map(c => { const m = c.querySelector('.cf-media'), a = m.querySelector('.mine-avatar');
      const mr = m.getBoundingClientRect(), ar = a ? a.getBoundingClientRect() : null;
      return { title: c.querySelector('.oc-title').textContent, bands: [...m.querySelectorAll('.lk-sw843 .lk-swb843 b')].map(b => b.textContent), cells: m.querySelectorAll('.fl-cell').length,
        watchOnly: m.querySelectorAll('.fl-cell').length === 1 && !!m.querySelector('.fl-watch'), avatarFits: ar ? (ar.height <= mr.height + 1 && ar.width <= mr.width + 1) : null }; })""")
    photo = [c for c in liked if c["title"] == "Racing Green & Stone"][0]
    assert photo["bands"] == ["Crew-neck knit", "Chinos", "Suede loafers"] and photo["cells"] == 0, liked
    assert not any(c["watchOnly"] for c in liked), liked
    assert any(c["avatarFits"] is True for c in liked) and not any(c["avatarFits"] is False for c in liked), liked
    assert not errors, errors
    print("Confirmed go-to's: avatar with %d pieces beside it; a logged outfit shows its own picture of him (cut-out, or the saved picture), never a selfie; Liked shows colours for photo looks and a fitted avatar" % first["pieces"])
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        browser.close()
