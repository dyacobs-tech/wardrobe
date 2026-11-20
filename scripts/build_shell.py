#!/usr/bin/env python3
"""Build the small app shell (index.html) from the editable source (src/app.html).

    python3 scripts/build_shell.py

EDIT src/app.html, never index.html or app/* — they are generated.

src/app.html is the whole app in one file, exactly as before. This script:
  · (EXTERNAL_CSS) can move the <style> blocks into app/app.<hash>.css —
    off for now, the CSS stays inline (see EXTERNAL_CSS);
  · moves every <script type="wardrobe/app"> block into app/NN.<hash>.js; the
    vault loader runs them in their original order (async=false) — they are
    <link rel=preload>ed from <head> so they download while the page parses;
  · moves the big parse-time inline scripts (colour data, IA cuts, try-on)
    into deferred app/*.js files (same order, still before the app scripts);
  · writes the list of code files into sw.js (CODE_FILES) for precaching;
  · deletes app/ files from older builds.
File names carry a content hash, so they are immutable.
"""
import hashlib, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, os.path.join(ROOT, "scripts", "vendor"))
import jslit                      # JS data literal -> JSON
import rjsmin, rcssmin            # vendored (Apache-2.0): comment/whitespace stripping only, no renaming
SRC = os.path.join(ROOT, "src", "app.html")
OUT = os.path.join(ROOT, "index.html")
APP = os.path.join(ROOT, "app")
SW = os.path.join(ROOT, "sw.js")
# parse-time inline scripts moved out as deferred files (matched by their first line)
DEFER_HEADS = ("window.WADA=", "/* Build .75 — IA cuts", "/* ================= See it on me")
LAZY_MARKUP = ("brand-list",)
# Big top-level `var NAME = <data literal>;` declarations moved to their own
# app/<name>.<hash>.json. NAME becomes a getter on window: the first read
# fetches the file synchronously (from the SW code cache once installed) and
# parses it; after the first paint the files are fetched on idle, so in
# practice nothing waits. Only names nothing reads while booting into Home
# belong here; window.__lazyTrace802 lists every synchronous read (name, ms, stack).
# (in the order they are fetched on idle)
LAZY_DATA = ("STYLE_ICONS", "EXTRA_RENDERS", "SALE_ITEMS", "ICON_DIRECTORY", "SHOP_CATALOGUE", "ICON_SPECS")
LAZY_LOADER = r"""<script>
(function () {
  var L = window.__lazy802 = {}, order = [];
  function sync(e) {
    /* a failed read (offline before the cache has it) is not retried on every access */
    if (e.failedAt && Date.now() - e.failedAt < 3000) return;
    Error.stackTraceLimit = 20;
    try {
      var x = new XMLHttpRequest(); x.open("GET", e.src, false); x.send(null);
      if (x.status === 200 || (x.status === 0 && x.responseText)) { e.val = JSON.parse(x.responseText); e.done = true; fire(e); }
    } catch (err) {}
    if (!e.done) e.failedAt = Date.now();
    (window.__lazyTrace802 = window.__lazyTrace802 || []).push([e.name, Math.round(performance.now()), String(new Error().stack || "").split("\n").slice(3, 14).join(" | ")]);
  }
  function fire(e) {
    var cb = e.cbs.splice(0);
    if (cb.length) setTimeout(function () { cb.forEach(function (f) { try { f(); } catch (err) { setTimeout(function () { throw err; }); } }); }, 0);
    if (order.every(function (x) { return x.done; })) { var a = all.splice(0); if (a.length) setTimeout(function () { a.forEach(function (f) { try { f(); } catch (err) {} }); }, 0); }
  }
  var all = [];
  /* lazyOn802(name, f): f runs once NAME's data is in (at once if it is) */
  window.lazyOn802 = function (name, f) { var e = L[name]; if (!e || e.done) f(); else e.cbs.push(f); };
  window.lazyAll802 = function (f) { if (order.every(function (x) { return x.done; })) f(); else all.push(f); };
  window.lazyHas802 = function (name) { var e = L[name]; return !e || e.done; };
  window.__lazyData802 = function (name, src, empty, rank) {
    var e = L[name] = { name: name, src: src, done: false, val: undefined, empty: empty, cbs: [], rank: rank };
    order.push(e); order.sort(function (a, b) { return a.rank - b.rank; });
    Object.defineProperty(window, name, { configurable: true, enumerable: true,
      get: function () { if (!e.done) sync(e); return e.done ? e.val : (e.empty === "[" ? [] : {}); },
      set: function (v) { e.val = v; if (!e.done) { e.done = true; fire(e); } } });
  };
  function warm() {
    if (window.__noWarm802) return;
    var e = null;
    for (var i = 0; i < order.length; i++) if (!order[i].done && !order[i].busy) { e = order[i]; break; }
    if (!e) return;
    e.busy = true;
    fetch(e.src).then(function (r) { return r.ok ? r.text() : null; }).then(function (t) {
      idle(function () { if (t && !e.done) { try { e.val = JSON.parse(t); e.done = true; fire(e); } catch (err) {} } e.busy = false; idle(warm); });
    }, function () { e.busy = false; });
  }
  function idle(f) { (window.requestIdleCallback || function (g) { return setTimeout(g, 50); })(f, { timeout: 4000 }); }
  /* A reopen (the service worker has them in its cache): read them all at
     once, in the background, while the app boots — nothing then reads them
     synchronously (a synchronous read can't use the worker's cache when
     offline). A first open: after Home's hero and look-ahead
     (src/app.html: afterLookahead803), one at a time, so they never take
     the link from the hero. */
  function now(e) {
    e.busy = true;
    fetch(e.src).then(function (r) { return r.ok ? r.json() : null; }).then(function (v) {
      e.busy = false;
      if (v != null && !e.done) { e.val = v; e.done = true; fire(e); }
    }, function () { e.busy = false; });
  }
  @@LAZY_CALLS@@
  var ctl = false;
  try { ctl = !!(navigator.serviceWorker && navigator.serviceWorker.controller); } catch (err) {}
  if (ctl) setTimeout(function () { order.forEach(function (e) { if (!e.done && !e.busy) now(e); }); }, 0);
  /* (a first open installs the service worker at that point too, which
     downloads these files into its cache: wait for it to take control, so
     each file comes down once) */
  function afterSw(f) {
    var done = false, go = function () { if (!done) { done = true; f(); } };
    try {
      if (!navigator.serviceWorker || navigator.serviceWorker.controller) return go();
      navigator.serviceWorker.addEventListener("controllerchange", function () { setTimeout(go, 500); });
    } catch (err) { return go(); }
    setTimeout(go, 2500);
  }
  window.addEventListener("load", function () { (window.afterLookahead803 || function (f) { setTimeout(f, 3500); })(function () { afterSw(function () { idle(warm); }); }); });
})();
</script>
"""
# The CSS stays inline for now: as a separate render-blocking file it cost a
# round trip before the first paint on a cold open (measured 1.2s -> 2.5s on
# Fast 3G). Set True once a critical-CSS subset is inlined instead.
EXTERNAL_CSS = False
# app scripts from this number on travel in one file (app/bundle.<hash>.js, which
# only stores their texts); the vault loader runs each as its own <script>, in order
BUNDLE_FROM = 3
BANNER = "<!-- GENERATED by scripts/build_shell.py from src/app.html — edit src/app.html, then run python3 scripts/build_shell.py -->\n"

def h(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]

def critical_subset(css, keep):
    """The rules of css whose selector is in keep, in order, inside their
    @media/@supports; @font-face/@keyframes/@property always."""
    import tinycss2
    def walk(rules):
        out = []
        for r in rules:
            if r.type == "qualified-rule":
                if tinycss2.serialize(r.prelude).strip() in keep: out.append(tinycss2.serialize([r]).strip())
            elif r.type == "at-rule":
                kw = r.lower_at_keyword
                if kw in ("media", "supports", "layer", "container") and r.content is not None:
                    inner = walk(tinycss2.parse_rule_list(r.content, skip_whitespace=True, skip_comments=True))
                    if inner: out.append("@%s%s{%s}" % (r.at_keyword, tinycss2.serialize(r.prelude), "\n".join(inner)))
                elif kw in ("font-face", "keyframes", "-webkit-keyframes", "property", "import", "charset", "layer"):
                    out.append(tinycss2.serialize([r]).strip())
        return out
    return "\n".join(walk(tinycss2.parse_stylesheet(css, skip_whitespace=True, skip_comments=True)))

def main():
    src = open(SRC, encoding="utf-8").read()
    files = {}
    head_end = src.index("</head>")
    head, body = src[:head_end], src[head_end:]
    # 1. CSS
    crit_path = os.path.join(ROOT, "src", "critical-selectors.json")
    critical = set(json.load(open(crit_path))["selectors"]) if os.path.exists(crit_path) else None
    split_css = EXTERNAL_CSS or critical is not None
    styles = list(re.finditer(r"[ \t]*<style>(.*?)</style>\n?", head, re.S)) if split_css else []
    css = "\n".join(m.group(1) for m in styles)
    css = css.replace('url("assets/', 'url("../assets/').replace("url('assets/", "url('../assets/").replace("url(assets/", "url(../assets/")
    crit_css = critical_subset("\n".join(m.group(1) for m in styles), critical) if critical is not None else ""
    css = rcssmin.cssmin(css)
    css_name = "app/app.%s.css" % h(css)
    if split_css: files[css_name] = css
    parts, last = [], 0
    for i, m in enumerate(styles):
        parts.append(head[last:m.start()])
        if i == 0 and critical is not None:
            # Home's first-paint rules inline; the whole sheet right after the
            # first paint (the app scripts wait for it, see the vault loader)
            parts.append("    <style>%s</style>\n" % rcssmin.cssmin(crit_css))
            parts.append('    <link rel="stylesheet" href="%s" media="print" data-full-css onload="this.media=\'all\';window.__cssFull=1;document.dispatchEvent(new Event(\'wardrobe-css\'))" />\n' % css_name)
            parts.append('    <noscript><link rel="stylesheet" href="%s" /></noscript>\n' % css_name)
        elif i == 0:
            parts.append('    <link rel="stylesheet" href="%s" />\n' % css_name)
            parts.append("@@PRELOADS@@")
        last = m.end()
    parts.append(head[last:])
    head = "".join(parts)
    # 2. scripts in body
    js_names, lazy_names, lazy_data, bundle, lazy_calls = [], [], [], [], []
    n = [0]
    def app_script(m):
        n[0] += 1
        code = m.group(1)
        # big data literals that only some views use: own file, loaded on demand
        for var in LAZY_DATA:
            t = jslit.take_var(code, var)
            if t:
                st, en, val = t
                data = json.dumps(val, ensure_ascii=False, separators=(",", ":"))
                dn = "app/%s.%s.json" % (var.lower().replace("_", "-"), h(data))
                files[dn] = data; lazy_data.append(dn)
                lazy_calls.append("__lazyData802(%s, %s, %s, %d);" % (json.dumps(var), json.dumps(dn), json.dumps("[" if isinstance(val, list) else "{"), LAZY_DATA.index(var)))
                code = code[:st] + "/* %s: lazy data, see the loader in <head> */" % var + code[en:]
        code = rjsmin.jsmin(code)
        if n[0] >= BUNDLE_FROM:
            bundle.append(code + "\n//# sourceURL=app/%02d.js" % n[0])
            return '<script type="wardrobe/app" data-bsrc="@@BUNDLE@@" data-bi="%d"></script>' % (len(bundle) - 1)
        name = "app/%02d.%s.js" % (n[0], h(code))
        files[name] = code; js_names.append(name)
        return '<script type="wardrobe/app" data-src="%s"></script>' % name
    def inline_script(m):
        code = m.group(1)
        if not code.lstrip().startswith(DEFER_HEADS):
            return m.group(0)
        n[0] += 1
        code = rjsmin.jsmin(code)
        name = "app/%02d.%s.js" % (n[0], h(code))
        files[name] = code; js_names.append(name)
        return '<script src="%s" defer></script>' % name
    # static markup nothing reads at parse time: filled in by a deferred
    # script that runs before every other deferred/app script
    for bid in LAZY_MARKUP:
        st = body.index('<div id="%s">' % bid); inner0 = body.index(">", st) + 1
        depth, i = 1, inner0
        while depth:
            o, c = body.find("<div", i), body.find("</div>", i)
            if o != -1 and o < c: depth += 1; i = o + 4
            else: depth -= 1; i = c + 6
        inner = body[inner0:i - 6]
        code = "document.getElementById(%s).innerHTML = %s;\n" % (json.dumps(bid), json.dumps(inner))
        name = "app/00-%s.%s.js" % (bid, h(code))
        files[name] = code; lazy_names.append(name)
        body = body[:inner0] + "</div>" + '<script src="%s" defer></script>' % name + body[i:]
    # Build .81: on-demand modules — <script type="wardrobe/module" data-name="x">
    # becomes app/x.<hash>.js, never loaded at boot (the page loads it via
    # window.__mod81[x] when a view needs it); precached by the SW like the
    # rest. /*@@INCLUDE name@@*/ inside a module is replaced by the source
    # between /*<name>*/ and /*</name>*/ in src/app.html (one copy of the code).
    mod_names = []
    def module_script(m):
        name, code = m.group(1), m.group(2)
        def inc(mm):
            tag = mm.group(1)
            a = src.index("/*<%s>*/" % tag) + len("/*<%s>*/" % tag); b = src.index("/*</%s>*/" % tag)
            return src[a:b]
        code = re.sub(r"/\*@@INCLUDE ([\w-]+)@@\*/", inc, code)
        code = rjsmin.jsmin(code)
        fn = "app/%s.%s.js" % (name, h(code))
        files[fn] = code; mod_names.append(fn)
        return "<script>(window.__mod81 = window.__mod81 || {})[%s] = %s;</script>" % (json.dumps(name), json.dumps(fn))
    body = re.sub(r'<script type="wardrobe/module" data-name="([\w-]+)">(.*?)</script>', module_script, body, flags=re.S)
    body = re.sub(r'<script type="wardrobe/app">(.*?)</script>', app_script, body, flags=re.S)
    body = re.sub(r"<script>(.*?)</script>", inline_script, body, flags=re.S)
    js_names = lazy_names + js_names
    bundle_name = None
    if bundle:
        btxt = "(window.__bundle803 = window.__bundle803 || {})[document.currentScript.getAttribute(\"src\")] = %s;\n" % json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
        bundle_name = "app/bundle.%s.js" % h(btxt)
        files[bundle_name] = btxt
        body = body.replace("@@BUNDLE@@", bundle_name)
    # HTML comments in the markup (not in scripts) are dropped from the shell
    chunks = re.split(r"(<script\b.*?</script>)", body, flags=re.S)
    body = "".join(c if c.startswith("<script") else re.sub(r"<!--.*?-->", "", c, flags=re.S) for c in chunks)
    hc = re.split(r"(<script\b.*?</script>)", head, flags=re.S)
    head = "".join(c if c.startswith("<script") else re.sub(r"<!--.*?-->", "", c, flags=re.S) for c in hc)
    pre = "".join('    <link rel="preload" as="script" href="%s" />\n' % j for j in js_names)
    if bundle_name: pre += '    <link rel="preload" as="script" href="%s" />\n' % bundle_name
    if "@@PRELOADS@@" in head: head = head.replace("@@PRELOADS@@", pre)
    else: head = head.rstrip(" ") + pre.replace('as="script"', 'as="script" fetchpriority="low"') + "  "  # end of <head>: after the inline CSS has streamed
    if lazy_data:
        cs = head.index("<meta charset")
        cs = head.index(">", cs) + 1
        head = head[:cs] + "\n" + LAZY_LOADER.replace("@@LAZY_CALLS@@", "\n  ".join(lazy_calls)) + head[cs:]
    out = BANNER + head + body
    if EXTERNAL_CSS and critical is None and "<style>" in head:
        sys.exit("a <style> block was left in <head>")
    # 3. write
    os.makedirs(APP, exist_ok=True)
    keep = set()
    for name, text in files.items():
        p = os.path.join(ROOT, name); keep.add(os.path.basename(name))
        if not os.path.exists(p) or open(p, encoding="utf-8").read() != text:
            open(p, "w", encoding="utf-8").write(text)
    for f in os.listdir(APP):
        if f not in keep: os.remove(os.path.join(APP, f))
    open(OUT, "w", encoding="utf-8").write(out)
    # 4. sw.js code list
    sw = open(SW, encoding="utf-8").read()
    lst = "const CODE_FILES = [%s];" % ", ".join("'./%s'" % f for f in ([css_name] if split_css else []) + js_names + ([bundle_name] if bundle_name else []) + lazy_data + mod_names)
    sw2, k = re.subn(r"const CODE_FILES = \[.*?\];", lst, sw, flags=re.S)
    if not k: sys.exit("sw.js has no CODE_FILES line")
    if sw2 != sw: open(SW, "w", encoding="utf-8").write(sw2)
    print("index.html %d bytes (was %d in src/app.html); %d code files; css %d; js %d" % (
        len(out.encode()), len(src.encode()), len(files), len(css.encode()), sum(len(files[j].encode()) for j in js_names + ([bundle_name] if bundle_name else []))))

if __name__ == "__main__":
    main()
