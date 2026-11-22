"""Liked has a Palettes sub page of its own (.86.53).

David, 22 Nov 2026:
  "We should create a section for "liked" palettes - in its own place, in
   liked, let's have palettes as its own sub page"
  "Palletes should have its own sub page in liked"

Liked > Looks holds liked outfits that have a picture. Liked > Palettes holds
the palettes he has liked: ones liked from the book, and liked looks that are
colours only. He can like more there, six at a time. Unliking never deletes.
"""
import json
import sys

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"


def run(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    ctx.add_init_script("localStorage.setItem('wardrobe.items'," + json.dumps(json.dumps(photographed_closet())) + ");localStorage.setItem('wardrobe.formality','2')")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="domcontentloaded")
    page.locator("#section-ideas").tap()
    page.wait_for_function("() => window.__cfLooks81 && __cfLooks81().length >= 2")
    page.evaluate("""() => {
      savedLooks.push({ id: 'old-colours', title: 'Racing Green & Stone', img: 'assets/photos/113a3f5b339f.webp', verdict: 'like', likedAt: 3,
        swatches: [{ name: 'Magenta', hex: '#ff00c8', role: 'Crew-neck knit' }, { name: 'Lime', hex: '#39ff14', role: 'Chinos' }] });
      savedLooks.push(Object.assign({}, __cfLooks81()[0], { id: 'liked-rendered', verdict: 'like', likedAt: 4 }));
    }""")
    page.locator('#panel-looks [data-lk-go="liked"]').tap()
    page.wait_for_function("() => document.querySelectorAll('#lk-liked841 [data-lk-sub853]').length === 2")
    looks = page.evaluate("""() => ({ pressed: document.querySelector('[data-lk-sub853][aria-pressed="true"]').textContent,
      titles: [...document.querySelectorAll('#lk-liked841 .lk-card841 .oc-title')].map(t => t.textContent), bands: document.querySelectorAll('#lk-liked841 .lk-sw853').length })""")
    assert looks["pressed"] == "Looks" and looks["bands"] == 0 and "Racing Green & Stone" not in looks["titles"] and len(looks["titles"]) >= 1, looks

    page.locator('[data-lk-sub853="palettes"]').tap()
    page.wait_for_function("() => document.querySelectorAll('#lk-liked841 .lk-pal853').length >= 2")
    pal = page.evaluate("""() => { const host = document.getElementById('lk-liked841'); const hs = [...host.querySelectorAll('.lk-h841')].map(h => h.textContent);
      const mine = [...host.querySelectorAll('[data-p853-unlike]')].map(b => b.closest('.lk-pal853')), more = [...host.querySelectorAll('[data-p853-like]')].map(b => b.closest('.lk-pal853'));
      return { hs, mine: mine.map(c => ({ t: c.querySelector('.oc-title').textContent, roles: [...c.querySelectorAll('.lk-swb853 b')].map(b => b.textContent), bands: c.querySelectorAll('.lk-swb853').length })),
        more: more.map(c => c.querySelectorAll('.lk-swb853').length), moreBtn: !!host.querySelector('[data-p853-more]'), avatars: host.querySelectorAll('img').length }; }""")
    assert pal["hs"] == ["Your palettes", "Find more palettes"], pal
    assert pal["mine"] == [{"t": "Racing Green & Stone", "roles": ["Crew-neck knit", "Chinos"], "bands": 2}], pal
    assert len(pal["more"]) == 6 and all(2 <= n <= 4 for n in pal["more"]) and pal["moreBtn"] and pal["avatars"] == 0, pal

    # Six more deals six different palettes
    first = page.evaluate("() => [...document.querySelectorAll('[data-p853-like]')].map(b => b.getAttribute('data-p853-like'))")
    page.evaluate("() => document.querySelector('[data-p853-more]').click()")  # a tap can land on the nav bar that floats over the page bottom
    second = page.evaluate("() => [...document.querySelectorAll('[data-p853-like]')].map(b => b.getAttribute('data-p853-like'))")
    assert len(second) == 6 and not set(first) & set(second), (first, second)

    # liking one keeps it: it moves to Your palettes, is saved, and is offered to the engine as approved
    plate = second[0]
    page.evaluate("p => document.querySelector('[data-p853-like=\"' + p + '\"]').click()", plate)
    after = page.evaluate("""plate => ({ mine: [...document.querySelectorAll('#lk-liked841 [data-p853-unlike]')].length, offered: !!document.querySelector('[data-p853-like="' + plate + '"]'),
      stored: JSON.parse(localStorage.getItem('wardrobe.palettes') || '[]').filter(p => p.plate === +plate && p.liked === true).length,
      approved: approvedPalettes853().filter(p => p.plate === +plate).length, count: document.querySelector('[data-lk-sub853="palettes"]').textContent })""", plate)
    assert after == {"mine": 2, "offered": False, "stored": 1, "approved": 1, "count": "Palettes · 2"}, after

    # unliking never deletes: the palette record stays (liked: false); the look stays, without its like
    for _ in range(2):
        page.evaluate("() => document.querySelector('#lk-liked841 [data-p853-unlike]').click()")
        page.wait_for_timeout(150)
    end = page.evaluate("""plate => ({ mine: document.querySelectorAll('#lk-liked841 [data-p853-unlike]').length, rec: customPalettes.filter(p => p.plate === +plate).map(p => p.liked),
      look: savedLooks.filter(l => l.id === 'old-colours').map(l => l.verdict || null), approved: approvedPalettes853().length })""", plate)
    assert end["mine"] == 0 and end["rec"] == [False] and len(end["look"]) == 1 and end["look"][0] != "like" and end["approved"] == 0, end
    assert not errors, errors
    print("Confirmed: Liked has Looks and Palettes; a colours-only liked look is a palette; six more palettes at a time; a like is saved and approved; unliking deletes nothing")
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        browser.close()
