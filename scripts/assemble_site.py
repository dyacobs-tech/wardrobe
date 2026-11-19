#!/usr/bin/env python3
"""Assemble the GitHub Pages output (Nov 19).

    python3 scripts/assemble_site.py LIVE_DIR [PREVIEW_DIR] OUT_DIR

Only the files the app serves are published. tests/ (fixtures included),
src/, scripts/, worker/, workers/, .github and docs never reach the site.
When PREVIEW_DIR is given, its build is published at OUT_DIR/preview/ —
without duplicating the photo library: preview/'s assets/ requests are
mapped onto the live assets/ by the preview service worker, and any asset
that exists only in the preview tree is added to the live assets/ (names
are content-hashed, so this is additive). A small banner marks the
preview, and the first visit reloads once so the worker serves assets.
"""
import os, shutil, sys
from pathlib import Path

PUBLISH = ["index.html", "sw.js", "manifest.webmanifest", ".nojekyll", "app", "assets"]
FORBIDDEN = ["tests", "src", "scripts", "worker", "workers", ".github"]


def copy_tree(src: Path, dst: Path, names):
    dst.mkdir(parents=True, exist_ok=True)
    for n in names:
        s = src / n
        if not s.exists():
            continue
        if s.is_dir():
            shutil.copytree(s, dst / n, dirs_exist_ok=True)
        else:
            shutil.copy2(s, dst / n)


PREVIEW_SNIPPET = """<script>/* preview build: first visit reloads once under its own worker so assets resolve */
(function(){try{var c=navigator.serviceWorker&&navigator.serviceWorker.controller,me=new URL('sw.js',location.href).href;if(!('serviceWorker' in navigator)||(c&&c.scriptURL.split('?')[0]===me))return;navigator.serviceWorker.register('sw.js',{updateViaCache:'none'}).then(function(){return navigator.serviceWorker.ready}).then(function(){if(sessionStorage.getItem('wardrobe.pvReload'))return;sessionStorage.setItem('wardrobe.pvReload','1');setTimeout(function(){location.reload()},300)})}catch(e){}})();</script>
<div style="position:fixed;top:env(safe-area-inset-top,0);left:50%;transform:translateX(-50%);z-index:2147483647;background:#5b4630;color:#fff;font:600 12px/1.6 system-ui;padding:2px 10px;border-radius:0 0 8px 8px;pointer-events:none">PREVIEW</div>"""


def main():
    args = sys.argv[1:]
    if len(args) not in (2, 3):
        sys.exit(__doc__)
    live, out = Path(args[0]), Path(args[-1])
    preview = Path(args[1]) if len(args) == 3 else None
    if out.exists():
        shutil.rmtree(out)
    copy_tree(live, out, PUBLISH)
    if preview and (preview / "index.html").exists():
        pv = out / "preview"
        copy_tree(preview, pv, ["index.html", "sw.js", "manifest.webmanifest", "app"])
        # preview-only assets join the shared assets/ tree (additive)
        added = 0
        for root, _, files in os.walk(preview / "assets"):
            for f in files:
                s = Path(root) / f
                rel = s.relative_to(preview)
                d = out / rel
                if not d.exists():
                    d.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(s, d)
                    added += 1
        html = (pv / "index.html").read_text()
        i = html.find(">", html.find("<body")) + 1
        html = html[:i] + PREVIEW_SNIPPET + html[i:]
        html = html.replace("<title>", "<title>PREVIEW · ", 1)
        (pv / "index.html").write_text(html)
        print(f"preview published at preview/ ({added} preview-only assets added)")
    bad = [f for f in FORBIDDEN if (out / f).exists() or (out / "preview" / f).exists()]
    if bad:
        sys.exit("refusing to publish: " + ", ".join(bad))
    for root, _, files in os.walk(out):
        for f in files:
            if f.startswith("fixture") or f.endswith((".py", ".ts")):
                sys.exit("refusing to publish test/source file: " + os.path.join(root, f))
    print("site assembled:", out)


if __name__ == "__main__":
    main()
