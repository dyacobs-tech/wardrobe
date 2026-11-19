
/* Build .78.4b — Home hero background layer + a smooth Next.
   The lag on Next/swipe was the main thread: each deal re-ran Shop the
   look's catalogue matching for the new look (renderFindLookMode →
   catalogueScored/garmentTypeFromText, ~75% of the time) even though
   that page is not on screen, plus a canvas getImageData colour sample
   per render and a layout probe on every tap. Now Shop the look syncs
   when it is opened (or in idle time), the background is one blurred
   layer, and the next renders are fetched and decoded ahead. */
(function () {
  /* ---- background layer ---- */
  var BD_KEY = "wardrobe.heroBackdrop";
  function layerFor(el) {
    if (!el) return null;
    var bg = el.querySelector(":scope > .hero-bg");
    if (!bg) {
      bg = document.createElement("div"); bg.className = "hero-bg"; bg.setAttribute("aria-hidden", "true");
      bg.innerHTML = '<img alt="" decoding="async" /><img alt="" decoding="async" />';
      el.insertBefore(bg, el.firstChild);
    }
    return bg;
  }
  /* ---- cut-outs + the closet backdrop (assets/onbody-cut/manifest.json) ---- */
  /* .78.9a: the closet backdrop is Home's default from the first paint —
     it never waits on the manifest — and every render's cut-out sits at
     assets/onbody-cut/<same name> until the manifest says otherwise */
  var CUT = { map: null, backdrop: "assets/backdrops/closet-walnut.webp", placeholder: "assets/backdrops/closet-walnut-tiny.webp" }, BADCUT = {};
  function idOf(src) { var m = String(src || "").match(/\/onbody\/([^\/?#]+?)\.(webp|png|jpe?g)/i); return m ? m[1] : ""; }
  window.cutFor784 = function (src) {
    if (!src) return "";
    var id = idOf(src); if (!id || BADCUT[id]) return "";
    if (CUT.map) return CUT.map[id] || "";
    return "assets/onbody-cut/" + id + ".webp";
  };
  /* a cut-out that fails to load is dropped and Home re-deals */
  document.addEventListener("error", function (e) {
    var t = e.target; if (!t || t.tagName !== "IMG") return;
    var m = String(t.getAttribute("src") || "").match(/onbody-cut\/([^\/?#]+?)\.(webp|png)/i); if (!m) return;
    if (BADCUT[m[1]]) return; BADCUT[m[1]] = 1;
    if (t.id === "today-img" && typeof renderToday === "function") setTimeout(function () { try { renderToday(); } catch (x) {} }, 0);
  }, true);
  function ingestCut(j) {
    if (!j || typeof j !== "object") return false;
    var map = j.r || j.map || j.cuts || j.cutouts || j.renders || null, bd = j.backdrop, ph = j.placeholder || j.backdropPlaceholder;
    if (bd && typeof bd === "object") { ph = ph || bd.placeholder || bd.thumb || bd.tiny; bd = bd.src || bd.path || bd.url || ""; }
    if (!map) { map = {}; Object.keys(j).forEach(function (k) { if (!/^(backdrop|placeholder|backdropPlaceholder|v|version|count|updated|generated)$/.test(k)) map[k] = j[k]; }); }
    var clean = {};
    Object.keys(map).forEach(function (k) {
      var v = map[k]; if (v && typeof v === "object") v = v.cut || v.cutout || v.src || v.path || "";
      if (typeof v !== "string" || !v) return;
      clean[idOf(k) || k.replace(/\.(webp|png|jpe?g)$/i, "").replace(/^.*\//, "")] = v;
    });
    CUT.map = clean; if (typeof bd === "string" && bd) CUT.backdrop = bd; if (typeof ph === "string" && ph) CUT.placeholder = ph;
    return true;
  }
  function loadCuts() {
    try {
      fetch("assets/onbody-cut/manifest.json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
        if (!ingestCut(j) || !Object.keys(CUT.map).length) return;
        if (typeof renderToday === "function" && typeof todayLook !== "undefined" && todayLook) try { renderToday(); } catch (e) {}
        if (typeof window.guestHero782 === "function") window.guestHero782();
      }).catch(function () {});
    } catch (e) {}
  }
  window.cutManifest784 = function () { return CUT; };
  window.ingestCut784 = ingestCut;
  setTimeout(loadCuts, 0);
  setTimeout(function () { if (typeof window.guestHero782 === "function") window.guestHero782(); }, 0);
  document.addEventListener("visibilitychange", function () { if (!document.hidden && !CUT.map) loadCuts(); });
  function backdrop(src) {
    var o = ""; try { o = localStorage.getItem(BD_KEY) || ""; } catch (e) {}
    if (o) return o;
    return src && CUT.backdrop && window.cutFor784(src) ? CUT.backdrop : "";
  }
  /* the blurred layer is built once per render from the render's own outer
     columns (stretched across, then blurred), so it continues the studio
     backdrop seamlessly at the render's edges — no panel, no band */
  var edgeCache = {};
  function edgeOf(src, cb) {
    if (edgeCache[src]) return cb(edgeCache[src]);
    var im = new Image(); im.decoding = "async";
    im.onload = function () {
      try {
        var W = im.naturalWidth, H = im.naturalHeight, R = 96, cv = document.createElement("canvas"); cv.width = 2; cv.height = R;
        var cx = cv.getContext("2d"), sw = Math.max(2, Math.round(W * 0.02));
        cx.drawImage(im, 0, 0, sw, H, 0, 0, 1, R);
        cx.drawImage(im, W - sw, 0, sw, H, 1, 0, 1, R);
        var d = cx.getImageData(0, 0, 2, R).data, col = [[], []];
        for (var y = 0; y < R; y++) for (var c = 0; c < 2; c++) { var k = (y * 2 + c) * 4; col[c].push([d[k], d[k + 1], d[k + 2]]); }
        /* rows where an arm, a hand or a shadow reaches the edge are not
           backdrop: replace them with the nearest clean backdrop row */
        var both = col[0].concat(col[1]).map(function (p) { return p[0] * .3 + p[1] * .59 + p[2] * .11; }).sort(function (a, b) { return a - b; });
        var med = both[both.length >> 1];
        var out = document.createElement("canvas"); out.width = 48; out.height = R;
        var ox = out.getContext("2d"), od = ox.createImageData(48, R);
        for (c = 0; c < 2; c++) {
          var ok = col[c].map(function (p) { return Math.abs(p[0] * .3 + p[1] * .59 + p[2] * .11 - med) < 14; });
          for (y = 0; y < R; y++) {
            var yy = y; if (!ok[y]) { for (var dd = 1; dd < R; dd++) { if (y - dd >= 0 && ok[y - dd]) { yy = y - dd; break; } if (y + dd < R && ok[y + dd]) { yy = y + dd; break; } } }
            var px = ok[yy] ? col[c][yy] : [med, med, med];
            for (var x = 0; x < 24; x++) { var o = (y * 48 + c * 24 + x) * 4; od.data[o] = px[0]; od.data[o + 1] = px[1]; od.data[o + 2] = px[2]; od.data[o + 3] = 255; }
          }
        }
        ox.putImageData(od, 0, 0);
        edgeCache[src] = out.toDataURL("image/jpeg", 0.85);
      } catch (e) { edgeCache[src] = src; }
      cb(edgeCache[src]);
    };
    im.onerror = function () { cb(src); };
    im.src = src;
  }
  function setBg(src, el) {
    var bg = layerFor(el); if (!bg) return;
    /* .78.9c: Home and the outfit view are the seamless off-white — no
       backdrop image, no blurred-render sampling (cheaper, too) */
    if (!(function () { try { return localStorage.getItem(BD_KEY); } catch (e) { return ""; } })()) { bg.style.backgroundImage = ""; return; }
    var bd = backdrop(src);
    if (bd && CUT.placeholder && !bg.style.backgroundImage) { bg.style.backgroundImage = "url(\"" + CUT.placeholder + "\")"; bg.style.backgroundSize = "cover"; bg.style.backgroundPosition = "center"; }
    bg.classList.toggle("bd-custom", !!bd);
    /* .78.8a: only the latest request paints — a slow edge sample from an
       earlier render must never land over the closet backdrop */
    var tok = bg.__tok = (bg.__tok || 0) + 1;
    if (!bd && src) { edgeOf(src, function (u) { if (bg.__tok === tok) paintBg(bg, u); }); return; }
    paintBg(bg, bd || src);
  }
  function paintBg(bg, want) {
    if (!want) return;
    var imgs = bg.querySelectorAll("img"), on = bg.querySelector("img.on");
    if (on && on.getAttribute("src") === want) return;
    var next = on === imgs[0] ? imgs[1] : imgs[0];
    function show() { next.classList.add("on"); if (on && on !== next) on.classList.remove("on"); }
    next.setAttribute("src", want);
    if (next.decode) next.decode().then(show, show); else show();
  }
  window.heroBgSet784 = function (src, el) {
    setBg(src, el);
    /* feather only the render's own edges: its drawn width inside the full-width box */
    try {
      var im = el && el.querySelector("img#today-img, img#ov-img");
      if (im) {
        var set = function () { var r = im.getBoundingClientRect(), nw = im.naturalWidth, nh = im.naturalHeight; if (!r.width || !nw) return;
          var dw = Math.min(r.width, r.height * nw / nh), pad = (r.width - dw) / 2, f = Math.max(0, pad + dw * 0.16);
          im.style.setProperty("--feather", Math.round(f) + "px"); el.style.setProperty("--feather", Math.round(f) + "px");
          el.style.setProperty("--fig-h", Math.round(im.offsetHeight) + "px"); el.style.setProperty("--fig-top", Math.round(im.offsetTop) + "px"); };
        if (im.complete && im.naturalWidth) set(); else im.addEventListener("load", set, { once: true });
      }
    } catch (e) {}
  };
  /* swap the background for a fixed backdrop image (null = the blurred render) */
  window.setHeroBackdrop = function (url) {
    try { if (url) localStorage.setItem(BD_KEY, url); else localStorage.removeItem(BD_KEY); } catch (e) {}
    var im = document.getElementById("today-img"), h = document.getElementById("today-hero");
    if (h && im) setBg(im.getAttribute("data-render") || im.getAttribute("src"), h);
  };
  var h0 = document.getElementById("today-hero"), i0 = document.getElementById("today-img");
  if (h0 && i0 && h0.classList.contains("hero-solo")) setBg(i0.getAttribute("data-render") || i0.getAttribute("src"), h0);

  /* ---- Shop the look syncs when it is opened, not on every Next ---- */
  if (typeof window.syncShopLookToToday === "function") {
    var _ss = window.syncShopLookToToday, dirty = false;
    function runNow() { dirty = false; try { _ss(); } catch (e) {} }
    window.syncShopLookToToday = function () {
      var pf = document.getElementById("panel-find");
      if (pf && !pf.hidden) return runNow();
      dirty = true; /* runs the moment Shop the look opens */
    };
    if (typeof window.switchTab === "function") {
      var _st = window.switchTab;
      window.switchTab = function (name) { if (name === "find" && dirty) runNow(); return _st.apply(this, arguments); };
    }
  }

  /* ---- fetch + decode the next renders ahead ----
     .79.3: Next is dealt from a look-ahead queue computed on idle, so the
     cut-out warmed (fetched + decoded) is the one Next will actually show;
     the service worker is told to keep the outfit of the day and the next
     five in Cache Storage. Nothing competes with the hero while it loads. */
  var warm = {}, warmQ = [], Q = null, dealing = false;
  var ric2 = window.requestIdleCallback || function (f) { return setTimeout(f, 300); };
  function warmOne(src, hi) {
    var cut = window.cutFor784 && window.cutFor784(src); if (cut) src = cut;
    if (!src || warm[src]) return src; warm[src] = 1;
    var im = new Image(); im.decoding = "async"; if (hi) try { im.fetchPriority = "high"; } catch (e) {} im.src = src;
    if (im.decode) im.decode().catch(function () {});
    warmQ.push(im); if (warmQ.length > 12) warmQ.shift();
    return src;
  }
  function qsig() {
    try {
      return [typeof formalityLevel !== "undefined" ? formalityLevel : "", typeof currentWeather !== "undefined" && currentWeather ? currentWeather.temp : "",
        typeof wardrobeItems !== "undefined" ? wardrobeItems.length : 0, typeof dislikedImgs !== "undefined" && dislikedImgs ? dislikedImgs.length : 0,
        typeof todayLook !== "undefined" && todayLook ? todayLook.title : ""].join("/");
    } catch (e) { return String(Math.random()); }
  }
  function dealable(l) {
    try {
      if (typeof lookIsMine === "function" && !lookIsMine(l)) return false;
      if (typeof isGraduatedLook === "function" && isGraduatedLook(l)) return false;
      if (typeof lookPhotoBanned56 === "function" && lookPhotoBanned56(l)) return false;
      var r = window.renderFor782 ? window.renderFor782(l) : null;
      return !!(r && window.cutFor784 && window.cutFor784(r) && !(typeof isDislikedImg === "function" && isDislikedImg(r)));
    } catch (e) { return false; }
  }
  if (typeof homeComposerLooks75 === "function" && typeof dealHeroForSource === "function") {
    var _hcl = homeComposerLooks75, _dh = dealHeroForSource;
    homeComposerLooks75 = function (count) {
      if (dealing && Q && Q.sig === qsig() && Q.list.length) { var l = Q.list; Q = null; return l; }
      return _hcl.apply(this, arguments);
    };
    dealHeroForSource = function () { dealing = true; try { return _dh.apply(this, arguments); } finally { dealing = false; } };
    window.homeLookahead793 = function () { return Q; };
  }
  function prefetch() {
    var him = document.getElementById("today-img");
    function run() {
      ric2(function () {
        try {
          var look = typeof todayLook !== "undefined" ? todayLook : null, r4 = window.renderFor782, urls = [];
          var cur = look && r4 ? r4(look) : null; if (cur && window.cutFor784 && window.cutFor784(cur)) urls.push(window.cutFor784(cur));
          if (look && typeof _hcl === "function") {
            var list = _hcl(8) || [], good = list.filter(dealable), rest = list.filter(function (l) { return !dealable(l); });
            /* the queue the next deal takes: looks he can be seen in first */
            Q = { sig: qsig(), list: good.concat(rest) };
            var nx = good.filter(function (l) { return l.title !== look.title; });
            nx.slice(0, 5).forEach(function (l, i) { var u = r4(l); if (!u) return; var c = window.cutFor784(u); if (c) urls.push(c); if (i < 3) warmOne(u, i === 0); });
            if (window.lqRemember793) window.lqRemember793(urls.map(function (u) { var m = u.match(/onbody-cut\/([^\/?#]+?)\./); return m ? m[1] : ""; }));
          }
          var sw = navigator.serviceWorker && navigator.serviceWorker.controller;
          if (sw && urls.length) sw.postMessage({ type: "warm-cuts", urls: urls.slice(0, 6) });
        } catch (e) {}
      }, { timeout: 1200 });
    }
    /* never compete with the hero itself */
    if (him && !(him.complete && him.naturalWidth)) { var once = false, go = function () { if (once) return; once = true; run(); }; him.addEventListener("load", go, { once: true }); setTimeout(go, 6000); }
    else run();
  }
  window.heroPrefetch784 = prefetch;
  /* Undo sits just above the action row it belongs to, never over it */
  window.placeUndo782 = function (box) {
    var row = null, ov = document.getElementById("outfit-view");
    if (ov && !ov.hidden) row = document.getElementById("ov-acts");
    else { var pt = document.getElementById("panel-today"); if (pt && !pt.hidden) row = document.getElementById("today-simple-actions"); }
    var r = row && row.getBoundingClientRect();
    if (r && r.height && r.top > 0 && r.top < window.innerHeight) box.style.setProperty("bottom", Math.max(12, Math.round(window.innerHeight - r.top + 10)) + "px", "important");
    else box.style.removeProperty("bottom");
  };
  if (typeof window.renderToday === "function") {
    var _rt = window.renderToday;
    window.renderToday = function () { var o = _rt.apply(this, arguments); prefetch(); return o; };
  }
  setTimeout(prefetch, 1500);
})();
    