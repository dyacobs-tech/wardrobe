
"use strict";
/* ================= What I'm Wearing Today + My Inspo =================
   Two pages layered on the same store as everything else.

   What I'm Wearing Today (Me) is the selfie log: take or upload a
   photo of the outfit, set the date (today by default), confirm
   the items in a quick sheet of rows — pick an existing Closet
   piece (marked worn, never duplicated) or type a new one
   (catalogued into the Closet on save, with the selfie as its
   reference photo). Saving also records the outfit — selfie and
   item list — in the worn log for that date, so it appears in
   this page's history and in Calendar's What I wore with the
   selfie itself as the entry's picture. The app cannot recognise
   items from the photo, so the rows start empty on purpose.

   My Inspo (Inspiration) is the gallery for the existing
   inspoImages store: add uploads there, tap one to build looks
   of him from it (buildImageLooks — first take is the upload,
   the rest are engine builds), delete there. The Studio's old
   upload door is gone; the engine is untouched. */

/* ---------- What I'm Wearing Today ---------- */
var wearingPhotoDataUrl = null;
var WEARING_DEFAULT_CATS = ["Shirts", "Trousers", "Shoes"];
function wearingCats() { return CATEGORIES.filter(function (c) { return c !== "All"; }); }
function wearingPickOptions(cat, selectedId) {
  var html = '<option value="">Pick from Closet — optional</option>';
  wardrobeItems.filter(function (i) { return i.category === cat; }).slice().sort(wardItemSort).forEach(function (i) {
    html += '<option value="' + i.id + '"' + (i.id === selectedId ? " selected" : "") + ">" + esc(i.name) + (i.colourName ? " — " + esc(i.colourName.split("·")[0].trim()) : "") + "</option>";
  });
  return html;
}
/* Search across EVERY category (build .35): a piece filed under the
   wrong category must stay findable, so results ignore the row's
   selected category and carry their filed category in the label. */
function wearingSearchOptions(q, selectedId) {
  var html = '<option value="">Pick from Closet — optional</option>';
  var needle = String(q || "").trim().toLowerCase();
  if (!needle) return html;
  wardrobeItems.filter(function (i) {
    var hay = (i.name + " " + (i.colourName || "") + " " + (i.category || "")).toLowerCase();
    return hay.indexOf(needle) !== -1;
  }).slice().sort(wardItemSort).forEach(function (i) {
    html += '<option value="' + i.id + '"' + (i.id === selectedId ? " selected" : "") + ">" + esc(i.name) + (i.colourName ? " — " + esc(i.colourName.split("·")[0].trim()) : "") + " · " + esc(i.category || "") + "</option>";
  });
  return html;
}
function refreshRowPick(row) {
  var cat = row.querySelector(".wr-cat").value;
  var pick = row.querySelector(".wr-pick");
  var search = row.querySelector(".wr-search");
  var cur = pick.value;
  pick.innerHTML = (search && search.value.trim()) ? wearingSearchOptions(search.value, cur) : wearingPickOptions(cat, cur);
  pick.value = cur;
  if (cur && pick.value !== cur) { pick.value = ""; if (row.querySelector(".wr-name")) syncWearingRow(row); }
}
/* A cross-category pick moves the row's category to the piece's own,
   so the row (and any later rebuild of its options) stays coherent. */
function syncRowCatToPick(row) {
  var pick = row.querySelector(".wr-pick");
  var cat = row.querySelector(".wr-cat");
  if (!pick || !cat || !pick.value) return;
  var it = closetItemById(pick.value);
  if (it && it.category && cat.value !== it.category) cat.value = it.category;
}
function wearingRowHTML(cat) {
  return '<div class="wearing-row">' +
    '<div class="wr-top"><select class="wr-cat" aria-label="Category">' + wearingCats().map(function (c) { return "<option" + (c === cat ? " selected" : "") + ">" + esc(c) + "</option>"; }).join("") + "</select>" +
    '<button type="button" class="btn-ghost wr-remove">Remove</button></div>' +
    '<input type="search" class="wr-search" placeholder="Search all categories…" autocomplete="off" aria-label="Search all categories" />' +
    '<select class="wr-pick" aria-label="Pick an existing closet item">' + wearingPickOptions(cat, "") + "</select>" +
    '<input type="text" class="wr-name" placeholder="Name — e.g. Navy linen shirt" autocomplete="off" />' +
    '<div class="wr-colour-row"><input type="text" class="wr-colour-name" placeholder="Colour" autocomplete="off" /><input type="color" class="wr-colour" value="#232d3f" aria-label="Pick the colour" /></div>' +
    "</div>";
}
function resetWearingRows() {
  var box = document.getElementById("wearing-rows");
  if (box) box.innerHTML = WEARING_DEFAULT_CATS.map(wearingRowHTML).join("");
}
function syncWearingRow(row) {
  var pick = row.querySelector(".wr-pick");
  var name = row.querySelector(".wr-name");
  var cname = row.querySelector(".wr-colour-name");
  var chex = row.querySelector(".wr-colour");
  var it = pick.value ? closetItemById(pick.value) : null;
  if (it) {
    name.value = it.name;
    cname.value = (it.colourName || "").split("·")[0].trim();
    if (it.colourHex) chex.value = it.colourHex;
  }
  [name, cname, chex].forEach(function (el) { el.disabled = !!it; el.classList.toggle("wr-picked", !!it); });
}
function refreshWearingPicks() {
  document.querySelectorAll("#wearing-rows .wearing-row").forEach(function (row) { refreshRowPick(row); });
}
/* The Wearing page history is renderWornLog now — the one
   worn list, month by month, selfie entries included. */
["wearing-photo-camera", "wearing-photo-upload"].forEach(function (id) {
  var input = document.getElementById(id);
  if (!input) return;
  input.addEventListener("change", function () {
    var file = this.files && this.files[0];
    if (!file) return;
    processPhotoFile(file, function (url) {
      if (!url) { toast("That photo couldn't be read — try a different photo."); return; }
      wearingPhotoDataUrl = url;
      var prev = document.getElementById("wearing-preview");
      prev.src = url;
      prev.alt = "Your outfit photo";
      prev.hidden = false;
    });
  });
});
var wearingRowsBox = document.getElementById("wearing-rows");
if (wearingRowsBox) {
  wearingRowsBox.addEventListener("change", function (e) {
    var row = e.target.closest ? e.target.closest(".wearing-row") : null;
    if (!row) return;
    if (e.target.classList.contains("wr-cat")) {
      var pick = row.querySelector(".wr-pick");
      var search = row.querySelector(".wr-search");
      if (search) search.value = "";
      pick.innerHTML = wearingPickOptions(e.target.value, "");
      pick.value = "";
      syncWearingRow(row);
    } else if (e.target.classList.contains("wr-pick")) {
      syncWearingRow(row);
      syncRowCatToPick(row);
    }
  });
  wearingRowsBox.addEventListener("input", function (e) {
    if (!e.target.classList.contains("wr-search")) return;
    var row = e.target.closest ? e.target.closest(".wearing-row") : null;
    if (row) refreshRowPick(row);
  });
  wearingRowsBox.addEventListener("click", function (e) {
    var rm = e.target.closest ? e.target.closest(".wr-remove") : null;
    if (!rm) return;
    var row = rm.closest(".wearing-row");
    if (row) row.remove();
  });
}
var wearingAddRowBtn = document.getElementById("wearing-add-row");
if (wearingAddRowBtn) wearingAddRowBtn.addEventListener("click", function () {
  wearingRowsBox.insertAdjacentHTML("beforeend", wearingRowHTML("Shirts"));
});
var wearingSaveBtn = document.getElementById("wearing-save");
if (wearingSaveBtn) wearingSaveBtn.addEventListener("click", function () {
  if (!wearingPhotoDataUrl) { toast("Add a photo first — take one or upload one."); return; }
  var dateEl = document.getElementById("wearing-date");
  var date = (dateEl && dateEl.value) || localTodayISO();
  var used = [], newItems = [];
  Array.prototype.slice.call(document.querySelectorAll("#wearing-rows .wearing-row")).forEach(function (row) {
    var pickId = row.querySelector(".wr-pick").value;
    if (pickId) {
      var picked = closetItemById(pickId);
      if (picked && used.indexOf(picked) === -1) used.push(picked);
      return;
    }
    var name = row.querySelector(".wr-name").value.trim();
    if (!name) return;
    var colourName = row.querySelector(".wr-colour-name").value.trim();
    var colourHex = row.querySelector(".wr-colour").value;
    var wada = nearestWada(colourHex);
    var ni = {
      id: "item-" + Date.now() + "-" + Math.floor(Math.random() * 1e6),
      name: name,
      category: row.querySelector(".wr-cat").value,
      colourName: colourName || wada.name,
      colourHex: colourHex,
      extraColours: colourName ? [{ name: "Nearest Wada: " + wada.name, hex: wada.hex }] : [],
      notes: "",
      price: null,
      wearCount: 0,
      lastWorn: null,
      addedISO: localTodayISO(),
      laundry: false,
      photo: wearingPhotoDataUrl
    };
    newItems.push(ni);
    used.push(ni);
  });
  if (!used.length) { toast("Confirm at least one item first."); return; }
  newItems.forEach(function (ni) { wardrobeItems.unshift(ni); });
  /* One worn store: recordWorn writes the log entry and every
     piece's wear counter together. */
  recordWorn({
    id: "selfie-" + Date.now(),
    date: date,
    title: "Logged outfit",
    img: wearingPhotoDataUrl,
    pieces: used.map(function (i) { return i.name; }),
    pieceDetails: used.map(function (i) { return { name: i.name, category: i.category }; }),
    selfie: true,
    pieceIds: used.map(function (i) { return i.id; })
  });
  var kept = persistAll();
  renderWardrobe();
  renderWornLog();
  wearingPhotoDataUrl = null;
  var prev = document.getElementById("wearing-preview");
  prev.hidden = true;
  prev.removeAttribute("src");
  ["wearing-photo-camera", "wearing-photo-upload"].forEach(function (id) { var el = document.getElementById(id); if (el) el.value = ""; });
  if (dateEl) dateEl.value = localTodayISO();
  resetWearingRows();
  toast(kept ? "Logged — in your Closet, and worn on " + fmtDateShort(date) + "." : "Logged — storage is full, so export a backup from Profile.");
});

/* ---------- My Inspo ---------- */
function renderMyInspo() {
  var grid = document.getElementById("myinspo-grid");
  var empty = document.getElementById("myinspo-empty");
  if (!grid) return;
  if (!inspoImages.length) {
    grid.innerHTML = "";
    if (empty) empty.innerHTML = '<div class="card empty">No inspiration saved yet — add a photo or screenshot above.</div>';
    return;
  }
  if (empty) empty.innerHTML = "";
  /* Build .56: the same photograph added twice shows once. */
  var seenMi56 = {};
  var entriesMi56 = inspoImages.filter(function (en) {
    if (!en || !en.img) return true;
    var k = "";
    try { k = canonicalImg(en.img); } catch (e) { k = ""; }
    if (!k || String(en.img).indexOf("data:") === 0) return true;
    if (seenMi56[k]) return false;
    seenMi56[k] = true;
    return true;
  });
  grid.innerHTML = entriesMi56.map(function (en) {
    return '<article class="card myinspo-card">' +
      '<button type="button" class="myinspo-imgbtn" data-myinspo-style="' + en.id + '" aria-label="Style this look"><img src="' + en.img + '" alt="' + esc(en.desc || "Your uploaded inspiration") + '" loading="lazy" /></button>' +
      '<div class="mi-body">' + (en.desc ? '<p class="mi-desc">' + esc(en.desc) + "</p>" : "") +
      /* The photo itself is the Style this look button — no
         duplicate beneath it. */
      '<div class="look-actions"><button type="button" class="btn-ghost" data-myinspo-delete="' + en.id + '">Delete</button></div></div></article>';
  }).join("");
}
function styleFromMyInspo(id) {
  var entry = inspoImageById(id);
  if (!entry) return;
  /* Not latched: the control that used to show and clear "building
     from your image" is gone, so a latch here made every later
     Create build from this image for the rest of the session. */
  activeInspoId = null;
  var season = typeof weatherSeason === "function" ? weatherSeason() : "";
  switchTab("studio");
  renderOptions(buildImageLooks(entry, "", "", season || ""), { desc: entry.desc || "From your image", occasion: "", season: season || "", opts: { basis: studioBasis, source: "inspo", inspoImageId: entry.id } });
  toast("Six takes built from your image.");
}
var myInspoPhoto = document.getElementById("myinspo-photo");
if (myInspoPhoto) myInspoPhoto.addEventListener("change", function () {
  var file = this.files && this.files[0];
  if (!file) return;
  var input = this;
  processPhotoFile(file, function (url) {
    if (!url) { input.value = ""; toast("That photo couldn't be read — try a different photo."); return; }
    var entry = {
      id: "inspo-" + Date.now(),
      img: url,
      desc: document.getElementById("myinspo-desc").value.trim(),
      ts: Date.now()
    };
    inspoImages.unshift(entry);
    if (inspoImages.length > 24) inspoImages = inspoImages.slice(0, 24);
    saveInspoImages();
    renderMyInspo();
    document.getElementById("myinspo-desc").value = "";
    input.value = "";
    toast("Saved to My Inspo.");
  });
});
var myInspoPanel = document.getElementById("panel-myinspo");
if (myInspoPanel) myInspoPanel.addEventListener("click", function (e) {
  var del = e.target.closest ? e.target.closest("[data-myinspo-delete]") : null;
  if (del) {
    var delId = del.getAttribute("data-myinspo-delete");
    var delIx = -1;
    inspoImages.forEach(function (x, i) { if (x.id === delId) delIx = i; });
    var delEntry = delIx >= 0 ? inspoImages[delIx] : null;
    inspoImages = inspoImages.filter(function (x) { return x.id !== delId; });
    if (activeInspoId === delId) activeInspoId = null;
    saveInspoImages();
    renderMyInspo();
    if (delEntry) showUndoToast("Removed from My Inspo.", function () {
      inspoImages.splice(Math.min(delIx, inspoImages.length), 0, delEntry);
      saveInspoImages();
      renderMyInspo();
    });
    return;
  }
  var st = e.target.closest ? e.target.closest("[data-myinspo-style]") : null;
  if (st) styleFromMyInspo(st.getAttribute("data-myinspo-style"));
});

/* Entering either page re-reads the live stores, so Closet picks
   and the inspo gallery never go stale. */
(function wrapSwitchForNewPages() {
  var orig = window.switchTab;
  if (typeof orig !== "function") return;
  window.switchTab = function (name, opts) {
    orig(name, opts);
    if (name === "wearing") refreshWearingPicks();
    if (name === "myinspo") renderMyInspo();
  };
})();

/* ---------- Upload a look (Today) ----------
   A standalone look from his own photo, saved from the Today
   hero: no day attached, nothing written to the worn log, never
   in Calendar's What I wore. The photo runs through the selfie
   log's downscale path (processPhotoFile) and the look joins
   savedLooks like any other, so the store's vault offload keeps
   the photo in IndexedDB (never raw base64 in localStorage) and
   cloud sync + backup carry it as part of savedLooks. The
   confirm sheet reuses the selfie sheet's Closet picker
   (wearingPickOptions rows): name and tags are optional — the
   photo alone saves. Tagged pieces also become the look's
   swatches and flatlay, so Shop the look reads them, and where
   the piece library knows a tagged Closet item its id goes into
   swapPieces, so Change a piece works through the usual mapper;
   untagged or unmapped looks get the standard “No swappable
   pieces in this look yet” line. The createdAt stamp is sort
   order only — it is never shown as a date anywhere. */
var uploadPhotoDataUrl = null;
function uploadRowHTML(cat) {
  return '<div class="wearing-row">' +
    '<div class="wr-top"><select class="wr-cat" aria-label="Category">' + wearingCats().map(function (c) { return "<option" + (c === cat ? " selected" : "") + ">" + esc(c) + "</option>"; }).join("") + "</select>" +
    '<button type="button" class="btn-ghost wr-remove">Remove</button></div>' +
    '<input type="search" class="wr-search" placeholder="Search all categories…" autocomplete="off" aria-label="Search all categories" />' +
    '<select class="wr-pick" aria-label="Tag a piece from your Closet">' + wearingPickOptions(cat, "") + "</select>" +
    "</div>";
}
function resetUploadRows() {
  var box = document.getElementById("upload-rows");
  if (box) box.innerHTML = WEARING_DEFAULT_CATS.map(uploadRowHTML).join("");
}
function openUploadSheet() {
  var sheet = document.getElementById("upload-sheet");
  if (sheet) sheet.hidden = false;
}
function closeUploadSheet() {
  var sheet = document.getElementById("upload-sheet");
  if (sheet) sheet.hidden = true;
}
function openUploadConfirm() {
  var prev = document.getElementById("upload-preview");
  if (prev && uploadPhotoDataUrl) { prev.src = uploadPhotoDataUrl; prev.hidden = false; }
  var nameEl = document.getElementById("upload-name");
  if (nameEl) nameEl.value = "";
  resetUploadRows();
  var sheet = document.getElementById("upload-confirm-sheet");
  if (sheet) sheet.hidden = false;
  var c = document.getElementById("upload-confirm-close");
  if (c) c.focus();
}
function closeUploadConfirm() {
  var sheet = document.getElementById("upload-confirm-sheet");
  if (sheet) sheet.hidden = true;
}
var todayUploadBtn = document.getElementById("today-upload");
if (todayUploadBtn) todayUploadBtn.addEventListener("click", openUploadSheet);
var uploadSheetClose = document.getElementById("upload-sheet-close");
if (uploadSheetClose) uploadSheetClose.addEventListener("click", closeUploadSheet);
var uploadSheetEl = document.getElementById("upload-sheet");
if (uploadSheetEl) uploadSheetEl.addEventListener("click", function (e) { if (e.target === this) closeUploadSheet(); });
var uploadConfirmClose = document.getElementById("upload-confirm-close");
if (uploadConfirmClose) uploadConfirmClose.addEventListener("click", closeUploadConfirm);
var uploadConfirmEl = document.getElementById("upload-confirm-sheet");
if (uploadConfirmEl) uploadConfirmEl.addEventListener("click", function (e) { if (e.target === this) closeUploadConfirm(); });
document.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeUploadSheet(); closeUploadConfirm(); } });
["upload-photo-camera", "upload-photo-upload"].forEach(function (id) {
  var input = document.getElementById(id);
  if (!input) return;
  input.addEventListener("change", function () {
    var file = this.files && this.files[0];
    if (!file) return;
    var self = this;
    /* Say what is happening while the photo is prepared: a big
       phone photo can take a moment to downscale, and silence
       here read as the app being stuck. A photo that cannot be
       read at all gets a plain answer and the sheet stays open
       so another can be picked straight away. */
    var status = document.getElementById("upload-status");
    if (status) { status.hidden = false; status.textContent = "Preparing your photo…"; }
    processPhotoFile(file, function (url) {
      self.value = "";
      if (status) { status.hidden = true; status.textContent = ""; }
      if (!url) { toast("That photo couldn't be read — try a different photo."); return; }
      uploadPhotoDataUrl = url;
      closeUploadSheet();
      openUploadConfirm();
    });
  });
});
var uploadRowsBox = document.getElementById("upload-rows");
if (uploadRowsBox) {
  uploadRowsBox.addEventListener("change", function (e) {
    var row = e.target.closest ? e.target.closest(".wearing-row") : null;
    if (!row) return;
    if (e.target.classList.contains("wr-cat")) {
      var pick = row.querySelector(".wr-pick");
      var search = row.querySelector(".wr-search");
      if (search) search.value = "";
      pick.innerHTML = wearingPickOptions(e.target.value, "");
      pick.value = "";
    } else if (e.target.classList.contains("wr-pick")) {
      syncRowCatToPick(row);
    }
  });
  uploadRowsBox.addEventListener("input", function (e) {
    if (!e.target.classList.contains("wr-search")) return;
    var row = e.target.closest ? e.target.closest(".wearing-row") : null;
    if (row) refreshRowPick(row);
  });
  uploadRowsBox.addEventListener("click", function (e) {
    var rm = e.target.closest ? e.target.closest(".wr-remove") : null;
    if (!rm) return;
    var row = rm.closest(".wearing-row");
    if (row) row.remove();
  });
}
var uploadAddRowBtn = document.getElementById("upload-add-row");
if (uploadAddRowBtn) uploadAddRowBtn.addEventListener("click", function () {
  if (uploadRowsBox) uploadRowsBox.insertAdjacentHTML("beforeend", uploadRowHTML("Shirts"));
});
function saveUploadedLook(withTags) {
  if (!uploadPhotoDataUrl) { closeUploadConfirm(); return; }
  var nameEl = document.getElementById("upload-name");
  /* Build .56: the generic placeholder is not a name — an unnamed
     upload titles from its cataloged pieces below. */
  var name = ((nameEl && nameEl.value) || "").trim();
  if (name === "Uploaded look") name = "";
  var tagged = [];
  if (withTags) {
    Array.prototype.slice.call(document.querySelectorAll("#upload-rows .wr-pick")).forEach(function (pick) {
      if (!pick.value) return;
      var it = closetItemById(pick.value);
      if (it && tagged.indexOf(it) === -1) tagged.push(it);
    });
  }
  var look = {
    id: newLookId(),
    title: name,
    img: uploadPhotoDataUrl,
    imgAlt: name,
    source: "uploaded",
    createdAt: Date.now(),
    swatches: tagged.map(function (i) {
      var cn = (i.colourName || "").split("·")[0].trim();
      return { name: cn || nearestWada(i.colourHex || "#888888").name, hex: i.colourHex || "#888888", role: cap(CLOSET_GARMENT[i.category] || "Piece") };
    }),
    flatlay: tagged.map(function (i) {
      return { hex: i.colourHex || "#888888", label: cap(CLOSET_GARMENT[i.category] || "Piece"), detail: (i.colourName || "").split("·")[0].trim().toLowerCase() };
    }),
    taggedPieces: tagged.map(function (i) {
      return { id: i.id, name: i.name, category: i.category, hex: i.colourHex || "" };
    }),
    notes: []
  };
  var sp = {};
  tagged.forEach(function (i) {
    var p = PIECE_BY_CID[i.id];
    if (p && p.slot && !sp[p.slot]) sp[p.slot] = p.id;
  });
  if (Object.keys(sp).length) look.swapPieces = sp;
  if (!look.title) { look.title = uploadedTitle56(look) || "My outfit"; look.imgAlt = look.title; }
  look.savedAt = Date.now(); /* build .56: stamp the save */
  savedLooks.unshift(look);
  var kept = persistAll();
  renderSaved();
  uploadPhotoDataUrl = null;
  var prev = document.getElementById("upload-preview");
  if (prev) { prev.hidden = true; prev.removeAttribute("src"); }
  closeUploadConfirm();
  toast(kept ? "Look saved to " + savedHomeName(look) + "." : "Saved on screen, but storage is full — export a backup from Profile.");
}
var uploadSaveBtn = document.getElementById("upload-save");
if (uploadSaveBtn) uploadSaveBtn.addEventListener("click", function () { saveUploadedLook(true); });
var uploadSkipBtn = document.getElementById("upload-skip");
if (uploadSkipBtn) uploadSkipBtn.addEventListener("click", function () { saveUploadedLook(false); });

/* ---------- From wardrobe (Ideas) ----------
   A standing section inside Ideas, dealt from the closet alone:
   six outfits built only from pieces he owns — the same engine
   behind the form's "From my closet" chip (buildClosetLooks),
   given a home of its own. Tapping a take opens it full-size in
   the Ideas results above, through the usual renderOptions flow,
   so liking, saving and changing an item all work as elsewhere.
   The grid re-deals when the closet itself changes (pieces added,
   removed or sent to laundry), checked whenever Ideas is opened. */
var fwLooks = [];
var fwClosetSig = null;
function closetSig() {
  if (typeof wardrobeItems === "undefined") return "";
  return wardrobeItems.map(function (i) { return i.id + (i.laundry ? "~" : ""); }).join("|");
}
function fwCardHTML(look, idx) {
  var pieces = look.fwPieces || [];
  var shoe = null;
  pieces.forEach(function (p) { if (p.category === "Shoes") shoe = p; });
  var shown = [pieces[0], shoe].filter(function (p, ix, a) { return p && p.photo && a.indexOf(p) === ix; });
  var photos = look.fwRender
    ? '<span class="fw-render"><img src="' + fwRenderSrc(look) + '" alt="' + esc(look.imgAlt || look.title || "") + '" loading="lazy" decoding="async" /></span>'
    : (shown.length
      ? '<span class="fw-photos' + (shown.length === 1 ? " one" : "") + '">' + shown.map(function (p) { return '<img src="' + p.photo + '" alt="' + esc(p.name) + '" loading="lazy" decoding="async" />'; }).join("") + "</span>"
      : "");
  /* The card says it once: the title and the Pair with line.
     The full piece names live in the outfit view, under
     Yours / Suggested — the title is derived from the pieces,
     so repeating them here said the same thing three times. */
  return '<button type="button" class="card option-card fw-card" data-fw-idx="' + idx + '" role="listitem">' +
    photos +
    '<span class="oc-body">' +
    '<span class="oc-title">' + esc(look.title) + '</span>' +
    (look.suggestedBottom ? '<span class="oc-meta fw-pair">Pair with: ' + esc(look.suggestedBottom.name) + ' — suggested</span>' : "") +
    "</span></button>";
}

/* The outfit view for a From wardrobe card: the verified render
   of him wearing this exact outfit full-width at the top when the
   pairing has one (tappable to full size), then his actual pieces
   listed below — their own photographs, named as his — plus the
   suggested bottom, named as a suggestion. A render is only ever
   shown for the exact top + shoes pairing it was verified for. */
function openFwOutfit(idx) {
  var look = fwLooks[idx];
  var layer = document.getElementById("fw-layer");
  var box = document.getElementById("fw-layer-body");
  if (!look || !layer || !box) return;
  var hero = look.fwRender ? '<img class="fw-hero" src="' + fwRenderSrc(look) + '" alt="' + esc(look.imgAlt || look.title || "") + '" data-popout="' + fwRenderSrc(look) + '" data-popout-alt="' + esc(look.imgAlt || "") + '" loading="lazy" decoding="async" />' : "";
  var figs = (look.fwPieces || []).map(function (p) {
    return '<figure class="fw-piece" data-fw-piece="' + esc(p.id) + '" role="button" tabindex="0" aria-label="Open ' + esc(p.name) + ' in the Closet">' +
      (p.photo
        ? '<img src="' + p.photo + '" alt="' + esc(p.name) + '" loading="lazy" decoding="async" />'
        : '<span class="fw-nophoto" style="background:' + (p.colourHex || "#8a8d8f") + '"></span>') +
      '<figcaption><span class="fw-yours">Yours</span>' + esc(p.name) + '</figcaption></figure>';
  }).join("");
  if (look.suggestedBottom) {
    figs += '<figure class="fw-piece fw-suggested"><span class="fw-nophoto" style="background:' + look.suggestedBottom.hex + '"></span>' +
      '<figcaption><span class="fw-yours suggested">Suggested</span>' + esc(look.suggestedBottom.name) + ' — not in your closet yet</figcaption></figure>';
  }
  var fwWatch = "";
  try { if (typeof compactWatchBtnHTML === "function" && !isSwimLook(look)) fwWatch = '<div class="cdd watch-cdd fw-watch-cdd" data-fw-watch="' + idx + '"><button type="button" class="cdd-btn watch-cdd-btn" aria-haspopup="true" aria-expanded="false" aria-label="Watch for this look — tap to choose a watch">' + compactWatchBtnHTML(look) + '</button><div class="cdd-menu watch-menu" hidden role="menu" aria-label="Choose a watch"></div></div>'; } catch (e) {}
  box.innerHTML = '<article class="card fw-outfit">' +
    '<div class="fw-outfit-head"><span class="oc-label">From wardrobe</span><button type="button" class="btn-ghost" data-fw-close>Back</button></div>' +
    '<h3>' + esc(look.title) + '</h3>' +
    hero + fwWatch +
    '<div class="fw-pieces">' + figs + '</div>' +
    '<p class="fw-outfit-note">' + esc((look.notes || []).join(" ")) + '</p>' +
    swapSectionHTML(look, idx) +
    '<div class="look-actions">' +
    '<button type="button" class="btn-ghost" data-fw-like="' + idx + '">I like it</button>' +
    '<button type="button" class="btn-ghost" data-fw-save="' + idx + '">Save</button>' +
    '<button type="button" class="btn-ghost" data-fw-find="' + idx + '">Shop the look</button>' +
    '</div>' +
    '</article>';
  if (layer.hidden && typeof viewPushLayer === "function") viewPushLayer("fw"); /* build .38 (2.11) */
  layer.hidden = false;
  layer.scrollTop = 0;
}
/* Close the From wardrobe pop-out: hide and empty the layer,
   and restore the dealt FW array a capsule visit swapped in. */
function closeFwLayer() {
  var layer = document.getElementById("fw-layer");
  var box = document.getElementById("fw-layer-body");
  var wasOpen = !!(layer && !layer.hidden);
  if (layer) layer.hidden = true;
  if (box) box.innerHTML = "";
  if (fwLooksBackup) { fwLooks = fwLooksBackup; fwLooksBackup = null; }
  if (wasOpen && typeof viewPopLayer === "function") viewPopLayer("fw"); /* build .38 (2.11) */
}


function dealFromWardrobe() {
  closeFwLayer();
  var grid = document.getElementById("fw-grid");
  var empty = document.getElementById("fw-empty");
  var more = document.getElementById("fw-more");
  var count = document.getElementById("fw-count");
  if (!grid) return;
  if (count && typeof wardrobeItems !== "undefined") {
    var availCount = wardrobeItems.filter(function (i) { return !i.laundry; }).length;
    count.textContent = availCount ? availCount + (availCount === 1 ? " piece" : " pieces") + " in your closet." : "";
  }
  var looks = (typeof buildClosetLooks === "function") ? buildClosetLooks() : null;
  fwClosetSig = closetSig();
  if (!looks || !looks.length) {
    fwLooks = [];
    grid.innerHTML = "";
    if (empty) empty.hidden = false;
    if (more) more.hidden = true;
    return;
  }
  /* Graduated (liked) closet looks leave the From wardrobe
     rotation; if every look has graduated, show the full list —
     graduation never blanks the section. */
  var fwFresh = looks.filter(function (l) { return !isGraduatedLook(l) && !lookPhotoBanned56(l); });
  fwLooks = fwFresh.length ? fwFresh : looks.filter(function (l) { return !lookPhotoBanned56(l); });
  if (empty) empty.hidden = true;
  if (more) more.hidden = false;
  grid.innerHTML = fwLooks.map(function (look, idx) { return fwCardHTML(look, idx); }).join("");
}
/* Deal six From wardrobe renders into the Ideas grid (build
   .28): a window over the verified closet looks. Liked looks
   graduate out (build .10); photographs already dealt sit out
   until the window runs dry, then the oldest return — the same
   discipline as the inspo deck. renderOptions records the six
   as dealt, so the next deal advances the window. */
/* The Wardrobe six, as a value (build .50): the window of
   verified closet looks dealWardrobeSix renders — and the ONLY
   looks a Wardrobe-stamped deal may ever contain, since every
   one of them comes from buildClosetLooks (fwPieces present,
   every id a closet item). buildSixLooks returns this same
   window for any deal whose source is Wardrobe, so no path can
   stamp pool renders as wardrobe looks. Null when the closet
   cannot deal. */
function wardrobeSixLooks() {
  var cl = (typeof buildClosetLooks === "function") ? buildClosetLooks() : null;
  if (!cl || !cl.length) return null;
  var fresh = cl.filter(function (l) { return !isGraduatedLook(l) && !lookPhotoBanned56(l); });
  var pool = fresh.length ? fresh : cl.filter(function (l) { return !lookPhotoBanned56(l); });
  function dealt(l) {
    return (l.fwRender && dealtImgHistory.indexOf(l.fwRender) !== -1) ||
      (l.img && dealtImgHistory.indexOf(l.img) !== -1) ||
      dealtImgHistory.indexOf(fwRenderSrc(l)) !== -1;
  }
  var six = pool.filter(function (l) { return !dealt(l); }).slice(0, 6);
  if (six.length < 6) {
    var used = {};
    six.forEach(function (l) { used[l.fwRender || l.img] = 1; });
    pool.forEach(function (l) {
      if (six.length < 6 && !used[l.fwRender || l.img]) { used[l.fwRender || l.img] = 1; six.push(l); }
    });
  }
  return six.length ? six : null;
}
function dealWardrobeSix() {
  var six = wardrobeSixLooks();
  if (!six) return false;
  renderOptions(six, { desc: "From your wardrobe", occasion: "", season: "", opts: { basis: (typeof studioBasis !== "undefined" ? studioBasis : "both"), source: "wardrobe" } });
  return true;
}
(function initFromWardrobe() {
  var grid = document.getElementById("fw-grid");
  if (grid) dealFromWardrobe();
  var more = document.getElementById("fw-more");
  if (more) more.addEventListener("click", function () {
    dealFromWardrobe();
    if (!fwLooks.length) toast("Your closet needs a top and a pair of shoes before it can build outfits.");
  });
  if (grid) grid.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-fw-idx]");
    if (!btn || !fwLooks.length) return;
    var idx = parseInt(btn.getAttribute("data-fw-idx"), 10);
    if (!fwLooks[idx]) return;
    openFwOutfit(idx);
  });
  var fwDetail = document.getElementById("fw-layer");
  if (fwDetail) fwDetail.addEventListener("click", function (e) {
    var fwPick = e.target.closest("[data-watch-pick]");
    var fwWrap = e.target.closest("[data-fw-watch]");
    if (fwPick && fwWrap) {
      var widx = parseInt(fwWrap.getAttribute("data-fw-watch"), 10);
      var wlook = fwLooks[widx];
      if (wlook && typeof applyWatchChoice === "function") { applyWatchChoice(wlook, fwPick.getAttribute("data-watch-pick")); if (typeof closeAllCdd === "function") closeAllCdd(); openFwOutfit(widx); }
      return;
    }
    if (fwWrap) return; /* the compact dropdown's own toggle handles the tap */
    if (e.target.closest("[data-fw-close]")) {
      closeFwLayer();
      return;
    }
    var fwLike = e.target.closest("[data-fw-like]");
    if (fwLike) {
      var lk = fwLooks[parseInt(fwLike.getAttribute("data-fw-like"), 10)];
      if (lk) {
        if (likeLook(lk)) toast("Liked — saved and queued in My Outfits.");
        else toast("That photo is on your not-for-me list — not saved.");
      }
      return;
    }
    var fwSave = e.target.closest("[data-fw-save]");
    if (fwSave) {
      var sv = fwLooks[parseInt(fwSave.getAttribute("data-fw-save"), 10)];
      if (sv) saveLook(JSON.parse(JSON.stringify(sv)));
      return;
    }
    var fwFind = e.target.closest("[data-fw-find]");
    if (fwFind) {
      var fd = fwLooks[parseInt(fwFind.getAttribute("data-fw-find"), 10)];
      if (fd) openFindLookMode(JSON.parse(JSON.stringify(fd)));
      return;
    }
    var fig = e.target.closest("[data-fw-piece]");
    if (fig) {
      var pid = fig.getAttribute("data-fw-piece");
      if (pid && typeof closetItemById === "function" && closetItemById(pid)) {
        closeFwLayer();
        detailItemId = pid;
        switchTab("wardrobe");
        renderItemDetail();
      }
    }
  });
  var prevSwitch = window.switchTab;
  if (typeof prevSwitch === "function") {
    window.switchTab = function (name, opts) {
      prevSwitch(name, opts);
      if (name === "studio" && closetSig() !== fwClosetSig) dealFromWardrobe();
    };
  }

  /* ---------- Ideas source selector — the three boxes at the top
     of Ideas. One shared source setting with Today's "Build from"
     selector: setSource already moves every [data-source] control
     together (these boxes, Today's row, the Customize form row);
     this wrapper also keeps the Today store key in step, so the
     saved mode persists on-device and fresh opens honour it in
     both places. Default Combo. A tap applies silently — no
     popup, no toast — and re-deals the Ideas below at once:
     wardrobe only deals his closet render looks, inspo only
     deals the inspo deck (the From wardrobe section steps
     aside), Combo is the usual mix of inspo deals plus the
     From wardrobe section. ---------- */
  /* setSource itself persists the single todaySource key now —
     no wrapper needed to keep the controls in step. */
  function syncFwSectionVisibility() {
    var sec = document.getElementById("from-wardrobe");
    /* The From wardrobe section is gone (build .28) — the toggle
       names the source and the one grid deals it. All that is
       left here is closing a stray FW outfit layer when the
       source leaves Combo. */
    if (sec) sec.hidden = true;
    if (studioSource !== "combo") closeFwLayer();
  }
  function dealIdeasForSource() {
    syncFwSectionVisibility();
    /* One grid, six looks, whichever source the toggle names
       (build .28): Wardrobe deals its window of verified closet
       renders; Inspo and Combo deal through the form's engine. */
    if (studioSource === "wardrobe" && dealWardrobeSix()) return;
    dealSilent = true;
    doStyleFromForm();
  }
  /* Build .50: the Ideas Outfit type row re-deals through this
     same path when a deal is showing. */
  window.dealIdeasForSource = dealIdeasForSource;
  var seg = document.getElementById("ideas-source-seg");
  if (seg) seg.addEventListener("click", function (e) {
    var b = e.target.closest("[data-source]");
    if (!b) return;
    var s = b.getAttribute("data-source");
    if (s === studioSource) { syncFwSectionVisibility(); return; }
    setSource(s);
    dealIdeasForSource();
  });
  syncFwSectionVisibility();
})();

/* ---------- Init ---------- */
(function initWearing() {
  var d = document.getElementById("wearing-date");
  if (d && !d.value) d.value = localTodayISO();
  resetWearingRows();
  renderWornLog();
})();
renderMyInspo();

/* ================= Blob store (build .57) =================
   Sync photo offload: photo bytes travel as their own "blobs"
   records, keyed by the SHA-256 of the data URI; synced records
   carry only a short "blob:<hash>" reference. The bytes live
   here — an in-memory cache backed by their own IndexedDB
   database ("wardrobe-blobs", store "b") — mirroring the photo
   vault's patterns. If IndexedDB is unavailable or fails, the
   store runs cache-only for the session and never throws. A
   blob that is not on this device yet is left as-is in the DOM
   (no error, no placeholder swap) until it arrives; when it
   arrives, the sync apply path's fillIn swaps it in. */
window.blobStore = (function () {
  "use strict";
  var cache = {};
  var db = null;
  var _fetching = {};
  var B = { cache: cache, missing: 0 };
  B.put = function (hash, uri) {
    if (!hash || typeof uri !== "string") return;
    cache[hash] = uri;
    if (!db) return;
    try {
      var tx = db.transaction("b", "readwrite");
      tx.objectStore("b").put(uri, hash);
    } catch (e) {}
  };
  B.fetch = function (hash, cb) {
    if (cache[hash] !== undefined) { cb(cache[hash]); return; }
    if (_fetching[hash]) { _fetching[hash].push(cb); return; }
    if (!db) { cb(null); return; }
    _fetching[hash] = [cb];
    function doneFetch(val) {
      var cbs = _fetching[hash] || [];
      delete _fetching[hash];
      cbs.forEach(function (f) { try { f(val); } catch (e) {} });
    }
    try {
      var rq = db.transaction("b").objectStore("b").get(hash);
      rq.onsuccess = function () {
        var val = rq.result === undefined ? null : rq.result;
        if (val !== null) cache[hash] = val;
        doneFetch(val);
      };
      rq.onerror = function () { doneFetch(null); };
    } catch (e) { doneFetch(null); }
  };
  B.fillIn = function (hash, uri) {
    if (!hash || typeof uri !== "string") return;
    var ref = "blob:" + hash;
    try {
      document.querySelectorAll("img").forEach(function (im) { if (im.getAttribute("src") === ref) im.src = uri; });
      document.querySelectorAll("[data-popout]").forEach(function (el) { if (el.getAttribute("data-popout") === ref) el.setAttribute("data-popout", uri); });
    } catch (e) {}
  };
  B.sha256 = function (str) {
    try {
      if (typeof crypto === "undefined" || !crypto.subtle || !crypto.subtle.digest || typeof TextEncoder === "undefined") return Promise.resolve(null);
      return crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(str))).then(function (buf) {
        var bytes = new Uint8Array(buf), hex = "";
        for (var i = 0; i < bytes.length; i++) { var h = bytes[i].toString(16); hex += (h.length === 1 ? "0" : "") + h; }
        return hex;
      }).catch(function () { return null; });
    } catch (e) { return Promise.resolve(null); }
  };
  function resolveRef(ref) {
    if (!ref || ref.indexOf("blob:") !== 0) return;
    var hash = ref.slice(5);
    if (!/^[0-9a-f]{64}$/.test(hash)) return;
    if (cache[hash] !== undefined) { B.fillIn(hash, cache[hash]); return; }
    B.fetch(hash, function (uri) { if (uri) B.fillIn(hash, uri); });
  }
  function checkImg(img) {
    if (!img || img.tagName !== "IMG") return;
    var s = null;
    try { s = img.getAttribute("src"); } catch (e) {}
    if (s && s.indexOf("blob:") === 0) resolveRef(s);
  }
  function checkPopout(el) {
    if (!el || !el.getAttribute) return;
    var s = null;
    try { s = el.getAttribute("data-popout"); } catch (e) {}
    if (s && s.indexOf("blob:") === 0) resolveRef(s);
  }
  function scan(root) {
    if (!root) return;
    try {
      if (root.tagName === "IMG") checkImg(root);
      checkPopout(root);
      if (root.querySelectorAll) {
        root.querySelectorAll("img").forEach(checkImg);
        root.querySelectorAll("[data-popout]").forEach(checkPopout);
      }
    } catch (e) {}
  }
  function startObserver() {
    scan(document);
    if (typeof MutationObserver === "undefined") return;
    try {
      var mo = new MutationObserver(function (muts) {
        muts.forEach(function (m) {
          if (m.type === "attributes") { checkImg(m.target); checkPopout(m.target); }
          else for (var i = 0; i < m.addedNodes.length; i++) { var n = m.addedNodes[i]; if (n.nodeType === 1) scan(n); }
        });
      });
      mo.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["src"] });
    } catch (e) {}
  }
  try {
    if (typeof indexedDB !== "undefined") {
      var rq = indexedDB.open("wardrobe-blobs", 1);
      rq.onupgradeneeded = function () {
        var d = rq.result;
        if (!d.objectStoreNames.contains("b")) d.createObjectStore("b");
      };
      rq.onerror = function () {};
      rq.onblocked = function () {};
      rq.onsuccess = function () {
        db = rq.result;
        try {
          var cur = db.transaction("b").objectStore("b").openCursor();
          cur.onerror = function () {};
          cur.onsuccess = function () {
            var c = cur.result;
            if (c) { if (typeof c.value === "string") cache[c.key] = c.value; c.continue(); return; }
            /* Every stored entry is in cache now: give any
               "blob:" image already on the page its bytes. */
            try { scan(document); } catch (e) {}
          };
        } catch (e) {}
      };
    }
  } catch (e) { db = null; }
  try {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startObserver);
    else startObserver();
  } catch (e) {}
  return B;
})();

/* ================= Cloud sync =================
   Wardrobe's state, synced through the wardrobe-sync service —
   a deliberate twin of Padel Log's sync: same contract, same
   merge rules. Records sync per-id, last-writer-wins by
   updatedAt, deletes as tombstones; settings sync as one meta
   document applied field-by-field. Per-device UI state (tab,
   openIcon, iconSeen) never syncs.

   Safety rules, non-negotiable:
   · A failed or empty pull NEVER touches local state — downloads
     apply only from a 200 response that parses and carries `now`.
   · Merges only, never replacement — an empty recs array is a
     normal result, never a signal to clear anything.
   · A record's dirty flag clears only after the server answers
     200 for the sync that carried it.
   · First run uploads before any download is applied, so existing
     local data can never be overwritten by a fresh empty account.
   · A rejected key is NEVER dropped automatically. Sync pauses
     and says so; a new account is only made when the user asks
     for one (two taps). One stray 401 used to split this device
     off into a fresh, empty account without a word.
   · A dirty flag clears only if the record has not changed again
     since the copy that was sent — an edit made while a sync is
     in flight stays dirty and goes up on the next pass.
   · Settings merge field by field, each with its own timestamp,
     so a device holding an old profile cannot overwrite a newer
     one just because it dealt a look more recently. */
var SYNC_URL = "https://wardrobe-sync.dyacobs.workers.dev";
try { SYNC_URL = localStorage.getItem("wardrobe.syncurl") || SYNC_URL; } catch (e) {}
var SY_COLLS = ["looks", "queue", "items", "watches", "worn", "inspo", "finds", "palettes", "icons", "plan", "anchors", "trips", "packed", "receipts", "shopwish", "pricedrops", "edits", "searches", "ask", "blobs"];
function syBlank() {
  var o = { key: null, acct: null, last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: "Not synced yet", lastOk: 0 };
  SY_COLLS.forEach(function (c) { o.snap[c] = {}; o.st[c] = {}; o.tomb[c] = {}; o.dirty[c] = {}; });
  o.snap.m = ""; o.st.m = 0; o.dirty.m = 0;
  o.mf = {}; o.rej = 0;
  o.quar = []; /* build .56: remote records that failed to apply, quarantined per record */
  o.bp = {}; /* build .57: hashes of blobs this device has pushed */
  o.mig57 = ""; /* build .57: account key the one-time blob migration ran for */
  o.restore59 = ""; /* build .59: account key the one-time tomb-restore re-download completed for */
  o.photoPull741 = ""; /* build .74.1: one-time photo re-pull after cursor-ahead-of-persist */
  o.photoPull742 = ""; /* build .74.2: the same re-pull, marked done only after the photo vault confirms its writes */
  return o;
}
var SY = null;
try { SY = JSON.parse(localStorage.getItem("wardrobe.sync") || "null"); } catch (e) { SY = null; }
if (!SY || typeof SY !== "object") SY = syBlank();
else {
  var _syb = syBlank();
  SY_COLLS.forEach(function (c) {
    SY.snap[c] = (SY.snap && SY.snap[c]) || {}; SY.st[c] = (SY.st && SY.st[c]) || {};
    SY.tomb[c] = (SY.tomb && SY.tomb[c]) || {}; SY.dirty[c] = (SY.dirty && SY.dirty[c]) || {};
  });
  SY.snap.m = typeof SY.snap.m === "string" ? SY.snap.m : "";
  SY.st.m = typeof SY.st.m === "number" ? SY.st.m : 0;
  SY.dirty.m = typeof SY.dirty.m === "number" ? SY.dirty.m : 0;
  if (typeof SY.last !== "number") SY.last = 0;
  if (!SY.status) SY.status = "Not synced yet";
  if (!("key" in SY)) SY.key = null;
  if (!("acct" in SY)) SY.acct = null;
  if (!SY.mf || typeof SY.mf !== "object") SY.mf = {};
  if (typeof SY.rej !== "number") SY.rej = 0;
  if (!Array.isArray(SY.quar)) SY.quar = [];
  if (!SY.bp || typeof SY.bp !== "object" || Array.isArray(SY.bp)) SY.bp = {};
  if (typeof SY.mig57 !== "string") SY.mig57 = "";
  if (typeof SY.restore59 !== "string") SY.restore59 = "";
}
function saveSY() { try { localStorage.setItem("wardrobe.sync", JSON.stringify(SY)); return true; } catch (e) { try { storeNoteFailure(); } catch (e2) {} return false; } }
function syHsh(x) {
  var t = JSON.stringify(x) || "";
  var h = 5381;
  for (var i = 0; i < t.length; i++) h = ((h * 33) ^ t.charCodeAt(i)) >>> 0;
  return h.toString(36) + t.length;
}
/* Build .55: the wire form of a sync value. A long data:image
   string is represented by its vault reference ("idb:<key>") —
   the key is content-derived (photoVault.keyOf is pure), so two
   devices holding the same photo hash identically without the
   hash ever touching the photo bytes. When the vault is live
   the blob is also put into it, so the reference is guaranteed
   resolvable on this device. Hashing always uses the wire form;
   upload payloads use it only where the brief says so. */
function syWire(v) {
  if (typeof v === "string") {
    if (v.length > 2048 && v.indexOf("data:image/") === 0) {
      var pv = window.photoVault;
      if (pv && pv.keyOf) {
        var key = pv.keyOf(v);
        if (pv.enabled && pv.put) { try { pv.put(key, v); } catch (e) {} }
        return "idb:" + key;
      }
    }
    return v;
  }
  if (Array.isArray(v)) return v.map(function (x) { return syWire(x); });
  if (v && typeof v === "object") {
    var out = {};
    Object.keys(v).forEach(function (k) { out[k] = syWire(v[k]); });
    return out;
  }
  return v;
}
/* The inverse for incoming data, mirroring the store reviver:
   a short "idb:<key>" string resolves from the vault cache when
   the blob is on this device; when it is not, the reference
   itself is kept (so a later save writes it back unchanged) and
   the miss is counted. */
function syUnwire(v) {
  if (typeof v === "string") {
    if (v.length < 80 && v.indexOf("idb:") === 0) {
      var pv2 = window.photoVault;
      var hit = pv2 && pv2.cache ? pv2.cache[v.slice(4)] : undefined;
      if (hit !== undefined) return hit;
      if (pv2) pv2.missing = (pv2.missing || 0) + 1;
    }
    return v;
  }
  if (Array.isArray(v)) return v.map(function (x) { return syUnwire(x); });
  if (v && typeof v === "object") {
    var out2 = {};
    Object.keys(v).forEach(function (k) { out2[k] = syUnwire(v[k]); });
    return out2;
  }
  return v;
}
function syWireRec(c, r) { return syWire(syRecData(c, r)); }
/* Record identity + access, per the wiring brief's mapping. Seed
   items/watches are static site content and never sync. */
function syWornId(en) { return en.id || ("worn-" + syHsh(en.date + "|" + en.title)); }
function syFindId(f) { return f.id || ("find-" + syHsh(f)); }
function syRecId(c, r) {
  if (!r) return null;
  if (c === "worn") return syWornId(r);
  if (c === "finds") return syFindId(r);
  if (c === "shopwish") return r.key || r.id || null;
  return r.id || null;
}
function syRecData(c, r) {
  if ((c === "worn" && !r.id) || (c === "finds" && !r.id) || (c === "shopwish" && !r.id)) {
    var cp = Object.assign({}, r);
    cp.id = syRecId(c, r);
    return cp;
  }
  return r;
}
function syCollGet(c) {
  switch (c) {
    case "looks": return savedLooks;
    case "queue": return queueLooks;
    case "items": return wardrobeItems.filter(function (i) { return i.id.indexOf("seed-") !== 0; });
    case "watches": return watches.filter(function (w) { return w.id.indexOf("seed-") !== 0; });
    case "worn": return wornLog;
    case "inspo": return inspoImages;
    case "finds": return finds;
    case "palettes": return customPalettes;
    case "icons": return customIcons;
    case "plan": return weekPlan;
    case "anchors": return buildAnchors;
    case "trips": return userTrips;
    case "packed": return packedItems;
    case "receipts": return receiptInbox;
    case "shopwish": return shopWishlist;
    case "pricedrops": return priceDrops;
    case "edits": return editMeta;
    case "searches": return editSearches;
    case "ask": return askSync;
    case "blobs": return [];
  }
  return [];
}
function syMetaOf() {
  return {
    profile: profile,
    deletedIds: deletedIds,
    overrides: entryOverrides,
    dislikedImgs: dislikedImgs,
    recentlyRemoved: recentlyRemoved,
    findBudget: budgetLevel,
    shopTier: shopTier,
    priceRange: (typeof priceRange === "string" ? priceRange : "any"),
    homeLocation: homeLoc,
    currentLocation: currentLoc,
    formality: formalityLevel,
    studioSettings: store.get("studioSettings", null),
    lastOpeningImg: store.get("lastOpeningImg", null)
  };
}
/* Change tracking: diff each collection against the content-hash
   snapshot. Changed/new records are stamped and marked dirty;
   vanished ids become tombstones. Runs on every tracked store
   write (hinted to the affected collection) and in full at boot
   and at the start of every sync, so no write path is missed. */
var SY_KEY_COLL = { looks: "looks", queue: "queue", items: "items", watches: "watches", wornLog: "worn", inspoImages: "inspo", finds: "finds", palettes: "palettes", icons: "icons", weekPlan: "plan", buildAnchors: "anchors", trips: "trips", packedItems: "packed", receiptInbox: "receipts", shopWishlist: "shopwish", priceDrops: "pricedrops", editMeta: "edits", editSearches: "searches", askSync: "ask" };
var SY_COLL_KEY = { looks: "looks", queue: "queue", items: "items", watches: "watches", worn: "wornLog", inspo: "inspoImages", finds: "finds", palettes: "palettes", icons: "icons", plan: "weekPlan", anchors: "buildAnchors", trips: "trips", packed: "packedItems", receipts: "receiptInbox", shopwish: "shopWishlist", pricedrops: "priceDrops", edits: "editMeta", searches: "editSearches", ask: "askSync" };
var SY_META_KEYS = { profile: 1, deletedIds: 1, overrides: 1, dislikedImgs: 1, recentlyRemoved: 1, findBudget: 1, shopTier: 1, priceRange: 1, homeLocation: 1, currentLocation: 1, formality: 1, studioSettings: 1, lastOpeningImg: 1 };
function syTrackChanges(onlyColl) {
  var now = Date.now(), ch = false, mig = false;
  var colls = onlyColl ? [onlyColl] : SY_COLLS;
  colls.forEach(function (c) {
    /* Poisoned store key: the in-memory list is a fallback, not
       the data. Diffing it would tombstone every real record —
       skip the collection entirely until it is restored. */
    if (store.poisoned(SY_COLL_KEY[c])) return;
    var seen = {};
    syCollGet(c).forEach(function (r) {
      var id = syRecId(c, r);
      if (!id) return;
      seen[id] = true;
      var h = syHsh(syWireRec(c, r));
      if (SY.snap[c][id] !== h) {
        /* Silent migration (build .55): a snapshot taken by an
           older build holds the OLD raw hash of this same record.
           Rewriting it to the wire hash is not a change — no
           dirty flag, no new stamp — or an upgrade would
           re-upload the whole library once. */
        if (SY.snap[c][id] !== undefined && SY.snap[c][id] === syHsh(syRecData(c, r))) { SY.snap[c][id] = h; mig = true; }
        else { SY.snap[c][id] = h; SY.st[c][id] = now; SY.dirty[c][id] = 1; delete SY.tomb[c][id]; ch = true; }
      }
    });
    Object.keys(SY.snap[c]).forEach(function (id) {
      if (!seen[id]) {
        /* Build .77: a closet / watch record that vanished without a
           deliberate delete this session (a boot-time repair, a merge,
           a half-written store) is NEVER tombstoned — that would delete
           a real piece on every device. Forget the snapshot entry and
           re-download everything once, so the server copy comes back. */
        if ((c === "items" || c === "watches") && id.indexOf("seed-") !== 0 &&
            !(typeof _sySessionDeletes !== "undefined" && _sySessionDeletes[c] && _sySessionDeletes[c][id])) {
          delete SY.snap[c][id]; delete SY.st[c][id]; delete SY.dirty[c][id];
          SY.restore59 = null; SY.lost77 = (SY.lost77 || 0) + 1; ch = true;
          return;
        }
        delete SY.snap[c][id]; delete SY.st[c][id]; SY.tomb[c][id] = now; SY.dirty[c][id] = 1; ch = true;
      }
    });
  });
  /* Settings: one hash + timestamp per field. A field seen for
     the first time inherits the old whole-document stamp, so an
     upgrade never makes stale settings look new. */
  var meta = syMetaOf(), mch = false;
  Object.keys(meta).forEach(function (f) {
    if (store.poisoned(f) || _syMetaRestore[f]) return; /* fallback value — never tracked, never uploaded */
    var h = syHsh(syWire(meta[f])), cur = SY.mf[f];
    if (!cur) { SY.mf[f] = { h: h, t: SY.st.m || 0 }; ch = true; }
    else if (cur.h !== h) { cur.h = h; cur.t = now; mch = true; }
  });
  if (mch) { SY.st.m = now; SY.dirty.m = 1; ch = true; }
  if (ch || mig) saveSY();
  return ch;
}
var _syT = null, _syBusy = false, _syApplying = false, _syAgain = false;
var _syForcePhotoPull741 = false;
function schedSync() { clearTimeout(_syT); _syT = setTimeout(function () { syncNow(); }, 1500); }
function syncStatusHTML() {
  return "<div><b>" + esc(SY.status) + "</b></div>" +
    '<p class="meta">' + (SY.lastOk ? "Last synced " + new Date(SY.lastOk).toLocaleString() : "Never synced") +
    (SY.acct ? " · account " + esc(String(SY.acct).slice(0, 8)) : "") + "</p>" +
    /* Build .56: the quarantine count lives here and only here —
       never a popup. */
    ((SY.quar && SY.quar.length) ? '<p class="meta">' + SY.quar.length + (SY.quar.length === 1 ? " synced record" : " synced records") + " couldn't be read and were skipped — everything else synced normally.</p>" : "");
}
function syShowRejected() {
  var b = document.getElementById("sync-new-acct");
  if (b) b.hidden = !SY.rej;
  if (!SY.rej) { var n = document.getElementById("sync-new-note"); if (n) n.textContent = ""; }
}
function setSyncStatus(t) {
  SY.status = t; saveSY();
  var e = document.getElementById("syncstat");
  if (e) e.innerHTML = syncStatusHTML();
  var kf = document.getElementById("sync-key");
  if (kf) kf.value = SY.key || "(created on first sync)";
  syShowRejected();
  syNoteRender();
}
/* The slim sync note. Sync state otherwise lives only in
   Profile, so a failed upload sat invisible while the user
   stood on My Looks — the look was saved, nothing said the
   sync hadn't landed, and the wait read as "stuck". A failure
   (or a rejected key) with changes still waiting on this
   device raises this note with a working Retry; a successful
   sync puts it away. It is a slim note, never a popup, and
   dismissing it holds only until the next failure. A failed
   sync also retries itself once after 30 seconds, so a brief
   connection drop heals without the user doing anything. */
var _syFailed = false, _syRetryT = null, _syNoteOff = false;
/* Mass-delete guard state: a sync pass that would delete more
   than ~20% of a collection is held until the user confirms it
   in the data-alert note (the worker enforces the same rule and can
   raise the hold itself with a 409). _syMassOkUntil arms one
   confirmed pass; _syMassDenied holds a coll silently for the
   session after a "Keep them" answer. */
var _syMassHold = null, _syMassOkUntil = 0, _syMassDenied = {};
/* Build .59: ids the user deleted in THIS page lifetime. Only a
   single such delete (not a mass batch) may block a live server
   record. Leftover unsent tombs are not in this map. */
var _sySessionDeletes = {};
/* Ids restored from a live server record over an unsent tomb —
   never uploaded as a delete, even if trackChanges re-arms one. */
var _syRestoredIds = {};
/* Settings fields being restored from the server after a poison:
   untracked and unuploaded until the download lands, so their
   in-memory fallback values can never overwrite the good copy. */
var _syMetaRestore = {};
/* Set when the worker refuses /register for want of the
   registration code: background syncs stand down (no retry loop)
   until the user saves a code and taps Sync now. */
var _syRegNeed = false;
function syPendingCount() {
  var n = SY.dirty.m ? 1 : 0;
  SY_COLLS.forEach(function (c) { n += Object.keys(SY.dirty[c]).length; });
  return n;
}
/* Build .56 defect fix — the fixed sync / data notes sit at
   bottom:76px on phone widths and would cover the Today hero's
   selector row. While either note is visible, pad #panel-today
   (border-box at phone widths, hero band flexes) so the caption
   and selector row rise clear of the note; when both notes hide,
   the padding clears and the hero returns to its exact geometry. */
function todayNotePad() {
  var panel = document.getElementById("panel-today");
  if (!panel) return;
  if (window.innerWidth > 899) { panel.style.paddingBottom = ""; return; }
  var max = 0;
  ["sync-note", "data-alert"].forEach(function (id) {
    var n = document.getElementById(id);
    if (n && !n.hidden) max = Math.max(max, n.offsetHeight);
  });
  panel.style.paddingBottom = max ? (max + 8) + "px" : "";
}
window.addEventListener("resize", todayNotePad);
function syNoteRender() {
  var el = document.getElementById("sync-note");
  if (!el) return;
  var pending = syPendingCount();
  var show = !_syNoteOff && (!!SY.rej || (_syFailed && pending > 0));
  el.hidden = !show;
  if (document.body) document.body.classList.toggle("sync-note-on", show);
  if (show) {
    var tx = document.getElementById("sync-note-text");
    if (tx) tx.textContent = SY.rej
      ? "Sync paused — this device's key wasn't accepted. Your looks are safe on this device."
      : "Couldn't sync — " + pending + (pending === 1 ? " change is" : " changes are") + " still on this device.";
  }
  todayNotePad();
}
/* The data alert: two guards share one slim note (never a popup).
   1) A stored list couldn't be read (poisoned key): its raw value
      is preserved and its uploads are blocked; Restore pulls the
      last good copy back from sync (or offers a backup import
      when this device has no sync key).
   2) A sync pass would delete more than ~20% of a collection:
      held until the user confirms the deletions here.
   Dismissing hides the note for the session; the blocks stay. */
var _dataNoteOff = false, _dataNoteMode = "";
function dataNoteRender() {
  var el = document.getElementById("data-alert");
  if (!el) return;
  var tx = document.getElementById("data-alert-text");
  var btn = document.getElementById("data-alert-btn");
  var poisoned = store.poisonedKeys();
  if (!_dataNoteOff && poisoned.length) {
    _dataNoteMode = "poison";
    el.hidden = false;
    if (tx) tx.textContent = "This list couldn't be read — " + poisoned.join(", ") + ". The unreadable copy is kept safe on this device and nothing from it will be uploaded. Restore from " + (SY && SY.key ? "your synced copy?" : "a backup?");
    if (btn) btn.textContent = "Restore";
    todayNotePad();
    return;
  }
  if (!_dataNoteOff && _syMassHold) {
    _dataNoteMode = "mass";
    el.hidden = false;
    if (tx) tx.textContent = "This device is trying to delete " + _syMassHold.deletions + " of " + _syMassHold.live + " records in one list. Those deletes were not sent — nothing on the server was changed. If you really want to delete them on every device, tap Confirm deletes.";
    if (btn) btn.textContent = "Confirm deletes";
    todayNotePad();
    return;
  }
  _dataNoteMode = "";
  el.hidden = true;
  todayNotePad();
}
function dataAlertAction() {
  if (_dataNoteMode === "mass") {
    /* Confirmed: arm one pass and let it through both guards. */
    _syMassOkUntil = Date.now() + 120000;
    _syMassHold = null;
    dataNoteRender();
    syncNow(false, true);
    return;
  }
  if (_dataNoteMode !== "poison") return;
  var keys = store.poisonedKeys();
  if (!keys.length) { dataNoteRender(); return; }
  if (SY && SY.key) {
    /* Restore from the synced copy: drop the local fallback state
       for the poisoned keys, forget what this device thinks the
       server holds for them, and re-download from sequence zero.
       The preserved raw text stays in the corrupt-copy store. */
    keys.forEach(function (k) {
      store.clearPoison(k);
      store.putRaw(k, null);
      var coll = SY_KEY_COLL[k];
      if (coll) { SY.snap[coll] = {}; SY.st[coll] = {}; SY.tomb[coll] = {}; SY.dirty[coll] = {}; }
      else if (SY_META_KEYS[k]) { delete SY.mf[k]; _syMetaRestore[k] = 1; }
    });
    SY.last = 0;
    saveSY();
    toast("Restoring from your synced copy…");
    dataNoteRender();
    syncNow(false, true);
  } else {
    var f = document.getElementById("data-import-file");
    if (f) { toast("No synced copy on this device — choose a backup file to restore from."); f.click(); }
    else toast("No synced copy on this device — import a backup from Profile to restore.");
  }
}
function dataAlertDismiss() {
  if (_dataNoteMode === "mass" && _syMassHold) {
    /* "Not now" = keep them: hold this collection's mass delete
       silently for the rest of the session. */
    _syMassDenied[_syMassHold.coll] = 1;
    _syMassHold = null;
  }
  _dataNoteOff = true;
  dataNoteRender();
}

/* fetch with a deadline: a request that never answers used to
   leave sync "busy" until the page was reloaded. */
function syFetch(url, opts, ms) {
  if (typeof AbortController === "undefined") return fetch(url, opts);
  var ac = new AbortController();
  var timer = setTimeout(function () { try { ac.abort(); } catch (e) {} }, ms);
  opts = Object.assign({}, opts, { signal: ac.signal });
  return fetch(url, opts).then(function (r) { clearTimeout(timer); return r; }, function (e) {
    clearTimeout(timer);
    throw (e && e.name === "AbortError") ? new Error("timed out") : e;
  });
}
function syPutLocal(c, data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) return;
  var id = syRecId(c, data);
  if (!id) return;
  function put(arr) {
    var ix = -1;
    arr.forEach(function (r, i) { if (syRecId(c, r) === id) ix = i; });
    if (ix >= 0) arr[ix] = data; else arr.push(data);
    return arr;
  }
  if (c === "looks") savedLooks = put(savedLooks);
  else if (c === "queue") queueLooks = put(queueLooks);
  else if (c === "plan") weekPlan = put(weekPlan);
  else if (c === "trips") { userTrips = put(userTrips); store.set("trips", userTrips); }
  else if (c === "packed") { packedItems = put(packedItems); store.set("packedItems", packedItems); }
  else if (c === "receipts") { receiptInbox = put(receiptInbox); store.set("receiptInbox", receiptInbox); if (typeof renderReceipts === "function") renderReceipts(); if (typeof renderReceiptsSection === "function") renderReceiptsSection(); }
  else if (c === "shopwish") { shopWishlist = put(shopWishlist); store.set("shopWishlist", shopWishlist); if (typeof refreshWishButtons === "function") refreshWishButtons(); if (typeof renderShopWishlist === "function") renderShopWishlist(); }
  else if (c === "pricedrops") { priceDrops = put(priceDrops); store.set("priceDrops", priceDrops); if (typeof renderShopWishlist === "function") renderShopWishlist(); }
  else if (c === "edits") { editMeta = put(editMeta); store.set("editMeta", editMeta); if (typeof editOnSync === "function") editOnSync(); }
  else if (c === "searches") { editSearches = put(editSearches); store.set("editSearches", editSearches); if (typeof editOnSync === "function") editOnSync(); }
  else if (c === "ask") { askSync = put(askSync); store.set("askSync", askSync); if (typeof window.askOnSync === "function") window.askOnSync(); }
  else if (c === "worn") wornLog = put(wornLog);
  else if (c === "inspo") inspoImages = put(inspoImages);
  else if (c === "finds") finds = put(finds);
  else if (c === "palettes") customPalettes = put(customPalettes);
  else if (c === "items") {
    var seeds = wardrobeItems.filter(function (i) { return i.id.indexOf("seed-") === 0; });
    var users = put(wardrobeItems.filter(function (i) { return i.id.indexOf("seed-") !== 0; }));
    wardrobeItems = applyEntryState(seeds.concat(users));
    /* Build .53 fix round 2: same alias-aware wear-count rule as
       the boot loop — a sync download carrying wornCount-only
       entries must not reintroduce zeroed or unset counts. */
    wardrobeItems.forEach(function (i) {
      var effWear = (typeof i.wearCount === "number") ? i.wearCount : ((typeof i.wornCount === "number") ? i.wornCount : 0);
      i.wearCount = effWear;
      if ("wornCount" in i) i.wornCount = effWear;
    });
  } else if (c === "watches") {
    var wseeds = watches.filter(function (w) { return w.id.indexOf("seed-") === 0; });
    var wusers = put(watches.filter(function (w) { return w.id.indexOf("seed-") !== 0; }));
    watches = applyEntryState(wseeds.concat(wusers));
  } else if (c === "icons") {
    var n = normalizeIcon(data);
    if (!n) return;
    var ix = -1;
    customIcons.forEach(function (r, i) { if (r.id === n.id) ix = i; });
    if (ix >= 0) customIcons[ix] = n; else customIcons.push(n);
  }
  else if (c === "anchors") {
    buildAnchors = put(buildAnchors);
    store.set("buildAnchors", buildAnchors);
    buildAnchors.forEach(function (a) { buildUploadPiece(a); });
  }
}
function syRemoveLocal(c, id) {
  function drop(arr) { return arr.filter(function (r) { return syRecId(c, r) !== id; }); }
  if (c === "looks") savedLooks = drop(savedLooks);
  else if (c === "queue") queueLooks = drop(queueLooks);
  else if (c === "plan") weekPlan = drop(weekPlan);
  else if (c === "trips") { userTrips = drop(userTrips); store.set("trips", userTrips); }
  else if (c === "packed") { packedItems = drop(packedItems); store.set("packedItems", packedItems); }
  else if (c === "receipts") { receiptInbox = drop(receiptInbox); store.set("receiptInbox", receiptInbox); if (typeof renderReceipts === "function") renderReceipts(); if (typeof renderReceiptsSection === "function") renderReceiptsSection(); }
  else if (c === "shopwish") { shopWishlist = drop(shopWishlist); store.set("shopWishlist", shopWishlist); if (typeof refreshWishButtons === "function") refreshWishButtons(); if (typeof renderShopWishlist === "function") renderShopWishlist(); }
  else if (c === "pricedrops") { priceDrops = drop(priceDrops); store.set("priceDrops", priceDrops); if (typeof renderShopWishlist === "function") renderShopWishlist(); }
  else if (c === "edits") { editMeta = drop(editMeta); store.set("editMeta", editMeta); if (typeof editOnSync === "function") editOnSync(); }
  else if (c === "searches") { editSearches = drop(editSearches); store.set("editSearches", editSearches); if (typeof editOnSync === "function") editOnSync(); }
  else if (c === "ask") { askSync = drop(askSync); store.set("askSync", askSync); if (typeof window.askOnSync === "function") window.askOnSync(); }
  else if (c === "worn") wornLog = drop(wornLog);
  else if (c === "inspo") inspoImages = drop(inspoImages);
  else if (c === "finds") finds = drop(finds);
  else if (c === "palettes") customPalettes = drop(customPalettes);
  else if (c === "items") wardrobeItems = drop(wardrobeItems);
  else if (c === "watches") watches = drop(watches);
  else if (c === "icons") customIcons = drop(customIcons);
  else if (c === "anchors") { buildAnchors = drop(buildAnchors); store.set("buildAnchors", buildAnchors); }
}
function syRebuildSeedLists() {
  function rebuild(list) {
    return list.filter(function (e) { return deletedIds.indexOf(e.id) === -1; }).map(function (e) {
      var ov = entryOverrides[e.id];
      return ov && e.id.indexOf("seed-") === 0 ? Object.assign({}, e, ov) : e;
    });
  }
  wardrobeItems = rebuild(wardrobeItems);
  watches = rebuild(watches);
}
function sySyncProfileForm() {
  PROFILE_FIELDS.forEach(function (f) {
    var el = document.getElementById("pf-" + f);
    if (el) el.value = profile[f] || "";
  });
}
function syValidMetaField(f, v) {
  function plain(o) { return !!o && typeof o === "object" && !Array.isArray(o); }
  switch (f) {
    case "profile": case "overrides": return plain(v);
    case "deletedIds": case "dislikedImgs":
      return Array.isArray(v) && v.every(function (x) { return typeof x === "string"; });
    case "recentlyRemoved":
      return Array.isArray(v) && v.every(function (x) { return plain(x) && typeof x.id === "string"; });
    case "findBudget": case "shopTier": case "formality":
      return typeof v === "string" || typeof v === "number";
    case "priceRange": return typeof v === "string" && v.length <= 40;
    case "homeLocation": case "currentLocation": case "studioSettings":
      return v === null || plain(v);
    case "lastOpeningImg": return v === null || typeof v === "string";
  }
  return true;
}
function syApplyMeta(meta) {
  if (!meta || !meta.data || typeof meta.data !== "object") return false;
  var d = sanitizeIncoming(meta.data, "");
  var rft = d._ft && typeof d._ft === "object" ? d._ft : {};
  var applied = false, localNewer = false;
  /* Remote field time: its own stamp, or — for a document written
     by an older build — the document's. Take the remote value only
     when it is strictly newer than what this device holds. */
  function take(f) {
    var lt = (SY.mf[f] && SY.mf[f].t) || 0;
    if (!(f in d) || d[f] == null) { if (lt) localNewer = true; return 0; }
    var rt = typeof rft[f] === "number" ? rft[f] : (meta.updatedAt || 0);
    if (rt > lt) { applied = true; return rt; }
    if (lt > rt) localNewer = true;
    return 0;
  }
  function stamp(f, t, v) { SY.mf[f] = { h: syHsh(syWire(v)), t: t }; }
  /* Build .55 (3.8): a malformed field is skipped entirely —
     not applied, not stamped, not counted — before take() ever
     sees it. Fields an older peer still sends that this build
     no longer syncs (the dealt* history) have no branch below
     and are ignored. */
  function ok(f) { return (f in d) && syValidMetaField(f, d[f]); }
  var t, seedState = false;
  if (ok("profile") && (t = take("profile"))) { profile = syUnwire(d.profile); store.set("profile", profile); sySyncProfileForm(); if (typeof syncFindSize === "function") syncFindSize(); stamp("profile", t, profile); }
  if (ok("deletedIds") && (t = take("deletedIds"))) {
    /* Build .55 (3.5): union, never replace — a deletion made on
       either device survives the merge. */
    var incDel = syUnwire(d.deletedIds);
    var mergedDel = deletedIds.slice();
    incDel.forEach(function (id) { if (mergedDel.indexOf(id) === -1) mergedDel.push(id); });
    deletedIds = mergedDel; store.set("deletedIds", deletedIds); stamp("deletedIds", t, deletedIds); seedState = true;
  }
  if (ok("overrides") && (t = take("overrides"))) {
    /* Build .55 (3.5): per-key merge — incoming keys overlay,
       keys held only locally survive. */
    entryOverrides = Object.assign({}, entryOverrides, syUnwire(d.overrides)); store.set("overrides", entryOverrides); stamp("overrides", t, entryOverrides); seedState = true;
  }
  if (seedState) syRebuildSeedLists();
  if (ok("dislikedImgs") && (t = take("dislikedImgs"))) { dislikedImgs = syUnwire(d.dislikedImgs); store.set("dislikedImgs", dislikedImgs); stamp("dislikedImgs", t, dislikedImgs); }
  if (ok("recentlyRemoved") && (t = take("recentlyRemoved"))) {
    /* Build .55 (3.5): merge by snapshot id — when both sides
       hold the same id the later removal wins; the merged list
       is capped at 50, newest first. */
    var incRR = syUnwire(d.recentlyRemoved);
    var rrById = {}, rrOrder = [];
    function rrPut(snap) {
      var ex = rrById[snap.id];
      if (!ex) { rrById[snap.id] = snap; rrOrder.push(snap.id); }
      else if ((snap._removedAt || 0) > (ex._removedAt || 0)) rrById[snap.id] = snap;
    }
    recentlyRemoved.forEach(rrPut);
    incRR.forEach(rrPut);
    var mergedRR = rrOrder.map(function (id) { return rrById[id]; });
    mergedRR.sort(function (a, b) { return (b._removedAt || 0) - (a._removedAt || 0); });
    recentlyRemoved = mergedRR.slice(0, 50); store.set("recentlyRemoved", recentlyRemoved); stamp("recentlyRemoved", t, recentlyRemoved);
  }
  if (ok("findBudget") && (t = take("findBudget"))) { budgetLevel = syUnwire(d.findBudget); store.set("findBudget", budgetLevel); if (typeof renderBudget === "function") renderBudget(); stamp("findBudget", t, budgetLevel); }
  if (ok("shopTier") && (t = take("shopTier"))) { shopTier = syUnwire(d.shopTier); store.set("shopTier", shopTier); if (typeof renderShopTier === "function") renderShopTier(); stamp("shopTier", t, shopTier); }
  if (ok("priceRange") && (t = take("priceRange"))) { priceRange = String(syUnwire(d.priceRange) || "any"); store.set("priceRange", priceRange); if (typeof priceRangeRefresh === "function") priceRangeRefresh(); stamp("priceRange", t, priceRange); }
  if (ok("homeLocation") && (t = take("homeLocation"))) { homeLoc = syUnwire(d.homeLocation); store.set("homeLocation", homeLoc); stamp("homeLocation", t, homeLoc); }
  if (ok("currentLocation") && (t = take("currentLocation"))) { currentLoc = syUnwire(d.currentLocation); store.set("currentLocation", currentLoc); stamp("currentLocation", t, currentLoc); }
  if (ok("formality") && (t = take("formality"))) { formalityLevel = syUnwire(d.formality); store.set("formality", formalityLevel); if (typeof renderFormality === "function") renderFormality(); stamp("formality", t, formalityLevel); }
  if (ok("studioSettings") && (t = take("studioSettings"))) { var ssVal = syUnwire(d.studioSettings); store.set("studioSettings", ssVal); stamp("studioSettings", t, ssVal); }
  if (ok("lastOpeningImg") && (t = take("lastOpeningImg"))) { var loVal = syUnwire(d.lastOpeningImg); store.set("lastOpeningImg", loVal); stamp("lastOpeningImg", t, loVal); }
  /* This device holds something newer than the server's copy:
     send the merged document back up. */
  if (localNewer) { SY.dirty.m = 1; if (!SY.st.m) SY.st.m = Date.now(); }
  return applied;
}
function sySortLooksByStamp() {
  /* My Looks is most-recent-first: after a merge, order by each
     look's sync stamp, newest first. The sort is stable, so
     looks sharing a stamp (e.g. everything stamped by a first
     track) keep their existing local order. */
  var deco = savedLooks.map(function (l, i) { return { l: l, i: i, s: SY.st.looks[l.id] || 0 }; });
  deco.sort(function (a, b) { return (b.s - a.s) || (a.i - b.i); });
  savedLooks = deco.map(function (x) { return x.l; });
}
function syRefresh() {
  try { persistAll(); } catch (e) {}
  try { saveQueue(); } catch (e) {}
  try { saveWeekPlan(); } catch (e) {}
  try { store.set("wornLog", wornLog); } catch (e) {}
  try { store.set("inspoImages", inspoImages); } catch (e) {}
  try { store.set("finds", finds); } catch (e) {}
  [renderSaved, renderWardrobe, renderWatches, renderWornLog, renderInspoImages, renderMyInspo, renderFinds, renderCustomPalettes, renderIcons, renderRecentlyRemoved, renderLoc, syncPaletteSelect, renderPurchased, renderWeekPlan, renderProfileHead, renderReceipts, renderReceiptsSection, renderShopWishlist].forEach(function (f) {
    try { if (typeof f === "function") f(); } catch (e) {}
  });
  try { dataNoteRender(); } catch (e) {}
  var se = document.getElementById("syncstat");
  if (se) se.innerHTML = syncStatusHTML();
  var kf = document.getElementById("sync-key");
  if (kf) kf.value = SY.key || "(created on first sync)";
}
/* Build .56: one downloaded record, applied on its own. A record
   that throws (or arrives malformed — data that is not an object,
   no usable id) is quarantined into SY.quar and the pass moves on:
   a single bad record must never fail a whole sync again. The
   quarantine is surfaced only in Profile's sync status. */
function syQuarantine56(x, err) {
  try {
    if (!Array.isArray(SY.quar)) SY.quar = [];
    var key = (x && x.coll ? x.coll : "?") + "|" + (x && x.id ? x.id : "?");
    for (var i = 0; i < SY.quar.length; i++) { if (SY.quar[i] && SY.quar[i].k === key) return; }
    SY.quar.push({ k: key, at: Date.now(), err: String(err && err.message ? err.message : (err || "")).slice(0, 120) });
    if (SY.quar.length > 200) SY.quar = SY.quar.slice(SY.quar.length - 200);
  } catch (e) {}
}
/* Build .59: an unsent tomb is one the server has never
   acknowledged (still dirty). Those must not block applying a
   live server record, except a single user-initiated delete
   made in this session. When in doubt, restore. */
function syUnsentTomb(coll, id) {
  return !!(SY.tomb[coll] && SY.tomb[coll][id] && SY.dirty[coll] && SY.dirty[coll][id]);
}
function syHasUnsentTombs() {
  for (var i = 0; i < SY_COLLS.length; i++) {
    var c = SY_COLLS[i], tombs = SY.tomb[c] || {}, dirty = SY.dirty[c] || {};
    for (var id in tombs) { if (tombs[id] && dirty[id]) return true; }
  }
  return false;
}
function syPreserveSessionDelete(coll, id) {
  if (!syUnsentTomb(coll, id)) return false;
  if (!_sySessionDeletes[coll] || !_sySessionDeletes[coll][id]) return false;
  var pending = 0;
  Object.keys(SY.tomb[coll] || {}).forEach(function (k) {
    if (SY.dirty[coll] && SY.dirty[coll][k]) pending++;
  });
  if (pending > 5) return false;
  if (_syMassHold && _syMassHold.coll === coll) return false;
  return true;
}
function syApplyDownload56(j) {
  var res = { down: 0, changedAny: false, changedLooks: false, count: 0 };
  if (!j) return res;
  var recs = Array.isArray(j.recs) ? j.recs : [];
  res.count = recs.length;
  _syApplying = true;
  try {
    recs.forEach(function (x) {
      try {
        /* Build .57 (B4): blob records are photo bytes, not
           collection records — they land in the blob store and
           are swapped into the page, never in syPutLocal, and
           SY.snap.blobs is never set (the differ stays blind to
           them). A deleted blob record is ignored. */
        if (x && x.coll === "blobs") {
          if (x.deleted) return;
          if (!/^[0-9a-f]{64}$/.test(x.id || "") || !x.data || typeof x.data !== "object" || Array.isArray(x.data) || typeof x.data.photo !== "string" || x.data.photo.indexOf("data:image/") !== 0) { syQuarantine56(x, "invalid blob record"); return; }
          try { if (window.blobStore) { window.blobStore.put(x.id, x.data.photo); window.blobStore.fillIn(x.id, x.data.photo); } } catch (e) {}
          if (!SY.st.blobs || typeof SY.st.blobs !== "object") SY.st.blobs = {};
          if (!SY.dirty.blobs || typeof SY.dirty.blobs !== "object") SY.dirty.blobs = {};
          SY.st.blobs[x.id] = x.updatedAt || 1;
          delete SY.dirty.blobs[x.id];
          res.down++; res.changedAny = true;
          return;
        }
        if (!x || SY_COLLS.indexOf(x.coll) === -1) return;
        var loc = SY.st[x.coll][x.id] || SY.tomb[x.coll][x.id] || 0;
        if (x.deleted) {
          if (!(x.updatedAt > loc)) return;
          syRemoveLocal(x.coll, x.id);
          SY.tomb[x.coll][x.id] = x.updatedAt;
          delete SY.snap[x.coll][x.id]; delete SY.st[x.coll][x.id];
          delete SY.dirty[x.coll][x.id];
          res.changedAny = true; res.down++; if (x.coll === "looks") res.changedLooks = true;
        } else if (x.data) {
          /* Build .59: a live server record beats an unsent local
             tomb, unless this is a single user-initiated delete
             from this session. */
          var _wasUnsentTomb = syUnsentTomb(x.coll, x.id);
          if (syPreserveSessionDelete(x.coll, x.id)) return;
          if (_wasUnsentTomb) {
            /* fall through and restore — ignore the tomb stamp */
          } else if (!(x.updatedAt > loc)) {
            /* Build .74.1: a one-time closet/watch photo re-pull
               applies the server copy even if this device already
               holds an equal or newer stamp. Boot-time change
               tracking can re-stamp every piece before the download
               starts, which would otherwise skip the studio photos
               forever and then push the old ones back up. Other
               collections keep last-writer-wins. Session deletes
               were already honoured above. */
            if (!(_syForcePhotoPull741 && (x.coll === "items" || x.coll === "watches"))) return;
          }
          if (typeof x.data !== "object" || Array.isArray(x.data)) { syQuarantine56(x, "record data is not an object"); return; }
          var _xrid = null;
          try { _xrid = syRecId(x.coll, x.data); } catch (e) { _xrid = null; }
          if (!_xrid) { syQuarantine56(x, "record has no usable id"); return; }
          sanitizeIncoming(x.data, "");
          syPutLocal(x.coll, x.data);
          SY.snap[x.coll][x.id] = syHsh(syWireRec(x.coll, x.data));
          SY.st[x.coll][x.id] = x.updatedAt;
          delete SY.tomb[x.coll][x.id];
          delete SY.dirty[x.coll][x.id];
          /* Only ids restored over an unsent tomb are blocked from
             a later delete upload — a normal apply must not freeze
             a real user delete later in the session. */
          if (_wasUnsentTomb) {
            if (!_syRestoredIds[x.coll]) _syRestoredIds[x.coll] = {};
            _syRestoredIds[x.coll][x.id] = 1;
          }
          res.changedAny = true; res.down++; if (x.coll === "looks") res.changedLooks = true;
        } else {
          /* Build .56 verification fix: a non-deleted record with
             no usable payload (data missing, null, or a scalar
             that is not an object) is malformed — quarantine it
             explicitly instead of dropping it silently, so the
             skip is visible in Profile's sync status. */
          syQuarantine56(x, "record has no usable data");
        }
      } catch (e) { syQuarantine56(x, e); }
    });
    try { if (syApplyMeta(j.meta)) res.changedAny = true; } catch (e) {}
  } finally { _syApplying = false; }
  return res;
}
function syncNow(isRetry, force) {
  /* Asked to sync while a sync is running: remember it, and go
     again as soon as this one finishes — otherwise an edit made
     mid-request waits for the two-minute timer. */
  if (_syBusy) { _syAgain = true; return; }
  if (!navigator.onLine) { setSyncStatus("Offline — will sync when back online"); return; }
  /* No-op poll throttle: a background check-in (the interval,
     a visibility return, a debounced write that changed nothing)
     costs a full storage rewrite on the worker even when there
     is nothing to send, and the free plan's daily write quota is
     small. If nothing is dirty and the last successful sync was
     under five minutes ago, skip the network entirely. Forced
     calls — the Sync-now button, coming back online, first load,
     account link/register — always go through, as does any call
     with real changes pending. */
  /* Key rejected earlier: background check-ins stand down until
     the user retries (Sync now), relinks, or the app is reopened. */
  if (!force && SY.rej) return;
  if (!force && _syRegNeed) return;
  if (!force && SY.key) {
    try { syTrackChanges(); } catch (e) {}
    var anyDirty = !!SY.dirty.m;
    if (!anyDirty) {
      for (var dci = 0; dci < SY_COLLS.length; dci++) {
        if (Object.keys(SY.dirty[SY_COLLS[dci]]).length) { anyDirty = true; break; }
      }
    }
    if (!anyDirty && SY.lastOk && (Date.now() - SY.lastOk) < 5 * 60 * 1000) return;
  }
  _syBusy = true;
  (async function () {
    try {
      if (!SY.key) {
        /* Build .58: never hit /register without a code. A blank
           POST only 403s and used to fire on every fresh visit. */
        var regCode = "";
        try { regCode = store.get("regCode", "") || ""; } catch (e) {}
        if (!String(regCode).trim()) {
          _syRegNeed = true;
          setSyncStatus("Sync needs the registration code — enter it under Cloud sync in Profile, then tap Sync now. Nothing on this device was changed.");
          return;
        }
        setSyncStatus("Creating sync account…");
        var r0 = await syFetch(SYNC_URL + "/register", {
          method: "POST",
          headers: { "x-register-secret": regCode }
        }, 20000);
        if (r0.status === 403) {
          _syRegNeed = true;
          setSyncStatus("Sync needs the registration code — enter it under Cloud sync in Profile, then tap Sync now. Nothing on this device was changed.");
          return;
        }
        if (!r0.ok) throw new Error("register " + r0.status);
        _syRegNeed = false;
        var j0 = await r0.json();
        if (!j0 || !j0.key) throw new Error("register failed");
        /* Adopt the auto-created account ONLY if no key has
           appeared while the register request was in flight.
           After a wipe the boot pass registers automatically; if
           the user confirmed Link in the meantime, SY.key is the
           linked key now — discarding the registration result
           entirely (no overwrite of key/acct/last/rej, no
           first-upload re-stamp for the auto account) and
           letting this pass continue as a normal sync under the
           linked key is the only correct outcome. The link's own
           forced syncNow already queued a re-run via _syAgain. */
        if (!SY.key) {
          SY.key = j0.key; SY.acct = j0.acct; SY.last = 0; SY.rej = 0;
          /* First upload: everything local is dirty, stamped by
             the track (or now) — uploads happen in this same pass,
             before any download is applied. */
          syTrackChanges();
          SY_COLLS.forEach(function (c) {
            syCollGet(c).forEach(function (r) { var id = syRecId(c, r); if (id) { SY.dirty[c][id] = 1; if (!SY.st[c][id]) SY.st[c][id] = Date.now(); } });
          });
          SY.dirty.m = 1; if (!SY.st.m) SY.st.m = Date.now();
          saveSY();
        }
      }
      syTrackChanges();
      /* Build .57 (B7): one-time migration, once per account per
         device (keyed on SY.key, so linked accounts run it too).
         The flag is set FIRST, then every closet item still
         holding a photo (inline or as a vault reference) is
         re-stamped dirty, so this pass re-uploads the closet in
         blob form through the B5 transform. No other collection
         is force-migrated — their photos blob-ify on their next
         ordinary push. */
      try {
        if (SY.key && SY.mig57 !== SY.key) {
          SY.mig57 = SY.key;
          try {
            syCollGet("items").forEach(function (r) {
              var ph = r && r.photo;
              if (typeof ph === "string" && (ph.indexOf("data:image/") === 0 || ph.indexOf("idb:") === 0)) {
                var rid = syRecId("items", r);
                if (rid) { SY.st.items[rid] = Date.now(); SY.dirty.items[rid] = 1; delete SY.tomb.items[rid]; }
              }
            });
          } catch (e) {}
          saveSY();
        }
      } catch (e) {}
      setSyncStatus("Syncing…");
      /* Build .56: PAGED DOWNLOAD. The old pass took the whole
         backlog in ONE response (~13.5 MB); it timed out (~60 s)
         before the position marker was ever persisted, so every
         sync restarted from zero and the pending note never
         cleared. An established account now downloads FIRST, in
         bounded pages (200 records per request, successive
         since-windows), and the position marker AND the applied
         state are saved after EACH page — an interrupted pass
         resumes where it stopped. Uploads then run exactly as
         before; their responses carry only what is newer than
         the position just saved. A first sync (no completed pass
         yet) keeps the standing rule: uploads before any download
         is applied. If the worker ignores the page limit, the
         first page may still be large — per-page persistence is
         the guarantee this client can make. */
      var down56 = 0, changedAny56 = false, changedLooks56 = false;
      /* Build .59: one-time full paged re-download (since: 0) so
         live server records can replace leftover unsent tombs.
         Runs for an established account (or any account that
         already has unsent tombs). A brand-new first sync still
         uploads before any download. The restore59 flag is set
         only after the pages finish and wardrobe.items persists. */
      var needRestore59 = !!(SY.key && SY.restore59 !== SY.key && (SY.lastOk || syHasUnsentTombs()));
      var needPhotoPull741 = !!(SY.key && SY.photoPull742 !== SY.key && (SY.lastOk || SY.last || needRestore59));
      var restoreFailed59 = false;
      if (SY.lastOk || needRestore59 || needPhotoPull741) {
        var _pg56 = 0;
        var _dlSince = (needRestore59 || needPhotoPull741) ? 0 : SY.last;
        _syForcePhotoPull741 = !!needPhotoPull741;
        var _vaultFails742 = (window.photoVault && window.photoVault.fails) || 0;
        while (_pg56 < 80) {
          _pg56++;
          var _pr56 = null;
          try {
            _pr56 = await syFetch(SYNC_URL + "/sync", {
              method: "POST",
              headers: { "authorization": "Bearer " + SY.key, "content-type": "application/json" },
              body: JSON.stringify({ since: _dlSince, changes: [], meta: null, limit: 200 })
            }, 180000);
          } catch (e) { restoreFailed59 = true; break; }
          if (_pr56.status === 401) {
            SY.rej = (SY.rej || 0) + 1;
            setSyncStatus("Sync paused — the server didn't accept this device's sync key. Nothing on this device was changed.");
            return;
          }
          if (!_pr56.ok) { restoreFailed59 = true; break; }
          var _pj56 = null;
          try { _pj56 = await _pr56.json(); } catch (e) { restoreFailed59 = true; break; }
          if (!_pj56 || typeof _pj56.now !== "number") { restoreFailed59 = true; break; }
          var _prev56 = _dlSince;
          var _pa56 = syApplyDownload56(_pj56);
          down56 += _pa56.down; if (_pa56.changedAny) changedAny56 = true; if (_pa56.changedLooks) changedLooks56 = true;
          /* Build .74.1: persist closet/watch records BEFORE the
             position marker is saved. A previous pass could apply
             photos in memory, advance SY.last, then die before
             persistAll — after reload the cursor skipped those
             photos forever. */
          var _persistedPage741 = true;
          if (_pa56.changedAny) {
            try { _persistedPage741 = persistAll() !== false; } catch (e) { _persistedPage741 = false; }
          }
          if (!_persistedPage741) { restoreFailed59 = true; break; }
          SY.last = _pj56.now;
          _dlSince = _pj56.now;
          saveSY();
          if (_pa56.count === 0) break;
          if (_pj56.now === _prev56) break;
          if (_pa56.count < 200) break;
        }
        _syForcePhotoPull741 = false;
        if ((needRestore59 || needPhotoPull741) && !restoreFailed59) {
          var _persisted59 = true;
          try { _persisted59 = persistAll() !== false; } catch (e) { _persisted59 = false; }
          /* Build .74.2: the photo vault writes asynchronously. The
             re-pull is only marked done once every photo write has
             landed in IndexedDB — a failed or slow write leaves the
             flag unset, so the next open pulls again. */
          var _vaultOk742 = true;
          if (_persisted59 && needPhotoPull741) {
            var _pv742 = window.photoVault;
            if (_pv742 && _pv742.flush && _pv742.hasDb && _pv742.hasDb()) {
              _vaultOk742 = await new Promise(function (res) { try { _pv742.flush(function (ok) { res(ok !== false); }); } catch (e) { res(false); } });
            }
            if (_pv742 && (_pv742.fails || 0) > _vaultFails742) _vaultOk742 = false;
          }
          if (_persisted59) {
            if (needRestore59) SY.restore59 = SY.key;
            if (needPhotoPull741 && _vaultOk742) { SY.photoPull741 = SY.key; SY.photoPull742 = SY.key; }
            saveSY();
          }
          if (_syMassHold) {
            var _hc = _syMassHold.coll, _still = 0;
            Object.keys((SY.tomb && SY.tomb[_hc]) || {}).forEach(function (id) {
              if (SY.dirty[_hc] && SY.dirty[_hc][id]) _still++;
            });
            if (_still <= 5) { _syMassHold = null; try { dataNoteRender(); } catch (e) {} }
          }
          try { syRefresh(); } catch (e) {}
        }
      }
      var changes = [], held = 0;
      var vaultGaps = !!(window.photoVault && window.photoVault.missing);
      /* Build .55 (3.2e): with the lazy vault, a record can still
         hold "idb:" references at upload time. Resolve each one
         from the vault into a COPY of the record for the payload;
         a reference this device cannot resolve holds the record
         back, exactly as the vault-gap rule below always has. */
      var _resMap = {};
      await (async function () {
        var jobs = [];
        SY_COLLS.forEach(function (c) {
          Object.keys(SY.dirty[c]).forEach(function (id) {
            var rec = null;
            syCollGet(c).forEach(function (r) { if (syRecId(c, r) === id) rec = r; });
            if (!rec) return;
            var data0 = syRecData(c, rec);
            var js = JSON.stringify(data0);
            if (js.indexOf("idb:") === -1) return;
            var keys = [], mm, re = /idb:([a-z0-9-]+)/g;
            while ((mm = re.exec(js))) { if (keys.indexOf(mm[1]) === -1) keys.push(mm[1]); }
            if (!keys.length) return;
            jobs.push({ k: c + "|" + id, js: js, keys: keys });
          });
        });
        for (var ji = 0; ji < jobs.length; ji++) {
          var job = jobs[ji], resolved = {}, allOk = true;
          for (var ki = 0; ki < job.keys.length; ki++) {
            var kk = job.keys[ki];
            var val = await new Promise(function (res) {
              if (window.photoVault && typeof window.photoVault.fetch === "function") window.photoVault.fetch(kk, function (dv) { res(dv); });
              else res(null);
            });
            if (typeof val === "string") resolved[kk] = val; else { allOk = false; break; }
          }
          _resMap[job.k] = allOk ? JSON.parse(job.js.replace(/idb:([a-z0-9-]+)/g, function (m, k) { return resolved[k]; })) : null;
        }
      })();
      SY_COLLS.forEach(function (c) {
        Object.keys(SY.dirty[c]).forEach(function (id) {
          var rec = null;
          syCollGet(c).forEach(function (r) { if (syRecId(c, r) === id) rec = r; });
          if (rec) {
            var data = syRecData(c, rec);
            var _rk = c + "|" + id;
            if (_rk in _resMap) {
              if (!_resMap[_rk]) { held++; return; }
              data = _resMap[_rk];
            }
            /* A record whose photograph is not on this device right
               now is held back: uploading it would replace the good
               copy on the server with a dangling reference. */
            else if (vaultGaps && JSON.stringify(data).indexOf('"idb:') !== -1) { held++; return; }
            changes.push({ coll: c, id: id, updatedAt: SY.st[c][id] || Date.now(), data: data });
          }
          else if (SY.tomb[c][id]) {
            if (_syRestoredIds[c] && _syRestoredIds[c][id]) return;
            changes.push({ coll: c, id: id, updatedAt: SY.tomb[c][id], deleted: true });
          }
        });
      });
      /* Mass-delete guard (client side; the worker enforces the
         same rule): hold any pass that would delete more than
         ~20% of a collection until the user confirms it in the
         data alert. Held tombstones stay dirty — they are simply
         not sent in this pass. */
      if (Date.now() > _syMassOkUntil) {
        var delByColl = {}, liveByColl = {};
        changes.forEach(function (ch) { if (ch.deleted) delByColl[ch.coll] = (delByColl[ch.coll] || 0) + 1; });
        Object.keys(delByColl).forEach(function (c) {
          var del = delByColl[c];
          var live = Object.keys(SY.snap[c] || {}).length;
          var total = live + del;
          /* Build .58 circuit breaker: never push a delete batch that
             would remove more than 5 records, or more than 10% of a
             collection, in one pass. Held tombstones stay dirty and
             are not sent. The user can confirm in the data alert. */
          if ((del > 5 || (del >= 2 && total > 0 && del > total * 0.1)) && !_syMassDenied[c]) {
            if (!_syMassHold) _syMassHold = { coll: c, deletions: del, live: total };
            changes = changes.filter(function (ch) { return !(ch.deleted && ch.coll === c); });
          }
        });
        if (_syMassHold) { saveSY(); try { dataNoteRender(); } catch (e) {} }
      }
      /* Build .57 (B5): sync photo offload. Each non-deleted
         change's data is replaced with a transformed COPY (a deep
         walk in the syWire style — live record objects are never
         mutated): a data:image string longer than 2048 chars
         becomes "blob:<sha256>", and the photo bytes ride as one
         "blobs" change per distinct photo. A blob change is
         included only when this device has not pushed that hash
         before (SY.bp) — except the insurance rule: a record
         referencing "blob:<hash>" (arrived from another device)
         whose bytes this device holds is included too when
         SY.bp lacks the hash; the server skips true duplicates
         by last-writer-wins. If SHA-256 is unavailable, the
         transform is skipped entirely for this pass and records
         upload inline exactly as before. */
      try {
        var _bs57 = window.blobStore;
        var _probe57 = null;
        if (_bs57 && typeof _bs57.sha256 === "function") { try { _probe57 = await _bs57.sha256(""); } catch (e) { _probe57 = null; } }
        if (_bs57 && typeof _probe57 === "string" && /^[0-9a-f]{64}$/.test(_probe57)) {
          if (!SY.bp || typeof SY.bp !== "object" || Array.isArray(SY.bp)) SY.bp = {};
          var _blobChanges57 = [], _blobSeen57 = {};
          var _collectBlob57 = function (hash, uri) {
            if (!hash || typeof uri !== "string" || _blobSeen57[hash]) return;
            _blobSeen57[hash] = 1;
            if (SY.bp[hash]) return;
            _blobChanges57.push({ coll: "blobs", id: hash, updatedAt: 1, data: { photo: uri } });
          };
          var _walkBlob57 = async function (v) {
            if (typeof v === "string") {
              if (v.length > 2048 && v.indexOf("data:image/") === 0) {
                var _h57 = null;
                try { _h57 = await _bs57.sha256(v); } catch (e) { _h57 = null; }
                if (typeof _h57 === "string" && /^[0-9a-f]{64}$/.test(_h57)) { _collectBlob57(_h57, v); return "blob:" + _h57; }
                return v;
              }
              if (/^blob:[0-9a-f]{64}$/.test(v)) {
                var _bh57 = v.slice(5);
                if (!SY.bp[_bh57] && !_blobSeen57[_bh57]) {
                  var _buri57 = (_bs57.cache && _bs57.cache[_bh57]) || null;
                  if (!_buri57 && typeof _bs57.fetch === "function") {
                    _buri57 = await new Promise(function (res) { try { _bs57.fetch(_bh57, function (dv) { res(dv); }); } catch (e) { res(null); } });
                  }
                  if (typeof _buri57 === "string" && _buri57.indexOf("data:image/") === 0) _collectBlob57(_bh57, _buri57);
                }
                return v;
              }
              return v;
            }
            if (Array.isArray(v)) {
              var _arr57 = [];
              for (var _ai57 = 0; _ai57 < v.length; _ai57++) _arr57.push(await _walkBlob57(v[_ai57]));
              return _arr57;
            }
            if (v && typeof v === "object") {
              var _obj57 = {}, _keys57 = Object.keys(v);
              for (var _ki57 = 0; _ki57 < _keys57.length; _ki57++) _obj57[_keys57[_ki57]] = await _walkBlob57(v[_keys57[_ki57]]);
              return _obj57;
            }
            return v;
          };
          for (var _ci57 = 0; _ci57 < changes.length; _ci57++) {
            if (!changes[_ci57].deleted && changes[_ci57].data) changes[_ci57].data = await _walkBlob57(changes[_ci57].data);
          }
          _blobChanges57.forEach(function (bc) { changes.push(bc); });
        }
      } catch (e) {}
      /* Uploads go in batches of about 900 KB, so a first sync
         full of photographs is not one enormous request that
         fails as a whole. Settings ride on the last batch. */
      var batches = [[]], size = 0;
      changes.forEach(function (ch) {
        var n = ch.deleted ? 80 : JSON.stringify(ch).length;
        if (size + n > 900000 && batches[batches.length - 1].length) { batches.push([]); size = 0; }
        batches[batches.length - 1].push(ch); size += n;
      });
      var metaOut = null;
      if (SY.dirty.m) {
        var ft = {};
        Object.keys(SY.mf).forEach(function (f) { ft[f] = SY.mf[f].t || 0; });
        var metaData = Object.assign({}, syMetaOf(), { _ft: ft });
        /* A poisoned settings field rides along as its fallback
           value in syMetaOf — leave it out of the upload entirely
           so the server's good copy survives. */
        Object.keys(metaData).forEach(function (f) { if (f !== "_ft" && (store.poisoned(f) || _syMetaRestore[f])) delete metaData[f]; });
        /* Build .55: photos ride as vault references when the
           vault is live on this device; without it the payload
           stays raw, exactly as before. */
        if (window.photoVault && window.photoVault.enabled) metaData = syWire(metaData);
        metaOut = { updatedAt: SY.st.m || Date.now(), data: metaData };
      }
      var since = SY.last, lastNow = null, sent = 0, down = down56;
      var changedAny = changedAny56, changedLooks = changedLooks56;
      for (var bi = 0; bi < batches.length; bi++) {
        var batch = batches[bi];
        var isLast = bi === batches.length - 1;
        var body = { since: since, changes: batch, meta: isLast ? metaOut : null };
        if (Date.now() <= _syMassOkUntil) body.confirmMassDelete = true;
        if (batches.length > 1) setSyncStatus("Syncing… " + (bi + 1) + " of " + batches.length);
        var r = await syFetch(SYNC_URL + "/sync", {
          method: "POST",
          headers: { "authorization": "Bearer " + SY.key, "content-type": "application/json" },
          body: JSON.stringify(body)
        }, 180000);
        if (r.status === 401) {
          /* Key rejected. Keep the key and every local record; pause
             and tell the user. Creating a fresh account is their
             call (the button beside Sync now), never automatic. */
          SY.rej = (SY.rej || 0) + 1;
          setSyncStatus("Sync paused — the server didn't accept this device's sync key. Nothing on this device was changed.");
          return;
        }
        if (r.status === 409) {
          /* The worker's own mass-delete guard fired (this client
             was already past its check, e.g. a confirmed window
             lapsed mid-pass). Nothing in this batch was applied;
             the tombstones stay dirty. Ask the user. */
          var j409 = null;
          try { j409 = await r.json(); } catch (e) {}
          if (j409 && j409.error === "mass_delete") {
            _syMassHold = { coll: j409.coll, deletions: j409.deletions, live: j409.live };
            saveSY();
            try { dataNoteRender(); } catch (e) {}
            setSyncStatus("Sync paused — that pass would delete " + j409.deletions + " of " + j409.live + " in one list. Confirm it in the note above Profile, or keep them.");
            return;
          }
          throw new Error("sync 409");
        }
        if (!r.ok) throw new Error("sync " + r.status);
        var j = await r.json();
        if (!j || typeof j.now !== "number") throw new Error("bad response");
        /* Confirmed 200: the sent dirty flags clear — but only for
           records that have not changed again since they were
           sent. An edit made during the request keeps its flag. */
        batch.forEach(function (ch) {
          var cur = ch.deleted ? SY.tomb[ch.coll][ch.id] : SY.st[ch.coll][ch.id];
          if (cur === undefined || cur === ch.updatedAt) delete SY.dirty[ch.coll][ch.id];
        });
        /* Build .57 (B5): blobs carried in a batch the server
           accepted are marked as pushed by this device, so later
           passes do not re-include them. Failed batches mark
           nothing; their blobs are re-included next pass. */
        batch.forEach(function (ch) {
          if (ch.coll === "blobs") {
            if (!SY.bp || typeof SY.bp !== "object" || Array.isArray(SY.bp)) SY.bp = {};
            SY.bp[ch.id] = 1;
          }
        });
        if (body.meta && (SY.st.m || 0) <= body.meta.updatedAt) SY.dirty.m = 0;
        sent += batch.length;
        /* Build .56: records apply through the quarantining
           helper, and the position marker is persisted after
           EVERY batch — an interrupted pass resumes here instead
           of restarting from zero. */
        var _ar56 = syApplyDownload56(j);
        down += _ar56.down; if (_ar56.changedAny) changedAny = true; if (_ar56.changedLooks) changedLooks = true;
        lastNow = j.now;
        SY.last = j.now;
        saveSY();
      }
      if (changedLooks) sySortLooksByStamp();
      if (changedLooks && window.enforceSavedInvariants53) window.enforceSavedInvariants53();
      if (lastNow !== null) SY.last = lastNow;
      SY.lastOk = Date.now();
      SY.rej = 0;
      _syMassOkUntil = 0; /* a confirmed pass is spent */
      _syMetaRestore = {}; /* the download had its chance this pass */
      _syFailed = false; _syNoteOff = false;
      clearTimeout(_syRetryT);
      saveSY();
      setSyncStatus("Synced ✓ " + sent + " up · " + down + " down" + (held ? " · " + held + " held (photo not on this device)" : ""));
      if (changedAny) syRefresh();
    } catch (e) {
      _syApplying = false;
      _syForcePhotoPull741 = false;
      _syFailed = true; _syNoteOff = false;
      clearTimeout(_syRetryT);
      _syRetryT = setTimeout(function () { if (document.visibilityState === "visible" && !SY.rej) syncNow(); }, 30000);
      setSyncStatus("Sync failed: " + (e && e.message ? e.message : "network error") + " — will retry");
    } finally {
      _syBusy = false;
      _syForcePhotoPull741 = false;
      if (_syAgain) { _syAgain = false; if (!SY.rej) schedSync(); }
    }
  })();
}
/* A new sync account, only ever on request. The old key is shown
   one last time so it can be copied before it is replaced. */
var _syNewArmed = false;
function newSyncAccount() {
  var note = document.getElementById("sync-new-note");
  if (!_syNewArmed) {
    _syNewArmed = true;
    if (note) note.textContent = "Start a fresh sync account for this device? Everything here is uploaded to it; your other devices will need the new key. Tap again to confirm.";
    return;
  }
  var newCode = "";
  try { newCode = store.get("regCode", "") || ""; } catch (e) {}
  if (!String(newCode).trim()) {
    _syNewArmed = false;
    if (note) note.textContent = "Enter the registration code first, then tap again to start a new account. The current key was not changed.";
    return;
  }
  _syNewArmed = false;
  if (note) note.textContent = "";
  SY.key = null; SY.acct = null; SY.last = 0; SY.rej = 0;
  saveSY();
  syncNow(false, true);
}
/* Linking a second context: paste the other device's key. Local
   data merges into that account record-by-record by updatedAt —
   linking never bulk-overwrites either side. Confirmation is
   inline (two taps), never a popup. */
var _syLinkArmed = false;
function linkSyncKey() {
  var inp = document.getElementById("sync-link-key");
  var note = document.getElementById("sync-link-note");
  var v = (inp && inp.value ? inp.value : "").trim();
  if (!/^[0-9a-f]{48}$/.test(v)) {
    _syLinkArmed = false;
    if (note) note.textContent = "That doesn't look like a sync key — keys are 48 characters (0–9, a–f). Nothing was changed.";
    return;
  }
  if (!_syLinkArmed) {
    _syLinkArmed = true;
    if (note) note.textContent = "Link this device to that sync account? Local data will be merged into it — nothing is overwritten. Tap Link again to confirm.";
    return;
  }
  _syLinkArmed = false;
  if (note) note.textContent = "";
  SY.key = v; SY.acct = null; SY.last = 0; SY.rej = 0;
  syTrackChanges();
  SY_COLLS.forEach(function (c) {
    syCollGet(c).forEach(function (r) { var id = syRecId(c, r); if (id) SY.dirty[c][id] = 1; });
  });
  SY.dirty.m = 1;
  saveSY();
  /* Say so immediately: without this the status line kept
     showing whatever the boot pass last wrote (often the
     auto-created account) and the link looked like it failed. */
  setSyncStatus("Linking to account…");
  syncNow(false, true);
}
(function initSync() {
  var stat = document.getElementById("syncstat");
  if (stat) stat.innerHTML = syncStatusHTML();
  var kf = document.getElementById("sync-key");
  if (kf) kf.value = SY.key || "(created on first sync)";
  var nb = document.getElementById("sync-now-btn");
  if (nb) nb.addEventListener("click", function () { syncNow(false, true); });
  var snr = document.getElementById("sync-note-retry");
  if (snr) snr.addEventListener("click", function () { _syNoteOff = false; syncNow(false, true); });
  var snd = document.getElementById("sync-note-dismiss");
  if (snd) snd.addEventListener("click", function () { _syNoteOff = true; syNoteRender(); });
  syNoteRender();
  var dab = document.getElementById("data-alert-btn");
  if (dab) dab.addEventListener("click", dataAlertAction);
  var dad = document.getElementById("data-alert-dismiss");
  if (dad) dad.addEventListener("click", dataAlertDismiss);
  dataNoteRender();
  /* Registration code (worker /register is gated): kept only in
     this device's local store — never synced, never exported. */
  var rci = document.getElementById("sync-regcode");
  if (rci) { try { rci.value = store.get("regCode", "") || ""; } catch (e) {} }
  var rcb = document.getElementById("sync-regcode-btn");
  if (rcb) rcb.addEventListener("click", function () {
    var v = (rci && rci.value ? rci.value : "").trim();
    try { store.set("regCode", v); } catch (e) {}
    _syRegNeed = false;
    var n = document.getElementById("sync-regcode-note");
    if (n) n.textContent = v ? "Code saved on this device — tap Sync now to create the account." : "Code cleared.";
  });
  var lb = document.getElementById("sync-link-btn");
  if (lb) lb.addEventListener("click", linkSyncKey);
  var na = document.getElementById("sync-new-acct");
  if (na) na.addEventListener("click", newSyncAccount);
  syShowRejected();
  /* One hook for every write: any store.set of a synced key
     tracks the change and schedules a sync — no missed call
     sites, whether the write came from persistAll or a direct
     store.set anywhere in the app. */
  var origSet = store.set;
  store.set = function (k, v) {
    var ok = origSet.call(store, k, v);
    if (ok && !_syApplying && (SY_KEY_COLL[k] || SY_META_KEYS[k])) {
      try { if (syTrackChanges(SY_KEY_COLL[k] || null)) schedSync(); } catch (e) {}
    }
    return ok;
  };
  try { syTrackChanges(); } catch (e) {}
  setTimeout(function () { syncNow(false, true); }, 800);
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") syncNow(); });
  window.addEventListener("online", function () { syncNow(false, true); });
  setInterval(function () { if (document.visibilityState === "visible") syncNow(); }, 120000);
})();

/* ================= Build .40 — Add from a photo =================
   One photo that may hold several garments (a flat-lay, a haul
   shot, a screenshot of a worn look) is analyzed off-platform by
   the wardrobe-sync worker's analyze queue — the same base and
   Bearer key as the render queue. The pieces it finds come back
   as a confirm sheet (panel-analyze); nothing files into the
   Closet without a tap on that piece's Add to closet. A job
   (photo + analyzeId) persists on-device until it settles, and
   unsettled jobs are polled on open and every ~10 s while the
   app is open, so leaving and reopening settles a job in place. */
var analyzeJobs = [];
try { analyzeJobs = store.get("analyzeJobs", []); } catch (e) { analyzeJobs = []; }
if (!Array.isArray(analyzeJobs)) analyzeJobs = [];
var analyzeNeedSync = false;
var analyzeRetryPickId = null;
var analyzeResubmitted = {};
function analyzeSaveJobs() { try { store.set("analyzeJobs", analyzeJobs); } catch (e) {} }
function analyzeJobById(id) {
  for (var i = 0; i < analyzeJobs.length; i++) if (analyzeJobs[i].id === id) return analyzeJobs[i];
  return null;
}
function analyzeNewId() {
  var b = new Uint8Array(8), i, s = "";
  if (window.crypto && crypto.getRandomValues) crypto.getRandomValues(b);
  else for (i = 0; i < 8; i++) b[i] = Math.floor(Math.random() * 256);
  for (i = 0; i < 8; i++) { var h = b[i].toString(16); s += (h.length < 2 ? "0" : "") + h; }
  return s;
}
function analyzeUnhandled(job) {
  if (!job || job.status !== "done" || !Array.isArray(job.items)) return 0;
  var n = 0;
  job.items.forEach(function (it, ix) { if (!job.handled || !job.handled[ix]) n++; });
  return n;
}
function analyzePendingCount() {
  return analyzeJobs.reduce(function (n, j) { return n + analyzeUnhandled(j); }, 0);
}
function analyzeSettle(job) {
  /* Every card handled: the job is settled and leaves the store,
     photo and all. Failed jobs stay — they are the retry path. */
  if (job.status === "done" && Array.isArray(job.items) && analyzeUnhandled(job) === 0) {
    analyzeJobs = analyzeJobs.filter(function (j) { return j !== job; });
    analyzeSaveJobs();
  }
}
function analyzeApplyState(job, j) {
  if (!j || !j.status) return;
  job.status = j.status;
  job.note = typeof j.note === "string" ? j.note : "";
  if (j.status === "done" && Array.isArray(j.items)) {
    job.items = j.items.map(function (it) {
      it = it || {};
      return {
        name: String(it.name || ""),
        category: String(it.category || ""),
        colourName: String(it.colourName || ""),
        colourHex: /^#[0-9a-f]{3,8}$/i.test(it.colourHex || "") ? it.colourHex : "#232d3f",
        brand: String(it.brand || ""),
        img: String(it.img || "").replace(/["'<>`]/g, "")
      };
    });
    if (!job.handled || typeof job.handled !== "object") job.handled = {};
    if (!job.items.length) {
      /* Nothing in the photo: settle at once, no sheet to show. */
      analyzeJobs = analyzeJobs.filter(function (x) { return x !== job; });
      analyzeSaveJobs();
      if (typeof toast === "function") toast("No pieces were found in that photo.");
    }
  }
}
function analyzeEnqueue(job) {
  var key = swapSyncKey();
  if (!key || !job.photo) return Promise.resolve(false);
  return swapFetch(swapSyncBase() + "/analyze-queue", {
    method: "POST",
    headers: { "authorization": "Bearer " + key, "content-type": "application/json" },
    body: JSON.stringify({ analyzeId: job.id, image: job.photo })
  }, 30000).then(function (r) {
    if (r && typeof r.ok === "boolean" && !r.ok) throw new Error("analyze submit " + r.status);
    return (r && typeof r.json === "function") ? r.json().catch(function () { return null; }) : null;
  }).then(function (j) {
    if (j) analyzeApplyState(job, j);
    analyzeSaveJobs();
    analyzeRefreshUI();
    return true;
  }).catch(function () { return false; });
}
function analyzePollJob(job) {
  var key = swapSyncKey();
  if (!key || !job || (job.status !== "queued" && job.status !== "analyzing")) return;
  swapFetch(swapSyncBase() + "/analyze-queue/" + job.id, {
    headers: { "authorization": "Bearer " + key }
  }, 20000).then(function (r) {
    if (r && r.status === 404) return { __missing: true };
    return (r && r.ok) ? r.json() : null;
  }).then(function (j) {
    if (!j) return;
    if (j.__missing) {
      /* The enqueue never landed (its failure was silent):
         resubmit once per session from the persisted photo —
         the worker revives the same analyzeId. */
      if (job.photo && !analyzeResubmitted[job.id]) { analyzeResubmitted[job.id] = 1; analyzeEnqueue(job); }
      return;
    }
    analyzeApplyState(job, j);
    analyzeSettle(job);
    analyzeSaveJobs();
    analyzeRefreshUI();
  }).catch(function () {});
}
function analyzePollAll() { analyzeJobs.slice().forEach(analyzePollJob); }
/* The picked photo, downscaled for the worker: max 1024 px on
   the long edge as a JPEG data URI, stepped down until the
   request body stays under the worker's ~1.8 MB ceiling. Same
   EXIF-safe decode paths as processPhotoFile. */
function analyzeScalePhoto(file, done) {
  var finished = false;
  var watchdog = setTimeout(function () { finish(null); }, 30000);
  function finish(url) {
    if (finished) return;
    finished = true;
    clearTimeout(watchdog);
    done(url);
  }
  function draw(source, w, h) {
    function encode(max, q) {
      var scale = Math.min(1, max / Math.max(w, h));
      var canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(w * scale));
      canvas.height = Math.max(1, Math.round(h * scale));
      canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL("image/jpeg", q);
    }
    try {
      var url = encode(1024, 0.85);
      if (url.length > 1500000) url = encode(1024, 0.7);
      if (url.length > 1500000) url = encode(1024, 0.55);
      if (url.length > 1500000) url = encode(896, 0.55);
      if (url.length > 1500000) url = encode(768, 0.5);
      finish(url);
    } catch (e) { finish(null); }
  }
  function legacy() {
    var reader = new FileReader();
    reader.onload = function () {
      var img = new Image();
      img.onload = function () { draw(img, img.width, img.height); };
      img.onerror = function () { finish(null); };
      img.src = reader.result;
    };
    reader.onerror = function () { finish(null); };
    try { reader.readAsDataURL(file); } catch (e) { finish(null); }
  }
  function bitmap(withOpts) {
    var p;
    try {
      p = withOpts ? createImageBitmap(file, { imageOrientation: "from-image" }) : createImageBitmap(file);
    } catch (e) { if (withOpts) bitmap(false); else legacy(); return; }
    p.then(function (bmp) { draw(bmp, bmp.width, bmp.height); }, function () {
      if (withOpts) bitmap(false); else legacy();
    });
  }
  if (window.createImageBitmap) bitmap(true); else legacy();
}
function analyzeRefreshUI() {
  var box = document.getElementById("analyze-status");
  if (box) {
    var rows = [];
    if (analyzeNeedSync) rows.push('<div class="analyze-status-row"><span>Turn on sync to analyze photos</span></div>');
    analyzeJobs.forEach(function (job) {
      if (job.status === "queued" || job.status === "analyzing") {
        /* Never an endless spinner: past ~15 minutes the line
           goes quiet and simply says to check back. */
        var stale = Date.now() - (job.createdAt || 0) > 15 * 60 * 1000;
        rows.push('<div class="analyze-status-row">' + (stale ? "" : '<span class="analyze-spin" aria-hidden="true"></span>') +
          "<span>" + (stale ? "Still analyzing — check back shortly" : "Analyzing your photo — pieces will appear here for review.") + "</span></div>");
      } else if (job.status === "failed") {
        rows.push('<div class="analyze-status-row"><span>' + esc(job.note || "That photo couldn't be analyzed.") + "</span>" +
          '<button type="button" class="btn-ghost" data-analyze-retry="' + esc(job.id) + '">Retry</button></div>');
      } else if (job.status === "done") {
        var n = analyzeUnhandled(job);
        if (n > 0) rows.push('<div class="analyze-status-row"><button type="button" class="btn-ink" data-analyze-review>Review ' + n + (n === 1 ? " piece" : " pieces") + "</button></div>");
      }
    });
    box.innerHTML = rows.join("");
  }
  var banner = document.getElementById("closet-analyze-banner");
  if (banner) {
    var total = analyzePendingCount();
    banner.hidden = total === 0;
    if (total > 0) banner.textContent = total === 1 ? "1 piece from your photo is ready to review" : total + " pieces from your photo are ready to review";
  }
  if (typeof currentTab !== "undefined" && currentTab === "analyze") renderAnalyzeSheet();
}
function analyzeCatOptions(selected) {
  var src = document.getElementById("item-cat");
  var out = "";
  if (!src) return out;
  for (var i = 0; i < src.options.length; i++) {
    var v = src.options[i].value;
    out += "<option" + (v === selected ? " selected" : "") + ">" + esc(v) + "</option>";
  }
  return out;
}
var analyzeSheetSig = null;
function renderAnalyzeSheet() {
  var list = document.getElementById("analyze-list");
  if (!list) return;
  /* A background poll settling another job must not rebuild the
     sheet under fingers mid-edit: only re-render when the set of
     unhandled cards actually changed. Explicit renders after an
     Add/Discard clear the signature first (analyzeRefreshUI's
     caller paths set analyzeSheetSig via the handled change —
     the signature covers job id + card index + handled state). */
  var sig = analyzeJobs.map(function (j) {
    return j.id + ":" + j.status + ":" + (Array.isArray(j.items) ? j.items.map(function (it, ix) { return (j.handled && j.handled[ix]) ? "x" : "o"; }).join("") : "-");
  }).join("|");
  if (sig === analyzeSheetSig && list.innerHTML) return;
  analyzeSheetSig = sig;
  var cards = [];
  analyzeJobs.forEach(function (job) {
    if (job.status !== "done" || !Array.isArray(job.items)) return;
    job.items.forEach(function (it, ix) {
      if (job.handled && job.handled[ix]) return;
      var fid = "an-" + job.id + "-" + ix;
      cards.push(
        '<article class="card add-form analyze-item" data-analyze-job="' + esc(job.id) + '" data-analyze-ix="' + ix + '">' +
        (it.img ? '<img class="analyze-item-photo" src="' + esc(it.img) + '" alt="Photograph of ' + esc(it.name) + '" loading="lazy" decoding="async" />' : "") +
        '<div><label class="field" for="' + fid + '-name">Name</label>' +
        '<input type="text" id="' + fid + '-name" data-an-f="name" value="' + esc(it.name) + '" /></div>' +
        '<div><label class="field" for="' + fid + '-cat">Category</label>' +
        '<select id="' + fid + '-cat" data-an-f="category">' + analyzeCatOptions(it.category) + "</select></div>" +
        '<div><label class="field" for="' + fid + '-colour">Colour</label>' +
        '<div class="row-inline">' +
        '<input type="text" id="' + fid + '-colour" data-an-f="colourName" value="' + esc(it.colourName) + '" class="grow" />' +
        '<input type="color" data-an-f="colourHex" value="' + esc(it.colourHex) + '" aria-label="Pick the colour" /></div></div>' +
        '<div><label class="field" for="' + fid + '-brand">Brand</label>' +
        '<input type="text" id="' + fid + '-brand" data-an-f="brand" value="' + esc(it.brand) + '" /></div>' +
        '<div class="analyze-item-actions">' +
        '<button type="button" class="btn-ink" data-analyze-add>Add to closet</button>' +
        '<button type="button" class="btn-ghost" data-analyze-discard>Discard</button>' +
        "</div></article>"
      );
    });
  });
  list.innerHTML = cards.length ? cards.join("") : '<div class="card empty">Nothing to review.</div>';
}
function analyzeFilePiece(card, job, ix) {
  /* File through the same path as the single-piece add form:
     same record shape, same Wada colour helper, same persist —
     with the analyzed photo kept as its published file
     reference, never a base64 copy. The Closet carries brand
     as the name prefix, so a read brand leads the name unless
     it is already there. */
  var it = job.items[ix];
  function field(f) { var el = card.querySelector('[data-an-f="' + f + '"]'); return el ? el.value : ""; }
  var name = field("name").trim();
  if (!name) return;
  var brand = field("brand").trim();
  if (brand && name.toLowerCase().indexOf(brand.toLowerCase()) !== 0) name = brand + " " + name;
  var colourName = field("colourName").trim();
  var colourHex = /^#[0-9a-f]{3,8}$/i.test(field("colourHex")) ? field("colourHex") : "#232d3f";
  var wada = nearestWada(colourHex);
  wardrobeItems.unshift({
    id: "item-" + Date.now() + "-" + ix,
    name: name,
    category: field("category"),
    colourName: colourName || wada.name,
    colourHex: colourHex,
    extraColours: colourName ? [{ name: "Nearest Wada: " + wada.name, hex: wada.hex }] : [],
    notes: "",
    price: null,
    wearCount: 0,
    lastWorn: null,
    addedISO: localTodayISO(),
    laundry: false,
    photo: it.img || null
  });
  var kept = persistAll();
  if (!job.handled) job.handled = {};
  job.handled[ix] = "added";
  analyzeSettle(job);
  analyzeSaveJobs();
  renderWardrobe();
  analyzeRefreshUI();
  toast(kept ? "Added — " + name + "." : "Added — storage full, not kept. Export a backup from Profile.");
}
(function analyzeWire() {
  var input = document.getElementById("analyze-photo");
  if (input) input.addEventListener("change", function () {
    var file = this.files && this.files[0];
    this.value = "";
    if (!file) return;
    if (!swapSyncKey()) { analyzeNeedSync = true; analyzeRefreshUI(); return; }
    analyzeNeedSync = false;
    analyzeScalePhoto(file, function (url) {
      if (!url) { toast("That photo couldn't be read — try a different photo."); return; }
      var job = analyzeRetryPickId ? analyzeJobById(analyzeRetryPickId) : null;
      analyzeRetryPickId = null;
      if (job) {
        /* Retry with a fresh pick: same analyzeId, new photo. */
        job.photo = url;
        job.status = "queued";
        job.note = "";
        job.createdAt = Date.now();
      } else {
        job = { id: analyzeNewId(), createdAt: Date.now(), status: "queued", note: "", items: null, handled: {}, photo: url };
        analyzeJobs.push(job);
      }
      analyzeSaveJobs();
      analyzeRefreshUI();
      analyzeEnqueue(job);
    });
  });
  var addCard = document.getElementById("analyze-add-card");
  if (addCard) addCard.addEventListener("click", function (e) {
    if (e.target.closest && e.target.closest("[data-analyze-review]")) { switchTab("analyze"); return; }
    var retry = e.target.closest ? e.target.closest("[data-analyze-retry]") : null;
    if (retry) {
      var job = analyzeJobById(retry.getAttribute("data-analyze-retry"));
      if (!job) return;
      if (!swapSyncKey()) { analyzeNeedSync = true; analyzeRefreshUI(); return; }
      analyzeNeedSync = false;
      if (job.photo) {
        /* Re-submitting a failed analyzeId revives the job. */
        job.status = "queued";
        job.note = "";
        job.createdAt = Date.now();
        analyzeSaveJobs();
        analyzeRefreshUI();
        analyzeEnqueue(job);
      } else if (input) {
        analyzeRetryPickId = job.id;
        input.click();
      }
    }
  });
  var banner = document.getElementById("closet-analyze-banner");
  if (banner) banner.addEventListener("click", function () { switchTab("analyze"); });
  var list = document.getElementById("analyze-list");
  if (list) list.addEventListener("click", function (e) {
    var add = e.target.closest ? e.target.closest("[data-analyze-add]") : null;
    var disc = e.target.closest ? e.target.closest("[data-analyze-discard]") : null;
    var btn = add || disc;
    if (!btn) return;
    var card = btn.closest("[data-analyze-job]");
    if (!card) return;
    var job = analyzeJobById(card.getAttribute("data-analyze-job"));
    if (!job) return;
    var ix = parseInt(card.getAttribute("data-analyze-ix"), 10);
    if (add) { analyzeFilePiece(card, job, ix); return; }
    if (!job.handled) job.handled = {};
    job.handled[ix] = "discarded";
    analyzeSettle(job);
    analyzeSaveJobs();
    analyzeRefreshUI();
  });
  analyzeRefreshUI();
  analyzePollAll();
  setInterval(analyzePollAll, 10000);
})();

/* ================= Audit pass — layers behave as dialogs; newer-build notice ================= */
(function () {
  /* The outfit pop-outs cover the page but were not announced as
     dialogs, kept no focus, and ignored Escape. Watching the
     `hidden` attribute covers every code path that opens or
     closes them. */
  var layers = [
    { el: document.getElementById("look-layer"), close: function () { if (typeof closeLookLayer === "function") closeLookLayer(); } },
    { el: document.getElementById("fw-layer"), close: function () { if (typeof closeFwLayer === "function") closeFwLayer(); } }
  ].filter(function (l) { return l.el; });
  layers.forEach(function (l) {
    l.el.setAttribute("role", "dialog");
    l.el.setAttribute("aria-modal", "true");
    if (!l.el.hasAttribute("aria-label")) l.el.setAttribute("aria-label", "Outfit details");
    l.opener = null;
    l.wasHidden = l.el.hidden;
    if (!("MutationObserver" in window)) return;
    new MutationObserver(function () {
      if (l.el.hidden === l.wasHidden) return;
      l.wasHidden = l.el.hidden;
      if (!l.el.hidden) {
        l.opener = document.activeElement;
        var first = l.el.querySelector("button, [href], input, select, textarea");
        if (first) { try { first.focus({ preventScroll: true }); } catch (e) {} }
      } else if (l.opener && document.contains(l.opener)) {
        try { l.opener.focus({ preventScroll: true }); } catch (e) {}
        l.opener = null;
      }
    }).observe(l.el, { attributes: true, attributeFilter: ["hidden"] });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    /* Topmost first: the From-wardrobe layer can sit over the look layer. */
    for (var i = layers.length - 1; i >= 0; i--) {
      if (!layers[i].el.hidden) { layers[i].close(); return; }
    }
  });

  /* A home-screen app can stay open for days. On load and on
     returning to it (at most every 30 seconds) read the first 2 KB
     of the page from the network and compare its build stamp with
     ours. If a newer build is on the server, reload once (session
     guard so it cannot loop). If we already reloaded for this build
     and the stamps still disagree, show the update bar as a fallback. */
  var lastCheck = 0;
  var BUILD_RELOAD_KEY = "wardrobe.reloadFor." + WARDROBE_BUILD;
  function reloadOnceForBuild() {
    try { if (sessionStorage.getItem(BUILD_RELOAD_KEY) === "1") return false; sessionStorage.setItem(BUILD_RELOAD_KEY, "1"); } catch (e) {}
    location.reload();
    return true;
  }
  function checkBuild(force) {
    if (!navigator.onLine || !window.fetch) return;
    if (!force && Date.now() - lastCheck < 30 * 1000) return;
    lastCheck = Date.now();
    fetch("index.html", { headers: { Range: "bytes=0-2047" }, cache: "no-store" })
      .then(function (r) { return (r.status === 200 || r.status === 206) ? r.text() : ""; })
      .then(function (t) {
        var m = /name="wardrobe-build"\s+content="([^"]+)"/.exec(t.slice(0, 4096));
        if (m && m[1] && m[1] !== WARDROBE_BUILD) {
          if (!reloadOnceForBuild()) {
            var b = document.getElementById("update-bar");
            if (b) b.hidden = false;
          }
        }
      })
      .catch(function () {});
  }
  var ub = document.getElementById("update-btn");
  if (ub) ub.addEventListener("click", function () { location.reload(); });
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState !== "visible") return;
    checkBuild();
    try {
      if (navigator.serviceWorker && navigator.serviceWorker.getRegistration) {
        navigator.serviceWorker.getRegistration().then(function (r) { if (r && r.update) r.update(); });
      }
    } catch (e) {}
  });
  checkBuild(true);
})();

/* ================= Build .53 — data repair =================
   The saved-collection invariants are enforced on EVERY boot —
   and again after any sync pull that changes the looks, via
   window.enforceSavedInvariants53 — so a stale copy restored by
   sync is re-cleaned in the same pass and corrupt entries never
   resurrect: the saved collections, the render queue's saved
   references and the week plan are walked, titles recomputed
   from the pictured render, duplicate photos dropped (earliest
   save kept), real worn photos moved to the worn log, the
   quarantined render and every verdict image evicted. The
   closet merge and denim colour audit run once only, gated by
   store key "repair53"; that record keeps the first run's
   counts under `counts` and stamps `lastRun` / `lastCounts`
   on every later run. The repaired collections persist through
   the normal sync collections, so the fix propagates. */
(function repair53() {
  try {
    var already = null;
    try { already = store.get("repair53", null); } catch (e) {}
    var firstRun = !(already && already.done);
    function freshCounts() {
      return { scanned: 0, titlesCorrected: 0, dupesRemoved: 0, wornRelocated: 0, verdictEvictions: [], closetMerged: 0, closetColourFixed: 0, quarantinedRemoved: 0, oatmealRepointed: 0, undetermined: [], changed: false };
    }
    function pictured(l) {
      try { return lookPicturedImg(l) || l.img || lookImg(l) || ""; } catch (e) { return (l && l.img) || ""; }
    }
    function ensureWorn(img, title, date) {
      if (!img || typeof wornLog === "undefined" || !Array.isArray(wornLog)) return;
      for (var i = 0; i < wornLog.length; i++) {
        if (wornLog[i] && wornLog[i].img && imgsEquivalent(wornLog[i].img, img)) return;
      }
      wornLog.unshift({ id: "worn-r53-" + Date.now() + "-" + Math.floor(Math.random() * 1e6), date: date || localTodayISO(), title: title || "Logged outfit", img: img, pieces: [], selfie: true });
    }
    function saveStampOf(e) {
      var v = e ? e.savedAt : null;
      if (typeof v === "number" && isFinite(v)) return v;
      if (typeof v === "string" && v) {
        var p = Date.parse(v);
        if (!isNaN(p)) return p;
        var n = Number(v);
        if (!isNaN(n)) return n;
      }
      return Infinity;
    }
    function processCollection(list, counts) {
      if (!Array.isArray(list)) return list;
      /* (b) dedupe first, by pictured image (watch variants count
         as the same photo). The stored collections are oldest-
         first, so per canonical image keep the entry with the
         smallest savedAt — the original save; ties or a missing
         savedAt keep the first entry in list order. Every other
         entry picturing the same image is a dupe. */
      var keeperIdx = {};
      list.forEach(function (entry, idx) {
        var k = entry && typeof entry === "object" ? canonicalImg(pictured(entry) || "") : "";
        if (!k) return;
        if (!(k in keeperIdx)) { keeperIdx[k] = idx; return; }
        if (saveStampOf(entry) < saveStampOf(list[keeperIdx[k]])) keeperIdx[k] = idx;
      });
      var deduped = [];
      list.forEach(function (entry, idx) {
        var k = entry && typeof entry === "object" ? canonicalImg(pictured(entry) || "") : "";
        if (k && keeperIdx[k] !== idx) { counts.dupesRemoved++; return; }
        deduped.push(entry);
      });
      list = deduped;
      var out = [];
      list.forEach(function (l) {
        if (!l || typeof l !== "object") { out.push(l); return; }
        counts.scanned++;
        var img = pictured(l);
        if (img && isQuarantinedImg(img)) { counts.quarantinedRemoved++; return; }
        if (img && isDislikedImg(img)) { counts.verdictEvictions.push(displayTitleForLook(l, img) || l.title || "Look"); return; }
        var wornPhoto = lookIsRealPhoto(l, img);
        if (wornPhoto && !(l.source === "uploaded" && !l.selfie)) {
          ensureWorn(img, l.title || "Logged outfit", l.wornDate || null);
          counts.wornRelocated++;
          return;
        }
        var nt = displayTitleForLook(l, img);
        if (nt && nt !== l.title) { l.title = nt; counts.titlesCorrected++; }
        out.push(l);
      });
      return out;
    }
    /* Build .56: JOINT dedupe across savedLooks and queueLooks.
       The .53 walk deduped within each list only, so a photo
       saved in one list and queued in the other survived twice
       and resurfaced as a second grid card. Now one keeper per
       canonical photo across BOTH lists: the entry with the
       smallest real savedAt (the walk's standing keeper rule —
       likes are stamped at save time since .56, so the freshly
       liked copy carries a real stamp and is never the Infinity
       entry that loses). An entry in the other list with the SAME
       id is the same look in its second state (saved + queued),
       not a duplicate, and stays. Empty pictured images are
       never duplicates of anything. */
    function jointDedupe56(counts) {
      if (typeof savedLooks === "undefined" || typeof queueLooks === "undefined") return;
      if (!Array.isArray(savedLooks) || !Array.isArray(queueLooks)) return;
      var keeper = {};
      function scan(list) {
        list.forEach(function (e) {
          if (!e || typeof e !== "object") return;
          var k = canonicalImg(pictured(e) || "");
          if (!k) return;
          var st = saveStampOf(e);
          if (!(k in keeper) || st < keeper[k].stamp) keeper[k] = { entry: e, stamp: st };
        });
      }
      scan(savedLooks); scan(queueLooks);
      function keepOnly(list) {
        return list.filter(function (e) {
          if (!e || typeof e !== "object") return true;
          var k = canonicalImg(pictured(e) || "");
          if (!k) return true;
          var kp = keeper[k];
          if (!kp || kp.entry === e) return true;
          if (kp.entry.id && e.id && kp.entry.id === e.id) return true;
          counts.dupesRemoved++;
          return false;
        });
      }
      savedLooks = keepOnly(savedLooks);
      queueLooks = keepOnly(queueLooks);
    }
    function walkCollections(counts) {
      if (typeof savedLooks !== "undefined") savedLooks = processCollection(savedLooks, counts);
      if (typeof queueLooks !== "undefined") queueLooks = processCollection(queueLooks, counts);
      jointDedupe56(counts);
      if (typeof weekPlan !== "undefined" && Array.isArray(weekPlan)) {
        weekPlan = weekPlan.filter(function (e) {
          if (!e || !e.look) return !!e;
          var im = pictured(e.look);
          if (im && (isQuarantinedImg(im) || isDislikedImg(im))) return false;
          if (!planLookValid(e.look)) return false;
          var nt = displayTitleForLook(e.look, im);
          if (nt && nt !== e.look.title) { e.look.title = nt; counts.titlesCorrected++; }
          return true;
        });
        if (typeof saveWeekPlan === "function") saveWeekPlan();
      }
    }
    function persistRepair() {
      try { if (typeof persistAll === "function") persistAll(); } catch (e) {}
      try { if (typeof saveQueue === "function") saveQueue(); } catch (e) {}
      try { if (typeof wornLog !== "undefined") store.set("wornLog", wornLog); } catch (e) {}
    }
    function collectionsSnapshot() {
      try {
        return JSON.stringify([
          typeof savedLooks !== "undefined" ? savedLooks : null,
          typeof queueLooks !== "undefined" ? queueLooks : null,
          typeof weekPlan !== "undefined" ? weekPlan : null,
          typeof wornLog !== "undefined" ? wornLog : null
        ]);
      } catch (e) { return ""; }
    }
    /* The collection walk, exposed so a sync pull that restores
       stale looks can be re-cleaned in the same pass (syncNow
       calls this when the looks changed). Persists only when
       the walk actually changed something. */
    function enforceSavedInvariants53() {
      var counts = freshCounts();
      var before = collectionsSnapshot();
      walkCollections(counts);
      counts.changed = collectionsSnapshot() !== before;
      if (counts.changed) persistRepair();
      return counts;
    }
    try { window.enforceSavedInvariants53 = enforceSavedInvariants53; } catch (e) {}
    var counts = enforceSavedInvariants53();
    if (firstRun) {
    /* ---- Closet: dedupe, junk-name cleanup, colour audit ---- */
    function normTokens(name) {
      var s = String(name || "").toLowerCase().replace(/['\u2019\u2018]/g, "");
      s = s.replace(/\u2026|\.\.\./g, " ");
      s = s.replace(/\b\d{2,3}\s?x\s?\d{2,3}\b/g, " ");
      s = s.replace(/\b(mens|men|womens|women|size|sz|new|used|pre-owned|preowned|excellent|condition|nwt|nwot|with tags|free shipping|rare)\b/g, " ");
      s = s.replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
      return s;
    }
    function closetSignature(it) {
      var toks = normTokens(it.name).split(" ").filter(Boolean);
      var model = null;
      toks.forEach(function (tk) { if (!model && /^\d{3,4}$/.test(tk)) model = tk; });
      var brand = toks.length ? toks[0] : "";
      if (brand === "levi" || brand === "levis") brand = "levis";
      if (model) return (it.category || "") + "|" + brand + "|" + model;
      var uniq = [];
      toks.forEach(function (tk) { if (uniq.indexOf(tk) === -1 && tk.length >= 3) uniq.push(tk); });
      return (it.category || "") + "|" + uniq.sort().join(" ");
    }
    function cleanClosetName(it) {
      var raw = String(it.name || "");
      if (/levi/.test(normTokens(raw)) && /\b517\b/.test(normTokens(raw)) && (it.category === "Jeans" || /jean/.test(normTokens(raw)))) return "Levi's 517 Jeans";
      var name = raw.replace(/\u2026.*$/, "").replace(/\.\.\..*$/, "");
      name = name.replace(/\b(mens|men's|womens|women's)\b/gi, " ");
      name = name.replace(/\b\d{2,3}\s?x\s?\d{2,3}\b/gi, " ");
      name = name.replace(/\bsize\s+[a-z0-9]+\b/gi, " ");
      name = name.replace(/\s+/g, " ").trim();
      var words = name.split(" ");
      if (words.length > 2) {
        var first = words[0].toLowerCase().replace(/['\u2019]/g, "");
        var outw = [words[0]];
        for (var i = 1; i < words.length; i++) {
          var w = words[i].toLowerCase().replace(/['\u2019]/g, "");
          if (w === first) continue;
          if (w === "vintage" && outw.some(function (x) { return x.toLowerCase() === "vintage"; })) continue;
          outw.push(words[i]);
        }
        name = outw.join(" ");
      }
      return name || raw;
    }
    if (typeof wardrobeItems !== "undefined" && Array.isArray(wardrobeItems)) {
      /* Build .77: only a true duplicate record merges. The fuzzy rule
         this replaced ("same brand + model number", "token subset",
         60% token overlap) collapsed distinct pieces — three different
         pairs of Levi's 517, navy leather vs navy suede loafers, mint vs
         white polos — and deleted them everywhere through sync. */
      function colourKey(it) { return String(it.colourName || it.color || "").split("\u00b7")[0].trim().toLowerCase(); }
      function sameGarment(a, b) {
        if ((a.category || "") !== (b.category || "")) return false;
        if (normTokens(a.name) !== normTokens(b.name)) return false;
        if (String(a.name || "").replace(/\s+/g, " ").trim().toLowerCase() !== String(b.name || "").replace(/\s+/g, " ").trim().toLowerCase()) return false;
        if (colourKey(a) && colourKey(b) && colourKey(a) !== colourKey(b)) return false;
        if (a.receiptId && b.receiptId && a.receiptId !== b.receiptId) return false;
        if (a.photo && b.photo && a.photo !== b.photo) return false;
        return true;
      }
      var parent = {};
      wardrobeItems.forEach(function (it) { if (it && it.id) parent[it.id] = it.id; });
      function findRoot(x) { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
      for (var gi = 0; gi < wardrobeItems.length; gi++) {
        for (var gj = gi + 1; gj < wardrobeItems.length; gj++) {
          var ga = wardrobeItems[gi], gb = wardrobeItems[gj];
          if (ga && gb && ga.id && gb.id && sameGarment(ga, gb)) { var ra = findRoot(ga.id), rb = findRoot(gb.id); if (ra !== rb) parent[ra] = rb; }
        }
      }
      var groups = {};
      wardrobeItems.forEach(function (it) { if (!it || !it.id) return; var sg = findRoot(it.id); (groups[sg] = groups[sg] || []).push(it); });
      var losers = {};
      Object.keys(groups).forEach(function (sg) {
        var g = groups[sg];
        if (g.length < 2) return;
        function photoScore(it) {
          if (!it.photo) return 0;
          return it.photo.indexOf("data:") === 0 ? 1 + String(it.photo).length / 1000000 : 2 + String(it.photo).length / 100000;
        }
        var keeper = g.slice().sort(function (a, b) {
          var d = photoScore(b) - photoScore(a);
          return d !== 0 ? d : cleanClosetName(a).length - cleanClosetName(b).length;
        })[0];
        var totalWorn = 0, latest = null;
        g.forEach(function (it) {
          totalWorn += (typeof it.wearCount === "number" ? it.wearCount : (typeof it.wornCount === "number" ? it.wornCount : 0));
          if (it.lastWorn && (!latest || it.lastWorn > latest)) latest = it.lastWorn;
          if (it === keeper) return;
          losers[it.id] = true;
          counts.closetMerged++;
          ["receiptRefs", "receipts", "provenance", "receiptId", "orderNo", "shopKey"].forEach(function (k) {
            var v = it[k]; if (v == null) return;
            var arr = Array.isArray(v) ? v : [v];
            var cur = keeper[k] == null ? [] : (Array.isArray(keeper[k]) ? keeper[k].slice() : [keeper[k]]);
            arr.forEach(function (x) { if (cur.indexOf(x) === -1) cur.push(x); });
            keeper[k] = (Array.isArray(keeper[k]) || cur.length > 1) ? cur : cur[0];
          });
          if (!keeper.photo && it.photo) keeper.photo = it.photo;
          if (!keeper.price && it.price) keeper.price = it.price;
          if (it.id.indexOf("seed-") === 0 && typeof deletedIds !== "undefined" && deletedIds.indexOf(it.id) === -1) deletedIds.push(it.id);
        });
        keeper.wearCount = totalWorn;
        if ("wornCount" in keeper) keeper.wornCount = totalWorn;
        if (latest) keeper.lastWorn = latest;
        keeper.name = cleanClosetName(keeper);
      });
      if (counts.closetMerged) wardrobeItems = wardrobeItems.filter(function (it) { return !losers[it.id]; });
      wardrobeItems.forEach(function (it) {
        if (!it || !it.name) return;
        if (/\b\d{2,3}\s?x\s?\d{2,3}\b|\u2026|\b(mens|womens)\b/i.test(it.name)) {
          var cn = cleanClosetName(it);
          if (cn && cn !== it.name) it.name = cn;
        }
      });
      var DENIM_HEX = { blue: "#3d5a80", indigo: "#2c3e63", black: "#26241f", white: "#f2eee3", grey: "#8a8d8f", ecru: "#e7dcc0", navy: "#232c44", stone: "#c9bda6" };
      var DENIM_WORDS = ["indigo", "black", "white", "grey", "gray", "ecru", "navy", "blue", "stone"];
      wardrobeItems.forEach(function (it) {
        if (!it) return;
        var isJeans = it.category === "Jeans" || /\b(jeans?|denim)\b/i.test(it.name || "");
        if (!isJeans) return;
        var col = String(it.colourName || it.color || "").split("\u00b7")[0].trim().toLowerCase();
        var plausible = false;
        DENIM_WORDS.forEach(function (w) { if (col.indexOf(w) !== -1) plausible = true; });
        if (plausible) return;
        var nameLow = " " + String(it.name || "").toLowerCase() + " ";
        var found = [];
        DENIM_WORDS.forEach(function (w) { if (nameLow.indexOf(" " + w + " ") !== -1 || nameLow.indexOf(" " + w + "-") !== -1) { var c = w === "gray" ? "grey" : w; if (found.indexOf(c) === -1) found.push(c); } });
        if (found.length > 1) { counts.undetermined.push(it.id + ": " + it.name); return; }
        if (found.length === 0 && !/orange|brown|red|green|tan|camel|leather/.test(col)) { counts.undetermined.push(it.id + ": " + it.name); return; }
        var target = found.length === 1 ? found[0] : "blue";
        var label = target.charAt(0).toUpperCase() + target.slice(1);
        it.colourName = label;
        if ("color" in it) it.color = label;
        it.colourHex = DENIM_HEX[target] || "#3d5a80";
        it.extraColours = [{ name: label, hex: target === "blue" ? "#6b8cae" : (DENIM_HEX[target] || "#3d5a80") }];
        counts.closetColourFixed++;
      });
    }
    } /* end first-run-only closet merge + colour audit */
    if (firstRun) { try { persistRepair(); } catch (e) {} }
    var nowIso = new Date().toISOString();
    var record;
    if (firstRun) {
      record = { done: true, at: nowIso, counts: counts };
    } else {
      record = already || { done: true, at: nowIso, counts: counts };
      record.lastRun = nowIso;
      record.lastCounts = counts;
    }
    try { store.set("repair53", record); } catch (e) {}
    try { window.WARDROBE_REPAIR53 = record; } catch (e) {}
    try { console.log("[Wardrobe repair .53]", JSON.stringify(counts)); } catch (e) {}
    if (firstRun || counts.changed) {
      try { if (typeof renderSaved === "function") renderSaved(); } catch (e) {}
      try { if (typeof renderWardrobe === "function") renderWardrobe(); } catch (e) {}
      try { if (typeof renderWornLog === "function") renderWornLog(); } catch (e) {}
    }
  } catch (err) {
    try { console.warn("[Wardrobe repair .53] failed", err); } catch (e) {}
  }
})();

    