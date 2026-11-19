
/* ================= Build .78.5 — Shop, Vesper style: one product card + one product sheet =================
   vpCardHTML(e, opts) is the single product card: cream studio image,
   brand in small caps, a two-line name, price, one muted retailer line
   and a compact icon row (wishlist, purchased, style this, see it on
   me, buy). Tapping the card opens #vp-sheet — the big image, the
   details, Buy at the retailer and the same actions with labels, plus
   See it on me rendered inline. Every action calls the app's existing
   functions (toggleWishlistItem, toggleShopPurchase,
   buildAroundShopEntry, tryonJob), and every card for the same product
   updates at once. */
var VP = {};
var VP_ICON = {
  heart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20.2s-7.6-4.6-9.3-9.2C1.6 7.8 3.7 4.6 7 4.6c2.1 0 3.6 1.2 5 3 1.4-1.8 2.9-3 5-3 3.3 0 5.4 3.2 4.3 6.4-1.7 4.6-9.3 9.2-9.3 9.2z"/></svg>',
  bag: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 8h14l-1 12.2H6z"/><path d="M8.6 8V6.8a3.4 3.4 0 0 1 6.8 0V8"/><path class="vp-chk" d="M9.2 14.2l2 2 3.8-4"/></svg>',
  hanger: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8.4V7.6a2.1 2.1 0 1 0-2.1-2.1"/><path d="M12 8.4l-8.6 6.4c-.9.7-.4 2.1.7 2.1h15.8c1.1 0 1.6-1.4.7-2.1z"/></svg>',
  person: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="7.2" r="3.2"/><path d="M5.2 20.4c.6-4 3.3-6.4 6.8-6.4s6.2 2.4 6.8 6.4"/></svg>',
  ext: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.5 4.5h6v6"/><path d="M19.5 4.5l-8.2 8.2"/><path d="M17.5 13.6v4.4a1.5 1.5 0 0 1-1.5 1.5H6a1.5 1.5 0 0 1-1.5-1.5V8a1.5 1.5 0 0 1 1.5-1.5h4.4"/></svg>',
  search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.6" cy="10.6" r="6.1"/><path d="M15.2 15.2l4.6 4.6"/></svg>',
  check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5.5 12.5l4.2 4.2 8.8-9.4"/></svg>'
};
function vpKey(e) { return e ? (e.key || shopEntryKey(e)) : ""; }
function vpName(e) {
  var nm = String((e && e.name) || ""), br = String((e && e.brand) || "");
  if (br && nm.toLowerCase().indexOf(br.toLowerCase()) === 0 && nm.length > br.length + 3) nm = nm.slice(br.length).replace(/^[\s\-\u2013\u2014:|,]+/, "");
  return nm ? nm.charAt(0).toUpperCase() + nm.slice(1) : "";
}
function vpPrice(e) {
  if (e && e.pd) return String(e.pd);
  var p = (typeof prNum === "function") ? prNum(e && e.price) : (e && e.price);
  return p ? "$" + Number(p).toLocaleString("en-US", { minimumFractionDigits: p % 1 ? 2 : 0, maximumFractionDigits: p % 1 ? 2 : 0 }) : "";
}
function vpRetailer(e) { return String((e && (e.retailer || e.store)) || ""); }
/* A snap whose name was tidied keeps its original key; the app's
   shop functions key by brand|name|url, so hand them that shape. */
function vpEntryFor(e) {
  if (!e || !e.key || shopEntryKey(e) === e.key) return e;
  var parts = String(e.key).split("|");
  if (parts.length < 3) return e;
  return Object.assign({}, e, { brand: parts[0], name: parts.slice(1, -1).join("|"), url: parts[parts.length - 1], retailer: e.retailer || e.store || "" });
}
function vpWished(e) { return typeof wishlistFor === "function" && !!wishlistFor(vpKey(e)); }
function vpBought(e) { return typeof shopPurchaseFor === "function" && !!shopPurchaseFor(vpKey(e)); }
/* opts: { pc, tag, picked, pick: { idx }, edit, overlay } — pick makes
   the card a choice for a Shop the look piece; edit makes it The
   Edit's card (heart = Save with its shortlist, + Look on the photo,
   Star / Not for me in the sheet), worked by The Edit's own handlers. */
/* A photo for a product that arrived without one (an old saved
   item): the same product in the catalogue, by URL. */
var vpPhotoIdx = null, vpPhotoIdxN = -1;
function vpPhotoFor(e) {
  if (prodHasPhoto(e)) return e.img;
  if (!e || !e.url || typeof shopCatalogueAll !== "function") return "";
  var all = shopCatalogueAll();
  if (!vpPhotoIdx || vpPhotoIdxN !== all.length) {
    vpPhotoIdx = {}; vpPhotoIdxN = all.length;
    all.forEach(function (x) { if (x.url && prodHasPhoto(x)) vpPhotoIdx[x.url] = x.img; });
  }
  var i = vpPhotoIdx[e.url] || "";
  return i && !PHOTO_BROKEN[i] ? i : "";
}
function vpCardHTML(e, opts) {
  if (!e) return "";
  opts = opts || {};
  /* .78.7: never a product card without a photo */
  var ph = vpPhotoFor(e);
  if (!ph) return "";
  if (ph !== e.img) e = Object.assign({}, e, { img: ph });
  var key = vpKey(e);
  VP[key] = { e: e, pc: opts.pc || null, pick: opts.pick || null, tag: opts.tag || "", edit: !!opts.edit };
  if (opts.h) opts.cls = (opts.cls ? opts.cls + " " : "") + "vp-h";
  var w = vpWished(e), b = vpBought(e), img = e.img || "";
  return '<article class="vp-card' + (opts.picked ? " is-picked" : "") + (opts.cls ? " " + opts.cls : "") + '" data-vp-key="' + esc(key) + '"' + (opts.edit ? ' data-edit-key="' + esc(key) + '"' : "") + (opts.pick ? ' data-vp-pick="' + opts.pick.idx + '"' : "") + ">" +
    '<div class="vp-media"><button type="button" class="vp-ph" data-vp-open aria-label="' + esc((e.brand ? e.brand + " " : "") + vpName(e)) + '">' + (img ? '<img src="' + esc(img) + '" alt="" loading="lazy" decoding="async" />' : '<span class="vp-noimg">' + esc(e.brand || "") + "</span>") + "</button>" +
    (opts.picked ? '<span class="vp-picked">' + VP_ICON.check + "Picked</span>" : (opts.tag ? '<span class="vp-tag">' + esc(opts.tag) + "</span>" : "")) + (opts.overlay || "") + "</div>" +
    '<div class="vp-body" data-vp-open><span class="vp-brand">' + esc(e.brand || "") + '</span><span class="vp-name">' + esc(vpName(e)) + "</span>" +
    '<span class="vp-price">' + esc(vpPrice(e)) + '</span><span class="vp-ret">' + esc(vpRetailer(e)) + "</span></div>" +
    '<div class="vp-acts">' +
    (opts.edit ? '<button type="button" class="vp-ico" data-edit-save data-vp-wish aria-pressed="' + w + '" aria-label="' + (w ? "Saved" : "Save") + '">' + VP_ICON.heart + "</button>" +
      '<span hidden><button type="button" data-edit-star></button><button type="button" data-edit-pass></button></span>'
      : '<button type="button" class="vp-ico" data-vp-act="wish" data-vp-wish aria-pressed="' + w + '" aria-label="Wishlist">' + VP_ICON.heart + "</button>") +
    '<button type="button" class="vp-ico" data-vp-act="bought" aria-pressed="' + b + '" aria-label="Purchased">' + VP_ICON.bag + "</button>" +
    (img ? '<button type="button" class="vp-ico" data-vp-act="style" aria-label="Style this">' + VP_ICON.hanger + "</button>" +
      '<button type="button" class="vp-ico" data-vp-act="onme" aria-label="See it on me">' + VP_ICON.person + "</button>" : "") +
    (e.url ? '<a class="vp-ico" data-vp-act="buy" href="' + esc(e.url) + '" target="_blank" rel="noopener" aria-label="Buy at ' + esc(vpRetailer(e) || "the store") + '">' + VP_ICON.ext + "</a>" : "") +
    "</div></article>";
}
function vpRowHTML(list, opts) {
  opts = opts || {};
  return '<div class="vp-row">' + list.map(function (e, i) { return vpCardHTML(e, typeof opts === "function" ? opts(e, i) : opts); }).join("") + "</div>";
}
function vpGridHTML(list, opts) {
  opts = opts || {};
  return '<div class="vp-grid">' + list.map(function (e, i) { return vpCardHTML(e, typeof opts === "function" ? opts(e, i) : opts); }).join("") + "</div>";
}
/* Wishlist / purchased state on every card and the open sheet. */
/* A card whose photo fails to load leaves the page (and that product
   stops being offered as a pick this session). */
document.addEventListener("error", function (ev) {
  var t = ev.target;
  if (!t || t.tagName !== "IMG" || !t.closest) return;
  var card = t.closest(".vp-card");
  if (!card) return;
  var src = t.getAttribute("src") || "";
  if (src) PHOTO_BROKEN[src] = 1;
  card.remove();
}, true);
function vpRefreshStates() {
  document.querySelectorAll(".vp-card[data-vp-key], #vp-sheet[data-vp-key]").forEach(function (c) {
    var r = VP[c.getAttribute("data-vp-key")];
    if (!r) return;
    var w = c.querySelector("[data-vp-wish]"), b = c.querySelector('[data-vp-act="bought"]');
    if (w) w.setAttribute("aria-pressed", String(vpWished(r.e)));
    if (b) b.setAttribute("aria-pressed", String(vpBought(r.e)));
    var wl = c.querySelector('[data-vp-act="wish"] .vp-lbl'), bl = c.querySelector('[data-vp-act="bought"] .vp-lbl');
    if (wl) wl.textContent = vpWished(r.e) ? "In wishlist" : "Wishlist";
    if (bl) bl.textContent = vpBought(r.e) ? "Purchased" : "Mark purchased";
  });
  if (typeof stlRenderSummary === "function") try { stlRenderSummary(); } catch (e) {}
}
(function () {
  if (typeof refreshWishButtons === "function") {
    var rwb = refreshWishButtons;
    refreshWishButtons = function () { rwb.apply(this, arguments); vpRefreshStates(); };
  }
  if (typeof saveShopWishlist === "function") {
    var ssw = saveShopWishlist;
    saveShopWishlist = function () { var r = ssw.apply(this, arguments); setTimeout(vpRefreshStates, 0); return r; };
  }
})();
var vpRun = 0;
function vpOpen(key, mode) {
  var r = VP[key], sheet = document.getElementById("vp-sheet");
  if (!r || !sheet) return;
  var e = r.e, run = ++vpRun;
  sheet.setAttribute("data-vp-key", key);
  var tier = e.tier && typeof shopTierInfo === "function" ? shopTierInfo(e.tier).name : "";
  var sell = typeof sellerLabel === "function" ? sellerLabel(e) : "";
  var sub = [vpRetailer(e), tier, sell].filter(Boolean).join(" \u00b7 ");
  var body = document.getElementById("vp-sheet-body");
  body.innerHTML = (e.img ? '<div class="vp-sh-ph"><img src="' + esc(e.img) + '" alt="" /></div>' : "") +
    '<div class="vp-sh-info"><span class="vp-brand">' + esc(e.brand || "") + '</span><h3 class="vp-sh-name">' + esc(vpName(e)) + "</h3>" +
    '<div class="vp-sh-price">' + esc(vpPrice(e)) + "</div>" + (sub ? '<p class="vp-sh-sub">' + esc(sub) + "</p>" : "") +
    (r.tag ? '<p class="vp-sh-sub">' + esc(r.tag) + "</p>" : "") + (e.matchNote ? '<p class="vp-sh-note">' + esc(e.matchNote) + "</p>" : "") + "</div>" +
    (e.url ? '<a class="btn-ink vp-sh-buy" href="' + esc(e.url) + '" target="_blank" rel="noopener">Buy at ' + esc(vpRetailer(e) || "the store") + "</a>" : "") +
    (r.pick ? '<button type="button" class="btn-ghost vp-sh-pick" data-vp-act="pick">' + (document.querySelector('.vp-card.is-picked[data-vp-key="' + cssEsc(key) + '"]') ? "Picked for this look" : "Pick for this look") + "</button>" : "") +
    '<div class="vp-sh-acts">' +
    '<button type="button" class="vp-act" data-vp-act="wish" data-vp-wish aria-pressed="' + vpWished(e) + '">' + VP_ICON.heart + '<span class="vp-lbl">' + (vpWished(e) ? "In wishlist" : "Wishlist") + "</span></button>" +
    '<button type="button" class="vp-act" data-vp-act="bought" aria-pressed="' + vpBought(e) + '">' + VP_ICON.bag + '<span class="vp-lbl">' + (vpBought(e) ? "Purchased" : "Mark purchased") + "</span></button>" +
    (e.img ? '<button type="button" class="vp-act" data-vp-act="style">' + VP_ICON.hanger + '<span class="vp-lbl">Style this</span></button>' +
      '<button type="button" class="vp-act" data-vp-act="onme">' + VP_ICON.person + '<span class="vp-lbl">See it on me</span></button>' : "") +
    "</div>" +
    (r.edit ? '<div class="vp-sh-more"><button type="button" class="chip" data-vp-act="star" aria-pressed="' + vpStarred(key) + '">\u2606 Star</button><button type="button" class="chip" data-vp-act="pass">Not for me</button><button type="button" class="chip" data-vp-act="look">+ Look</button></div>' : "") +
    "";
  /* the On me area is static markup below the body; reset it */
  var om = document.getElementById("vp-onme"), omi = document.getElementById("vp-onme-img"), wm = sheet.querySelector(".vp-withmine");
  if (om) om.hidden = true; if (omi) { omi.hidden = true; omi.removeAttribute("src"); } if (wm) wm.hidden = true;
  sheet.hidden = false;
  var card = sheet.querySelector(".info-pop-card"); if (card) card.scrollTop = 0;
  if (mode === "onme") vpOnMe(key, run);
}
function vpStarred(key) { var c = document.querySelector('.vp-card[data-edit-key="' + cssEsc(key) + '"].is-star'); return !!c; }
/* The Edit's own handler does the work: click its button on the card. */
function vpProxy(key, sel) {
  var c = document.querySelector('#panel-find .vp-card[data-edit-key="' + cssEsc(key) + '"]');
  var b = c ? c.querySelector(sel) : null;
  if (b) { b.click(); return true; }
  return false;
}
function cssEsc(s) { return String(s).replace(/(["\\])/g, "\\$1"); }
function vpClose() { vpRun++; var s = document.getElementById("vp-sheet"); if (s) { s.hidden = true; s.removeAttribute("data-vp-key"); } }
/* See it on me, inline in the sheet — the same try-on job as the
   On you sheet (tryonJob: device cache, worker cache, cap). */
function vpOnMe(key, run) {
  var r = VP[key];
  if (!r || typeof tryonJob !== "function") return;
  var box = document.getElementById("vp-onme"), st = document.getElementById("vp-onme-st"), img = document.getElementById("vp-onme-img");
  if (!box) return;
  box.hidden = false; img.hidden = true; st.hidden = false; st.textContent = "Getting ready\u2026";
  setTimeout(function () { try { box.scrollIntoView({ block: "nearest", behavior: "smooth" }); } catch (e) {} }, 50);
  tryonJob(tryonEntryItems(vpEntryFor(r.e)), function (state, text, url) {
    if (state === "done") {
      img.onload = function () { if (run === vpRun) { st.hidden = true; img.hidden = false; try { img.scrollIntoView({ block: "nearest", behavior: "smooth" }); } catch (e) {} } };
      img.onerror = function () { if (run === vpRun) st.textContent = "The render finished but couldn't load. Try again."; };
      img.src = url;
      var wm = document.querySelector("#vp-onme .vp-withmine"); if (wm) wm.hidden = false;
      return;
    }
    st.textContent = text || (state === "error" ? "Couldn't render that right now." : "Putting it on you\u2026");
  }, function () { return run === vpRun; });
}
/* Is there already a render of him in this piece on this device?
   (the try-on cache key is built from the same garment image ref) */
var vpOnMeTok = 0;
function vpHasRender(e) {
  if (!e || !e.img || typeof tryonEntryItems !== "function" || typeof tryonCacheKey !== "function" || typeof tryonCache === "undefined") return Promise.resolve(false);
  return Promise.resolve(tryonEntryItems(e)).then(function (items) {
    if (!items || !items.length) return false;
    var c = tryonCache[tryonCacheKey(items.slice(0, 6))];
    return !!(c && c.u);
  }).catch(function () { return false; });
}
function vpAct(act, key, el) {
  var r = VP[key];
  if (!r) return;
  var e = vpEntryFor(r.e);
  if (r.edit && act === "wish") { vpProxy(key, "[data-edit-save]"); setTimeout(vpRefreshStates, 0); return; }
  if (r.edit && act === "star") { vpProxy(key, "[data-edit-star]"); vpClose(); return; }
  if (r.edit && act === "pass") { vpProxy(key, "[data-edit-pass]"); vpClose(); return; }
  if (r.edit && act === "look") { vpProxy(key, "[data-edit-look]"); vpClose(); return; }
  if (act === "wish") { toggleWishlistItem(e, r.pc); vpRefreshStates(); if (typeof window.editOnSync === "function") try { window.editOnSync(); } catch (x) {} return; }
  if (act === "bought") {
    toggleShopPurchase(e, r.pc);
    vpRefreshStates();
    return;
  }
  if (act === "style") { vpClose(); if (typeof buildAroundShopEntry === "function") buildAroundShopEntry(e); return; }
  if (act === "onme") {
    var sheet = document.getElementById("vp-sheet");
    if (sheet && !sheet.hidden && sheet.getAttribute("data-vp-key") === key) { vpOnMe(key, vpRun); return; }
    /* .78.9: from a card, a render he already has opens the try-on
       straight away (served from the device cache, no new render);
       otherwise the product sheet renders it inline. */
    var tok = ++vpOnMeTok;
    vpHasRender(e).then(function (has) {
      if (tok !== vpOnMeTok) return;
      if (has && typeof tryonForEntry === "function") { vpClose(); tryonForEntry(Object.assign({ retailer: e.store || e.retailer }, e), false); }
      else vpOpen(key, "onme");
    });
    return;
  }
  if (act === "withmine") { vpClose(); if (typeof tryonForEntry === "function") tryonForEntry(Object.assign({ retailer: e.store || e.retailer }, e), true); return; }
  if (act === "pick" && r.pick && typeof setPieceSelection === "function") { setPieceSelection(r.pick.idx, key); vpClose(); return; }
}
document.addEventListener("click", function (ev) {
  var t = ev.target;
  if (!t || !t.closest) return;
  var sheet = document.getElementById("vp-sheet");
  if (sheet && !sheet.hidden && (t === sheet || t.closest("#vp-sheet-close"))) { vpClose(); return; }
  var host = t.closest(".vp-card[data-vp-key], #vp-sheet[data-vp-key]");
  if (!host) return;
  var key = host.getAttribute("data-vp-key");
  var a = t.closest("[data-vp-act]");
  if (a) {
    var act = a.getAttribute("data-vp-act");
    if (act === "buy") return; /* plain link out */
    ev.preventDefault(); ev.stopPropagation();
    vpAct(act, key, a);
    return;
  }
  if (host.id !== "vp-sheet" && t.closest("[data-vp-open]")) { ev.preventDefault(); vpOpen(key); }
});
document.addEventListener("keydown", function (e) { var s = document.getElementById("vp-sheet"); if (e.key === "Escape" && s && !s.hidden) vpClose(); });
if (window.stlPending) { window.stlPending = false; try { renderFindLookMode(); } catch (e) {} }
    