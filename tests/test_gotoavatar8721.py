"""Every go-to is shown on his avatar, and a tap opens it full screen (.87.21).

David (26 Nov 2026): "MY GO-tos should be shown on my avatar!!!!"

Four go-to's he logged from a mirror photo showed their pieces only, and nine
showed his old avatar from the picture saved with the log entry. Each go-to is
now drawn on his new avatar from the closet photo of every piece, and stored in
the high-res picture list under the go-to's own key (its piece ids). A go-to
with such a picture shows it beside its pieces, ahead of the picture saved with
the log entry and even when the entry was logged from a mirror photo.

Tapping a go-to used to throw an error and open nothing (the full-screen view
lists the outfit's colours and a go-to carried none). It opens now.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent


def goto_pictures():
    """The go-to pictures in the high-res list: each one is a real file, under a key no other entry uses."""
    j = json.loads((ROOT / "assets" / "onbody-hires" / "manifest.json").read_text())
    gotos = [e for e in j["r"] if e.get("goto")]
    assert len(gotos) >= 12, "expected the 12 go-to pictures drawn on 26 Nov 2026, found %d" % len(gotos)
    keys = [e["k"] for e in j["r"]]
    assert len(keys) == len(set(keys)), "two pictures share one key in the high-res list"
    assert j.get("count") == len(j["r"]), "the list's count does not match its entries"
    for e in gotos:
        assert len(e["k"].split("|")) >= 2, e["k"]
        for kind in ("card", "full"):
            assert (ROOT / e[kind]).is_file(), "missing " + e[kind]
    return gotos


def run(browser, gotos):
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
    page.wait_for_function("() => typeof HIRES !== 'undefined' && HIRES.ready", timeout=20000)

    # two outfits with no library picture: one logged from a mirror photo, one with the old avatar picture saved
    px = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    made = page.evaluate("""px => {
      const tops = wardrobeItems.filter(i => /Shirts|Polos|Tees/.test(i.category)), bots = wardrobeItems.filter(i => /Trousers|Jeans/.test(i.category));
      const have = {}, pairs = [];
      for (const t of tops) { for (const b of bots) { const k = [t.id, b.id].sort().join('|'); if (have[k] || HIRES.map[k] || onbodyForLook({ fwPieces: [t, b], composerKey: k })) continue; pairs.push({ ids: [t.id, b.id], k }); have[k] = 1; break; } if (pairs.length >= 2) break; }
      if (pairs.length < 2) return { n: pairs.length };
      wornLog.push({ id: 'worn-mirror', date: '2026-10-03', title: 'From a mirror photo', img: px, selfie: true, pieces: [], pieceIds: pairs[0].ids });
      wornLog.push({ id: 'worn-old', date: '2026-10-02', title: 'Old avatar saved', img: px, selfie: false, pieces: [], pieceIds: pairs[1].ids });
      return { n: 2, keys: pairs.map(p => p.k) };
    }""", px)
    assert made["n"] == 2, made
    page.locator('#panel-looks [data-lk-go="gotos"]').tap()
    page.wait_for_function("() => document.querySelectorAll('.lk-goto843').length >= 2")
    read = """() => { const by = {}; document.querySelectorAll('.lk-goto843').forEach(c => { by[c.querySelector('.oc-title').textContent] = c; });
      const f = t => { const c = by[t]; const i = c && c.querySelector('.ob-figure:not([hidden]) img');
        return { card: !!c, src: i ? i.getAttribute('src') : null, worn: i ? i.hasAttribute('data-worn845') : false, loaded: i ? (i.complete && i.naturalWidth > 0) : false,
          pieces: c ? c.querySelectorAll('.ob-pieces .fl-cell img').length : 0, flat: c ? c.querySelectorAll('.flatlay:not(.onbody-split) .fl-cell').length : 0,
          fig: i ? Math.round(i.getBoundingClientRect().height) : 0 }; };
      return { mirror: f('From a mirror photo'), old: f('Old avatar saved') }; }"""
    before = page.evaluate(read)
    # before they are drawn: the mirror photo is never shown (pieces only), the saved old picture is
    assert before["mirror"]["card"] and before["mirror"]["src"] is None and before["mirror"]["flat"] >= 2, before
    assert before["old"]["worn"] and before["old"]["src"].startswith("data:image/png"), before

    # they are drawn on his avatar: the high-res list holds a picture under each go-to's key
    page.evaluate("""a => { hiresIngest({ r: [
        { k: a.keys[0], card: a.g[0].card, full: a.g[0].full }, { k: a.keys[1], card: a.g[1].card, full: a.g[1].full }] });
      document.querySelector('#panel-looks [data-lk-go="liked"]').click(); document.querySelector('#panel-looks [data-lk-go="gotos"]').click(); }""",
                  {"keys": made["keys"], "g": [{"card": g["card"], "full": g["full"]} for g in gotos[:2]]})
    page.wait_for_function("""() => { const i = [...document.querySelectorAll('.lk-goto843 .ob-figure img')].filter(x => /onbody-hires\\//.test(x.getAttribute('src') || ''));
      return i.length >= 2 && i.every(x => x.complete && x.naturalWidth > 0); }""", timeout=20000)
    after = page.evaluate(read)
    for name, card in (("mirror", gotos[0]["card"]), ("old", gotos[1]["card"])):
        c = after[name]
        assert c["src"] == card and c["loaded"] and not c["worn"], (name, after)
        assert c["pieces"] >= 2 and c["fig"] > 150, (name, after)

    # a tap opens the go-to full screen on his avatar, with no error
    page.evaluate("() => window.scrollTo(0, 0)")
    page.evaluate("""() => { const c = [...document.querySelectorAll('.lk-goto843')].filter(c => c.querySelector('.oc-title').textContent === 'From a mirror photo')[0];
      c.querySelector('[data-g841-open]').click(); }""")
    page.wait_for_function("""() => { const L = document.querySelector('#look-layer'); if (!L) return false;
      const i = [...L.querySelectorAll('img')].filter(x => /onbody-hires\\//.test(x.getAttribute('src') || '') && x.getBoundingClientRect().height > 250);
      return i.length >= 1 && i[0].complete && i[0].naturalWidth > 0; }""", timeout=15000)
    assert not errors, errors
    print("Confirmed go-to's on his avatar: %d go-to pictures in the high-res list; a go-to logged from a mirror photo and one with the old avatar saved both show the new picture with %d and %d pieces beside it; a tap opens it full screen"
          % (len(gotos), after["mirror"]["pieces"], after["old"]["pieces"]))
    ctx.close()


gotos = goto_pictures()
with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser, gotos)
        browser.close()
