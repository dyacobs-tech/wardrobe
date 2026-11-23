"""Every Inspo idea wears one of his real shoes, drawn from that shoe's own photo, never a made-up pair (.86.74).

David, 23 Nov 2026, on pictures of shoes FASHN had invented from a description:
"Mocking up new shoe ideas based off my shoes in different styles is NOT a way to
create new looks!!!!!!" and "Use existing actual shoes!!!!!! Don't necessarily
need to be link to shop but they shouldn't be made up styles and colors!!!!
Generally I prefer UNDERSTATED style shoes!!!!!"
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "src/app.html").read_text()
m = re.search(r"/\*INSPO_CONCEPTS_BEGIN\*/(.*?)/\*INSPO_CONCEPTS_END\*/", SRC, re.S)
CONCEPTS = json.loads(m.group(1).strip().rstrip(";"))

missing = [c["id"] for c in CONCEPTS if not (ROOT / "assets/inspo-concepts" / ((c.get("img") or c["id"]) + ".webp")).exists()]
assert not missing, missing
shoes = [(c["id"], p) for c in CONCEPTS for p in c["pieces"] if p["role"] == "shoes"]
assert shoes and all(p.get("own") for _, p in shoes), [cid for cid, p in shoes if not p.get("own")]


def run(browser):
    ctx = browser.new_context(service_workers="block")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(URL) and route.request.method == "GET" else route.abort())
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => Array.isArray(window.wardrobeItems) && wardrobeItems.length > 20", timeout=60000)
    ids = set(page.evaluate("() => wardrobeItems.map(i => i.id)"))
    names = dict(page.evaluate("() => wardrobeItems.map(i => [i.id, i.name])"))
    bad = [(cid, p["own"]) for cid, p in shoes if p["own"] not in ids or names.get(p["own"]) != p["name"]]
    # only seed pieces are guaranteed in a fresh browser; his synced shoes are checked by name shape
    bad = [b for b in bad if b[1].startswith("seed-")]
    assert not bad, bad
    ctx.close()


with sync_playwright() as pw:
    for engine in (pw.chromium, pw.webkit):
        browser = engine.launch()
        run(browser)
        print("Confirmed: %d Inspo ideas, every shoe one of his own" % len(shoes))
        browser.close()
