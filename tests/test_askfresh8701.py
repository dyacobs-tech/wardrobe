"""Ask DONNA opens on a clean chat every time; earlier chats are behind a button and never deleted (.87.01).

David, 24 Nov 2026, with a screenshot of Ask DONNA reopening on an old "Hi" chat: "Ask Donna just opening to an old
chat box this needs to be refreshed and clean for every query right?". Asked how, he chose "Clean on open + an Earlier
button": opening Ask DONNA shows an empty chat with the suggestions; follow-up questions in the same visit stay
together and keep their context; a small "Earlier chats" button shows past questions. Old chats are synced records,
so they are only hidden: none is deleted. Chromium and WebKit, real taps.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
cat = json.loads((Path(__file__).resolve().parents[1] / "assets/edit-catalog.json").read_text())["products"]
prods = [c for c in cat if c["cat"] in ("trousers", "shoes")][:3]
OLD = [{"id": "old1", "q": "OLD QUESTION ONE", "at": "2026-11-20T10:00:00.000Z", "state": "done", "answer": "OLD ANSWER ONE", "picks": []},
       {"id": "old2", "q": "OLD QUESTION TWO", "at": "2026-11-21T10:00:00.000Z", "state": "done", "answer": "OLD ANSWER TWO", "picks": []}]
SEEN = """() => ({ text: document.getElementById('ask-thread').innerText, sugs: document.querySelectorAll('#ask-sugs [data-ask-sug]').length,
  earlier: (document.querySelector('[data-ask-earlier903]') || {}).textContent || null,
  turns: askState().thread.length, synced: (askSync || []).filter(r => r.kind === 'turn').length,
  tombs: Object.keys((SY.tomb && SY.tomb.ask) || {}).length })"""


def run(engine):
    bodies = []
    browser = engine.launch()
    ctx = browser.new_context(viewport={"width": 402, "height": 874}, is_mobile=True, has_touch=True, service_workers="block")

    def route(r):
        u = r.request.url
        if u.startswith(URL):
            return r.continue_()
        if u.endswith("/ask") and r.request.method == "POST":
            body = json.loads(r.request.post_data or "{}")
            bodies.append(body)
            ans = {"answer": "ANSWER TO " + body.get("query", "")[:30], "meta": {"model": "test", "fallback": False},
                   "picks": [{"sku": p["sku"], "why": "Goes with yours.", "pairsWith": [],
                              "product": {k: p.get(k) for k in ("sku", "brand", "name", "price", "priceDisplay", "url", "img", "cat", "colour", "hex", "retailer")}} for p in prods]}
            return r.fulfill(status=200, content_type="application/json", body=json.dumps(ans))
        return r.abort()
    ctx.route("**/*", route)
    ctx.add_init_script("if (!sessionStorage.getItem('af8701')) { sessionStorage.setItem('af8701', '1'); localStorage.setItem('wardrobe.items', %s); localStorage.setItem('wardrobe.ask.thread', %s); }"
                        % (json.dumps(json.dumps(photographed_closet())), json.dumps(json.dumps(OLD))))
    page = ctx.new_page()

    def open_ask():
        page.locator("#tab-find").first.tap()
        page.wait_for_timeout(700)
        page.evaluate("() => { SY.key = 'a'.repeat(48); }")
        page.locator("#edit-tab-askdonna").tap()
        page.wait_for_timeout(600)
        return page.evaluate(SEEN)

    def send(q):
        n = len(bodies)
        page.locator("#ask-q").fill(q)
        page.locator("#ask-send").tap()
        page.wait_for_function("q => document.getElementById('ask-thread').innerText.includes('ANSWER TO ' + q.slice(0, 20))", arg=q, timeout=15000)
        assert len(bodies) == n + 1, (engine.name, "the question was not sent once", len(bodies) - n)
        return bodies[-1]

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => typeof window.editShow === 'function' && typeof window.askState === 'function'")
    page.wait_for_timeout(1200)
    s = open_ask()
    assert "OLD" not in s["text"] and s["sugs"] > 0, (engine.name, "Ask DONNA did not open clean", s)
    assert s["earlier"] and "2" in s["earlier"], (engine.name, "no Earlier chats button", s)
    b1 = send("Trousers for my navy polo")
    assert not b1.get("history"), (engine.name, "an old chat was sent as context to a new chat", b1.get("history"))
    b2 = send("Something cheaper please")
    hist = json.dumps(b2.get("history"))
    assert "Trousers for my navy polo" in hist and "OLD" not in hist, (engine.name, "a follow-up lost this chat's context or carried an old one", hist)
    page.locator("[data-ask-earlier903]").tap()
    page.wait_for_timeout(300)
    s = page.evaluate(SEEN)
    assert "OLD ANSWER ONE" in s["text"] and "OLD ANSWER TWO" in s["text"] and "Something cheaper" in s["text"], (engine.name, "Earlier chats did not show", s["text"][:300])
    page.locator("[data-ask-earlier903]").tap()
    page.wait_for_timeout(300)
    assert "OLD" not in page.evaluate(SEEN)["text"], (engine.name, "Earlier chats did not hide again")
    # leave Ask DONNA and come back: a clean chat again, and this visit's chat is now an earlier one
    page.locator("#edit-tab-shop").tap()
    page.wait_for_timeout(400)
    page.locator("#edit-tab-askdonna").tap()
    page.wait_for_timeout(500)
    s = page.evaluate(SEEN)
    assert "Something cheaper" not in s["text"] and "OLD" not in s["text"] and s["sugs"] > 0, (engine.name, "reopened on the old chat", s)
    assert s["earlier"] and "4" in s["earlier"], (engine.name, "Earlier chats should count 4", s)
    # nothing was deleted: all four chats are still kept and synced, with no delete marks
    page.wait_for_timeout(500)
    s = page.evaluate(SEEN)
    assert s["turns"] == 4 and s["synced"] == 4 and s["tombs"] == 0, (engine.name, "a chat was deleted", s)
    # a fresh app start opens clean too
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("() => typeof window.editShow === 'function' && typeof window.askState === 'function'")
    page.wait_for_timeout(1200)
    s = open_ask()
    assert "Something cheaper" not in s["text"] and "OLD" not in s["text"], (engine.name, "after a restart Ask DONNA opened on an old chat", s)
    browser.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        run(engine)
print("Confirmed Ask DONNA opens clean, follow-ups keep this chat's context only, Earlier chats shows the rest, and nothing is deleted")
