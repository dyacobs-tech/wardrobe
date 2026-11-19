
"use strict";
/* ================= Audit round — findings 1–27 =================
   Layered on the main script: Studio Home one-tap deal with the
   wizard demoted to Customize (settings remembered), formality
   chips, Today verdicts + swipe + location, card ••• menus, Undo
   and Recently removed, the worn log, the wishlist, trip capsules,
   Dress-for, and the compact-form / bottom-sheet / new-look
   touches. Everything here reads and writes the same on-device
   store as the rest of the app. */

/* ---------- Undo toast ---------- */
var pendingUndo = null, undoTimer = null;
function showUndoToast(msg, action) {
  var box = document.getElementById("undo-toast");
  if (!box) return;
  document.getElementById("undo-msg").textContent = msg;
  pendingUndo = action;
  box.hidden = false;
  clearTimeout(undoTimer);
  undoTimer = setTimeout(function () { box.hidden = true; pendingUndo = null; }, 4000);
  try { if (typeof window.placeUndo782 === "function") window.placeUndo782(box); } catch (e) {}
}
document.getElementById("undo-btn").addEventListener("click", function () {
  var box = document.getElementById("undo-toast");
  box.hidden = true;
  clearTimeout(undoTimer);
  if (pendingUndo) { var a = pendingUndo; pendingUndo = null; a(); }
});

/* ---------- Recently removed (5) ---------- */
var recentlyRemoved = store.get("recentlyRemoved", []);
function renderRecentlyRemoved() {
  var wrap = document.getElementById("recently-removed-wrap");
  var list = document.getElementById("recently-removed-list");
  if (!wrap || !list) return;
  wrap.hidden = !recentlyRemoved.length;
  list.innerHTML = recentlyRemoved.map(function (r) {
    return '<div class="removed-row">' + (r._img || r.img ? '<img src="' + (r._img || r.img) + '" alt="" loading="lazy" data-popout="' + (r._img || r.img) + '" />' : "") +
      '<span class="r-name">' + esc(r.title || "Look") + '</span>' +
      '<button type="button" class="btn-ghost" data-restore-removed="' + r.id + '">Restore</button></div>';
  }).join("");
}
function registerRemoved(look, img) {
  if (!look) return;
  var snap = JSON.parse(JSON.stringify(look));
  snap._img = img || look.img || "";
  snap._removedAt = Date.now();
  /* Seed-catalogue removals are tagged: the grid hides them for
     exactly as long as this snapshot exists, and restoring lifts
     the removal (and any ban tied to it) with it. */
  snap._seed = !savedLooks.some(function (l) { return l.id === snap.id; }) && SEED_LOOKS.some(function (s) { return s.id === snap.id; });
  recentlyRemoved = recentlyRemoved.filter(function (r) { return r.id !== snap.id; });
  recentlyRemoved.unshift(snap);
  /* Capped at 50 (build .55): the newest removals stay
     recoverable; older snapshots drop off the end. */
  if (recentlyRemoved.length > 50) recentlyRemoved.length = 50;
  store.set("recentlyRemoved", recentlyRemoved);
  renderRecentlyRemoved();
  var id = snap.id;
  showUndoToast("Removed — " + (snap.title || "look") + ".", function () { restoreRemoved(id); });
}
function restoreRemoved(id) {
  var snap = recentlyRemoved.filter(function (r) { return r.id === id; })[0];
  if (!snap) return;
  recentlyRemoved = recentlyRemoved.filter(function (r) { return r.id !== id; });
  store.set("recentlyRemoved", recentlyRemoved);
  var img = snap._img || snap.img;
  if (img && typeof removeDislike56 === "function") removeDislike56(img);
  var isSeed = SEED_LOOKS.some(function (s) { return s.id === id; });
  if (!isSeed && !savedLooks.some(function (l) { return l.id === id; })) {
    var copy = JSON.parse(JSON.stringify(snap));
    delete copy._img; delete copy._removedAt;
    if (copy.verdict === "dislike") copy.verdict = null;
    savedLooks.unshift(copy);
    persistAll();
  }
  renderSaved();
  renderRecentlyRemoved();
  toast("Restored — " + (snap.title || "look") + ".");
}
function showDislikeUndo(look) {
  if (!look) return;
  var img = look.img, id = look.id;
  showUndoToast("Not for you — " + (look.title || "look") + ".", function () {
    if (img && typeof removeDislike56 === "function") removeDislike56(img);
    if (currentLook && currentLook.id === id) {
      currentLook.verdict = null;
      persistLookFeedback(currentLook);
      document.querySelectorAll("[data-verdict]").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
    }
    var saved = savedLooks.filter(function (l) { return l.id === id; })[0];
    if (saved) { saved.verdict = null; persistAll(); renderSaved(); }
    toast("Undone — that outfit is back in the deck.");
  });
}
document.addEventListener("click", function (e) {
  var b = e.target.closest("[data-restore-removed]");
  if (b) restoreRemoved(b.getAttribute("data-restore-removed"));
});

/* ---------- Card ••• menus (2, 3) ---------- */
document.addEventListener("click", function (e) {
  var btn = e.target.closest ? e.target.closest("[data-menu-btn]") : null;
  if (btn) {
    var card = btn.closest(".saved-card");
    var menu = card ? card.querySelector(".card-menu") : null;
    var willOpen = menu && menu.hidden;
    document.querySelectorAll(".card-menu").forEach(function (m) { m.hidden = true; });
    document.querySelectorAll("[data-menu-btn]").forEach(function (b2) { b2.setAttribute("aria-expanded", "false"); });
    if (menu && willOpen) { menu.hidden = false; btn.setAttribute("aria-expanded", "true"); }
    return;
  }
  if (!e.target.closest(".card-menu")) {
    document.querySelectorAll(".card-menu").forEach(function (m) { m.hidden = true; });
    document.querySelectorAll("[data-menu-btn]").forEach(function (b2) { b2.setAttribute("aria-expanded", "false"); });
  } else {
    var menu2 = e.target.closest(".card-menu");
    setTimeout(function () { menu2.hidden = true; }, 60);
  }
});

/* ---------- Studio Home — Deal me a look + Customize (1) ---------- */
var STUDIO_FIELDS = ["desc", "season", "occasion-text", "style-direction", "blend-direction", "palette-source"];
var dressForKey = "";
function saveStudioSettings() {
  /* Source mode is NOT part of this blob: it lives under its own
     single key (todaySource), written by setSource itself. */
  var s = { basis: studioBasis, dress: dressForKey };
  STUDIO_FIELDS.forEach(function (id) { var el = document.getElementById(id); if (el) s[id] = el.value; });
  store.set("studioSettings", s);
}
function restoreStudioSettings() {
  var s = store.get("studioSettings", null);
  if (!s) return;
  /* The old "Palm Beach winter" season label is retired; stored
     settings carrying it land on plain Winter. */
  if (s.season === "Palm Beach winter") s.season = "Winter";
  STUDIO_FIELDS.forEach(function (id) { var el = document.getElementById(id); if (el && typeof s[id] === "string") el.value = s[id]; });
  if (s.basis && s.basis !== studioBasis) setBasis(s.basis);
  if (s.dress) applyDressFor(s.dress, true);
  if (typeof renderDirectionPreview === "function") renderDirectionPreview();
}
(function studioHome() {
  var form = document.getElementById("studio-form");
  var deal = document.getElementById("studio-deal");
  var cust = document.getElementById("studio-customize");
  if (form) {
    form.addEventListener("change", saveStudioSettings);
    form.addEventListener("input", saveStudioSettings);
  }
  if (cust && form) cust.addEventListener("click", function () {
    var open = form.style.display === "none";
    form.style.display = open ? "" : "none";
    cust.setAttribute("aria-expanded", open ? "true" : "false");
    cust.textContent = open ? "Hide customize" : "Customize";
    if (open) form.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
  if (deal) deal.addEventListener("click", function () {
    saveStudioSettings();
    var desc = document.getElementById("desc").value.trim();
    var isDealer = /dealer|surprise/i.test(desc) ||
      (!desc && !currentOccasion() && !document.getElementById("season").value &&
       document.getElementById("palette-source").value === "auto");
    if (isDealer) runDealProgress(doStyleFromForm);
    else doStyleFromForm();
  });
  var _sb = window.setBasis, _ss = window.setSource;
  if (typeof _sb === "function") window.setBasis = function (b) { _sb(b); saveStudioSettings(); };
  if (typeof _ss === "function") window.setSource = function (s2) { _ss(s2); saveStudioSettings(); };
})();

/* ---------- Dress for (24) ---------- */
var DRESS_FOR = {
  golf: { occ: "Club lunch", f: 4, label: "Golf" },
  padel: { occ: "", f: 2, label: "Padel" },
  dinner: { occ: "Dinner out", f: 4, label: "Dinner" },
  work: { occ: "Smart casual", f: 5, label: "Work" },
  date: { occ: "Dinner out", f: 5, label: "Date" },
  travel: { occ: "Travel day", f: 3, label: "Travel" }
};
function applyDressFor(key, silent) {
  var d = DRESS_FOR[key];
  document.querySelectorAll("[data-dress]").forEach(function (b) {
    b.setAttribute("aria-pressed", b.getAttribute("data-dress") === key ? "true" : "false");
  });
  dressForKey = d ? key : "";
  if (!d) return;
  /* The chip IS the occasion now (currentOccasion reads it) —
     no second control to keep in step. */
  setFormality(d.f, { silent: true });
}
/* Occasion is ONE control: the Dress-for chips plus the
   free-text line. Free text wins when it names an occasion;
   otherwise the active Dress-for chip supplies it. */
function currentOccasion() {
  var t = document.getElementById("occasion-text");
  var tv = t ? t.value.trim() : "";
  if (tv) {
    var p = parseOccasionText(tv);
    if (p && p.occasion) return p.occasion;
  }
  var d = DRESS_FOR[dressForKey];
  return d ? d.occ : "";
}
document.getElementById("dress-for").addEventListener("click", function (e) {
  var b = e.target.closest("[data-dress]");
  if (!b) return;
  var key = b.getAttribute("data-dress");
  if (dressForKey === key) { applyDressFor("", true); var occ = document.getElementById("occasion"); if (occ) occ.value = ""; saveStudioSettings(); return; }
  applyDressFor(key);
  saveStudioSettings();
});

/* ---------- Formality chips (11) ---------- */
var FSHORT = ["Swim", "Shorts", "Casual", "Smart", "Business", "Formal", "Black Tie"];
function buildFormalityChips(rangeId) {
  var range = document.getElementById(rangeId);
  if (!range || range.getAttribute("data-chips")) return;
  range.setAttribute("data-chips", "1");
  var wrap = document.createElement("div");
  wrap.className = "formality-chips";
  wrap.setAttribute("role", "group");
  wrap.setAttribute("aria-label", "Formality — pick a level");
  FORMALITY_LEVELS.forEach(function (lv) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "fchip";
    b.textContent = FSHORT[lv.level - 1];
    b.setAttribute("data-flevel", lv.level);
    b.setAttribute("aria-pressed", lv.level === formalityLevel ? "true" : "false");
    wrap.appendChild(b);
  });
  range.style.display = "none";
  range.parentNode.insertBefore(wrap, range.nextSibling);
  wrap.addEventListener("click", function (e) {
    var b = e.target.closest("[data-flevel]");
    if (!b) return;
    var v = parseInt(b.getAttribute("data-flevel"), 10);
    var changed = v !== formalityLevel;
    setFormality(v);
    if (changed && rangeId === "today-formality-range") {
      var d = document.getElementById("today-deal");
      if (d) d.click();
    }
  });
}
/* The two extra formality sliders (Today hero, Customize form)
   are gone — formality is ONE control: Ideas' Outfit type
   selector, backed by setFormality. The Dress-for macros still
   set the same level. */
/* The formality-chip wrapper is gone with the chips themselves —
   renderFormality stands alone now. */

/* ---------- Today — verdict, wore-it, swipe, location (4, 9, 21) ---------- */
var wornLog = store.get("wornLog", []);
/* One worn store, one writer. Every path that records an outfit
   as worn — Today's "Wore this today", a look's Mark worn, a
   Closet piece's "Wore it today", the selfie log — calls
   recordWorn, which writes the log entry, the saved look's worn
   flag and the pieces' wear counters together, keyed by the
   entry's own id (never by title, so two outfits on one day both
   survive). Calendar, What I'm Wearing Today, My Looks' Worn
   filter and the item wear counts all read from this one store.
   The log is a diary: it is never silently capped. */
function recordWorn(entry) {
  var date = entry.date || localTodayISO();
  if (entry.lookId && wornLog.some(function (en) { return en.lookId === entry.lookId && en.date === date; })) return null;
  /* Build .38 (2.5): piece credits arrive as mappedClosetPieces
     {id, name} objects from some callers and bare ids from
     others — normalize to id strings ONCE, here, and store them
     on the log entry itself, so an un-mark later can roll back
     exactly what this wear credited. (Before this, object-shaped
     ids silently failed the closetItemById lookup and the
     credit never landed at all.) */
  var pids = (entry.pieceIds || []).map(function (p) {
    return (p && typeof p === "object") ? p.id : p;
  }).filter(function (p) { return !!p; });
  /* Build .55 (3.7): the id is deterministic when the caller
     doesn't supply one — date + look (or pieces) + title — so
     two devices logging the same wear on the same day produce
     the same id and sync merges them into one entry; a second
     log of the same wear on this device is a duplicate. */
  var _wid = entry.id || ("worn-" + syHsh(date + "|" + (entry.lookId || pids.join("+") || "") + "|" + (entry.title || "")));
  if (wornLog.some(function (en) { return en.id === _wid; })) return null;
  var e = {
    id: _wid,
    date: date,
    title: entry.title || "Logged outfit",
    img: entry.img || "",
    pieces: entry.pieces || []
  };
  if (pids.length) e.pieceIds = pids;
  if (entry.pieceDetails) e.pieceDetails = entry.pieceDetails;
  if (entry.selfie) e.selfie = true;
  if (entry.lookId) e.lookId = entry.lookId;
  if (entry.watchId) e.watchId = entry.watchId;
  if (entry.watch) e.watch = entry.watch;
  wornLog.unshift(e);
  store.set("wornLog", wornLog);
  if (entry.lookId) {
    var sv = savedLooks.filter(function (l) { return l.id === entry.lookId; })[0];
    if (sv) { sv.worn = true; sv.wornDate = date; }
  }
  pids.forEach(function (pid) {
    var it = closetItemById(pid);
    if (!it) return;
    it.wearCount = (it.wearCount || 0) + 1;
    /* Build .38 (2.6): lastWorn never moves backwards, and a
       past-dated wear never clears today's laundry state. */
    if (!it.lastWorn || date > it.lastWorn) it.lastWorn = date;
    if (date >= localTodayISO()) it.laundry = false;
    if (it.id.indexOf("seed-") === 0) saveEntryEdit("items", it);
  });
  return e;
}
/* Build .38 (2.5): roll back the piece credits of removed worn
   entries — wearCount decremented per removed wear, lastWorn
   recomputed from the wears still in the log (cleared when the
   count is spent and no dated wear remains). Entries logged
   before pieceIds were stored fall back to their piece names. */
function rollbackWornCredits(removedEntries) {
  var counts = {};
  (removedEntries || []).forEach(function (en) {
    var pids = (en.pieceIds && en.pieceIds.length) ? en.pieceIds : null;
    if (!pids) {
      pids = [];
      (en.pieces || []).forEach(function (nm) {
        var it = (typeof wardrobeItems !== "undefined" ? wardrobeItems : []).filter(function (x) { return x.name === nm; })[0];
        if (it) pids.push(it.id);
      });
    }
    pids.forEach(function (pid) { counts[pid] = (counts[pid] || 0) + 1; });
  });
  Object.keys(counts).forEach(function (pid) {
    var it = closetItemById(pid);
    if (!it) return;
    it.wearCount = Math.max(0, (it.wearCount || 0) - counts[pid]);
    var latest = null;
    wornLog.forEach(function (en) {
      if ((en.pieceIds || []).indexOf(pid) !== -1 && (!latest || en.date > latest)) latest = en.date;
    });
    if (latest) it.lastWorn = latest;
    else if (it.wearCount === 0) it.lastWorn = null;
    if (it.id.indexOf("seed-") === 0) saveEntryEdit("items", it);
  });
}
function removeWornEntryById(id) {
  var entry = wornLog.filter(function (en) { return en.id === id; })[0];
  if (!entry) return null;
  wornLog = wornLog.filter(function (en) { return en.id !== id; });
  store.set("wornLog", wornLog);
  rollbackWornCredits([entry]);
  persistAll();
  return entry;
}
function removeWornForLook(lookId, date) {
  var removed = wornLog.filter(function (en) { return en.lookId === lookId && (!date || en.date === date); });
  if (!removed.length) return;
  wornLog = wornLog.filter(function (en) { return !(en.lookId === lookId && (!date || en.date === date)); });
  store.set("wornLog", wornLog);
  rollbackWornCredits(removed);
}
function addWornLog(entry) { recordWorn(entry); }
/* Build .36: the hero's verdict buttons are icons now; their
   filled state is aria-pressed, synced from the look's verdict —
   the same state the pop-out's verdict buttons show. Presentation
   only: the verdict itself is still set by likeLook / the dislike
   path, exactly as before. */
function syncTodayVerdict() {
  var v = (typeof todayLook !== "undefined" && todayLook) ? todayLook.verdict : null;
  var like = document.getElementById("today-like");
  var dislike = document.getElementById("today-dislike");
  if (like) like.setAttribute("aria-pressed", v === "like" ? "true" : "false");
  if (dislike) dislike.setAttribute("aria-pressed", v === "dislike" ? "true" : "false");
}
/* Build .38 (2.8): un-liking reverses a like completely — the
   verdict clears (so the look is eligible again at once) and the
   queued copy the like added comes back out. The saved copy
   itself stays in My Looks, verdict-neutral, as the dislike-undo
   precedent keeps entries. */
function unlikeLookById(id) {
  if (!id) return;
  savedLooks.forEach(function (l) {
    if (l.id === id && l.verdict === "like") { l.verdict = null; l.likedAt = null; }
  });
  queueLooks = queueLooks.filter(function (x) { return x.id !== id; });
  saveQueue();
  persistAll();
  renderSaved();
}
function likeToday() {
  if (!todayLook) return;
  /* Most recently liked sits FIRST in My Looks, in the Queued
     state — the shared likeLook path. */
  var likedId = todayLook.id;
  var savedOk56 = likeLook(todayLook);
  syncTodayVerdict();
  if (!savedOk56) {
    /* Build .56: no false "saved" toast — the save was refused
       because this photograph is on the not-for-me list (its twin
       file form was dealt before the dealers went canonical).
       The hero's like state is rolled back to match. */
    todayLook.verdict = null; todayLook.likedAt = null; syncTodayVerdict();
    toast("That photo is on your not-for-me list — not saved.");
    return;
  }
  /* Build .38 (2.8): the like toast carries Undo — one tap
     restores the look to the rotation immediately. */
  showUndoToast("Liked — saved to " + savedHomeName(todayLook) + "; it sits out for 14 days.", function () {
    unlikeLookById(likedId);
    if (todayLook && todayLook.id === likedId) { todayLook.verdict = null; todayLook.likedAt = null; syncTodayVerdict(); }
    toast("Undone — that outfit is back in the rotation.");
  });
}
function woreToday() {
  if (!todayLook) return;
  var today = localTodayISO();
  /* The hero outfit is logged as worn, right here — one tap, no
     form, no photo required. (The selfie log on What I'm Wearing
     Today is the separate photo path.) */
  if (!savedLooks.some(function (l) { return l.id === todayLook.id; })) {
    savedLooks.unshift(JSON.parse(JSON.stringify(todayLook)));
  }
  /* Wear credit comes ONLY from the look's real piece mapping
     (mappedClosetPieces: fwPieces ids + the swap map's closet
     pieces). The old anchor-name match and palette colour-hex
     fallback credited garments that were never in the outfit —
     a navy suit logged a wear for the Cream Cricket Sweater.
     Nothing mapped → the entry records pieces: [] and no
     garment's wearCount/lastWorn/laundry changes. */
  var mappedWorn = mappedClosetPieces(todayLook);
  var wornIds = mappedWorn.map(function (m) { return m.id; });
  var wornNames = mappedWorn.map(function (m) { return m.name; });
  /* The watch on the hero — his choice if he made one, the
     recommendation otherwise — is the watch recorded as worn. */
  var wres = (typeof resolveWatch === "function") ? resolveWatch(todayLook) : { state: "none" };
  var wornEntry = { date: today, title: todayLook.title, img: lookImg(todayLook), pieces: wornNames, pieceIds: wornIds, lookId: todayLook.id };
  if (wres.state === "watch" && wres.watch) { wornEntry.watch = wres.watch.name; wornEntry.watchId = wres.watch.id; }
  var entry = recordWorn(wornEntry);
  queueLooks = queueLooks.filter(function (x) { return x.id !== todayLook.id; });
  saveQueue();
  persistAll();
  renderSaved();
  renderWardrobe();
  renderWornLog();
  toast(entry ? "Worn today — logged" + (wornNames.length ? ": " + wornNames.join(", ") : "") + "." : "Already logged as worn today.");
}
(function todayControls() {
  var like = document.getElementById("today-like");
  if (like) like.addEventListener("click", likeToday);
  /* Build .36: the hero has no "Wore this today" button — worn-
     marking stays available in Calendar/planner and the pop-out. */
  var hero = document.getElementById("today-hero");
  if (hero) {
    var sx = null, sy = null;
    hero.addEventListener("touchstart", function (e) {
      if (e.touches.length !== 1) { sx = null; return; }
      sx = e.touches[0].clientX; sy = e.touches[0].clientY;
    }, { passive: true });
    hero.addEventListener("touchend", function (e) {
      if (sx === null || !e.changedTouches.length) return;
      var dx = e.changedTouches[0].clientX - sx;
      var dy = e.changedTouches[0].clientY - sy;
      sx = null;
      if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.4) return;
      if (dx < 0) { dealAnotherToday(); }
      /* Build .56 (amendment): swipe right goes BACK to the look
         dealt before this one — for the verdict the user meant
         to give it. Like keeps its button. At the bottom of the
         stack the gesture does nothing. */
      else if (typeof heroGoBack56 === "function") { heroGoBack56(); }
    }, { passive: true });
  }
  /* Build .56 (amendment): the same swipe-right go-back on the
     Ideas deal surface — back to the previous six dealt. */
  var lrEl = document.getElementById("look-result");
  if (lrEl) {
    var lx = null, ly = null;
    lrEl.addEventListener("touchstart", function (e) {
      if (e.touches.length !== 1) { lx = null; return; }
      lx = e.touches[0].clientX; ly = e.touches[0].clientY;
    }, { passive: true });
    lrEl.addEventListener("touchend", function (e) {
      if (lx === null || !e.changedTouches.length) return;
      var dx2 = e.changedTouches[0].clientX - lx;
      var dy2 = e.changedTouches[0].clientY - ly;
      lx = null;
      if (dx2 < 60 || Math.abs(dx2) < Math.abs(dy2) * 1.4) return;
      if (typeof ideasGoBack56 === "function") ideasGoBack56();
    }, { passive: true });
  }
  /* Outfit type in the old Location slot: the pills carry
     data-studio-type, so syncStudioType (hooked into
     renderFormality) keeps their pressed state on the ONE
     app-wide formality value; a pick sets that value and
     re-deals Today at it, strictly. */
  var typeRow = document.getElementById("today-type-row");
  if (typeRow) {
    typeRow.addEventListener("click", function (e) {
      var b = e.target.closest("[data-studio-type]");
      if (!b) return;
      var v = parseInt(b.getAttribute("data-studio-type"), 10);
      var changed = v !== formalityLevel;
      setFormality(v);
      if (changed) dealAnotherToday();
    });
  }
})();

/* ---------- Worn log (22) ---------- */
/* Build .38 (2.4): ONE merge for the two worn sources, shared by
   both readers. A wear lives in the log AND as a worn flag on
   the saved look (recordWorn writes both); merged naively, one
   wear counts twice. A log entry registers under BOTH its
   lookId|date key and its date|title key, duplicate log entries
   for the same look + date collapse to the first, and a saved
   look's synthetic entry is dropped when EITHER of its keys is
   already registered — the old code cross-checked only the
   lookId key, so a log entry with a missing or mismatched
   lookId let the same wear through twice. iso = one date, or
   null for every date. */
function mergedWornEntries(iso) {
  var entries = [], seen = {}, lookWorn = {};
  wornLog.forEach(function (en) {
    if (!en || !en.date) return;
    if (iso && en.date !== iso) return;
    if (en.lookId) {
      var lk = "L|" + en.lookId + "|" + en.date;
      if (lookWorn[lk]) return;
      lookWorn[lk] = 1;
    }
    /* An entry for the same date + title + photograph as one
       already kept is the same wear written twice (the log's
       second pen — e.g. an import beside the recorded entry,
       in either order) — it collapses too. A different
       photograph never collapses: two looks can share a title,
       they cannot share a photo and be two wears of it on
       one day. */
    var ti = "TI|" + en.date + "|" + en.title + "|" + (en.img || "");
    if (seen[ti]) return;
    seen[ti] = 1;
    var k = en.id ? "id:" + en.id : "T|" + en.date + "|" + en.title;
    if (seen[k]) return;
    seen[k] = 1;
    seen["T|" + en.date + "|" + en.title] = 1;
    entries.push(en);
  });
  savedLooks.forEach(function (l) {
    if (!l.worn || !l.wornDate) return;
    if (iso && l.wornDate !== iso) return;
    if (lookWorn["L|" + l.id + "|" + l.wornDate]) return;
    if (seen["TI|" + l.wornDate + "|" + l.title + "|" + lookImg(l)]) return;
    var k = "T|" + l.wornDate + "|" + l.title;
    if (seen[k]) return;
    seen[k] = 1;
    entries.push({ date: l.wornDate, title: l.title, img: lookImg(l), pieces: [], lookId: l.id, synthetic: true });
  });
  return entries;
}
function renderWornLog() {
  var list = document.getElementById("worn-log-list");
  if (!list) return;
  var entries = mergedWornEntries(null);
  entries.sort(function (a, b) { return a.date < b.date ? 1 : -1; });
  if (!entries.length) {
    list.innerHTML = '<p class="meta">Nothing worn yet.</p>';
    return;
  }
  /* Grouped by EXACT DATE (build .28) \u2014 "Monday \u00b7 Nov 16" \u2014
     newest date first, today included as the newest date; each
     outfit a compact row with a small thumbnail (a pieces-only
     entry gets a small placeholder block). This list lives in
     Calendar only \u2014 the Wearing Today page is the form alone.
     Build .35: tapping a row opens its edit sheet. */
  var html = "", lastDay = "";
  entries.forEach(function (en) {
    var dk = en.date || "";
    if (dk && dk !== lastDay) {
      lastDay = dk;
      var dd = new Date(dk + "T12:00:00");
      var head = isNaN(dd.getTime()) ? esc(dk) : dd.toLocaleDateString(undefined, { weekday: "long" }) + " \u00b7 " + dd.toLocaleDateString(undefined, { month: "short", day: "numeric" });
      html += '<p class="worn-date-head">' + head + "</p>";
    }
    var label = (en.pieces && en.pieces.length) ? en.pieces.join(", ") : (en.title || "Outfit");
    var subParts = [];
    if (en.pieces && en.pieces.length && en.title) subParts.push(en.title);
    if (en.watch) subParts.push("Watch: " + en.watch);
    var attrs = "";
    if (en.id) attrs = ' data-worn-edit="' + esc(en.id) + '" role="button" tabindex="0"';
    else if (en.synthetic && en.lookId) attrs = ' data-worn-look="' + esc(en.lookId) + '" data-worn-date="' + esc(en.date || "") + '" role="button" tabindex="0"';
    html += '<div class="worn-row compact' + (en.selfie ? " selfie" : "") + '"' + attrs + '>' + (en.img ? '<img src="' + en.img + '" alt="" loading="lazy" data-popout="' + en.img + '" />' : '<span class="worn-thumb-ph" aria-hidden="true"></span>') +
      '<span class="w-main"><span class="w-name">' + esc(label) + '</span>' +
      (subParts.length ? '<span class="w-sub">' + esc(subParts.join(" \u00b7 ")) + "</span>" : "") + "</span></div>";
  });
  list.innerHTML = html;
}

/* ---------- Edit a What I wore entry (build .35) ----------
   Tapping a row in Calendar's What I wore opens this sheet:
   date, title and pieces are prefilled from the log entry, and
   saving writes the SAME entry back through store.set("wornLog")
   \u2014 the normal sync path \u2014 so an entry is corrected in
   place, never duplicated. Removing the entry un-marks a linked
   look, mirroring toggleWorn. */
var wornEditId = null;
function wornEntryById(id) {
  return wornLog.filter(function (en) { return en.id === id; })[0] || null;
}
function wornPieceMatch(name, det) {
  var match = null;
  wardrobeItems.forEach(function (i) {
    if (!match && i.name === name && (!det || !det.category || i.category === det.category)) match = i;
  });
  if (!match) wardrobeItems.forEach(function (i) { if (!match && i.name === name) match = i; });
  return match;
}
function openWornEdit(id) {
  var en = wornEntryById(id);
  if (!en) return;
  wornEditId = id;
  document.getElementById("worn-edit-date").value = en.date || "";
  document.getElementById("worn-edit-name").value = en.title || "";
  var pieces = (en.pieces && en.pieces.length) ? en.pieces : [];
  var box = document.getElementById("worn-edit-rows");
  box.innerHTML = pieces.length ? pieces.map(function (name, ix) {
    var det = (en.pieceDetails && en.pieceDetails[ix]) || {};
    var match = wornPieceMatch(name, det);
    return wearingRowHTML(match ? match.category : (det.category || "Shirts"));
  }).join("") : wearingRowHTML("Shirts");
  Array.prototype.slice.call(box.querySelectorAll(".wearing-row")).forEach(function (row, ix) {
    var name = pieces[ix] || "";
    if (!name) return;
    var det = (en.pieceDetails && en.pieceDetails[ix]) || {};
    var match = wornPieceMatch(name, det);
    if (match) row.querySelector(".wr-pick").value = match.id;
    syncWearingRow(row);
    if (!match) row.querySelector(".wr-name").value = name;
  });
  showBuildSheet("worn-edit-sheet");
}
function closeWornEdit() {
  wornEditId = null;
  hideBuildSheet("worn-edit-sheet");
}
function saveWornEdit() {
  var en = wornEntryById(wornEditId);
  if (!en) return;
  var date = document.getElementById("worn-edit-date").value || en.date;
  var title = document.getElementById("worn-edit-name").value.trim();
  var pieces = [], details = [];
  Array.prototype.slice.call(document.querySelectorAll("#worn-edit-rows .wearing-row")).forEach(function (row) {
    var pickId = row.querySelector(".wr-pick").value;
    if (pickId) {
      var it = closetItemById(pickId);
      if (it) { pieces.push(it.name); details.push({ name: it.name, category: it.category }); }
      return;
    }
    var name = row.querySelector(".wr-name").value.trim();
    if (!name) return;
    pieces.push(name);
    details.push({ name: name, category: row.querySelector(".wr-cat").value });
  });
  var oldDate = en.date;
  en.date = date;
  if (title) en.title = title;
  en.pieces = pieces;
  en.pieceDetails = details;
  store.set("wornLog", wornLog);
  if (en.lookId && oldDate !== date) {
    var sv = savedLooks.filter(function (l) { return l.id === en.lookId; })[0];
    if (sv && sv.worn) { sv.wornDate = date; persistAll(); }
  }
  closeWornEdit();
  renderWornLog();
  if (typeof renderWeekPlan === "function") renderWeekPlan();
  toast("Worn entry updated.");
}
function removeWornEdit() {
  var en = wornEntryById(wornEditId);
  if (!en) return;
  wornLog = wornLog.filter(function (x) { return x.id !== en.id; });
  store.set("wornLog", wornLog);
  rollbackWornCredits([en]); /* build .38 (2.5): un-marking rolls the piece credits back too */
  if (en.lookId) {
    var sv = savedLooks.filter(function (l) { return l.id === en.lookId; })[0];
    if (sv && sv.worn) { sv.worn = false; sv.wornDate = null; persistAll(); }
  }
  closeWornEdit();
  renderWornLog();
  if (typeof renderWeekPlan === "function") renderWeekPlan();
  if (typeof renderSaved === "function") renderSaved();
  toast("Worn entry removed.");
}
var wornLogListEl = document.getElementById("worn-log-list");
if (wornLogListEl) wornLogListEl.addEventListener("click", function (e) {
  if (e.target.closest && e.target.closest("[data-popout]")) return;
  var row = e.target.closest ? (e.target.closest("[data-worn-edit]") || e.target.closest("[data-worn-look]")) : null;
  if (!row) return;
  var editId = row.getAttribute("data-worn-edit");
  if (editId) { openWornEdit(editId); return; }
  var lookId = row.getAttribute("data-worn-look");
  var date = row.getAttribute("data-worn-date");
  var look = savedLooks.filter(function (l) { return l.id === lookId; })[0];
  if (!look) return;
  /* A worn look with no log entry of its own gets one through the
     normal recordWorn path (deduped by look + date), then edits. */
  var made = recordWorn({ date: date || look.wornDate, title: look.title, img: lookImg(look), pieces: [], lookId: lookId });
  var en = made || wornLog.filter(function (x) { return x.lookId === lookId && x.date === (date || look.wornDate); })[0];
  if (en) { renderWornLog(); openWornEdit(en.id); }
});
var wornEditRowsEl = document.getElementById("worn-edit-rows");
if (wornEditRowsEl) {
  wornEditRowsEl.addEventListener("change", function (e) {
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
  wornEditRowsEl.addEventListener("input", function (e) {
    if (!e.target.classList.contains("wr-search")) return;
    var row = e.target.closest ? e.target.closest(".wearing-row") : null;
    if (row) refreshRowPick(row);
  });
  wornEditRowsEl.addEventListener("click", function (e) {
    var rm = e.target.closest ? e.target.closest(".wr-remove") : null;
    if (!rm) return;
    var row = rm.closest(".wearing-row");
    if (row) row.remove();
  });
}
var wornEditCloseEl = document.getElementById("worn-edit-close");
if (wornEditCloseEl) wornEditCloseEl.addEventListener("click", closeWornEdit);
var wornEditSaveEl = document.getElementById("worn-edit-save");
if (wornEditSaveEl) wornEditSaveEl.addEventListener("click", saveWornEdit);
var wornEditRemoveEl = document.getElementById("worn-edit-remove");
if (wornEditRemoveEl) wornEditRemoveEl.addEventListener("click", removeWornEdit);
var wornEditAddEl = document.getElementById("worn-edit-add-row");
if (wornEditAddEl) wornEditAddEl.addEventListener("click", function () {
  wornEditRowsEl.insertAdjacentHTML("beforeend", wearingRowHTML("Shirts"));
});

/* ---------- Wishlist — missing pieces, aggregated (25) ---------- */
var lastWishlist = [];
function renderWishlist() {
  var list = document.getElementById("wishlist-list");
  if (!list) return;
  var agg = {}, order = [];
  function consider(look) {
    if (!look) return;
    lookPieces(look).forEach(function (pc) {
      var cat = garmentCategory(pc.garment);
      var owned = wardrobeItems.some(function (it) {
        if (it.category !== cat) return false;
        if (pc.hex && it.colourHex && dist2(hexRgb(it.colourHex), hexRgb(pc.hex)) < 3200) return true;
        return (it.name || "").toLowerCase().indexOf(pc.garment.toLowerCase().split(" ").pop()) !== -1;
      });
      if (owned) return;
      var key = (cat + "|" + (pc.colourName || "") + "|" + pc.garment).toLowerCase();
      if (!agg[key]) { agg[key] = { desc: pieceDescription(pc), cat: cat, hex: pc.hex, colour: pc.colourName || "", count: 0, titles: [] }; order.push(key); }
      agg[key].count++;
      if (agg[key].titles.indexOf(look.title) === -1) agg[key].titles.push(look.title);
    });
  }
  savedLooks.forEach(consider);
  SEED_LOOKS.forEach(consider);
  queueLooks.forEach(consider);
  (currentOptions || []).forEach(consider);
  lastWishlist = order.map(function (k) { return agg[k]; }).sort(function (a, b) { return b.count - a.count; }).slice(0, 12);
  if (!lastWishlist.length) {
    list.innerHTML = '<p class="meta">Nothing missing.</p>';
    renderGapList();
    return;
  }
  list.innerHTML = lastWishlist.map(function (w, i) {
    return '<div class="wish-row"><span class="cdot" style="background:' + (w.hex || "transparent") + '"></span>' +
      '<span class="w-main"><span class="w-name">' + esc(w.desc) + '</span>' +
      '<span class="w-sub">' + esc(w.cat) + " · needed by " + w.count + (w.count === 1 ? " look: " : " looks: ") + esc(w.titles.slice(0, 2).join(", ")) + "</span></span>" +
      '<button type="button" class="btn-ghost" data-wish-find="' + i + '">Shop the look</button></div>';
  }).join("");
  renderGapList();
}
/* The same missing-pieces ranking, kept quietly at the foot of
   the Closet: each gap row leads into Shop the look for that
   piece (the shared data-wish-find path). Ranked by how many
   outfits the piece would complete. */
function renderGapList() {
  var wrap = document.getElementById("gap-wrap");
  var list = document.getElementById("gap-list");
  if (!wrap || !list) return;
  var ce = document.getElementById("closet-gaps-count");
  if (ce) ce.textContent = lastWishlist.length ? "(" + Math.min(8, lastWishlist.length) + ")" : "";
  if (!lastWishlist.length) { wrap.hidden = false; list.innerHTML = '<p class="meta">Nothing missing.</p>'; return; }
  wrap.hidden = false;
  list.innerHTML = lastWishlist.slice(0, 8).map(function (w, i) {
    return '<div class="wish-row"><span class="cdot" style="background:' + (w.hex || "transparent") + '"></span>' +
      '<span class="w-main"><span class="w-name">' + esc(w.desc) + '</span>' +
      '<span class="w-sub">' + esc(w.cat) + " · completes " + w.count + (w.count === 1 ? " outfit" : " outfits") + "</span></span>" +
      '<button type="button" class="btn-ghost" data-wish-find="' + i + '">Shop the look</button></div>';
  }).join("");
}
document.addEventListener("click", function (e) {
  var b = e.target.closest("[data-wish-find]");
  if (!b) return;
  var w = lastWishlist[parseInt(b.getAttribute("data-wish-find"), 10)];
  if (!w) return;
  /* The gap-shopping surface is the Search tab's form now
     (build .28): the same handoff data prefills it — the piece
     as the description, its category, its colour, and the
     needed-by note as the details — and Add & search creates
     the brief there, in the size from the Profile. */
  var descEl = document.getElementById("find-desc");
  if (descEl) descEl.value = w.desc;
  var catEl = document.getElementById("find-cat");
  if (catEl) catEl.value = w.cat;
  if (typeof buildFindCatOpts === "function") buildFindCatOpts();
  if (typeof syncFindSize === "function") syncFindSize();
  var colEl = document.getElementById("find-colour");
  if (colEl) colEl.value = w.colour || "";
  var detEl = document.getElementById("find-details");
  if (detEl) detEl.value = "From the wishlist — needed by: " + w.titles.join(", ");
  var iconEl = document.getElementById("find-icon");
  if (iconEl) iconEl.value = "";
  if (typeof finds !== "undefined") {
    finds.unshift({
      id: "find-" + Date.now(),
      desc: w.desc,
      cat: w.cat,
      size: (typeof profileSizeFor === "function") ? profileSizeFor(w.cat) : "",
      budget: "", budgetTier: (typeof shopTierName === "function") ? shopTierName() : "",
      budgetNote: "", colour: w.colour || "",
      details: "From closet gaps — needed by: " + (w.titles || []).join(", "),
      iconId: null
    });
    if (typeof store !== "undefined") store.set("finds", finds);
  }
  if (typeof switchTab === "function") switchTab("find");
  if (typeof renderTheEdit === "function") renderTheEdit();
  toast("On the hunt — " + w.desc + ".");
});

/* ---------- Trip capsules (23) ---------- */
var TRIPS = {
  marbella: { name: "Marbella", dates: "Jun 21 – Jul 5, 2027 · 14 nights", temp: 86, nightTemp: 78, days: 14, slots: ["Day", "Pool", "Night"],
    weather: "Seasonal weather basis: Marbella in late June and early July is hot — roughly 80–90°F and sunny. Outfits are built light from your closet: polos, tees and linen up top, open or light shoes below.",
    essentials: ["Swim trunks", "Sunscreen", "Sunglasses", "Passport", "A light layer for evenings", "Charger"],
    note: "Marbella in late June: heat at midday, warm evenings. Light tailoring, linen, swim pieces and one smart layer for dinner — the outfits above are built from your closet and mix across the fortnight." },
  aspen: { name: "Aspen", dates: "Mar 12 – 26, 2027 · 14 nights", temp: 30, nightTemp: 24, days: 14, slots: ["Day", "Après"],
    weather: "Seasonal weather basis: Aspen in March is ski cold — roughly 20–40°F with snow possible. Outfits are built for cold from your closet: knits and layers up top, closed shoes below.",
    essentials: ["Ski jacket & pants", "Base layers", "Ski socks", "Sunscreen — altitude sun", "Lip balm", "Passport / ID", "Charger"],
    note: "Aspen: cold air, bright sun, dinners that dress up. Layers first — knits under blazers, a real coat, closed shoes — the outfits above are built from your closet." }
};
/* ---------- Build .39: Trips as synced objects + packed state ----------
   Trip records live in the synced "trips" collection (store key
   "trips"); the two built-in capsules seed as records on first
   run, carrying their full capsule definitions, so nothing about
   Marbella or Aspen is lost and every trip — seeded or created —
   is the same kind of object. Packing state is the synced
   "packed" collection (store key "packedItems", one record per
   ticked item), migrated once from the old capsulePacked map,
   which is still written as a mirror for backups and old builds. */
var TRIP_SEEDS = [
  { id: "trip-marbella", key: "marbella", name: "Marbella", start: "2027-06-21", end: "2027-07-05", legs: ["Marbella"], days: 14, slots: ["Day", "Pool", "Night"], temp: 86, nightTemp: 78, dates: "Jun 21 – Jul 5, 2027 · 14 nights", weather: TRIPS.marbella.weather, essentials: TRIPS.marbella.essentials.slice(), note: TRIPS.marbella.note },
  { id: "trip-aspen", key: "aspen", name: "Aspen", start: "2027-03-12", end: "2027-03-26", legs: ["Aspen"], days: 14, slots: ["Day", "Après"], temp: 30, nightTemp: 24, dates: "Mar 12 – 26, 2027 · 14 nights", weather: TRIPS.aspen.weather, essentials: TRIPS.aspen.essentials.slice(), note: TRIPS.aspen.note }
];
var userTrips = store.get("trips", []);
if (!Array.isArray(userTrips)) userTrips = [];
(function () {
  var changed = false;
  TRIP_SEEDS.forEach(function (s) {
    if (!userTrips.some(function (t) { return t && t.id === s.id; })) { userTrips.push(s); changed = true; }
  });
  if (changed) store.set("trips", userTrips);
})();
function saveUserTrips() { store.set("trips", userTrips); }
function tripDef(key) {
  var t = userTrips.filter(function (x) { return x && (x.key === key || x.id === key); })[0];
  return t || TRIPS[key] || null;
}
function allTripKeys() {
  var ks = [];
  userTrips.forEach(function (t) { if (t && (t.key || t.id)) ks.push(t.key || t.id); });
  Object.keys(TRIPS).forEach(function (k) { if (ks.indexOf(k) === -1) ks.push(k); });
  return ks;
}
var packedItems = store.get("packedItems", null);
if (!Array.isArray(packedItems)) {
  packedItems = [];
  var legacyPacked = store.get("capsulePacked", {}) || {};
  Object.keys(legacyPacked).forEach(function (k) {
    Object.keys(legacyPacked[k] || {}).forEach(function (label) {
      if (legacyPacked[k][label]) packedItems.push({ id: k + "|" + label, trip: k, label: label });
    });
  });
  store.set("packedItems", packedItems);
}
function savePacked() {
  store.set("packedItems", packedItems);
  var obj = {};
  packedItems.forEach(function (p) { if (!obj[p.trip]) obj[p.trip] = {}; obj[p.trip][p.label] = true; });
  store.set("capsulePacked", obj);
}
function packIsOn(key, label) { return packedItems.some(function (p) { return p.trip === key && p.label === label; }); }
function packToggle(key, label) {
  var ix = -1;
  packedItems.forEach(function (p, i) { if (p.trip === key && p.label === label) ix = i; });
  if (ix >= 0) packedItems.splice(ix, 1); else packedItems.push({ id: key + "|" + label, trip: key, label: label });
  savePacked();
}
var currentCapsule = null;
var capsuleLooks = [];
var fwLooksBackup = null;
/* The Pool slot's outfit, from the closet's own swim pieces —
   paired with a light top and open shoes when they're there. */
function capsulePoolLook(d) {
  var swim = wardrobeItems.filter(function (i) { return i.category === "Bathing suits" && i.photo; });
  if (!swim.length) return null;
  var s = swim[d % swim.length];
  var top = wardrobeItems.filter(function (i) { return (i.category === "Tees" || i.category === "Shirts") && i.photo && i.id !== s.id; })[0] || null;
  var pieces = [s]; if (top) pieces.push(top);
  return { fwPieces: pieces, swatches: [], suggestedBottom: null, fwRender: null,
    title: s.name + (top ? " × " + top.name : ""),
    imgAlt: pieces.map(function (p) { return p.name; }).join(" with ") };
}
function capsuleOutfitHTML(look, gi) {
  var pieces = look.fwPieces || [];
  var shoe = null;
  pieces.forEach(function (p) { if (p.category === "Shoes") shoe = p; });
  var shown = [pieces[0], shoe].filter(function (p, ix, a) { return p && p.photo && a.indexOf(p) === ix; });
  /* The verified render of him wearing it leads when the pairing
     has one — the same picture From wardrobe shows — and the
     whole card taps through to the outfit view. */
  var photos = look.fwRender
    ? '<span class="fw-render"><img src="' + fwRenderSrc(look) + '" alt="' + esc(look.title || "") + '" loading="lazy" decoding="async" /></span>'
    : (shown.length ? '<span class="fw-photos' + (shown.length === 1 ? " one" : "") + '">' + shown.map(function (p) { return '<img src="' + p.photo + '" alt="' + esc(p.name) + '" loading="lazy" decoding="async" />'; }).join("") + "</span>" : "");
  var names = pieces.map(function (p) { return p.name; }).join(" · ");
  return '<button type="button" class="capsule-outfit" data-capsule-look="' + gi + '">' + photos + '<span class="oc-title">' + esc(look.title) + "</span>" +
    (names ? '<span class="oc-meta">' + esc(names) + "</span>" : "") +
    (look.suggestedBottom ? '<span class="oc-meta">Pair with: ' + esc(look.suggestedBottom.name) + " — suggested</span>" : "") + "</button>";
}
function buildCapsule(key) {
  var trip = tripDef(key);
  var out = document.getElementById("capsule-out");
  if (!trip || !out) return;
  currentCapsule = key;
  /* Outfits from his closet, organized BY DAY: each day carries
     its slots (Day / Pool / Night on a beach trip; Day / Après
     in the cold), each slot built from his closet pieces at the
     slot's temperature — the same closet engine as Today. */
  var days = trip.days || 14;
  var daySet = (typeof buildClosetLooks === "function") ? buildClosetLooks({ temp: trip.temp, rainy: false, salt: 0 }) : null;
  var nightSet = (typeof buildClosetLooks === "function") ? buildClosetLooks({ temp: (trip.nightTemp != null ? trip.nightTemp : trip.temp), rainy: false, salt: 77 }) : null;
  var outfits = [];
  capsuleLooks = outfits;
  var html = '<article class="card custom-card"><h4>' + trip.name + ' capsule</h4><p class="meta">' + trip.dates + "</p>";
  html += '<p class="capsule-note">' + trip.weather + "</p>";
  if (!daySet || !daySet.length) {
    html += '<p class="capsule-note">Your closet has no pieces to build outfits from yet — add pieces in the Closet and the capsule builds itself from them.</p>';
  } else {
    var hasSwim = wardrobeItems.some(function (i) { return i.category === "Bathing suits" && i.photo; });
    for (var d = 0; d < days; d++) {
      html += '<div class="capsule-day"><h5 class="capsule-day-head">Day ' + (d + 1) + '</h5><div class="capsule-outfits">';
      trip.slots.forEach(function (slot) {
        var look = null;
        if (slot === "Pool") {
          look = capsulePoolLook(d);
        } else {
          var set = (slot === "Day") ? daySet : nightSet;
          if (set && set.length) look = set[(d + (slot === "Day" ? 0 : Math.floor(days / 2))) % set.length];
        }
        if (look) {
          var gi = outfits.length; outfits.push(look);
          html += '<div class="capsule-slot"><span class="capsule-slot-label">' + slot + "</span>" + capsuleOutfitHTML(look, gi) + "</div>";
        } else if (slot === "Pool" && !hasSwim) {
          html += '<div class="capsule-slot"><span class="capsule-slot-label">Pool</span><p class="capsule-note">No swim piece in your closet yet — swim trunks are on the essentials list below.</p></div>';
        }
      });
      html += "</div></div>";
    }
  }
  /* Packing checklist: the capsule outfits' own pieces first
     (suggested bottoms named as suggestions), then the trip
     essentials. Tap an item to check it off — the state is kept
     on this device with the rest of the app. */
  var checkItems = [], seenLabel = {};
  outfits.forEach(function (look) {
    (look.fwPieces || []).forEach(function (p) {
      if (seenLabel[p.name]) return;
      seenLabel[p.name] = 1;
      checkItems.push({ cat: p.category, label: p.name });
    });
    if (look.suggestedBottom && !seenLabel[look.suggestedBottom.name]) {
      seenLabel[look.suggestedBottom.name] = 1;
      checkItems.push({ cat: "Suggested", label: look.suggestedBottom.name + " — suggested" });
    }
  });
  trip.essentials.forEach(function (label) {
    if (seenLabel[label]) return;
    seenLabel[label] = 1;
    checkItems.push({ cat: "Essential", label: label });
  });
  if (checkItems.length) {
    html += '<h5 class="capsule-check-head">Packing checklist</h5><ul class="pack-list">' + checkItems.map(function (ci) {
      var on = packIsOn(key, ci.label);
      return '<li><button type="button" class="pack-item" data-pack="' + esc(ci.label) + '" aria-pressed="' + (on ? "true" : "false") + '"><span class="pk-box" aria-hidden="true">' + (on ? "✓" : "") + '</span><span class="pk-cat">' + esc(ci.cat) + "</span><span>" + esc(ci.label) + "</span></button></li>";
    }).join("") + "</ul>";
  }
  /* Gaps for this trip: shoppable essentials the closet does not
     cover, routed to Shop through the same Search-brief handoff
     the Closet gaps use. Documents/consumables are not gaps. */
  var nonShopGap = { "Passport": 1, "Passport / ID": 1, "Charger": 1, "Sunscreen": 1, "Sunscreen — altitude sun": 1, "Lip balm": 1 };
  var gapLabels = [];
  (trip.essentials || []).forEach(function (label) {
    if (nonShopGap[label] || gapLabels.indexOf(label) !== -1) return;
    var owned = wardrobeItems.some(function (it) {
      var nm = (it.name || "").toLowerCase(), ct = (it.category || "").toLowerCase();
      return nm.indexOf(label.toLowerCase()) !== -1 || (ct.length > 3 && label.toLowerCase().indexOf(ct) !== -1);
    });
    if (!owned) gapLabels.push(label);
  });
  if (trip.slots && trip.slots.indexOf("Pool") !== -1 && !hasSwim && gapLabels.indexOf("Swim trunks") === -1) gapLabels.push("Swim trunks");
  if (gapLabels.length) {
    html += '<h5 class="capsule-check-head">Gaps for this trip</h5>' + gapLabels.map(function (label) {
      return '<div class="wish-row"><span class="w-main"><span class="w-name">' + esc(label) + '</span><span class="w-sub">Not in your closet</span></span><button type="button" class="btn-ghost" data-trip-gap="' + esc(label) + '">Shop the look</button></div>';
    }).join("");
  }
  html += '<p class="capsule-note">' + trip.note + "</p></article>";
  out.innerHTML = html;
}
document.getElementById("trips-wrap").addEventListener("click", function (e) {
  var pk = e.target.closest("[data-pack]");
  if (pk && currentCapsule) {
    packToggle(currentCapsule, pk.getAttribute("data-pack"));
    buildCapsule(currentCapsule);
    return;
  }
  var tg = e.target.closest("[data-trip-gap]");
  if (tg) {
    var glabel = tg.getAttribute("data-trip-gap");
    var gdesc = document.getElementById("find-desc"); if (gdesc) gdesc.value = glabel;
    var gcat = document.getElementById("find-cat"); if (gcat) { try { gcat.value = glabel === "Swim trunks" ? "Bathing suits" : ""; } catch (err) {} }
    if (typeof buildFindCatOpts === "function") buildFindCatOpts();
    if (typeof syncFindSize === "function") syncFindSize();
    var gdet = document.getElementById("find-details"); if (gdet) gdet.value = "Trip gap — " + ((tripDef(currentCapsule) || {}).name || "trip");
    var gicon = document.getElementById("find-icon"); if (gicon) gicon.value = "";
    switchTab("search");
    toast("On the hunt — " + glabel + ".");
    return;
  }
  var to = e.target.closest("[data-trip-open]");
  if (to) { calOpenTrip(to.getAttribute("data-trip-open")); return; }
  var b = e.target.closest("[data-trip]");
  if (b) buildCapsule(b.getAttribute("data-trip"));
  var co = e.target.closest("[data-capsule-look]");
  if (co) {
    /* A capsule outfit opens the same outfit view From wardrobe
       uses — render, pieces, Like / Save / Shop the look. The
       dealt FW array is restored when the view closes. */
    var oi = parseInt(co.getAttribute("data-capsule-look"), 10);
    if (capsuleLooks[oi]) {
      if (!fwLooksBackup) fwLooksBackup = fwLooks;
      fwLooks = capsuleLooks;
      openFwOutfit(oi);
    }
  }
});

/* ---------- Build .39: Calendar sub-pages + Trips UI ----------
   This week / Trips / What I wore are sub-views inside the
   Calendar page. Moving between them — and into a trip — pushes
   onto the universal back stack (calNavStack), so the small
   top-margin chevron walks back out exactly the way it walks
   between pages. */
var calView = "week";
function calViewApply() {
  var wk = document.getElementById("week-plan-wrap"), tr = document.getElementById("trips-wrap"), wn = document.getElementById("worn-wrap");
  if (!wk || !tr || !wn) return;
  if (calView === "worn") calView = "week"; /* build .75: worn log removed */
  wk.hidden = calView !== "week";
  tr.hidden = calView !== "trips";
  wn.hidden = calView !== "worn";
  document.querySelectorAll("[data-calview]").forEach(function (b) {
    b.setAttribute("aria-pressed", b.getAttribute("data-calview") === calView ? "true" : "false");
  });
  if (calView === "week" && typeof renderWeekPlan === "function") renderWeekPlan();
  if (calView === "worn" && typeof renderWornLog === "function") renderWornLog();
  if (calView === "trips") renderTripList();
}
function calNavPush() {
  calNavStack.push({ view: calView, trip: currentCapsule });
  viewHist.push(viewCur);
  viewCur = "calnav";
  syncViewBack();
}
function calNavRestore() {
  var st = calNavStack.pop();
  viewHist.pop();
  if (st) {
    if (st.trip) { calView = "trips"; calShowTrip(st.trip); }
    else if (st.view === "trips") { currentCapsule = null; calView = "trips"; calShowList(); }
    else calView = st.view;
    calViewApply();
  }
  viewCur = calNavStack.length ? "calnav" : "calendar";
  syncViewBack();
}
function calNavReset() {
  calNavStack.length = 0;
  if (viewCur === "calnav") viewCur = "calendar";
}
function calShowList() {
  var list = document.getElementById("trip-list"), det = document.getElementById("trip-detail"), form = document.getElementById("trip-form");
  if (list) list.hidden = false;
  if (form) form.hidden = false;
  if (det) { det.hidden = true; var co = document.getElementById("capsule-out"); if (co) co.innerHTML = ""; }
  renderTripList();
}
function calShowTrip(key) {
  var list = document.getElementById("trip-list"), det = document.getElementById("trip-detail"), form = document.getElementById("trip-form");
  if (list) list.hidden = true;
  if (form) form.hidden = true;
  if (det) det.hidden = false;
  buildCapsule(key);
}
function calOpenTrip(key) {
  if (!tripDef(key)) return;
  calNavPush();
  calShowTrip(key);
}
function tripDatesLabel(t) {
  if (t.dates) return t.dates;
  if (t.start && t.end) {
    var a = planDateOfISO(t.start), b = planDateOfISO(t.end);
    var fmt = function (d) { return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }); };
    var nights = Math.round((b - a) / 86400000);
    return fmt(a) + " – " + fmt(b) + ", " + b.getFullYear() + " · " + nights + (nights === 1 ? " night" : " nights");
  }
  return "";
}
function renderTripList() {
  var el = document.getElementById("trip-list");
  if (!el) return;
  el.innerHTML = allTripKeys().map(function (k) {
    var t = tripDef(k);
    if (!t) return "";
    var dests = (t.legs && t.legs.length) ? t.legs.join(" · ") : "";
    return '<button type="button" class="trip-card" data-trip-open="' + esc(k) + '"><span class="tc-name">' + esc(t.name) + '</span><span class="tc-meta">' + esc(tripDatesLabel(t)) + (dests ? " · " + esc(dests) : "") + "</span></button>";
  }).join("");
}
document.getElementById("panel-calendar").addEventListener("click", function (e) {
  var b = e.target.closest("[data-calview]");
  if (!b) return;
  var v = b.getAttribute("data-calview");
  if (v === calView && !currentCapsule) return;
  calNavPush();
  if (v !== "trips") currentCapsule = null;
  calView = v;
  if (v === "trips") calShowList();
  calViewApply();
});
(function () {
  var form = document.getElementById("trip-form");
  if (!form) return;
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var name = (document.getElementById("trip-name").value || "").trim();
    var start = document.getElementById("trip-start").value || "";
    var end = document.getElementById("trip-end").value || "";
    var dests = (document.getElementById("trip-dests").value || "").split(",").map(function (s) { return s.trim(); }).filter(Boolean);
    if (!name || !start || !end) { toast("A trip needs a name, a start and an end date."); return; }
    var a = planDateOfISO(start), b = planDateOfISO(end);
    var days = Math.round((b - a) / 86400000) + 1;
    if (days < 1) { toast("The end date is before the start."); return; }
    if (days > 31) days = 31;
    var pool = document.getElementById("trip-pool").checked;
    var id = "trip-" + name.toLowerCase().replace(/[^a-z0-9]+/g, "-") + "-" + Date.now().toString(36);
    userTrips.push({ id: id, key: id, name: name, start: start, end: end, legs: dests.length ? dests : [name], days: days,
      slots: pool ? ["Day", "Pool", "Night"] : ["Day", "Night"], temp: 75, nightTemp: 68,
      weather: "Dealt at a mild-weather default (75°F days) — outfits build from your closet with light layers.",
      essentials: ["Sunglasses", "Passport", "Charger", "A light layer for evenings"], note: "" });
    saveUserTrips();
    form.reset();
    calOpenTrip(id);
    toast("Trip created — " + name + ".");
  });
})();

/* ---------- Week planner — seven days on the Calendar ----------
   Mon–Sun slots for the displayed week, with prev/next chevrons
   so the coming week can be planned on a Sunday. A slot shows
   the day, its date, the day's forecast where the weather read
   covers that date (dailyForecast — past week through the
   forecast horizon; nothing beyond it, never an invented one),
   and the planned look's own photograph or an empty slot.
   Tapping the slot opens the plan sheet (the shared bottom
   sheet): pick a liked/queued look, deal a fresh one in, or
   clear the day. Tapping the photograph itself opens the
   standard photo pop-out — the global data-popout rule, which
   stops the tap before it reaches the slot. Past days keep
   their plan, greyed; nothing is auto-deleted. */
var planWeekOffset = 0;
var planSheetDate = null;
function planISOOf(d) {
  var m = d.getMonth() + 1, day = d.getDate();
  return d.getFullYear() + "-" + (m < 10 ? "0" : "") + m + "-" + (day < 10 ? "0" : "") + day;
}
function planDateOfISO(iso) {
  var p = String(iso || "").split("-");
  return new Date(parseInt(p[0], 10) || 2026, (parseInt(p[1], 10) || 1) - 1, parseInt(p[2], 10) || 1, 12);
}
function planMonday(offset) {
  var now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7) + (offset || 0) * 7, 12);
}
/* Every worn outfit recorded for one date — the worn log plus
   looks flagged worn — deduped the same way the What I wore
   history dedupes, newest first. The Calendar reads placement
   from here; the log itself is never altered. */
function wornForDate(iso) {
  /* Build .38 (2.4): the same shared merge as the What I wore
     list — one wear, one entry. */
  return mergedWornEntries(iso);
}
function renderWeekPlan() {
  var grid = document.getElementById("week-plan-grid");
  if (!grid) return;
  var mon = planMonday(planWeekOffset);
  var sun = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6, 12);
  var rangeEl = document.getElementById("week-plan-range");
  if (rangeEl) rangeEl.textContent = mon.toLocaleDateString(undefined, { day: "numeric", month: "short" }) + " – " + sun.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  var todayIso = localTodayISO();
  var html = "";
  for (var i = 0; i < 7; i++) {
    var d = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + i, 12);
    var iso = planISOOf(d);
    var look = planLookForDate(iso);
    var worn = wornForDate(iso);
    var wornImg = "";
    for (var wi = 0; wi < worn.length; wi++) { if (worn[wi].img) { wornImg = worn[wi].img; break; } }
    var fc = (typeof dailyForecast !== "undefined" && dailyForecast) ? dailyForecast[iso] : null;
    var fcTxt = fc && typeof fc.hi === "number" ? Math.round(fc.hi) + "°" + (fc.label ? " " + fc.label.replace("Thunderstorms", "T-storms").replace("Thunderstorm", "T-storm") : "") : "";
    var cls = "wp-day" + (iso === todayIso ? " wp-today" : "") + (iso < todayIso ? " wp-past" : "") + (look ? " wp-planned" : "") + (worn.length ? " wp-hasworn" : "");
    /* Worn wins the CELL DISPLAY only — the plan underneath is
       untouched and still shows in the day sheet. */
    var img = wornImg || (look ? lookImg(look) : "");
    var imgTitle = wornImg ? worn[0].title : (look ? look.title : "");
    var aria = esc(d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })) +
      (worn.length ? " — wore: " + esc(worn.map(function (w) { return w.title; }).join(", ")) : "") +
      (look ? " — planned: " + esc(look.title) : "");
    html += '<div class="' + cls + '" data-plan-day="' + iso + '" role="button" tabindex="0" aria-label="' + aria + '">' +
      (worn.length > 1 ? '<span class="wp-worn-count">' + worn.length + '</span>' : "") +
      '<span class="wp-dow">' + esc(d.toLocaleDateString(undefined, { weekday: "short" })) + '</span>' +
      '<span class="wp-date">' + d.getDate() + '</span>' +
      '<span class="wp-fc">' + esc(fcTxt) + '</span>' +
      (img
        ? '<img class="wp-thumb" src="' + esc(img) + '" alt="' + esc(imgTitle) + '" loading="lazy" decoding="async" data-popout="' + esc(img) + '" data-popout-alt="' + esc(imgTitle) + '" />'
        : (worn.length ? '<span class="wp-empty" aria-hidden="true">✓</span>' : '<span class="wp-empty" aria-hidden="true">+</span>')) +
      "</div>";
  }
  grid.innerHTML = html;
}
/* The sheet's pick list: My Looks' liked and queued looks — the
   savedLooks entries carrying a like (or queued) verdict, plus
   the queue's own snapshots, one entry per look id. */
function planCandidates() {
  var out = [], seen = {};
  function add(l) { if (l && l.id && !seen[l.id] && planLookValid(l)) { seen[l.id] = 1; out.push(l); } }
  savedLooks.forEach(function (l) { if (l.verdict === "like" || l.verdict === "queued") add(l); });
  queueLooks.forEach(add);
  return out;
}
/* Deal a fresh one for a planned day: the hero's own machinery,
   by source mode — Only my wardrobe builds from the Closet,
   Inspo / Combo deal from the deck — with like-graduation
   exclusions respected on every path (buildClosetLooks' fresh
   filter here; dealFromDeck and dealerLook exclude graduated
   photographs themselves). */
function dealPlanLook() {
  var src = (typeof studioSource !== "undefined") ? studioSource : "combo";
  if (src === "wardrobe" && typeof buildClosetLooks === "function") {
    var cl = buildClosetLooks();
    if (cl && cl.length) {
      var fresh = cl.filter(function (l) { return !isGraduatedLook(l); });
      var list = fresh.length ? fresh : cl;
      return list[Math.floor(Math.random() * list.length)];
    }
  }
  /* The deck path can deal an icon reference look (refLook — a
     photograph of someone else). A planned look becomes Today's
     hero, so a reference photograph must never be dealt here:
     deal again, up to 12 attempts, and take the first
     non-reference look; if every attempt is a reference, there
     is no plan look (the sheet's no-look handling applies). */
  for (var attempt = 0; attempt < 12; attempt++) {
    var cand = null;
    if (typeof dealFromDeck === "function") {
      var dealt = dealFromDeck(1, {});
      if (dealt && dealt.length) cand = dealt[0];
    }
    if (!cand && typeof dealerLook === "function") cand = dealerLook({});
    if (!cand) return null;
    if (!cand.refLook) return cand;
  }
  return null;
}
function openPlanSheet(iso) {
  var sheet = document.getElementById("plan-sheet");
  var body = document.getElementById("plan-sheet-body");
  var title = document.getElementById("plan-sheet-title");
  if (!sheet || !body) return;
  planSheetDate = iso;
  var d = planDateOfISO(iso);
  if (title) title.textContent = d.toLocaleDateString(undefined, { weekday: "long" }) + " · " + d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  var planned = planLookForDate(iso);
  var wornDay = wornForDate(iso);
  var cands = planCandidates();
  var html = "";
  if (wornDay.length) {
    html += '<p class="wp-pick-label">Worn</p>' + wornDay.map(function (en) {
      return '<div class="worn-row' + (en.selfie ? " selfie" : "") + '">' + (en.img ? '<img src="' + esc(en.img) + '" alt="" loading="lazy" data-popout="' + esc(en.img) + '" />' : "") +
        '<span class="w-main"><span class="w-name">' + esc(en.title) + '</span>' +
        '<span class="w-sub">' + esc(fmtDateShort(en.date)) + (en.pieces && en.pieces.length ? " · " + esc(en.pieces.join(", ")) : "") + (en.watch ? " · Watch: " + esc(en.watch) : "") + "</span></span></div>";
    }).join("");
  }
  if (iso < localTodayISO()) {
    /* A past day is a record, not a plan (build .28): worn
       outfits only — no Deal a fresh one, no Liked & queued
       picker, no plan controls. The stored plan for the day is
       untouched; it simply isn't presented. */
    if (!wornDay.length) html += '<p class="wp-pick-label">Nothing worn logged for this day.</p>';
  } else {
    if (planned) {
      var pimg = lookImg(planned);
      html += '<div class="wp-current"><img src="' + esc(pimg) + '" alt="" data-popout="' + esc(pimg) + '" data-popout-alt="' + esc(planned.imgAlt || planned.title) + '" loading="lazy" />' +
        '<span class="wp-current-main"><span class="wp-current-name">' + esc(planned.title) + '</span><span class="wp-current-sub">Planned</span></span>' +
        '<button type="button" class="btn-ghost" data-plan-clear>Remove</button></div>';
    }
    html += '<button type="button" class="btn-accent wp-deal" data-plan-deal>Deal a fresh one</button>';
    if (cands.length) {
      html += '<p class="wp-pick-label">Liked &amp; queued</p><div class="wp-pick-grid">' + cands.map(function (l) {
        return '<button type="button" class="wp-pick" data-plan-pick="' + esc(l.id) + '" aria-label="Plan ' + esc(l.title) + '"><img src="' + esc(lookImg(l)) + '" alt="" loading="lazy" decoding="async" /></button>';
      }).join("") + "</div>";
    } else {
      html += '<p class="wp-pick-label">No liked or queued looks yet</p>';
    }
  }
  body.innerHTML = html;
  sheet.hidden = false;
  var c = document.getElementById("plan-sheet-close");
  if (c) c.focus();
}
function closePlanSheet() {
  var sheet = document.getElementById("plan-sheet");
  if (sheet) sheet.hidden = true;
  planSheetDate = null;
}
(function weekPlannerInit() {
  var wrap = document.getElementById("week-plan-wrap");
  if (wrap) {
    wrap.addEventListener("click", function (e) {
      var nav = e.target.closest ? e.target.closest("[data-plan-nav]") : null;
      if (nav) { planWeekOffset += parseInt(nav.getAttribute("data-plan-nav"), 10) || 0; renderWeekPlan(); return; }
      var day = e.target.closest ? e.target.closest("[data-plan-day]") : null;
      if (day) openPlanSheet(day.getAttribute("data-plan-day"));
    });
    wrap.addEventListener("keydown", function (e) {
      if ((e.key === "Enter" || e.key === " ") && e.target.hasAttribute && e.target.hasAttribute("data-plan-day")) {
        e.preventDefault();
        openPlanSheet(e.target.getAttribute("data-plan-day"));
      }
    });
  }
  var sheet = document.getElementById("plan-sheet");
  if (sheet) {
    document.getElementById("plan-sheet-close").addEventListener("click", closePlanSheet);
    sheet.addEventListener("click", function (e) {
      if (e.target === sheet) { closePlanSheet(); return; }
      if (!planSheetDate) return;
      var iso = planSheetDate;
      if (e.target.closest("[data-plan-clear]")) {
        clearPlanForDate(iso);
        closePlanSheet();
        renderWeekPlan();
        toast("Plan cleared.");
        return;
      }
      if (e.target.closest("[data-plan-deal]")) {
        var fresh = dealPlanLook();
        if (fresh && setPlanForDate(iso, fresh)) {
          if (fresh.img) recordDealt([fresh.img]);
          closePlanSheet();
          renderWeekPlan();
          toast("Planned — " + fresh.title + ".");
        } else {
          toast("Couldn't deal a look just now.");
        }
        return;
      }
      var pick = e.target.closest("[data-plan-pick]");
      if (pick) {
        var id = pick.getAttribute("data-plan-pick");
        var look = planCandidates().filter(function (l) { return l.id === id; })[0];
        if (look && setPlanForDate(iso, look)) {
          closePlanSheet();
          renderWeekPlan();
          toast("Planned — " + look.title + ".");
        }
      }
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !sheet.hidden) closePlanSheet(); });
    /* Swipe down dismisses, like the other (i) sheets. */
    var card = sheet.querySelector(".info-pop-card");
    if (card) {
      var psy = null;
      card.addEventListener("touchstart", function (e) { psy = e.touches.length === 1 ? e.touches[0].clientY : null; }, { passive: true });
      card.addEventListener("touchend", function (e) {
        if (psy === null || !e.changedTouches.length) return;
        var dy = e.changedTouches[0].clientY - psy;
        psy = null;
        if (dy > 70) closePlanSheet();
      }, { passive: true });
    }
  }
  renderWeekPlan();
  /* Opening the Calendar re-reads the live plan and forecast —
     both can move while other pages are in front. */
  var prevSwitchPlan = window.switchTab;
  if (typeof prevSwitchPlan === "function") {
    window.switchTab = function (name, opts) {
      prevSwitchPlan(name, opts);
      if (name === "calendar") { renderWeekPlan(); if (typeof renderWornLog === "function") renderWornLog(); }
    };
  }
})();

/* ---------- My Looks extras refresh with the grid ---------- */
(function wrapRenderSaved() {
  var orig = window.renderSaved;
  if (typeof orig !== "function") return;
  window.renderSaved = function () {
    orig();
    renderWishlist();
    renderWornLog();
    renderRecentlyRemoved();
  };
})();

/* ---------- Closet Add form — two columns, More details, sticky Add (12) ---------- */
(function closetForm() {
  var form = document.getElementById("add-form");
  if (!form) return;
  function wrap(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    var n = el;
    while (n && n.parentNode !== form) n = n.parentNode;
    return n;
  }
  var catDiv = wrap("item-cat"), colDiv = wrap("item-colour-name");
  if (catDiv && colDiv) {
    var row = document.createElement("div");
    row.className = "form-row";
    form.insertBefore(row, catDiv);
    row.appendChild(catDiv);
    row.appendChild(colDiv);
  }
  var notesDiv = wrap("item-notes"), costDiv = wrap("item-price");
  if (notesDiv && costDiv) {
    var tog = document.createElement("button");
    tog.type = "button";
    tog.className = "btn-ghost more-toggle";
    tog.textContent = "More details ▾";
    tog.setAttribute("aria-expanded", "false");
    var body = document.createElement("div");
    body.hidden = true;
    body.style.display = "grid";
    body.style.gap = "7px";
    form.insertBefore(tog, notesDiv);
    form.insertBefore(body, notesDiv);
    body.appendChild(notesDiv);
    body.appendChild(costDiv);
    tog.addEventListener("click", function () {
      var open = body.hidden;
      body.hidden = !open;
      tog.setAttribute("aria-expanded", open ? "true" : "false");
      tog.textContent = open ? "More details ▴" : "More details ▾";
    });
  }
})();

/* ---------- Closet sub-pages — entry rows + back (25) ---------- */
document.addEventListener("click", function (e) {
  var back = e.target.closest ? e.target.closest("[data-back-wardrobe]") : null;
  if (back) { if (typeof switchTab === "function") switchTab("wardrobe"); return; }
  if (e.target.closest && e.target.closest("#closet-add-entry")) { if (typeof switchTab === "function") switchTab("add"); return; }
});

/* ---------- Profile measurements — grouped, two columns (13) ---------- */
(function profileGroups() {
  var grid = document.querySelector("#profile-form .profile-grid");
  if (!grid) return;
  function wrap(id) { var el = document.getElementById(id); return el ? el.parentElement : null; }
  var groups = [
    ["Tops", ["pf-tee", "pf-polo", "pf-shirt", "pf-knit", "pf-blazer", "pf-coat"]],
    ["Bottoms", ["pf-waist", "pf-inseam", "pf-jeans", "pf-shorts"]],
    ["Shoes & extras", ["pf-shoe", "pf-glove", "pf-hat", "pf-belt", "pf-sleeve", "pf-chest", "pf-height", "pf-fit"]]
  ];
  var frag = document.createDocumentFragment();
  groups.forEach(function (g) {
    var h = document.createElement("p");
    h.className = "profile-group-head";
    h.textContent = g[0];
    frag.appendChild(h);
    g[1].forEach(function (id) { var w = wrap(id); if (w) frag.appendChild(w); });
  });
  Array.prototype.slice.call(grid.children).forEach(function (c) { frag.appendChild(c); });
  grid.appendChild(frag);
})();

/* ---------- (i) pop-ups — swipe down to dismiss (15) ---------- */
(function sheetSwipe() {
  function wire(card, close) {
    if (!card) return;
    var sy = null;
    card.addEventListener("touchstart", function (e) { sy = e.touches.length === 1 ? e.touches[0].clientY : null; }, { passive: true });
    card.addEventListener("touchend", function (e) {
      if (sy === null || !e.changedTouches.length) return;
      var dy = e.changedTouches[0].clientY - sy;
      sy = null;
      if (dy > 70) close();
    }, { passive: true });
  }
})();

/* ---------- Individual image — one compact row, expands on tap (16) ---------- */
(function imageInspoCollapse() {
  var field = document.getElementById("image-inspo-field");
  if (!field) return;
  var labelRow = field.querySelector(".label-row");
  if (!labelRow) return;
  var body = document.createElement("div");
  body.hidden = true;
  Array.prototype.slice.call(field.children).forEach(function (c) { if (c !== labelRow) body.appendChild(c); });
  field.appendChild(body);
  labelRow.style.cursor = "pointer";
  labelRow.setAttribute("role", "button");
  labelRow.setAttribute("aria-expanded", "false");
  var chev = document.createElement("span");
  chev.textContent = "▾";
  chev.style.marginLeft = "auto";
  chev.style.color = "var(--brass)";
  chev.setAttribute("aria-hidden", "true");
  labelRow.appendChild(chev);
  function setOpen(open) {
    body.hidden = !open;
    labelRow.setAttribute("aria-expanded", open ? "true" : "false");
    chev.textContent = open ? "▴" : "▾";
  }
  labelRow.addEventListener("click", function (e) {
    if (e.target.closest(".info-btn")) return;
    setOpen(body.hidden);
  });
  var thumbs = document.getElementById("inspo-thumbs");
  if (thumbs && thumbs.children.length) setOpen(true);
})();

/* ---------- Icons — new looks surfacing (26) ---------- */
(function iconNews() {
  if (typeof allIcons !== "function") return;
  var counts = {};
  allIcons().forEach(function (ic) { counts[ic.id] = (ic.looks || []).length; });
  var seen = store.get("iconSeen", null);
  if (!seen) { store.set("iconSeen", counts); seen = counts; }
  var freshIds = allIcons().filter(function (ic) { return counts[ic.id] > (seen[ic.id] || 0); }).map(function (ic) { return ic.id; });
  function badgeRows() {
    document.querySelectorAll("[data-open-icon]").forEach(function (r) {
      var id = r.getAttribute("data-open-icon");
      if (freshIds.indexOf(id) !== -1 && !r.querySelector(".new-badge")) {
        var s = document.createElement("span");
        s.className = "new-badge";
        s.textContent = "New";
        var nm = r.querySelector(".nm");
        if (nm) nm.appendChild(s);
      }
    });
  }
  badgeRows();
  document.getElementById("panel-icons").addEventListener("click", function (e) {
    var o = e.target.closest("[data-open-icon]");
    if (!o) return;
    var id = o.getAttribute("data-open-icon");
    var ic = iconById(id);
    if (!ic) return;
    var seenNow = store.get("iconSeen", {});
    seenNow[id] = (ic.looks || []).length;
    store.set("iconSeen", seenNow);
    freshIds = freshIds.filter(function (x) { return x !== id; });
  });
})();

/* ---------- Init ---------- */
restoreStudioSettings();
renderRecentlyRemoved();
renderWishlist();
renderWornLog();
    