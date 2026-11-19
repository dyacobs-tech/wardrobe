
/* Build .78.6b — one sheet manager. Watches every pop-out; while any is
   open the page behind is locked (body fixed at its scroll offset, put
   back exactly on close) and the nav is tucked away. Swipe down on a
   sheet whose content is at the top closes it. Listeners are passive;
   the drag only writes a transform. */
(function () {
  var root = document.documentElement, lockedY = null;
  function itemOpen() { var d = document.getElementById("item-detail"); return !!(d && d.firstElementChild); }
  function iconOpen() { var d = document.getElementById("icon-detail"); return !!(d && !d.hidden && d.firstElementChild && document.getElementById("panel-icons") && !document.getElementById("panel-icons").hidden); }
  function sheets() {
    var out = [];
    document.querySelectorAll(".info-pop-backdrop:not([hidden])").forEach(function (b) { out.push({ el: b.querySelector(".info-pop-card, .principles") || b, close: function () { var x = b.querySelector(".info-pop-close"); if (x) x.click(); else b.hidden = true; } }); });
    var ll = document.getElementById("look-layer"); if (ll && !ll.hidden) out.push({ el: ll, close: function () { var x = document.getElementById("look-layer-close"); if (x) x.click(); } });
    var ov = document.getElementById("outfit-view"); if (ov && !ov.hidden) out.push({ el: document.getElementById("ov-scroll") || ov, close: function () { var x = document.getElementById("ov-close"); if (x) x.click(); } });
    if (itemOpen()) out.push({ el: document.querySelector("#item-detail > .item-detail-card"), close: function () { var x = document.querySelector('#item-detail [data-item-act="close"]'); if (x) x.click(); } });
    if (iconOpen()) out.push({ el: document.querySelector("#icon-detail > .icon-detail-card"), close: function () { var x = document.querySelector("#icon-detail [data-back-icons]"); if (x) x.click(); } });
    document.querySelectorAll(".cdd-menu:not([hidden]):not(#today-type-row)").forEach(function (m) { out.push({ el: m, close: function () { if (typeof closeAllCdd === "function") closeAllCdd(); else m.hidden = true; } }); });
    /* only sheets actually on screen — an item sheet left open on a tab
       the user has switched away from must not keep the page locked */
    return out.filter(function (x) { return x.el && x.el.getClientRects().length > 0; });
  }
  window.openSheets782 = sheets;
  function lock() {
    if (lockedY !== null) return;
    lockedY = window.scrollY || 0;
    root.style.setProperty("--lock-top", (-lockedY) + "px");
    root.classList.add("sheet-lock");
  }
  function unlock() {
    if (lockedY === null) return;
    var y = lockedY; lockedY = null;
    root.classList.remove("sheet-lock"); root.style.removeProperty("--lock-top");
    window.scrollTo(0, y);
    requestAnimationFrame(function () { if (Math.abs((window.scrollY || 0) - y) > 2 && lockedY === null) window.scrollTo(0, y); });
    if (typeof window.__navShow === "function") window.__navShow();
  }
  window.sheetLockedY782 = function () { return lockedY; };
  function decorate() {
    /* a sticky × on the item and icon sheets (their own Close / back stay too) */
    var card = document.querySelector("#item-detail > .item-detail-card");
    if (card && !card.querySelector(".sheet-x")) card.insertAdjacentHTML("afterbegin", '<button type="button" class="sheet-x" data-item-act="close" aria-label="Close">&times;</button>');
    var llb = document.querySelector("#look-layer .look-layer-bar");
    if (llb && !llb.querySelector(".sheet-x")) {
      llb.insertAdjacentHTML("beforeend", '<button type="button" class="sheet-x" aria-label="Close">&times;</button>');
      llb.querySelector(".sheet-x").addEventListener("click", function () { var b = document.getElementById("look-layer-close"); if (b) b.click(); });
    }
    document.querySelectorAll(".cdd-menu:not([hidden]):not(#today-type-row)").forEach(function (m) {
      if (m.querySelector(":scope > .sheet-x")) return;
      m.insertAdjacentHTML("afterbegin", '<button type="button" class="sheet-x cdd-x" aria-label="Close">&times;</button>');
    });
    var ic = document.getElementById("icon-detail");
    if (ic) {
      var on = iconOpen(); ic.classList.toggle("sheet782-on", on);
      var icard = ic.querySelector(".icon-detail-card");
      if (on && icard && !icard.querySelector(".sheet-x")) {
        icard.insertAdjacentHTML("afterbegin", '<button type="button" class="sheet-x" aria-label="Close">&times;</button>');
        icard.querySelector(".sheet-x").addEventListener("click", function () { var b = ic.querySelector("[data-back-icons]"); if (b) b.click(); });
      }
      /* the list stays behind the sheet */
      if (on) ["icon-list-view", "icon-search-card", "icon-form"].forEach(function (id) { var e = document.getElementById(id); if (e) e.hidden = false; });
    }
  }
  var pending = false;
  /* .79.4: checked once per frame (not on every DOM change in a microtask,
     which forced a layout mid-update); the full-screen outfit view locks
     the page only after its slide-in, so the open frame never re-lays
     out the whole page */
  var lockT = null;
  function sync() {
    pending = false;
    decorate();
    var list = sheets();
    if (list.length) {
      var ovOnly = list.every(function (x) { return x.el && x.el.closest && x.el.closest("#outfit-view"); });
      if (ovOnly && lockedY === null) { clearTimeout(lockT); lockT = setTimeout(function () { if (sheets().length) lock(); }, 320); }
      else { clearTimeout(lockT); lock(); }
    } else { clearTimeout(lockT); unlock(); }
  }
  function soon() { if (!pending) { pending = true; requestAnimationFrame(sync); } }
  new MutationObserver(soon).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["hidden"], childList: true });
  /* tap on the dim backdrop of the item / icon sheet closes it */
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (t && t.closest && t.closest(".cdd-x")) { e.stopPropagation(); if (typeof closeAllCdd === "function") closeAllCdd(); return; }
    if (t && (t.id === "item-detail" || (t.id === "icon-detail" && t.classList.contains("sheet782-on")))) {
      var x = t.querySelector('[data-item-act="close"], [data-back-icons]'); if (x) x.click();
    }
  });
  /* swipe down to close */
  var drag = null;
  document.addEventListener("touchstart", function (e) {
    if (e.touches.length !== 1) return;
    var list = sheets(); if (!list.length) return;
    var top = list[list.length - 1], el = top.el;
    if (!el.contains(e.target)) return;
    var sc = e.target.closest ? e.target.closest("[data-sheet-scroll], .ov-scroll, .look-layer-body") : null;
    if ((el.scrollTop || 0) > 0 || (sc && sc.scrollTop > 0)) return;
    drag = { el: el, y0: e.touches[0].clientY, dy: 0, close: top.close };
  }, { passive: true });
  document.addEventListener("touchmove", function (e) {
    if (!drag) return;
    drag.dy = Math.max(0, e.touches[0].clientY - drag.y0);
    if (drag.dy > 6) { drag.el.classList.add("sheet-drag"); drag.el.style.transform = "translate3d(0," + drag.dy + "px,0)"; }
  }, { passive: true });
  function end() {
    if (!drag) return;
    var d = drag; drag = null;
    d.el.classList.remove("sheet-drag");
    if (d.dy > 90) { d.el.style.transform = ""; d.close(); return; }
    if (d.dy > 6) { d.el.classList.add("sheet-snap"); d.el.style.transform = ""; setTimeout(function () { d.el.classList.remove("sheet-snap"); }, 260); }
  }
  document.addEventListener("touchend", end, { passive: true });
  document.addEventListener("touchcancel", end, { passive: true });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { var l = sheets(); if (l.length) l[l.length - 1].close(); } });
  sync();
})();
    