
/* Build .78.2c — Home is him: the hero is the one full-length render of
   him in today's outfit (whole head to feet, never cropped), and Next
   crossfades to the next render so the clothes change around him. No
   piece collage on Home. Tapping him (or the title) opens the outfit
   view: the render full-screen, then each piece (studio photo, name,
   brand) — a piece opens its item page. Outfits cards show the render
   alone too; their pieces live in the look's detail. */
(function () {
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  var hero = document.getElementById("today-hero"), img = document.getElementById("today-img"), collage = document.getElementById("today-collage");
  if (!hero || !img) return;

  /* ---------- the render for a look ---------- */
  function renderFor(look) {
    if (!look) return "";
    if (look.swapPhoto && (look.swapPieces || look.swapComboId)) return look.swapPhoto;
    if (look.fwRender) return look.fwRender;
    var ob = typeof onbodyForLook === "function" ? onbodyForLook(look) : null;
    return ob || "";
  }
  function piecesOf(look) {
    var ps = (look && (look.fwPieces || look.pieces)) || [];
    return ps.map(function (p) {
      var it = p && p.id && typeof closetItemById === "function" ? (closetItemById(p.id) || p) : p;
      return it && typeof it === "object" ? it : null;
    }).filter(Boolean);
  }
  function photoOf(p) {
    var ph = typeof itemPhoto === "function" ? itemPhoto(p) : (p.photo || "");
    if (ph && ph.indexOf("idb:") === 0) { var pv = window.photoVault; var hit = pv && pv.cache ? pv.cache[ph.slice(4)] : undefined; if (hit) ph = hit; else if (pv && pv.fetch) { try { pv.fetch(ph.slice(4), function () {}); } catch (e) {} } }
    else if (ph && /^blob:[0-9a-f]{16,}/.test(ph)) { var bs = window.blobStore; var bh = bs && bs.cache ? bs.cache[ph.slice(5)] : undefined; if (bh) ph = bh; }
    return ph || "";
  }
  function brandOf(p) {
    if (p.brand) return String(p.brand);
    var bl = typeof bulkBrands === "function" ? bulkBrands() : [], nm = String(p.name || "");
    var hit = bl.filter(function (b) { return nm.toLowerCase().indexOf(String(b).toLowerCase() + " ") === 0; }).sort(function (a, b) { return b.length - a.length; })[0];
    return hit || "";
  }

  /* the render's own studio colour behind it, so contain never shows a band */
  var bgCache = {};
  function sampleBg(src, el) { if (window.heroBgSet784) window.heroBgSet784(src, el); }
  function sampleBgOld(src, el) {
    if (!src || !el) return;
    if (bgCache[src]) { el.style.setProperty("--hero-bg", bgCache[src]); return; }
    var im = new Image();
    im.onload = function () {
      try {
        /* the bars sit beside the render's left and right edges: carry
           those edge columns' colours top to bottom, so there is no seam */
        var H = 48, cv = document.createElement("canvas"); cv.width = 32; cv.height = H;
        var cx = cv.getContext("2d"); cx.drawImage(im, 0, 0, 32, H);
        var stops = [];
        for (var y = 0; y < H; y += 6) {
          var L = cx.getImageData(0, y, 2, 6).data, R = cx.getImageData(30, y, 2, 6).data, r = 0, g = 0, b = 0, n = 0, i;
          for (i = 0; i < L.length; i += 4) { r += L[i] + R[i]; g += L[i + 1] + R[i + 1]; b += L[i + 2] + R[i + 2]; n += 2; }
          stops.push("rgb(" + Math.round(r / n) + "," + Math.round(g / n) + "," + Math.round(b / n) + ") " + Math.round((y + 3) / H * 100) + "%");
        }
        bgCache[src] = "linear-gradient(" + stops.join(",") + ")";
        el.style.setProperty("--hero-bg", bgCache[src]);
      } catch (e) {}
    };
    im.src = src;
  }

  /* ---------- the hero ---------- */
  var skip = 0, prevSrc = null;
  function crossfade(prev) {
    if (!prev || prev === img.getAttribute("src")) return;
    var old = hero.querySelector(".hero-xfade");
    if (old) old.remove();
    var ov = document.createElement("img");
    ov.className = "hero-xfade"; ov.alt = ""; ov.setAttribute("aria-hidden", "true"); ov.src = prev;
    ov.style.top = img.offsetTop + "px"; ov.style.height = img.offsetHeight + "px";
    img.parentNode.insertBefore(ov, img.nextSibling);
    var went = false;
    function go() {
      if (went) return; went = true;
      /* fade only once the new cut-out is decoded, so nothing blinks */
      var dec = img.decode ? img.decode().catch(function () {}) : Promise.resolve();
      dec.then(function () { requestAnimationFrame(function () { ov.classList.add("out"); setTimeout(function () { ov.remove(); }, 260); }); });
    }
    if (img.complete && img.naturalWidth) go(); else { img.addEventListener("load", go, { once: true }); img.addEventListener("error", go, { once: true }); setTimeout(go, 4000); }
  }
  function placeHero() {
    var bb = document.getElementById("bottombar");
    var band = bb && bb.getBoundingClientRect().height ? Math.max(0, Math.round(window.innerHeight - bb.getBoundingClientRect().top)) : 0;
    hero.style.setProperty("--nav-band", band + "px");
  }
  var booted782 = false, userDeal782 = false, rcache = { sig: "", v: false };
  function anyRenderable782() {
    try {
      var keys = typeof ONBODY !== "undefined" && ONBODY.map ? Object.keys(ONBODY.map) : [];
      var sig = keys.length + "/" + (typeof wardrobeItems !== "undefined" ? wardrobeItems.length : 0) + "/" + (typeof dislikedImgs !== "undefined" ? dislikedImgs.length : 0);
      if (rcache.sig === sig) return rcache.v;
      var own = {}; (wardrobeItems || []).forEach(function (i) { own[i.id] = 1; });
      var v = keys.some(function (k) { var src = ONBODY.map[k]; return k.split("|").every(function (id) { return own[id]; }) && !(typeof isDislikedImg === "function" && isDislikedImg(src)) && !(typeof window.cutFor784 === "function" && !window.cutFor784(src)); });
      rcache = { sig: sig, v: v }; return v;
    } catch (e) { return true; }
  }
  document.addEventListener("click", function (e) { if (e.target && e.target.closest && e.target.closest("#today-next, #today-dislike, #ov-next, #ov-dislike")) userDeal782 = true; }, true);
  /* .78.7c: no account data (fresh browser, built-in looks only), or
     no look at all — never his old mirror selfie, never a letterbox:
     one of his on-body cut-outs on the walnut closet backdrop */
  var SELFIE782 = /assets\/photos\/9a543e585d8b\./;
  function guestMode782() {
    if (typeof todayLook === "undefined" || !todayLook) return true;
    if (String(todayLook.id || "").indexOf("seed-") === 0 && !(todayLook.fwPieces && todayLook.fwPieces.length)) return true;
    try { return !homeOwnedPhotoPieces742().own.length; } catch (e) { return false; }
  }
  var gOff782 = 0;
  function guestSrc782() {
    var C = typeof window.cutManifest784 === "function" ? window.cutManifest784() : null;
    var keys = C && C.map ? Object.keys(C.map).sort() : [];
    var day = typeof localTodayISO === "function" ? localTodayISO() : new Date().toISOString().slice(0, 10), h = 0;
    for (var i = 0; i < day.length; i++) h = (h * 31 + day.charCodeAt(i)) >>> 0;
    h += gOff782;
    keys = keys.filter(function (k) { return window.cutFor784("assets/onbody/" + k + ".webp"); });
    if (keys.length) { var k = keys[h % keys.length]; return { cut: C.map[k], render: "assets/onbody/" + k + ".webp" }; }
    var rs = typeof ONBODY !== "undefined" && ONBODY.map ? Object.keys(ONBODY.map).sort().map(function (x) { return ONBODY.map[x]; }) : [];
    /* .78.9e: only ever a cut-out — never the plain studio render */
    rs = rs.filter(function (r) { return typeof window.cutFor784 === "function" && window.cutFor784(r); });
    return rs.length ? { cut: window.cutFor784(rs[h % rs.length]), render: rs[h % rs.length] } : null;
  }
  function guestHero782(forceTitle) {
    if (userDeal782) { gOff782++; userDeal782 = false; }
    var g = guestSrc782(); if (!g) return false;
    var before = hero.classList.contains("hero-solo") ? img.getAttribute("src") : null;
    if (collage) { collage.hidden = true; collage.innerHTML = ""; collage.classList.remove("flatlay-host"); }
    var shown = g.cut || g.render;
    hero.classList.toggle("has-cut", !!g.cut);
    hero.classList.add("hero-solo", "hero-guest");
    img.setAttribute("data-render", g.render);
    if (img.getAttribute("src") !== shown) img.setAttribute("src", shown);
    img.hidden = false; img.alt = "David in a look from his closet";
    var nm = document.getElementById("today-name"); if (nm && (forceTitle || !nm.textContent.trim())) nm.textContent = "From your closet";
    sampleBg(g.render, hero); placeHero();
    if (before && before !== shown && !/^data:/.test(before)) crossfade(before);
    return true;
  }
  window.guestHero782 = function () { try { if (guestMode782()) return guestHero782(); } catch (e) {} return false; };
  function soloHero() {
    hero.classList.remove("hero-guest");
    if (guestMode782() && guestHero782()) return;
    if (typeof todayLook === "undefined" || !todayLook) return;
    var src = renderFor(todayLook);
    /* .78.9a: Home only deals a render that has its cut-out */
    if (src && typeof window.cutFor784 === "function" && !window.cutFor784(src)) src = null;
    /* .78.2c: a render he gave a thumbs-down never comes back */
    if (src && typeof isDislikedImg === "function" && isDislikedImg(src)) src = null;
    if (!src) {
      /* Home only deals looks he can be seen in: skip one with no render */
      var lkey = todayLook.composerKey || todayLook.id || todayLook.img || "", acc = null, dayIso = typeof localTodayISO === "function" ? localTodayISO() : "";
      try { acc = JSON.parse(localStorage.getItem("wardrobe.ootdNoRender782") || "null"); } catch (e) {}
      var accepted = acc && acc.date === dayIso && acc.key === lkey && !userDeal782;
      if (!accepted && !anyRenderable782()) accepted = true; /* none of his looks has a render yet: don't churn */
      if (!accepted && skip < 30 && typeof dealAnotherToday === "function") { skip++; setTimeout(dealAnotherToday, 0); return; }
      /* nothing he can be seen in today: settle on this look for the day (stable across opens) */
      if (!accepted && !userDeal782) { try { localStorage.setItem("wardrobe.ootdNoRender782", JSON.stringify({ date: dayIso, key: lkey })); } catch (e) {} if (typeof persistOpeningLook === "function") try { persistOpeningLook(todayLook); } catch (e) {} }
      skip = 0; booted782 = true; userDeal782 = false;
      /* nothing rendered to show: one photo, never a tile grid */
      if (collage) { collage.hidden = true; collage.innerHTML = ""; collage.classList.remove("flatlay-host"); }
      /* .78.9e: the hero only ever shows a transparent cut-out — when this
         look has none, one of his cut-outs stands in (never the plain
         studio render, never a piece photo) */
      if (guestHero782(true)) return;
      var fb = (typeof lookImg === "function" && lookImg(todayLook)) || "";
      if (SELFIE782.test(fb)) fb = "";
      if (!fb || /^data:image\/svg/.test(fb)) { var pp = piecesOf(todayLook).map(photoOf).filter(Boolean); fb = pp[0] || fb; }
      if (fb && img.getAttribute("src") !== fb) img.setAttribute("src", fb);
      img.removeAttribute("data-render"); hero.classList.remove("has-cut");
      hero.classList.add("hero-solo");
      img.hidden = false; placeHero(); return;
    }
    /* .78.2c: the day's opening look is the first one he can be seen in —
       keep THAT as the outfit of the day so every app open shows it */
    if ((!booted782 || !userDeal782) && skip > 0 && typeof persistOpeningLook === "function") try { persistOpeningLook(todayLook); } catch (e) {}
    booted782 = true; userDeal782 = false;
    skip = 0;
    var prev = prevSrc; prevSrc = null;
    if (collage) { collage.hidden = true; collage.innerHTML = ""; collage.classList.remove("flatlay-host"); }
    /* .78.5b: his cut-out on the closet backdrop when one exists */
    var shown = (typeof window.cutFor784 === "function" && window.cutFor784(src)) || src;
    hero.classList.toggle("has-cut", shown !== src);
    img.setAttribute("data-render", src);
    if (img.getAttribute("src") !== shown) img.setAttribute("src", shown);
    img.hidden = false;
    img.alt = (todayLook.title || "Outfit") + " on David";
    hero.classList.add("hero-solo");
    sampleBg(src, hero);
    placeHero();
    crossfade(prev && prev !== shown ? prev : null);
    if (ovOpen) fillView(); else if (typeof prewarmView === "function") prewarmView();
  }
  if (typeof renderToday === "function") {
    var _rt782 = renderToday;
    renderToday = function () {
      prevSrc = hero.classList.contains("hero-solo") ? img.getAttribute("src") : null;
      var out = _rt782.apply(this, arguments); try { soloHero(); } catch (e) {} try { if (typeof watchdog === "function") watchdog(); } catch (e) {} return out;
    };
  }
  /* .79.2: the hero shows only a genuine cut-out — checked in JS (never
     by URL substring alone), and a watchdog makes sure a dealt hero is
     actually on screen: ~1.5s after a deal, a hero that has not loaded
     is reloaded once, then replaced by a stand-in cut-out */
  function isCutSrc(u) {
    u = String(u || ""); if (!u || /^data:/.test(u)) return false;
    if (/\/onbody-cut(-hq)?\/[^\/?#]+\.(webp|png)/i.test(u) || /^assets\/onbody-cut(-hq)?\//.test(u)) return true;
    try { var C = window.cutManifest784 && window.cutManifest784(); if (C && C.map) for (var k in C.map) if (u.indexOf(C.map[k]) !== -1) return true; } catch (e) {}
    return false;
  }
  function guard(el) {
    if (!el) return;
    var ok = isCutSrc(el.getAttribute("src")) || !hero.classList.contains("hero-solo");
    if (ok) el.removeAttribute("data-nocut"); else el.setAttribute("data-nocut", "");
  }
  window.heroIsCut792 = isCutSrc;
  if ("MutationObserver" in window) new MutationObserver(function (ms) {
    ms.forEach(function (m) {
      if (m.type === "attributes") guard(m.target);
      else m.addedNodes.forEach(function (n) { if (n.tagName === "IMG") guard(n); });
    });
  }).observe(hero, { subtree: true, attributes: true, attributeFilter: ["src"], childList: true });
  guard(img);
  var wd = null, wdTries = 0;
  function heroOnScreen() {
    if (img.hidden || img.hasAttribute("data-nocut")) return false;
    if (!(img.complete && img.naturalWidth > 0)) return false;
    var cs = getComputedStyle(img); if (cs.visibility === "hidden" || cs.display === "none" || +cs.opacity < 0.5) return false;
    return img.getBoundingClientRect().height > 60;
  }
  /* .79.3: a hero still downloading on a slow link is never restarted
     (that only made a slow load slower): its blurred placeholder shows
     meanwhile. Only a cut-out that failed — or is still nowhere after
     12s — is replaced by a stand-in cut-out. */
  var wdT0 = 0;
  function watchdog() {
    clearTimeout(wd); if (!wdT0) wdT0 = Date.now();
    wd = setTimeout(function () {
      if (!hero.classList.contains("hero-solo") || (typeof currentTab !== "undefined" && currentTab !== "today")) { wdT0 = 0; return; }
      if (heroOnScreen()) { wdTries = 0; wdT0 = 0; hero.querySelectorAll(".hero-xfade").forEach(function (x) { if (x.classList.contains("out")) x.remove(); }); return; }
      var src = img.getAttribute("src") || "", failed = img.complete && !img.naturalWidth && isCutSrc(src);
      if (!failed && isCutSrc(src) && Date.now() - wdT0 < 12000) { watchdog(); return; }
      wdTries = 0; wdT0 = 0;
      if (typeof guestHero782 === "function" && guestHero782(true)) watchdog();
    }, 1500);
  }
  /* ---- .79.3: the blurred placeholder + the last hero for a cold open ---- */
  var lqEl = document.getElementById("today-lq"), LQ_GEN = lqEl ? lqEl.getAttribute("src") : "", LQMAP = null, LQ_KEY = "wardrobe.lq793";
  function cutId(u) { var m = String(u || "").match(/onbody-cut(?:-hq)?\/([^\/?#]+?)\.(webp|png)/i); return m ? m[1] : ""; }
  function lqLocal() { try { return JSON.parse(localStorage.getItem(LQ_KEY) || "{}") || {}; } catch (e) { return {}; } }
  function lqFor(u) { var id = cutId(u); if (!id) return LQ_GEN; if (LQMAP && LQMAP[id]) return LQMAP[id]; var l = lqLocal(); return l[id] || LQ_GEN; }
  function lqRemember(ids) {
    if (!LQMAP) return; var l = lqLocal(), keys = Object.keys(l);
    ids.forEach(function (id) { if (id && LQMAP[id] && !l[id]) { l[id] = LQMAP[id]; keys.push(id); } });
    while (keys.length > 16) delete l[keys.shift()];
    try { localStorage.setItem(LQ_KEY, JSON.stringify(l)); } catch (e) {}
  }
  window.lqRemember793 = lqRemember; window.lqFor793 = lqFor;
  function lqPlace() {
    if (!lqEl) return;
    if (img.offsetHeight > 60) { hero.style.setProperty("--lq-top", img.offsetTop + "px"); hero.style.setProperty("--lq-h", img.offsetHeight + "px"); }
  }
  var shownOnce80 = false;
  function lqSync() {
    if (!lqEl) return;
    var src = img.getAttribute("src") || "", ready = img.complete && img.naturalWidth > 0 && isCutSrc(src);
    /* .80.1: the placeholder is for a cold first paint only — once a
       cut-out has shown, a Next crossfades cut-out to cut-out (the old one
       stays on screen until the new one is decoded), never via the blur */
    if (ready) shownOnce80 = true;
    if (shownOnce80) { if (hero.classList.contains("lq-show")) hero.classList.remove("lq-show"); return; }
    if (!ready) { var want = lqFor(src); if (lqEl.getAttribute("src") !== want) lqEl.setAttribute("src", want); lqPlace(); }
    hero.classList.toggle("lq-show", !ready);
  }
  function heroLoaded() {
    lqSync(); lqPlace();
    var src = img.getAttribute("src") || "";
    if (!(img.naturalWidth > 0 && isCutSrc(src))) return;
    if (window.__heroReady793) try { window.__heroReady793(); } catch (e) {}
    try {
      var day = typeof localTodayISO === "function" ? localTodayISO() : "";
      var nm = document.getElementById("today-name");
      localStorage.setItem("wardrobe.hero793", JSON.stringify({ date: day, cut: src.replace(/[?#].*$/, ""), render: img.getAttribute("data-render") || "", title: nm ? nm.textContent : "", lq: lqFor(src) !== LQ_GEN ? lqFor(src) : "" }));
    } catch (e) {}
  }
  img.addEventListener("load", heroLoaded); img.addEventListener("error", lqSync);
  if ("MutationObserver" in window) new MutationObserver(lqSync).observe(img, { attributes: true, attributeFilter: ["src"] });
  window.addEventListener("resize", lqPlace, { passive: true });
  if (img.complete && img.naturalWidth) heroLoaded(); else lqSync();
  /* every cut-out's placeholder (assets/onbody-cut/lq.json, ~1KB each) —
     read after the hero, cached by the service worker */
  function loadLq() {
    fetch("assets/onbody-cut/lq.json").then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (j && j.lq) { LQMAP = j.lq; lqRemember([cutId(img.getAttribute("src"))]); lqSync(); }
    }).catch(function () {});
  }
  (function () { var done = false; function go() { if (done) return; done = true; (window.requestIdleCallback || setTimeout)(loadLq, { timeout: 3000 }); }
    if (img.complete && img.naturalWidth) go(); else { img.addEventListener("load", go, { once: true }); setTimeout(go, 5000); } })();
  window.heroWatchdog792 = watchdog;
  /* the occasion dropdown: a tap outside only closes it (it never also
     opens the look underneath); Esc closes it too */
  function ddMenu() { return document.getElementById("today-type-row"); }
  function ddClose() { var m = ddMenu(); if (!m || m.hidden) return; if (typeof closeAllCdd === "function") closeAllCdd(); else m.hidden = true; var b = document.getElementById("today-type-btn"); if (b) b.setAttribute("aria-expanded", "false"); }
  ["pointerdown", "click"].forEach(function (ev) {
    document.addEventListener(ev, function (e) {
      var m = ddMenu(); if (!m || m.hidden) return;
      if (e.target.closest && (e.target.closest("#today-type-row") || e.target.closest("#today-type-btn"))) return;
      e.preventDefault(); e.stopPropagation();
      if (ev === "click") ddClose();
    }, true);
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") ddClose(); });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) watchdog(); });
  window.addEventListener("pageshow", watchdog);
  window.addEventListener("resize", placeHero);
  if (collage && "MutationObserver" in window) new MutationObserver(function () {
    if (hero.classList.contains("hero-solo") && !collage.hidden) { collage.hidden = true; img.hidden = false; }
  }).observe(collage, { attributes: true, attributeFilter: ["hidden"], childList: true });

  /* ---------- the outfit view ---------- */
  var ov = document.createElement("div");
  ov.id = "outfit-view"; ov.className = "outfit-view"; ov.hidden = true;
  ov.setAttribute("role", "dialog"); ov.setAttribute("aria-modal", "true"); ov.setAttribute("aria-labelledby", "ov-title");
  ov.innerHTML = '<div class="ov-top"><button type="button" class="ov-close" id="ov-close" aria-label="Close">×</button><h2 class="ov-title" id="ov-title"></h2></div>' +
    '<div class="ov-scroll" id="ov-scroll"><div class="ov-figure" id="ov-figure"><img id="ov-img" alt="" decoding="async" /></div>' +
    '<div class="ov-acts" id="ov-acts"><button type="button" class="hero-icon-btn thumb-btn" id="ov-like" aria-pressed="false" aria-label="Like">Like</button><button type="button" class="hero-icon-btn thumb-btn thumb-down" id="ov-dislike" aria-label="Dislike — remove this look">Dislike</button><button type="button" class="hero-icon-btn" id="ov-next" aria-label="Next look">Next</button></div>' +
    '<h3 class="ov-head">In this look</h3><ul class="ov-pieces" id="ov-pieces"></ul></div>';
  document.body.appendChild(ov);
  var ovOpen = false, ovLook = null, ovFromHome = true;
  function pieceRows(look) {
    return piecesOf(look).map(function (p) {
      var ph = photoOf(p), br = brandOf(p);
      return '<li><button type="button" class="ov-piece" data-ov-item="' + esc(p.id) + '">' +
        '<span class="ov-pph">' + (ph ? '<img src="' + esc(ph) + '" alt="" loading="lazy" decoding="async" />' : '<span class="ov-sw" style="background:' + esc(p.colourHex || "#d9cfbd") + '"></span>') + "</span>" +
        '<span class="ov-pt">' + (br ? '<span class="ov-pb">' + esc(br) + "</span>" : "") + '<span class="ov-pn">' + esc(p.name || "") + "</span></span>" +
        '<span class="ov-chev" aria-hidden="true">›</span></button></li>';
    }).join("");
  }
  window.outfitPieceRows782 = pieceRows; window.renderFor782 = renderFor; window.fillOutfitView782 = function () { if (ovOpen) fillView(); };
  function fillView() {
    var look = ovFromHome && typeof todayLook !== "undefined" ? todayLook : ovLook;
    if (!look) return;
    var src0 = renderFor(look) || (typeof lookImg === "function" ? lookImg(look) : "");
    var src = (typeof window.cutFor784 === "function" && window.cutFor784(src0)) || src0;
    var fig0 = document.getElementById("ov-figure"); if (fig0) fig0.classList.toggle("has-cut", src !== src0);
    var im = document.getElementById("ov-img"), prev = im.getAttribute("src");
    if (prev !== src) {
      if (prev && ovOpen) { im.classList.add("swap"); setTimeout(function () { im.setAttribute("src", src); im.classList.remove("swap"); }, 180); }
      else im.setAttribute("src", src);
    }
    im.alt = (look.title || "Outfit") + " on David";
    /* .79.3: the full view swaps to the full-resolution cut-out (cut from
       the original render, assets/onbody-cut-hq/) once it has loaded and
       decoded — fetched only here, on demand */
    if (src !== src0 && /\/onbody-cut\//.test(src) || /^assets\/onbody-cut\//.test(src)) {
      var hq = src.replace("onbody-cut/", "onbody-cut-hq/"), t = new Image(); t.decoding = "async";
      t.onload = function () { var p = t.decode ? t.decode() : Promise.resolve(); p.catch(function () {}).then(function () { var cur = im.getAttribute("src"); if (ovOpen && (cur === src || cur === null)) im.setAttribute("src", hq); }); };
      t.src = hq;
    }
    sampleBg(src0, document.getElementById("ov-figure"));
    document.getElementById("ov-title").textContent = look.title || "Outfit";
    document.getElementById("ov-pieces").innerHTML = pieceRows(look);
    var lk = document.getElementById("today-like");
    document.getElementById("ov-like").setAttribute("aria-pressed", lk ? lk.getAttribute("aria-pressed") || "false" : "false");
    document.getElementById("ov-acts").hidden = !ovFromHome;
  }
  var ovKey = "";
  function viewKey() { var look = ovFromHome && typeof todayLook !== "undefined" ? todayLook : ovLook; return look ? (look.composerKey || look.id || look.title || "") + "|" + ovFromHome : ""; }
  function openView(look, fromHome) {
    ovFromHome = fromHome !== false; ovLook = look || null;
    ovOpen = true;
    /* .79.4: the view was pre-built (and its images decoded) on idle after
       the hero painted — opening only unhides it and slides it in */
    if (ovKey !== viewKey()) fillView(); else { var lk = document.getElementById("today-like"); document.getElementById("ov-like").setAttribute("aria-pressed", lk ? lk.getAttribute("aria-pressed") || "false" : "false"); }
    ovKey = "";
    ov.classList.remove("ov-in"); ov.hidden = false;
    ov.classList.add("ov-in");
    /* reading scrollTop would force a layout of the whole view: only a view
       he scrolled last time is put back to the top */
    var sc = document.getElementById("ov-scroll"); if (sc && sc.__scrolled) { sc.scrollTop = 0; sc.__scrolled = false; }
    if (sc && !sc.__wired) { sc.__wired = true; sc.addEventListener("scroll", function () { sc.__scrolled = true; }, { passive: true }); }
    /* page-level class + focus after the first frame is on screen */
    requestAnimationFrame(function () { setTimeout(function () {
      if (!ovOpen) return; document.body.classList.add("ov-open");
      var c = document.getElementById("ov-close"); if (c) try { c.focus({ preventScroll: true }); } catch (e) {}
    }, 260); });
  }
  ov.addEventListener("animationend", function () { ov.classList.remove("ov-in"); });
  /* pre-build the outfit view for the look on Home, off-screen, on idle */
  var pwT = null;
  function prewarmView() {
    clearTimeout(pwT);
    pwT = setTimeout(function () {
      (window.requestIdleCallback || function (f) { return setTimeout(f, 200); })(function () {
        try {
          if (ovOpen || typeof todayLook === "undefined" || !todayLook) return;
          var keep = ovFromHome; ovFromHome = true;
          if (ovKey !== viewKey()) { fillView(); ovKey = viewKey(); }
          ovFromHome = keep;
          var im = document.getElementById("ov-img"), src = im.getAttribute("src") || "";
          var hq = /\/onbody-cut\//.test(src) || /^assets\/onbody-cut\//.test(src) ? src.replace("onbody-cut/", "onbody-cut-hq/") : "";
          if (hq) { var t = new Image(); t.decoding = "async"; t.src = hq; (t.decode ? t.decode() : Promise.resolve()).then(function () { if (!ovOpen && im.getAttribute("src") === src) im.setAttribute("src", hq); }).catch(function () {}); }
          if (im.decode) im.decode().catch(function () {});
          document.querySelectorAll("#ov-pieces img").forEach(function (x) { x.decoding = "async"; if (x.decode) x.decode().catch(function () {}); });
        } catch (e) {}
      }, { timeout: 1500 });
    }, 400);
  }
  window.prewarmOutfitView794 = prewarmView;
  /* .79.4: the Outfits feed is built once on idle a few seconds after the
     hero, so the first visit to Outfits only shows it */
  setTimeout(function () {
    (window.requestIdleCallback || function (f) { return setTimeout(f, 300); })(function () {
      try {
        var g = document.getElementById("cf-grid");
        if (g && !g.children.length && typeof window.composerSyncFeed === "function" && !(typeof currentTab !== "undefined" && currentTab === "looks")) window.composerSyncFeed(true);
      } catch (e) {}
    }, { timeout: 4000 });
  }, 3500);
  /* .79.4: every image the app writes decodes off the main thread */
  if ("MutationObserver" in window) {
    var asyncImgs = function (root) { if (root.tagName === "IMG") { if (!root.hasAttribute("decoding")) root.decoding = "async"; return; } if (root.querySelectorAll) root.querySelectorAll("img:not([decoding])").forEach(function (x) { x.decoding = "async"; }); };
    asyncImgs(document.body);
    new MutationObserver(function (ms) { for (var i = 0; i < ms.length; i++) { var a = ms[i].addedNodes; for (var j = 0; j < a.length; j++) if (a[j].nodeType === 1) asyncImgs(a[j]); } }).observe(document.body, { childList: true, subtree: true });
  }
  function closeView() { if (!ovOpen) return; ovOpen = false; ov.hidden = true; document.body.classList.remove("ov-open"); }
  window.openOutfitView = openView; window.closeOutfitView = closeView;
  ov.addEventListener("click", function (e) {
    var t = e.target; if (!t || !t.closest) return;
    if (t.closest("#ov-close")) { closeView(); return; }
    if (t.closest("#ov-like")) { var l = document.getElementById("today-like"); if (l) l.click(); setTimeout(fillView, 60); return; }
    if (t.closest("#ov-dislike")) { var d = document.getElementById("today-dislike"); if (d) d.click(); setTimeout(fillView, 60); return; }
    if (t.closest("#ov-next")) { var n = document.getElementById("today-next"); if (n) n.click(); setTimeout(fillView, 60); return; }
    var b = t.closest("[data-ov-item]");
    if (b) {
      var iid = b.getAttribute("data-ov-item");
      if (typeof closetItemById === "function" && closetItemById(iid) && typeof switchTab === "function") {
        closeView();
        if (typeof lookLayerOpen !== "undefined" && lookLayerOpen && typeof closeLookLayer === "function") closeLookLayer();
        detailItemId = iid; switchTab("wardrobe");
        if (typeof renderItemDetail === "function") renderItemDetail();
        var dt = document.getElementById("item-detail"); if (dt && dt.scrollIntoView) try { dt.scrollIntoView({ block: "start" }); } catch (x) {}
      }
    }
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && ovOpen) closeView(); });

  /* tap him (or the title) → the outfit view; a swipe still deals */
  var tx = 0, ty = 0, moved = 0, tEnd = 0;
  hero.addEventListener("touchstart", function (e) { if (e.touches.length === 1) { tx = e.touches[0].clientX; ty = e.touches[0].clientY; moved = 0; } }, { passive: true, capture: true });
  hero.addEventListener("touchend", function (e) { if (e.changedTouches.length) { var dx = e.changedTouches[0].clientX - tx, dy = e.changedTouches[0].clientY - ty; moved = Math.sqrt(dx * dx + dy * dy); tEnd = Date.now(); } }, { passive: true, capture: true });
  hero.addEventListener("click", function (e) {
    var t = e.target; if (!t || !t.closest) return;
    var onTitle = t.closest("#today-name");
    if (!onTitle && (t.closest(".today-caption") || t.closest(".hero-corner"))) return;
    if (Date.now() - tEnd < 600 && moved > 40) return;
    if (typeof todayLook === "undefined" || !todayLook) return;
    e.stopImmediatePropagation(); e.preventDefault();
    openView(todayLook, true);
  }, true);

  try { soloHero(); } catch (e) {}
})();
    