#!/usr/bin/env python3
"""Pick the CSS rules Home needs for its first paint -> src/critical-selectors.json.

    python3 scripts/critical_css.py      (needs playwright + tinycss2; serves the repo)

Opens Home in Chromium (phone 375/390/430 and desktop 1280/1440/1920, light
and dark, installed-app and browser, with his closet and with no data), waits
for the hero (and once more with the app scripts blocked: the shell's own paint), then marks every rule whose selector (minus :hover/::before-style
state and pseudo-element parts) matches an element that is rendered, or whose
parent is (so the rules that hide things are kept too).
build_shell.py inlines just those rules (in their original order, inside their
@media/@supports) and loads the full stylesheet right after the first paint.
Re-run it after a Home redesign; rules added since only apply once the full
sheet lands (a few ms from cache).
"""
import functools, http.server, json, os, re, socketserver, sys, threading
import tinycss2
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import audit78 as A
from playwright.sync_api import sync_playwright
OUT = os.path.join(ROOT, "src", "critical-selectors.json")
STRIP = r"::?(?:hover|focus-visible|focus-within|focus|active|visited|target|before|after|placeholder|selection|first-line|first-letter|marker|backdrop|-webkit-[\w-]+|-moz-[\w-]+)(?:\([^)]*\))?"

def css_of(src):
    head = src[:src.index("</head>")]
    return "\n".join(m.group(1) for m in re.finditer(r"[ \t]*<style>(.*?)</style>\n?", head, re.S))

def preludes(rules, out):
    for r in rules:
        if r.type == "qualified-rule":
            out.append(tinycss2.serialize(r.prelude).strip())
        elif r.type == "at-rule" and r.lower_at_keyword in ("media", "supports", "layer", "container") and r.content is not None:
            preludes(tinycss2.parse_rule_list(r.content, skip_whitespace=True, skip_comments=True), out)
    return out

JS = """([sels, strip]) => { const re = new RegExp(strip, 'g'); const shown = (el) => el === document.documentElement || el === document.body || el.getClientRects().length > 0; const vis = (el) => shown(el) || (el.parentElement && shown(el.parentElement));
  return sels.map((s) => { let q = s.replace(re, '').replace(/(^|,|\\(|\\s)(?=\\s*(,|\\)|$))/g, '$1*');
    try { for (const el of document.querySelectorAll(q)) if (vis(el)) return 1; return 0; } catch (e) { return 2; } }); }"""

def main():
    src = open(os.path.join(ROOT, "src", "app.html"), encoding="utf-8").read()
    sels = sorted(set(preludes(tinycss2.parse_stylesheet(css_of(src), skip_whitespace=True, skip_comments=True), [])))
    H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H); srv.daemon_threads = True
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/" % srv.server_address[1]
    used, unsure = set(), set()
    with sync_playwright() as p:
        b = p.chromium.launch()
        for (w, h, mobile) in [(390, 844, True), (375, 667, True), (430, 932, True), (1280, 800, False), (1920, 1080, False)]:
            for theme in ("light", "dark"):
                for seeded in (True, False):
                    for standalone, shell_only in [(st, so) for st in ((True, False) if mobile else (False,)) for so in (False, True)]:
                        ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, device_scale_factor=3 if mobile else 1, service_workers="block")
                        if standalone: ctx.add_init_script(A.STANDALONE_INIT)
                        if seeded: ctx.add_init_script(A.seed_script())
                        ctx.add_init_script("try{localStorage.setItem('wardrobe-theme', %s)}catch(e){}" % json.dumps(theme))
                        ctx.route(A.BLOCK, lambda r: r.abort())
                        # the shell's own first paint, before any app script has run
                        if shell_only: ctx.route("**/app/*.js", lambda r: r.abort())
                        pg = ctx.new_page(); pg.goto(url)
                        if shell_only: pg.wait_for_timeout(1200)
                        else:
                            try: pg.wait_for_function("() => { const i = document.getElementById('today-img'); return i && i.complete && i.naturalWidth > 0; }", timeout=20000)
                            except Exception: pass
                            pg.wait_for_timeout(2500)
                        for s, v in zip(sels, pg.evaluate(JS, [sels, STRIP])):
                            if v == 1: used.add(s)
                            elif v == 2: unsure.add(s)
                        ctx.close()
        b.close()
    srv.shutdown()
    keep = sorted(used | {s for s in unsure if re.search(r":root|^html|^body", s)})
    json.dump({"note": "generated by scripts/critical_css.py", "selectors": keep}, open(OUT, "w"), indent=0)
    print("%d of %d selectors are used on Home's first paint (%d could not be tested: %s)" % (len(keep), len(sels), len(unsure), sorted(unsure)[:8]))

if __name__ == "__main__":
    main()
