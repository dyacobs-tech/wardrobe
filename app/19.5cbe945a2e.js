
/* ================= Build .79.6 — Outfits toggles are instant =================
   Mine / Inspo and the Inspo pages (On you, Icons, Palettes, Saved) used to
   rebuild their whole list on every tap. Each list is now built once (on idle
   after boot, or the first time it is needed) and kept mounted; a toggle only
   flips aria-pressed and the hidden attribute, synchronously. A list is built
   again only when his data changed since it was last built (any write to his
   stored closet, looks, likes, inspo...), and then after the new state has
   painted, never inside the tap. UI-only keys (current tab, Home's hero
   cache) don't count as changes. */
(function () {
  "use strict";
  var ver = 1;
  var IGN = /^wardrobe\.(tab|editView|hero793|lq793|navDiag\.|dealtImgs|todayOpening|scroll|perf)/;
  var _set = Storage.prototype.setItem, _rm = Storage.prototype.removeItem, _clr = Storage.prototype.clear;
  Storage.prototype.setItem = function (k) { if (this === window.localStorage && !IGN.test(String(k))) ver++; return _set.apply(this, arguments); };
  Storage.prototype.removeItem = function (k) { if (this === window.localStorage && !IGN.test(String(k))) ver++; return _rm.apply(this, arguments); };
  Storage.prototype.clear = function () { ver++; return _clr.apply(this, arguments); };
  window.outfitsDirty796 = function () { ver++; };
  var ric = window.requestIdleCallback ? function (f, o) { return window.requestIdleCallback(f, o); } : function (f) { return setTimeout(function () { f({ timeRemaining: function () { return 50; } }); }, 200); };
  var seen = {};
  var VIEWS = { mine: "renderSaved", onyou: "renderInspoOnYou", icons: "renderIcons", palettes: "renderPlates", myinspo: "renderMyInspo" };
  function wrap(n) {
    var f = window[n];
    if (typeof f !== "function" || f.__w796) return;
    var w = function () { var r = f.apply(this, arguments); seen[n] = ver; return r; };
    w.__w796 = 1; w.__orig = f;
    window[n] = w;
  }
  Object.keys(VIEWS).forEach(function (k) { wrap(VIEWS[k]); });
  function fresh(n) { return seen[n] === ver; }
  function build(n) { var f = window[n]; if (typeof f === "function") { try { f(); } catch (e) {} } }
  /* after the new state has painted: one frame, then a task */
  function later(fn) { requestAnimationFrame(function () { setTimeout(fn, 0); }); }
  function ensureSoon(n) { if (!fresh(n)) later(function () { if (!fresh(n)) build(n); }); }

  window.syncOutfitsToggle = function () {
    var isMine = window.outfitsMode !== "inspo";
    var mine = document.getElementById("outfits-mine"), inspo = document.getElementById("outfits-inspo");
    var mv = document.getElementById("outfits-mine-view"), iv = document.getElementById("outfits-inspo-view");
    var osh = document.getElementById("outfits-shuffle");
    if (mine) mine.setAttribute("aria-pressed", isMine ? "true" : "false");
    if (inspo) inspo.setAttribute("aria-pressed", isMine ? "false" : "true");
    if (mv) mv.hidden = !isMine;
    if (osh) osh.hidden = !isMine;
    if (iv) iv.hidden = isMine;
    if (isMine) ensureSoon("renderSaved");
    else window.showInspoView(window.inspoView || "icons");
    if (typeof composerSyncFeed === "function") composerSyncFeed(false);
    window.prelayOutfits796();
  };
  window.showInspoView = function (v) {
    var host = document.getElementById("inspo-host");
    if (!host) return;
    window.inspoView = v;
    ["onyou", "icons", "palettes", "myinspo"].forEach(function (n) {
      var pn = document.getElementById("panel-" + n);
      if (!pn) return;
      if (pn.parentNode !== host) host.appendChild(pn);
      if (pn.hidden !== (n !== v)) pn.hidden = n !== v;
    });
    document.querySelectorAll("[data-inspo-view]").forEach(function (b) {
      var on = b.getAttribute("data-inspo-view") === v ? "true" : "false";
      if (b.getAttribute("aria-pressed") !== on) b.setAttribute("aria-pressed", on);
    });
    if (VIEWS[v]) ensureSoon(VIEWS[v]);
  };
  /* while Outfits is on screen, lay out the views he is not looking at once, after paint */
  var laid = {};
  function prelay() {
    var pl = document.getElementById("panel-looks");
    if (!pl || pl.hidden) return;
    ["outfits-mine-view", "outfits-inspo-view", "panel-onyou", "panel-icons", "panel-palettes", "panel-myinspo"].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el || !el.hidden || laid[id] === ver) return;
      if (id.indexOf("panel-") === 0 && el.parentNode && el.parentNode.id !== "inspo-host") return;
      laid[id] = ver;
      el.classList.add("pl796"); void el.offsetHeight; el.classList.remove("pl796");
    });
  }
  window.prelayOutfits796 = function () { later(function () { ric(prelay, { timeout: 1500 }); }); };
  /* build every list once on idle after boot, one per idle slot */
  var order = ["mine", "icons", "onyou", "myinspo", "palettes"];
  function step() {
    var k = order.shift();
    if (!k) return;
    var n = VIEWS[k];
    if (!fresh(n)) build(n);
    ric(step, { timeout: 4000 });
  }
  setTimeout(function () { ric(step, { timeout: 4000 }); }, 4500);
})();
    