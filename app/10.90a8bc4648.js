
/* ================= Build .77 — The Edit · Ask =================
   A plain-words thread with Vesper. POST {TRYON_URL}/ask with the
   same Bearer key the app already holds (tryonKey()); the answer
   arrives in 5-12 s. Each answer carries 4-6 verified catalogue
   cards (☆ stars it into The Edit's Saved, 👎 hides it for good)
   and one outfit that "Build this look" lays on the Build board.
   Build .78: thread, liked and disliked sync across devices through
   the "ask" collection (askSync); ask.thread / ask.liked / ask.disliked
   stay as this device's working copy. */
(function () {
  var ASK_MAX_TURNS = 30;
  var ASK_SUGS = ["Fill my gaps under $500", "Trousers for my olive Kiton polo", "Quieter white sneakers"];
  var askThread = store.get("ask.thread", []) || [];
  var askLiked = store.get("ask.liked", []) || [];
  var askDisliked = store.get("ask.disliked", []) || [];
  var askBusy = false, askAdded = {};
  if (!Array.isArray(askThread)) askThread = [];
  /* a reply that never landed (closed mid-wait) is not left spinning */
  askThread.forEach(function (t) { if (t && t.state === "pending") { t.state = "error"; t.msg = "That one didn't come through."; } });
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function saveThread() { askThread = askThread.slice(-ASK_MAX_TURNS); store.set("ask.thread", askThread); publish(); }
  function saveLists() { store.set("ask.liked", askLiked.slice(0, 500)); store.set("ask.disliked", askDisliked.slice(0, 500)); publish(); }

  /* ---------- sync (build .78) ---------- */
  var SYNC_TURN_KEYS = ["id", "q", "at", "state", "answer", "picks", "outfit", "fallback"];
  function tsOf(t) { var n = Date.parse(t && t.at || ""); return isNaN(n) ? 0 : n; }
  function prefsFromRecs() {
    var m = {};
    (Array.isArray(askSync) ? askSync : []).forEach(function (r) { if (r && r.kind === "pref" && r.sku) m[r.sku] = { v: r.v || "", at: Number(r.at) || 0 }; });
    return m;
  }
  /* local lists -> pref records (only what changed gets a new stamp) */
  function publish() {
    if (typeof askSync === "undefined") return;
    var prefs = prefsFromRecs(), now = Date.now(), want = {};
    askLiked.forEach(function (k) { want[k] = "like"; });
    askDisliked.forEach(function (k) { want[k] = "dislike"; });
    Object.keys(want).forEach(function (k) { if (!prefs[k] || prefs[k].v !== want[k]) prefs[k] = { v: want[k], at: now }; });
    Object.keys(prefs).forEach(function (k) { if (prefs[k].v && !want[k]) prefs[k] = { v: "", at: now }; });
    var recs = askThread.filter(function (t) { return t && t.id && t.state === "done"; }).map(function (t) {
      var r = { id: "t-" + t.id, kind: "turn" };
      SYNC_TURN_KEYS.forEach(function (k) { if (k !== "id" && t[k] !== undefined) r[k] = t[k]; });
      return r;
    });
    Object.keys(prefs).forEach(function (k) {
      var old = (askSync || []).filter(function (r) { return r && r.kind === "pref" && r.sku === k; })[0];
      recs.push(old && old.v === prefs[k].v ? old : { id: "p-" + String(k).slice(0, 160), kind: "pref", sku: k, v: prefs[k].v, at: prefs[k].at });
    });
    if (JSON.stringify(recs) === JSON.stringify(askSync)) return;
    askSync = recs;
    store.set("askSync", askSync);
  }
  /* records -> local working copy; local unsent / failed turns stay */
  function absorb() {
    var recs = Array.isArray(askSync) ? askSync : [];
    var turns = recs.filter(function (r) { return r && r.kind === "turn" && r.id; }).map(function (r) {
      var t = {}; SYNC_TURN_KEYS.forEach(function (k) { if (r[k] !== undefined) t[k] = r[k]; }); t.id = String(r.id).replace(/^t-/, ""); return t;
    });
    var have = {}; turns.forEach(function (t) { have[t.id] = 1; });
    askThread.forEach(function (t) { if (t && t.id && !have[t.id] && t.state !== "done") turns.push(t); });
    turns.sort(function (a, b) { return tsOf(a) - tsOf(b); });
    askThread = turns.slice(-ASK_MAX_TURNS);
    var prefs = prefsFromRecs(), ks = Object.keys(prefs).sort(function (a, b) { return prefs[b].at - prefs[a].at; });
    askLiked = ks.filter(function (k) { return prefs[k].v === "like"; });
    askDisliked = ks.filter(function (k) { return prefs[k].v === "dislike"; });
    store.set("ask.thread", askThread); store.set("ask.liked", askLiked.slice(0, 500)); store.set("ask.disliked", askDisliked.slice(0, 500));
  }
  /* first run on .78: this device's thread + lists join whatever the
     other devices already synced, then go up as records */
  (function migrate() {
    var prefs = prefsFromRecs(), have = {};
    (askSync || []).forEach(function (r) { if (r && r.kind === "turn") have[String(r.id).replace(/^t-/, "")] = 1; });
    var localOnly = askThread.filter(function (t) { return t && t.id && !have[t.id]; });
    var keepL = askLiked.filter(function (k) { return !prefs[k]; }), keepD = askDisliked.filter(function (k) { return !prefs[k]; });
    absorb();
    localOnly.forEach(function (t) { if (!askThread.some(function (x) { return x.id === t.id; })) askThread.push(t); });
    askThread.sort(function (a, b) { return tsOf(a) - tsOf(b); });
    askLiked = keepL.concat(askLiked.filter(function (k) { return keepL.indexOf(k) === -1; }));
    askDisliked = keepD.concat(askDisliked.filter(function (k) { return keepD.indexOf(k) === -1; }));
    saveThread(); saveLists();
  })();
  window.askOnSync = function () {
    if (askBusy) { setTimeout(window.askOnSync, 1500); return; }
    absorb();
    var p = document.getElementById("panel-find");
    if (p && !p.hidden && p.getAttribute("data-edit-mode") === "ask") renderAsk(false);
  };
  function isLiked(sku) { return askLiked.indexOf(sku) !== -1; }
  function isDisliked(sku) { return askDisliked.indexOf(sku) !== -1; }
  function online() { return typeof navigator === "undefined" || navigator.onLine !== false; }

  /* ---------- the catalogue: local Edit SKUs first, then /ask/catalog ---------- */
  var askCat = (function () { var c = store.get("ask.catalog", null); return c && c.items ? c : null; })();
  function catBySku(sku) {
    var e = typeof editProductBySku === "function" ? editProductBySku(sku) : null;
    if (e) return e;
    var arr = askCat && askCat.items || [];
    for (var i = 0; i < arr.length; i++) if (arr[i].sku === sku) return entryOf(arr[i]);
    return null;
  }
  function refreshCatalog() {
    if (askCat && askCat.at && Date.now() - askCat.at < 864e5) return;
    var k = tryonKey(); if (!k || typeof fetch !== "function") return;
    fetch(TRYON_URL + "/ask/catalog", { headers: { authorization: "Bearer " + k } }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (!j || !Array.isArray(j.items)) return;
      askCat = { at: Date.now(), v: j.version || "", items: j.items };
      store.set("ask.catalog", askCat);
    }).catch(function () {});
  }
  /* a server card -> an Edit entry (the local copy keeps its local image) */
  function entryOf(pr) {
    if (!pr) return null;
    var loc = pr.sku && typeof editProductBySku === "function" ? editProductBySku(pr.sku) : null;
    if (loc) return loc;
    return { sku: pr.sku, brand: pr.brand || "", name: pr.name || "", cat: pr.cat || pr.subcat || "", subcat: pr.subcat || "", price: pr.price, url: pr.url || "",
      img: pr.imgUrl || pr.img || "", retailer: pr.retailer || "", colour: pr.colourName || "", hex: pr.hex || "", pd: pr.priceDisplay || "", cur: pr.currency || "", verified: true };
  }
  function money(e, pr) {
    if (pr && pr.priceDisplay) return pr.priceDisplay;
    if (e.pd) return e.pd;
    return typeof e.price === "number" ? "$" + Math.round(e.price).toLocaleString("en-US") : "";
  }

  /* ---------- request ---------- */
  function closetPayload() {
    var out = [];
    (typeof wardrobeItems !== "undefined" ? wardrobeItems : []).forEach(function (it) {
      if (!it || !it.id || out.length >= 400) return;
      var oo = typeof itemOccasionOnly === "function" ? itemOccasionOnly(it) : null;
      out.push(Object.assign({ id: it.id, name: it.name || "", cat: it.category || "", color: String(it.colourName || "").split("\u00b7")[0].trim(), hex: it.colourHex || "" }, oo ? { occasionOnly: oo } : {}));
    });
    return out;
  }
  function historyPayload(beforeIdx) {
    var h = [];
    askThread.slice(0, beforeIdx).filter(function (t) { return t && t.state === "done"; }).slice(-3).forEach(function (t) {
      h.push({ role: "user", content: String(t.q || "").slice(0, 1000) });
      var picks = (t.picks || []).map(function (p) { var pr = p.product || {}; return (pr.brand ? pr.brand + " " : "") + (pr.name || "") + (pr.priceDisplay ? " (" + pr.priceDisplay + ")" : ""); });
      h.push({ role: "assistant", content: String(t.answer || "") + (picks.length ? " Picks: " + picks.join("; ") + "." : "") });
    });
    return h;
  }
  function ask(q) {
    q = String(q || "").trim().slice(0, 1000);
    if (!q || askBusy || !online()) return;
    var k = tryonKey();
    var turn = { id: "a" + Date.now().toString(36), q: q, at: new Date().toISOString(), state: "pending" };
    askThread.push(turn); saveThread();
    var idx = askThread.length - 1;
    if (!k) { turn.state = "error"; turn.msg = "Sign in to sync first."; saveThread(); renderAsk(true); return; }
    askBusy = true;
    renderAsk(true);
    var prq = (typeof priceRangeActive === "function" && priceRangeActive()) ? " (Budget per piece: " + (function () { var st = prState(); return st.tier ? shopTierInfo(st.tier).name.toLowerCase() + " price tier" : priceRangeLabel(st).replace("\u2013", " to $"); })() + ")" : "";
    var body = { query: q + prq, closet: closetPayload(), history: historyPayload(idx), liked: askLiked.slice(0, 500), disliked: askDisliked.slice(0, 500) };
    var ctl = typeof AbortController === "function" ? new AbortController() : null;
    var to = setTimeout(function () { if (ctl) ctl.abort(); }, 45000);
    fetch(TRYON_URL + "/ask", { method: "POST", headers: { "content-type": "application/json", authorization: "Bearer " + k }, body: JSON.stringify(body), signal: ctl ? ctl.signal : undefined })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { s: r.status, j: j || {} }; }); })
      .then(function (res) {
        var j = res.j;
        if (res.s === 200 && j && typeof j.answer === "string") {
          turn.state = "done"; turn.answer = j.answer;
          turn.picks = (j.picks || []).filter(function (p) { return p && p.sku; }).map(function (p) { return { sku: p.sku, why: p.why || "", pairsWith: p.pairsWith || [], product: p.product || null }; });
          turn.outfit = j.outfit && ((j.outfit.ownedIds || []).length || (j.outfit.skuIds || []).length) ? { ownedIds: j.outfit.ownedIds || [], skuIds: j.outfit.skuIds || [] } : null;
          /* .78.8c: drop a Pool-only piece from a non-swim outfit the server suggests */
          if (turn.outfit && typeof itemPoolOnly === "function" && typeof closetItemById === "function") {
            var oi = turn.outfit.ownedIds.map(closetItemById).filter(Boolean);
            if (!oi.some(pieceIsSwim)) turn.outfit.ownedIds = turn.outfit.ownedIds.filter(function (id) { var x = closetItemById(id); return !(x && itemPoolOnly(x)); });
          }
          turn.fallback = !!(j.meta && j.meta.fallback);
        } else {
          turn.state = "error";
          turn.msg = (j && j.message) || (res.s === 401 ? "Sync isn't signed in on this device." : res.s === 429 ? "That's today's asks." : res.s === 503 ? "Ask isn't available right now." : "That one didn't come through.");
          turn.code = res.s;
        }
      })
      .catch(function () { turn.state = "error"; turn.msg = "That one didn't come through."; })
      .then(function () { clearTimeout(to); askBusy = false; saveThread(); renderAsk(true); });
  }
  window.askSend = ask;

  /* ---------- render ---------- */
  function cardHTML(t, p) {
    var e = entryOf(p.product) || catBySku(p.sku);
    if (!e) return "";
    var pr = p.product || {};
    if (typeof priceOK === "function" && !priceOK({ price: (typeof e.price === "number" ? e.price : pr.price), tier: e.tier || pr.tier || "" })) return "";
    var hex = pr.hex || e.hex || "";
    var owns = (p.pairsWith || []).map(function (id) { return typeof closetItemById === "function" ? closetItemById(id) : null; }).filter(Boolean);
    /* .78.8c: Pool-only pieces pair only with a swim product */
    var swimPick = /swim|bathing|trunk/i.test(String(e.cat || "") + " " + String(e.name || "") + " " + String(pr.name || ""));
    owns = owns.filter(function (it) { return swimPick || !(typeof itemPoolOnly === "function" && itemPoolOnly(it)); }).slice(0, 3);
    var star = isLiked(p.sku), added = askAdded[t.id + "|" + p.sku];
    /* .78.8: the shared product card's look — cream studio photo,
       brand in small caps, icon row (wishlist / star / not for me /
       see it on me / shop) — with the deck, why line, Owns and Add to
       Build kept. The photo opens the product sheet. */
    var ve = Object.assign({}, e, { retailer: e.retailer || e.store || "" }), vk = "";
    if (typeof vpKey === "function" && typeof VP !== "undefined") { vk = vpKey(ve); VP[vk] = { e: ve, pc: null, pick: null, tag: "", edit: false }; }
    var I = (typeof VP_ICON !== "undefined") ? VP_ICON : {};
    var w = vk && typeof vpWished === "function" ? vpWished(ve) : false;
    return '<article class="card ask-card vp-card vp-ask' + (star ? " is-star" : "") + '" data-ask-sku="' + esc(p.sku) + '" data-ask-turn="' + esc(t.id) + '"' + (vk ? ' data-vp-key="' + esc(vk) + '"' : "") + ">" +
      '<div class="ask-ph"' + (vk ? ' data-vp-open role="button" tabindex="0" aria-label="' + esc(e.brand + " " + e.name) + '"' : "") + '><img src="' + esc(e.img) + '" alt="" loading="lazy" decoding="async" /></div>' +
      '<div class="ask-body"><span class="edit-kick vp-brand">' + esc(e.brand) + '</span><div class="vp-name ask-name" role="heading" aria-level="3">' + esc(e.name) + "</div>" +
      '<div class="ask-pr">' + (hex ? '<span class="ask-dot" style="background:' + esc(hex) + '"></span>' : "") + "<b>" + esc(money(e, pr)) + "</b><span>" + esc(pr.colourName || e.colour || "") + "</span></div>" +
      (p.why ? '<p class="ask-why">' + esc(p.why) + "</p>" : "") +
      (owns.length ? '<div class="ask-owns"><span>Owns</span>' + owns.map(function (it) {
        var src = typeof editItemSrc === "function" ? editItemSrc(it) : it.photo;
        return '<button type="button" data-ask-item="' + esc(it.id) + '" aria-label="' + esc(it.name) + '">' + (src ? '<img src="' + esc(src) + '" alt="" loading="lazy" />' : "") + "</button>";
      }).join("") + "</div>" : "") +
      '<div class="ask-acts vp-acts">' +
      (vk ? '<button type="button" class="vp-ico" data-vp-act="wish" data-vp-wish aria-pressed="' + w + '" aria-label="Wishlist">' + (I.heart || "") + "</button>" : "") +
      '<button type="button" class="vp-ico ask-star" data-ask-star aria-pressed="' + (star ? "true" : "false") + '" aria-label="Star"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.6l2.5 5.3 5.8.7-4.3 4 1.1 5.8L12 16.6l-5.1 2.8 1.1-5.8-4.3-4 5.8-.7z"/></svg></button>' +
      '<button type="button" class="vp-ico" data-ask-down aria-label="Not for me"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7.5 4.5h9.2a1.6 1.6 0 0 1 1.6 1.4l1 7.1a1.6 1.6 0 0 1-1.6 1.8h-4.4l.7 3.4a1.7 1.7 0 0 1-3.1 1.2L7.5 14.5z"/><path d="M4 4.5h3.5v10H4z"/></svg></button>' +
      (vk && e.img ? '<button type="button" class="vp-ico" data-vp-act="onme" aria-label="See it on me">' + (I.person || "") + "</button>" : "") +
      (e.url ? '<a class="edit-onme vp-ico" data-vp-act="buy" href="' + esc(e.url) + '" target="_blank" rel="noopener" aria-label="Shop at ' + esc(ve.retailer || "the store") + '">' + (I.ext || "Shop") + "</a>" : "") + "</div>" +
      '<button type="button" class="ask-add' + (added ? " on" : "") + '" data-ask-add>' + (added ? "In Build" : "Add to Build") + "</button></div></article>";
  }
  function turnHTML(t) {
    var h = '<div class="ask-turn" data-ask-turn-id="' + esc(t.id) + '"><div class="ask-q">' + esc(t.q) + "</div>";
    if (t.state === "pending") return h + '<div class="ask-a" aria-live="polite"><span class="ask-dots" aria-label="Vesper is typing"><i></i><i></i><i></i></span></div></div>';
    if (t.state === "error") return h + '<p class="ask-a ask-msg">' + esc(t.msg || "That one didn't come through.") + "</p>" +
      (t.code === 429 || t.code === 401 ? "" : '<button type="button" class="chip ask-retry" data-ask-retry="' + esc(t.id) + '">Try again</button>') + "</div>";
    var cards = (t.picks || []).filter(function (p) { return !isDisliked(p.sku); }).map(function (p) { return cardHTML(t, p); }).join("");
    var prHid = !cards && (t.picks || []).length && typeof priceRangeActive === "function" && priceRangeActive();
    return h + '<p class="ask-a">' + esc(t.answer) + "</p>" + (cards ? '<div class="ask-deck">' + cards + "</div>" : "") +
      (prHid ? '<p class="ask-a ask-msg">No picks in ' + esc(priceRangeLabel()) + ".</p>" : "") +
      (t.outfit ? '<button type="button" class="btn-ink ask-build" data-ask-build="' + esc(t.id) + '">Build this look</button>' : "") + "</div>";
  }
  function syncSend() {
    var b = document.getElementById("ask-send"), q = document.getElementById("ask-q");
    if (b) b.disabled = askBusy || !online() || !(q && q.value.trim());
  }
  /* the input rides just above the fixed bottom nav */
  function placeForm() {
    var bb = document.getElementById("bottombar"), f = document.getElementById("ask-form");
    if (!bb || !f) return;
    if (document.documentElement.classList.contains("nav-away")) return; /* .78.2b: bar tucked; keep the last spot */
    var r = bb.getBoundingClientRect();
    f.style.bottom = (r.height ? Math.max(0, Math.round(window.innerHeight - r.top)) : 0) + "px";
  }
  window.addEventListener("resize", placeForm);
  function renderAsk(toEnd) {
    var host = document.getElementById("ask-thread");
    if (!host) return;
    placeForm();
    host.innerHTML = askThread.map(turnHTML).join("");
    var sg = document.getElementById("ask-sugs");
    if (sg) sg.innerHTML = askThread.length ? "" : ASK_SUGS.map(function (s) { return '<button type="button" class="chip" data-ask-sug>' + esc(s) + "</button>"; }).join("");
    syncSend();
    if (toEnd) {
      var last = host.lastElementChild;
      if (last && last.scrollIntoView) try { last.scrollIntoView({ block: "start", behavior: "smooth" }); } catch (e) {}
    }
  }
  window.renderAsk = renderAsk;
  window.askState = function () { return { thread: askThread, liked: askLiked, disliked: askDisliked, busy: askBusy }; };

  /* ---------- actions ---------- */
  function turnById(id) { return askThread.filter(function (t) { return t && t.id === id; })[0] || null; }
  function pickOf(card) {
    var t = turnById(card.getAttribute("data-ask-turn")), sku = card.getAttribute("data-ask-sku");
    var p = t && (t.picks || []).filter(function (x) { return x.sku === sku; })[0];
    return p ? { t: t, p: p, e: entryOf(p.product) || catBySku(sku) } : null;
  }
  function setStar(sku, e, on) {
    askLiked = askLiked.filter(function (x) { return x !== sku; });
    if (on) askLiked.unshift(sku);
    saveLists();
    if (e && typeof editStarEntry === "function") editStarEntry(e, on);
  }
  document.addEventListener("submit", function (ev) {
    if (!ev.target || ev.target.id !== "ask-form") return;
    ev.preventDefault();
    var q = document.getElementById("ask-q");
    if (!q || !q.value.trim() || askBusy || !online()) return;
    var v = q.value; q.value = ""; syncSend();
    ask(v);
  });
  document.addEventListener("input", function (ev) { if (ev.target && ev.target.id === "ask-q") syncSend(); });
  window.addEventListener("online", syncSend);
  window.addEventListener("offline", syncSend);
  document.addEventListener("click", function (ev) {
    var t = ev.target; if (!t || !t.closest || !t.closest("#edit-v-ask")) return;
    var b, card, x;
    if ((b = t.closest("[data-ask-sug]"))) { ask(b.textContent); return; }
    if ((b = t.closest("[data-ask-retry]"))) {
      var old = turnById(b.getAttribute("data-ask-retry"));
      if (old && !askBusy && online()) { askThread = askThread.filter(function (z) { return z !== old; }); saveThread(); ask(old.q); }
      return;
    }
    if ((b = t.closest("[data-ask-build]"))) {
      var tt = turnById(b.getAttribute("data-ask-build"));
      if (!tt || !tt.outfit) return;
      var prods = (tt.outfit.skuIds || []).filter(function (s) { return !isDisliked(s); }).map(function (s) {
        var p = (tt.picks || []).filter(function (z) { return z.sku === s; })[0];
        return (p && entryOf(p.product)) || catBySku(s);
      }).filter(Boolean);
      if (typeof editLoadOutfit === "function") editLoadOutfit(tt.outfit.ownedIds || [], prods);
      return;
    }
    if ((b = t.closest("[data-ask-item]"))) {
      /* Build .78: an "Owns" thumbnail opens that piece's page */
      var iid = b.getAttribute("data-ask-item");
      if (typeof closetItemById === "function" && closetItemById(iid) && typeof switchTab === "function") {
        detailItemId = iid;
        switchTab("wardrobe");
        renderItemDetail();
        var dt = document.getElementById("item-detail");
        if (dt && dt.scrollIntoView) try { dt.scrollIntoView({ block: "start" }); } catch (e) {}
      }
      return;
    }
    card = t.closest(".ask-card"); if (!card || !(x = pickOf(card))) return;
    if (t.closest("[data-ask-star]")) {
      var on = !isLiked(x.p.sku);
      setStar(x.p.sku, x.e, on);
      card.classList.toggle("is-star", on);
      var sb = card.querySelector("[data-ask-star]"); if (sb) sb.setAttribute("aria-pressed", on ? "true" : "false");
      return;
    }
    if (t.closest("[data-ask-down]")) {
      var sku = x.p.sku, wasStar = isLiked(sku);
      askDisliked = askDisliked.filter(function (z) { return z !== sku; }); askDisliked.unshift(sku);
      if (wasStar) setStar(sku, x.e, false);
      saveLists();
      card.classList.add("is-gone");
      setTimeout(function () { renderAsk(false); }, 260);
      if (typeof showUndoToast === "function") {
        showUndoToast("Hidden", function () {
          askDisliked = askDisliked.filter(function (z) { return z !== sku; });
          if (wasStar) setStar(sku, x.e, true);
          saveLists(); renderAsk(false);
        });
        try { clearTimeout(undoTimer); undoTimer = setTimeout(function () { var bx = document.getElementById("undo-toast"); if (bx) bx.hidden = true; pendingUndo = null; }, 4000); } catch (e) {}
      }
      return;
    }
    if (t.closest("[data-ask-add]")) {
      if (x.e && typeof editPutPiece === "function" && editPutPiece(x.e)) {
        askAdded[x.t.id + "|" + x.p.sku] = 1;
        var ab = card.querySelector("[data-ask-add]"); if (ab) { ab.textContent = "In Build"; ab.classList.add("on"); }
      }
      return;
    }
  });

  /* ---------- availability: hide Ask when the server says so ---------- */
  function setAvailable(on) {
    var tab = document.getElementById("edit-tab-ask");
    if (tab) tab.hidden = !on;
    if (!on && typeof editShow === "function" && document.getElementById("panel-find") && document.getElementById("panel-find").getAttribute("data-edit-mode") === "ask") editShow("saved");
  }
  if (store.get("ask.off", false)) setAvailable(false);
  /* asked once per launch, when The Edit first opens (Home stays quiet) */
  var askHealthAsked = false;
  window.askCheckHealth = function () {
    if (askHealthAsked) return;
    askHealthAsked = true;
    try {
      if (typeof fetch === "function") fetch(TRYON_URL + "/health", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
        if (!j || !j.ask) return;
        var on = j.ask.configured !== false;
        store.set("ask.off", !on);
        setAvailable(on);
        if (on) refreshCatalog();
      }).catch(function () {});
    } catch (e) {}
  };
  if (typeof currentTab !== "undefined" && currentTab === "find") window.askCheckHealth();
  if (typeof currentTab !== "undefined" && currentTab === "find" && document.getElementById("panel-find") && document.getElementById("panel-find").getAttribute("data-edit-mode") === "ask") renderAsk(false);
})();
    