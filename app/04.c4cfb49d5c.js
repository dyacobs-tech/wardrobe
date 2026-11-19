
"use strict";
/* ================= Narrow redo — pop-out, verdict,
   Studio outfit type ================= */

/* ---------- Item 1: one shared full-size photo pop-out ---------- */
var popoutEl = document.getElementById("photo-popout");
var popoutImg = document.getElementById("popout-img");
var popoutCloseBtn = document.getElementById("popout-close");
/* Anchor the close button to the displayed photo's own top-right corner
   (the img is object-fit: contain, so the photo is letterboxed inside the
   full-viewport img box). Its top is clamped so it never rises into the
   Dynamic Island / status-bar zone: max(photo top + inset, safe-area + 8). */
function placePopoutClose() {
  if (!popoutCloseBtn || !popoutEl || popoutEl.hidden || !popoutImg.naturalWidth || !popoutImg.naturalHeight) return;
  var vw = popoutEl.clientWidth, vh = popoutEl.clientHeight;
  var scale = Math.min(vw / popoutImg.naturalWidth, vh / popoutImg.naturalHeight);
  var dispW = popoutImg.naturalWidth * scale;
  var dispH = popoutImg.naturalHeight * scale;
  var photoTop = (vh - dispH) / 2;
  var photoRightInset = (vw - dispW) / 2;
  popoutCloseBtn.style.top = "max(" + (photoTop + 10).toFixed(1) + "px, calc(env(safe-area-inset-top, 0px) + 8px))";
  popoutCloseBtn.style.right = (photoRightInset + 10).toFixed(1) + "px";
}
if (popoutImg) popoutImg.addEventListener("load", placePopoutClose);
window.addEventListener("resize", placePopoutClose);
function openPopout(src, alt) {
  if (!src || !popoutEl) return;
  popoutImg.src = src;
  popoutImg.alt = alt || "";
  popoutEl.hidden = false;
  document.body.style.overflow = "hidden";
  placePopoutClose();
}
function closePopout() {
  if (!popoutEl) return;
  popoutEl.hidden = true;
  popoutImg.removeAttribute("src");
  document.body.style.overflow = "";
}
window.openPopout = openPopout;
document.addEventListener("click", function (e) {
  var t = e.target && e.target.closest ? e.target.closest("[data-popout]") : null;
  if (!t) return;
  var srcAttr = t.getAttribute("data-popout");
  if (!srcAttr) return;
  e.preventDefault();
  e.stopPropagation();
  openPopout(srcAttr, t.getAttribute("data-popout-alt") || t.getAttribute("alt") || "");
}, true);
if (popoutEl) popoutEl.addEventListener("click", closePopout);
document.addEventListener("keydown", function (e) { if (e.key === "Escape" && popoutEl && !popoutEl.hidden) closePopout(); });

/* Today hero: tapping the photo itself (not the caption controls)
   opens the pop-out; a swipe still deals / likes as before. */
var heroEl = document.getElementById("today-hero");
if (heroEl) {
  var htX = 0, htY = 0, htDist = 0, htEnd = 0;
  heroEl.addEventListener("touchstart", function (e) {
    if (e.touches.length === 1) { htX = e.touches[0].clientX; htY = e.touches[0].clientY; htDist = 0; }
  }, { passive: true });
  heroEl.addEventListener("touchend", function (e) {
    if (e.changedTouches.length) {
      var dx = e.changedTouches[0].clientX - htX, dy = e.changedTouches[0].clientY - htY;
      htDist = Math.sqrt(dx * dx + dy * dy);
      htEnd = Date.now();
    }
  }, { passive: true });
  heroEl.addEventListener("click", function (e) {
    if (Date.now() - htEnd < 600 && htDist > 40) return;
    if (e.target.closest && e.target.closest(".today-caption")) return;
    if (e.target.closest && e.target.closest(".hero-corner")) return;
    if (e.target.closest && e.target.closest("[data-popout]")) return;
    if (typeof todayLook !== "undefined" && todayLook) {
      /* The pop-out is the look's OWN image — the render of him
         wearing the outfit that the hero is displaying (lookImg
         resolves fwRender first). Never a piece photograph:
         piece photos live on Closet / item pages only. */
      var popSrc = lookImg(todayLook);
      openPopout(popSrc, todayLook.imgAlt || "");
    }
  });
}

/* ---------- Item 2: Don't like it — dislike + remove + undo + new deal ---------- */
var dislikeBtn = document.getElementById("today-dislike");
if (dislikeBtn) dislikeBtn.addEventListener("click", function () {
  if (!todayLook) return;
  var look = JSON.parse(JSON.stringify(todayLook));
  look.verdict = "dislike";
  recordDislike(lookImg(look));
  registerRemoved(look, lookImg(look));
  savedLooks = savedLooks.filter(function (l) { return l.id !== look.id; });
  queueLooks = queueLooks.filter(function (x) { return x.id !== look.id; });
  saveQueue();
  persistAll();
  renderSaved();
  if (typeof dealAnotherToday === "function") dealAnotherToday();
});

/* A chosen watch is the watch the look wears: the wrist call
   honours the pick instead of re-deriving one. */
var _origRecommendWatch = recommendWatch;
recommendWatch = function (look) {
  if (look && look.watchId === "none") {
    return { watch: null, metalAdvice: "", reasons: [] };
  }
  if (look && look.watchId) {
    var picked = null;
    watches.forEach(function (w) { if (w.id === look.watchId && !w.sold) picked = w; });
    if (picked) return { watch: picked, metalAdvice: "", reasons: [{ k: "Your pick", t: "You chose this watch for this look." }] };
  }
  return _origRecommendWatch(look);
};

/* ---------- Item 6 refinement: outfit-type boxes under Deal ---------- */
function syncStudioType() {
  document.querySelectorAll("[data-studio-type]").forEach(function (b) {
    b.setAttribute("aria-pressed", parseInt(b.getAttribute("data-studio-type"), 10) === formalityLevel ? "true" : "false");
  });
}
var _origRenderFormality = window.renderFormality;
if (typeof _origRenderFormality === "function") {
  window.renderFormality = function () { _origRenderFormality(); syncStudioType(); };
}
var studioTypeRow = document.getElementById("studio-type-row");
if (studioTypeRow) studioTypeRow.addEventListener("click", function (e) {
  var b = e.target.closest ? e.target.closest("[data-studio-type]") : null;
  if (!b) return;
  setFormality(parseInt(b.getAttribute("data-studio-type"), 10));
});
syncStudioType();

/* ---------- Studio Ideas — slim closed selectors ----------
   Dress-for and Outfit type live behind two slim rows under the
   primary button. A tap opens that row's options beneath it (the
   other row closes); a pick applies silently and closes the row —
   the row's label is the only feedback. The underlying behaviour is
   unchanged: Dress-for still drives applyDressFor (occasion +
   formality), Outfit type still drives setFormality, so ideas land
   exactly at the chosen type. "Any" clears Dress-for, and returns
   Outfit type to the default range (the meter resting at Smart
   Casual). */
var studioTypeAny = false;
var STUDIO_TYPE_LABELS = ["Swim/Pool", "Shorts & Tee", "Casual", "Smart Casual", "Business Casual", "Formal", "Black Tie"];
function closeStudioSel(which) {
  [["dress-sel-toggle", "dress-for"], ["type-sel-toggle", "studio-type-row"]].forEach(function (pair) {
    if (which && pair[1] !== which) return;
    var t = document.getElementById(pair[0]), o = document.getElementById(pair[1]);
    if (o) o.hidden = true;
    if (t) t.setAttribute("aria-expanded", "false");
  });
}
function syncStudioSelectors() {
  var dv = document.getElementById("dress-sel-val");
  if (dv) dv.textContent = (typeof dressForKey !== "undefined" && dressForKey && typeof DRESS_FOR !== "undefined" && DRESS_FOR[dressForKey]) ? DRESS_FOR[dressForKey].label : "Any";
  var anyDress = document.querySelector("[data-dress-any]");
  if (anyDress) anyDress.setAttribute("aria-pressed", (typeof dressForKey !== "undefined" && dressForKey) ? "false" : "true");
  var typeName = studioTypeAny ? "Any" : (STUDIO_TYPE_LABELS[formalityLevel - 1] || "Smart Casual");
  var tv = document.getElementById("type-sel-val");
  if (tv) tv.textContent = typeName;
  var iv = document.getElementById("ideas-type-label");
  if (iv) iv.textContent = typeName;
  document.querySelectorAll("[data-studio-type-any]").forEach(function (anyType) {
    anyType.setAttribute("aria-pressed", studioTypeAny ? "true" : "false");
  });
  if (studioTypeAny) {
    document.querySelectorAll("[data-studio-type]").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
  }
}
var _origApplyDressFor2 = applyDressFor;
applyDressFor = function (key, silent) {
  _origApplyDressFor2(key, silent);
  if (key) studioTypeAny = false;
  syncStudioSelectors();
};
var _origRenderFormality2 = window.renderFormality;
if (typeof _origRenderFormality2 === "function") {
  window.renderFormality = function () { _origRenderFormality2(); syncStudioSelectors(); };
}
[["dress-sel-toggle", "dress-for"], ["type-sel-toggle", "studio-type-row"]].forEach(function (pair) {
  var t = document.getElementById(pair[0]), o = document.getElementById(pair[1]);
  if (!t || !o) return;
  t.addEventListener("click", function () {
    var willOpen = o.hidden;
    closeStudioSel();
    if (willOpen) { o.hidden = false; t.setAttribute("aria-expanded", "true"); }
  });
});
var dressOptsEl = document.getElementById("dress-for");
if (dressOptsEl) dressOptsEl.addEventListener("click", function (e) {
  var anyBtn = e.target.closest ? e.target.closest("[data-dress-any]") : null;
  if (anyBtn) {
    applyDressFor("", true);
    var occ = document.getElementById("occasion");
    if (occ) occ.value = "";
    saveStudioSettings();
  }
  closeStudioSel();
  syncStudioSelectors();
});
if (studioTypeRow) studioTypeRow.addEventListener("click", function (e) {
  var anyBtn = e.target.closest ? e.target.closest("[data-studio-type-any]") : null;
  if (anyBtn) {
    studioTypeAny = true;
    setFormality(4, { silent: true });
  } else if (e.target.closest && e.target.closest("[data-studio-type]")) {
    studioTypeAny = false;
  }
  closeStudioSel();
  syncStudioSelectors();
});
syncStudioSelectors();

/* ---------- Build .50: Outfit type row on the Ideas deal surface ----------
   The same pills, on the surface where deals happen: they carry
   the same data-studio-type / data-studio-type-any attributes,
   so setFormality drives them and syncStudioType (hooked into
   renderFormality) plus syncStudioSelectors keep every selector
   — this row, the Customize row, the Today dropdown, a brief's
   parsed level — showing the ONE state. A pick re-deals the
   Ideas grid at once when a deal is showing, through the same
   dealIdeasForSource path the source seg uses; otherwise it
   simply constrains the next deal. A manual pick after a brief
   deal wins over the brief's level, exactly as in Customize. */
var ideasTypeRow = document.getElementById("ideas-type-row");
if (ideasTypeRow) ideasTypeRow.addEventListener("click", function (e) {
  var anyBtn = e.target.closest ? e.target.closest("[data-studio-type-any]") : null;
  if (anyBtn) {
    studioTypeAny = true;
    setFormality(4, { silent: true });
  } else {
    var b = e.target.closest ? e.target.closest("[data-studio-type]") : null;
    if (!b) return;
    studioTypeAny = false;
    setFormality(parseInt(b.getAttribute("data-studio-type"), 10));
  }
  syncStudioSelectors();
  if (typeof currentOptions !== "undefined" && currentOptions && currentOptions.length &&
      typeof window.dealIdeasForSource === "function") window.dealIdeasForSource();
});
    