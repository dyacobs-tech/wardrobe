#!/usr/bin/env python3
"""Safety (Nov 19) — updates never break the page or lose input.

  A. wardrobeSafeReload holds a reload while a dialog is open, a field has
     focus, or input happened in the last 15 s; it shows "Update ready."
     and applies once the UI is idle.
  B. Service worker install is atomic: when a new build's code file fails
     to download, the new worker never takes over (the old one keeps
     control) — when everything downloads, it takes over.
  C. The previous build's code files survive one release in CODE_CACHE.
No network beyond the local server; workers.dev is blocked.
"""
from __future__ import annotations
import http.server, os, re, shutil, socketserver, sys, tempfile, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
fails: list[str] = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + str(detail)[:400]))
    if not ok:
        fails.append(name)


SITE = Path(tempfile.mkdtemp(prefix="wardrobe-upd-"))


def make_site():
    # a private copy of the published files, so sw.js / index.html can be
    # rewritten on disk between phases (SW update fetches bypass routing)
    for name in os.listdir(ROOT):
        if name.startswith(".") or name in ("tests", "src", "scripts", "worker"):
            continue
        src = ROOT / name
        if name in ("index.html", "sw.js", "app"):
            (shutil.copytree if src.is_dir() else shutil.copy)(src, SITE / name)
        else:
            os.symlink(src, SITE / name)


def start_server():
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(SITE), **k)

        def log_message(self, *a):
            pass
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Q)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def wait_until(pg, expr, tries=60, step=500):
    for _ in range(tries):
        if pg.evaluate(expr):
            return True
        pg.wait_for_timeout(step)
    return False


def main():
    make_site()
    httpd, base = start_server()
    sw_src = (ROOT / "sw.js").read_text()
    build = re.search(r"const WARDROBE_BUILD = '([^']+)'", sw_src).group(1)
    index = (ROOT / "index.html").read_text()

    def set_mode(mode):
        nb = build + "-t" + mode
        extra = "zz-test.%s.js" % ("0123456789" if mode == "bad" else "abcdefabcd")
        sw = sw_src.replace(build, nb).replace("const CODE_FILES = [", "const CODE_FILES = ['./app/%s', " % extra, 1)
        (SITE / "sw.js").write_text(sw)
        (SITE / "index.html").write_text(index.replace(build, nb))
        if mode == "good":
            (SITE / "app" / extra).write_text("/* test */")

    def route(r):
        if ".workers.dev" in r.request.url:
            return r.abort()
        return r.continue_()

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, service_workers="allow")
        ctx.route("**/*", route)
        errors = []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base, wait_until="load")
        wait_until(pg, "() => typeof window.wardrobeSafeReload === 'function'")

        # ---------- A ----------
        a = pg.evaluate("""() => {
          window.__rl = 0;
          const layer = document.getElementById('look-layer');
          layer.hidden = false; layer.style.display = 'block';
          const applied = window.wardrobeSafeReload(() => { window.__rl++; });
          const bar = document.getElementById('update-bar');
          return { applied, rl: window.__rl, bar: bar && !bar.hidden, txt: bar ? bar.textContent : '', id: layer.id };
        }""")
        check("A: reload is held while a dialog is open", not a["applied"] and a["rl"] == 0, a)
        check("A: 'Update ready.' bar shows", a["bar"] and "Update ready" in a["txt"], a)
        pg.wait_for_timeout(3500)
        check("A: still held while the dialog stays open", pg.evaluate("() => window.__rl") == 0)
        pg.evaluate("""() => { const l = document.getElementById('look-layer'); l.hidden = true; l.style.display = ''; }""")
        ok = wait_until(pg, "() => window.__rl === 1", tries=20)
        check("A: applies by itself once the dialog closes", ok, pg.evaluate("() => window.__rl"))
        busy = pg.evaluate("""() => { const i = document.createElement('input'); i.type='text'; document.body.appendChild(i); i.focus(); const b1 = window.wardrobeUiBusy(); i.blur(); i.dispatchEvent(new Event('input', {bubbles:true})); const b2 = window.wardrobeUiBusy(); i.remove(); return [b1, b2]; }""")
        check("A: a focused field counts as busy", busy[0], busy)
        check("A: recent typing counts as busy", busy[1], busy)

        # ---------- B/C: service worker ----------
        ok = wait_until(pg, "() => !!(navigator.serviceWorker && navigator.serviceWorker.controller)", tries=40)
        if not ok:
            pg.reload(wait_until="load")
            ok = wait_until(pg, "() => !!(navigator.serviceWorker && navigator.serviceWorker.controller)", tries=40)
        check("B: service worker controls the page", ok)
        cache1 = pg.evaluate("""async () => { const c = await caches.open('wardrobe-code-v1'); const ks = (await c.keys()).map(r => r.url); const m = await c.match('https://wardrobe.invalid/__code-manifest__'); return { ks, man: m ? await m.json() : null }; }""")
        files = re.search(r"const CODE_FILES = \[(.*?)\];", sw_src, re.S).group(1)
        names = re.findall(r"'\./(app/[^']+)'", files)
        missing = [n for n in names if not any(k.endswith(n) for k in cache1["ks"])]
        check("B: every code file precached", not missing, missing)
        check("C: code manifest written", bool(cache1["man"]) and cache1["man"]["build"] == build, cache1["man"])

        # a broken update: one code file 404s
        set_mode("bad")
        r = pg.evaluate("""async () => { const reg = await navigator.serviceWorker.getRegistration(); try { await reg.update(); } catch (e) {}
          await new Promise(r => setTimeout(r, 4000));
          const reg2 = await navigator.serviceWorker.getRegistration();
          return { waiting: !!reg2.waiting, installing: !!reg2.installing, activeUrl: reg2.active && reg2.active.scriptURL }; }""")
        vb = pg.evaluate("""async () => { const c = await caches.open('wardrobe-code-v1'); const m = await c.match('https://wardrobe.invalid/__code-manifest__'); return m ? (await m.json()).build : null; }""")
        check("B: a failed precache never takes over (old build still active)", vb == build and not r["waiting"], {"r": r, "build": vb})

        # a good update: takes over; previous build's files are kept
        set_mode("good")
        pg.evaluate("""() => { window.__ctl = 0; navigator.serviceWorker.addEventListener('controllerchange', () => window.__ctl++); }""")
        pg.evaluate("""async () => { const reg = await navigator.serviceWorker.getRegistration(); try { await reg.update(); } catch (e) {} }""")
        wait_until(pg, "async () => { const reg = await navigator.serviceWorker.getRegistration(); return !!(reg && reg.active && reg.active.state === 'activated' && !reg.installing && !reg.waiting && (await (await caches.open('wardrobe-code-v1')).match('https://wardrobe.invalid/__code-manifest__').then(m => m && m.json())).build.indexOf('-tgood') > 0); }", tries=40)
        man = pg.evaluate("""async () => { const c = await caches.open('wardrobe-code-v1'); const m = await c.match('https://wardrobe.invalid/__code-manifest__'); const ks = (await c.keys()).map(r => r.url); return { man: m ? await m.json() : null, ks }; }""")
        nb = build + "-tgood"
        check("B: a complete update takes over", man["man"] and man["man"]["build"] == nb, man["man"])
        prev_kept = all(any(k.endswith(n) for k in man["ks"]) for n in names)
        check("C: previous build's code files kept for one release", prev_kept and man["man"]["prev"] and man["man"]["prev"]["build"] == build, man["man"] and man["man"].get("prev", {}) and man["man"]["prev"].get("build"))
        check("no page errors", not errors, errors)
        b.close()
    httpd.shutdown()
    shutil.rmtree(SITE, ignore_errors=True)
    print("FAILED %d" % len(fails) if fails else "ALL PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
