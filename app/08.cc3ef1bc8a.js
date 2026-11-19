
/* ================= Build .76 — The Edit: Saved / Searches / Build =================
   Saved      everything he has saved (the wishlist), searchable and
              grouped by category, colour, search, brand, store or
              price; star or pass on any piece.
   Searches   every store search is kept automatically with its own
              shortlist (what he saved, starred or put in a look from
              it), how many results he saw and the price range.
   Build      Layer / Top / Bottom / Shoes from his closet and his
              saved pieces, See it on me on his template, and a To buy
              list with buy links for every piece he doesn't own.
   Sync: product notes (star / pass / which searches) ride the
   "edits" collection, searches the "searches" collection, saved
   items stay in "shopwish" — same last-writer-wins records as every
   other collection, no worker change. */
(function () {
  var EDIT_CATALOG = [];
  var editState = { view: store.get("editView", "saved") || "saved", group: "Category", starred: false, q: "", openSearch: null, results: [], resultsN: 0 };
  if (["saved", "searches", "build", "ask"].indexOf(editState.view) === -1) editState.view = "saved";
  var EDIT_HEART = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20.5s-7.5-4.6-7.5-10.1A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.8c0 5.5-7.5 10.1-7.5 10.1z"/></svg>';
  var EDIT_STAR = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.6l2.5 5.3 5.8.7-4.3 4 1.1 5.8L12 16.6l-5.1 2.8 1.1-5.8-4.3-4 5.8-.7z"/></svg>';
  var EDIT_DOWN = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7.5 4.5h9.2a1.6 1.6 0 0 1 1.6 1.4l1 7.1a1.6 1.6 0 0 1-1.6 1.8h-4.4l.7 3.4a1.7 1.7 0 0 1-3.1 1.2L7.5 14.5z"/><path d="M4 4.5h3.5v10H4z"/></svg>';
  var EDIT_X = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/></svg>';
  function h76(s) { return (typeof tryonHash === "function") ? tryonHash(String(s)) : String(s).length.toString(16); }
  function money(n) { return (typeof n === "number" && isFinite(n)) ? "$" + Math.round(n).toLocaleString("en-US") : ""; }
  /* a product's own price text — the verified GBP rows keep their £ */
  function priceText(sn) { return (sn && sn.pd) ? String(sn.pd) : money(sn && sn.price); }
  function totalText(list) {
    var usd = 0, other = {}, parts = [];
    list.forEach(function (p) { if (p.cur && p.cur !== "USD") other[p.cur] = (other[p.cur] || 0) + (p.price || 0); else usd += (p.price || 0); });
    if (usd || !Object.keys(other).length) parts.push(money(usd));
    Object.keys(other).forEach(function (c) { parts.push((c === "GBP" ? "£" : c === "EUR" ? "€" : c + " ") + Math.round(other[c]).toLocaleString("en-US")); });
    return parts.join(" + ");
  }
  function nowISO() { return new Date().toISOString(); }

  /* ---------- products ---------- */
  var CAT_LABEL = { knitwear: "Knitwear", top: "Tops", shirt: "Shirts", blazer: "Blazers", suit: "Suits", outerwear: "Outerwear", trousers: "Trousers", jeans: "Jeans", shorts: "Shorts", swim: "Swim", shoes: "Shoes", belt: "Belts", tie: "Ties", sunglasses: "Sunglasses" };
  var CAT_FROM = [[/loafer|sneaker|shoe|boot|derby|oxford|mule|sandal|espadrille|driver|trainer/, "shoes"], [/blazer|sport ?coat/, "blazer"], [/suit\b/, "suit"],
    [/jacket|coat|parka|overshirt|outer|gilet|vest|bomber/, "outerwear"], [/jean|denim/, "jeans"], [/short/, "shorts"], [/swim/, "swim"],
    [/trouser|pant|chino/, "trousers"], [/knit|sweater|cardigan|crew|cashmere|jumper|turtleneck|roll ?neck/, "knitwear"],
    [/shirt|oxford/, "shirt"], [/polo|tee|t-shirt|henley|top/, "top"], [/belt/, "belt"], [/tie\b/, "tie"], [/sunglass/, "sunglasses"]];
  function catOf(e) {
    if (e.cat && CAT_LABEL[e.cat]) return e.cat;
    var s = String((e.cat || "") + " " + (e.category || "") + " " + (e.name || "")).toLowerCase();
    for (var i = 0; i < CAT_FROM.length; i++) if (CAT_FROM[i][0].test(s)) return CAT_FROM[i][1];
    return "top";
  }
  /* Build .77: accessories are slots of their own */
  var ACC_SLOT = { belt: "belt", sunglasses: "eyewear", tie: "tie" };
  function slotOfCat(c) { if (ACC_SLOT[c]) return ACC_SLOT[c]; var m = (typeof BUILD_CAT_MAP !== "undefined") ? BUILD_CAT_MAP[c] : null; return m ? m[1] : "top"; }
  function colourOf(e) {
    if (e.colour) return String(e.colour);
    if (e.colourName) return e.colourName;
    var c = (typeof buildShopColour === "function") ? buildShopColour(e) : null;
    return c && c.name ? c.name : "";
  }
  function cap(s) { s = String(s || ""); return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  function storeName(e) {
    var st = String(e.retailer || e.store || "").trim();
    if (st.length <= 3) st = e.brand || st;
    return st;
  }
  /* One plain product snapshot — what Saved, Searches and Build keep. */
  function snap(e) {
    var key = e.key || (typeof shopEntryKey === "function" ? shopEntryKey(e) : (e.brand + "|" + e.name + "|" + e.url));
    var c = catOf(e);
    var hex = e.hex || ((typeof buildShopColour === "function") ? buildShopColour(e).hex : "");
    var nm = String(e.name || ""), br = String(e.brand || "");
    /* "Giorgio Armani - Pleated trousers" -> "Pleated trousers": the brand is the kicker */
    if (br && nm.toLowerCase().indexOf(br.toLowerCase()) === 0 && nm.length > br.length + 3) nm = nm.slice(br.length).replace(/^[\s\-–—:|,]+/, "");
    if (nm) nm = nm.charAt(0).toUpperCase() + nm.slice(1);
    return { key: key, brand: e.brand || "", name: nm, price: (typeof e.price === "number" ? e.price : parseFloat(e.price) || null),
      url: e.url || "", img: e.img || "", store: storeName(e), cat: c, colour: cap(colourOf(e)), hex: hex || "",
      cur: e.cur || e.currency || "", pd: e.pd || e.priceDisplay || "", gap: e.gap ? 1 : 0, tier: e.tier || "" };
  }
  function pool() {
    var base = (typeof shopCatalogueAll === "function") ? shopCatalogueAll() : [];
    var sale = (typeof SALE_ITEMS !== "undefined" && SALE_ITEMS) ? SALE_ITEMS : [];
    return EDIT_CATALOG.concat(base, sale).filter(prodHasPhoto);
  }
  /* ---------- the verified Edit catalogue (assets/edit-catalog.json) ---------- */
  window.editNormalizeCatalog = function (j) {
    var arr = Array.isArray(j) ? j : (j && (j.products || j.items || j.skus)) || [];
    var out = [], seen = {};
    arr.forEach(function (p) {
      if (!p || typeof p !== "object") return;
      var url = p.url || p.link || p.pdp || p.href;
      var name = p.name || p.title;
      var price = typeof p.price === "number" ? p.price : parseFloat(String(p.price || p.price_usd || "").replace(/[^0-9.]/g, ""));
      var img = p.img || p.image || p.image_url || p.imageUrl || (Array.isArray(p.images) ? (typeof p.images[0] === "string" ? p.images[0] : p.images[0] && (p.images[0].src || p.images[0].url)) : null);
      if (!url || !name || !isFinite(price) || !img || seen[url]) return;
      seen[url] = 1;
      var e = { brand: p.brand || p.vendor || "", name: String(name), price: price, url: url, img: img, retailer: p.retailer || p.store || p.seller || "", colour: p.colour || p.colourName || p.color || "", verified: true };
      var rc = String(p.cat || p.category || p.type || "").toLowerCase();
      rc = { chinos: "trousers", chino: "trousers", polo: "knitwear", pants: "trousers" }[rc] || rc;
      e.cat = catOf({ cat: rc, name: name });
      if (p.subcat) e.subcat = String(p.subcat).toLowerCase();
      if (p.sku) e.sku = String(p.sku);
      if (p.hex) e.hex = p.hex;
      if (Array.isArray(p.keys)) e.keys = p.keys.concat(e.subcat ? [e.subcat] : []);
      ["tier", "st", "sq", "occasion"].forEach(function (k) { if (p[k]) e[k] = p[k]; });
      var cur = p.currency || p.cur;
      if (cur && cur !== "USD") { e.cur = cur; if (p.priceDisplay) e.pd = p.priceDisplay; }
      var tg = p.tags || {};
      if (p.gap || tg.gapFiller === true || /^(yes|true|1)$/i.test(String(tg.gapFiller || ""))) e.gap = 1;
      var pw = p.pairs || tg.pairsWith;
      if (Array.isArray(pw) && pw.length) e.pairs = pw;
      if (typeof p.wasPrice === "number") e.wasPrice = p.wasPrice;
      out.push(e);
    });
    /* colourways share a name: name the colour so the cards differ */
    var nn = {};
    out.forEach(function (e) { var k = (e.brand + "|" + e.name).toLowerCase(); nn[k] = (nn[k] || 0) + 1; });
    out.forEach(function (e) {
      if (nn[(e.brand + "|" + e.name).toLowerCase()] > 1 && e.colour && e.name.toLowerCase().indexOf(String(e.colour).toLowerCase()) === -1) e.name += ", " + e.colour;
    });
    return out;
  };
  window.editLoadCatalog = function () {
    try {
      fetch("assets/edit-catalog.json", { cache: "no-cache" }).then(function (r) { return r && r.ok ? r.json() : null; }).then(function (j) {
        if (!j) return;
        EDIT_CATALOG = editNormalizeCatalog(j);
        /* gap fillers (trousers above all) also lead Shop the look */
        var gu = {};
        EDIT_CATALOG.forEach(function (e) { if (e.gap) gu[e.url] = (e.cat === "trousers" ? 2 : 1); });
        window.EDIT_GAP_URLS = gu;
        _textCache = null;
        if (typeof currentTab !== "undefined" && currentTab === "find") renderTheEdit();
      }).catch(function () {});
    } catch (e) {}
  };
  window.editCatalogCount = function () { return EDIT_CATALOG.length; };

  /* ---------- notes (edits collection) + searches ---------- */
  function metaId(key) { return "m-" + h76(key); }
  function metaFor(key) { var id = metaId(key); return editMeta.filter(function (m) { return m && m.id === id; })[0] || null; }
  function putMeta(key, patch, sn) {
    var m = metaFor(key);
    if (!m) { m = { id: metaId(key), kind: "note", key: key, star: false, pass: false, searches: [], at: nowISO() }; editMeta.unshift(m); }
    Object.keys(patch).forEach(function (k) { m[k] = patch[k]; });
    if (sn) m.p = sn;
    m.upd = nowISO();
    store.set("editMeta", editMeta);
    return m;
  }
  function isSaved(key) { return !!(typeof wishlistFor === "function" && wishlistFor(key)); }
  function saveProduct(sn) {
    if (isSaved(sn.key)) return;
    shopWishlist.unshift({ key: sn.key, brand: sn.brand, name: sn.name, price: sn.price, wasPrice: null, retailer: sn.store, url: sn.url, img: sn.img,
      cur: sn.cur || "", pd: sn.pd || "", gap: sn.gap || 0, cat: sn.cat, category: "", pieceDesc: "", garment: "", hex: sn.hex || "", colourName: sn.colour || "", addedISO: localTodayISO() });
    saveShopWishlist();
    if (typeof refreshWishButtons === "function") refreshWishButtons();
  }
  function unsaveProduct(key) {
    shopWishlist = shopWishlist.filter(function (w) { return w.key !== key; });
    saveShopWishlist();
    if (typeof refreshWishButtons === "function") refreshWishButtons();
  }
  function searchById(id) { return editSearches.filter(function (s) { return s && s.id === id; })[0] || null; }
  function shortlistAdd(sn) {
    var s = editState.openSearch ? searchById(editState.openSearch) : null;
    if (!s) return;
    s.shortlist = (s.shortlist || []).filter(function (x) { return x.key !== sn.key; });
    s.shortlist.unshift(sn);
    s.upd = nowISO();
    store.set("editSearches", editSearches);
    var m = metaFor(sn.key);
    var ids = (m && m.searches) || [];
    if (ids.indexOf(s.id) === -1) putMeta(sn.key, { searches: [s.id].concat(ids).slice(0, 12) }, sn);
  }
  function shortlistDrop(key) {
    var ch = false;
    editSearches.forEach(function (s) {
      var n = (s.shortlist || []).length;
      s.shortlist = (s.shortlist || []).filter(function (x) { return x.key !== key; });
      if (s.shortlist.length !== n) { s.upd = nowISO(); ch = true; }
    });
    if (ch) store.set("editSearches", editSearches);
  }

  /* ---------- store search ---------- */
  var SYN = { pants: ["trouser", "pant", "chino"], trousers: ["trouser", "pant", "chino"], trouser: ["trouser", "pant", "chino"], chinos: ["chino"], sneakers: ["sneaker", "trainer"], sneaker: ["sneaker", "trainer"],
    sweater: ["sweater", "knit", "crew", "cardigan", "jumper", "pullover"], sweaters: ["sweater", "knit", "crew", "cardigan", "jumper", "pullover"], knit: ["knit", "sweater", "crew"], crewneck: ["crew", "crewneck"],
    jacket: ["jacket", "blouson", "bomber", "overshirt"], tee: ["tee", "t-shirt"], tshirt: ["tee", "t-shirt"], loafers: ["loafer"], shoes: ["shoe", "loafer", "sneaker", "boot", "derby", "oxford"],
    grey: ["grey", "gray"], gray: ["grey", "gray"], navy: ["navy", "midnight"], olive: ["olive", "khaki", "military"], cream: ["cream", "ecru", "off-white", "ivory"], tan: ["tan", "camel", "beige"], beige: ["beige", "tan", "sand", "stone"] };
  var LOUNGE = /pyjama|pajama|lounge|sleep|robe\b/i;
  var _textCache = null;
  function textOf(e) {
    if (!_textCache) _textCache = new WeakMap();
    var t = _textCache.get(e);
    if (t === undefined) {
      t = (" " + [e.brand, e.name, e.cat, e.category, e.retailer, e.colour, (e.keys || []).join(" ")].join(" ") + " ").toLowerCase();
      _textCache.set(e, t);
    }
    return t;
  }
  function alts(tok) {
    var a = SYN[tok] ? SYN[tok].slice() : [tok];
    if (tok.length > 3 && /s$/.test(tok)) a.push(tok.slice(0, -1));
    if (a.indexOf(tok) === -1) a.push(tok);
    return a;
  }
  window.editSearchCatalog = function (q) {
    var toks = String(q || "").toLowerCase().replace(/[^a-z0-9\- ]+/g, " ").split(/\s+/).filter(function (t) { return t && ["men", "mens", "men's", "the", "a", "and", "in", "for", "with"].indexOf(t) === -1; });
    if (!toks.length) return [];
    var A = toks.map(alts), seen = {}, out = [];
    pool().forEach(function (e) {
      if (!e || !e.url || !e.name || !e.img || seen[e.url]) return;
      if (/\/wom[ae]n|womens/.test(e.url)) return;
      var t = textOf(e), score = 0;
      for (var i = 0; i < A.length; i++) {
        var hit = false;
        for (var j = 0; j < A[i].length; j++) if (t.indexOf(A[i][j]) !== -1) { hit = true; break; }
        if (!hit) return;
        if ((" " + String(e.name).toLowerCase() + " ").indexOf(A[i][0]) !== -1) score += 2;
      }
      seen[e.url] = 1;
      if (e.verified) score += 3;
      if (e.gap) score += (e.cat === "trousers" ? 2 : 1);
      if (LOUNGE.test(e.name) && !LOUNGE.test(q)) score -= 6;
      if (e.sq === "good") score += 1;
      out.push({ e: e, s: score });
    });
    out.sort(function (a, b) { return b.s - a.s || (a.e.price || 0) - (b.e.price || 0); });
    return out.map(function (x) { return x.e; });
  };
  function recordSearch(q, results) {
    var norm = String(q).trim().toLowerCase().replace(/\s+/g, " ");
    /* Typing refines the search in place: a newer query that extends
       (or trims) the one recorded seconds ago, with nothing shortlisted
       from it yet, replaces it instead of piling up partials. */
    var top = editSearches[0];
    if (top && top.kind === "search" && !(top.shortlist || []).length && top.last && Date.now() - Date.parse(top.last) < 30000) {
      var tq = String(top.q || "").toLowerCase();
      if (tq !== norm && (norm.indexOf(tq) === 0 || tq.indexOf(norm) === 0)) { top.q = String(q).trim(); }
    }
    var s = editSearches.filter(function (x) { return x && String(x.q || "").toLowerCase() === norm; })[0];
    var prices = results.map(function (e) { return e.price; }).filter(function (p) { return typeof p === "number"; });
    if (!s) { s = { id: "s-" + Date.now().toString(36) + h76(norm).slice(0, 4), kind: "search", q: String(q).trim(), shortlist: [], at: nowISO() }; editSearches.unshift(s); }
    else { editSearches = editSearches.filter(function (x) { return x !== s; }); editSearches.unshift(s); }
    s.seen = results.length;
    s.lo = prices.length ? Math.min.apply(null, prices) : null;
    s.hi = prices.length ? Math.max.apply(null, prices) : null;
    s.last = nowISO();
    s.upd = s.last;
    store.set("editSearches", editSearches);
    return s;
  }
  function runSearch(q, keepOpen) {
    q = String(q || "").trim();
    if (!q) { editState.openSearch = null; renderSearches(); return; }
    var res = editSearchCatalog(q).filter(function (e) { var m = metaFor(snap(e).key); return !(m && m.pass); });
    var s = recordSearch(q, res);
    editState.openSearch = s.id;
    editState.results = res;
    var inp = document.getElementById("edit-search-q");
    if (inp && inp.value !== q) inp.value = q;
    renderSearches();
    updateCounts();
  }
  window.editRunSearch = runSearch;

  /* ---------- cards ---------- */
  var SNAPS = {};
  function remember(sn) { SNAPS[sn.key] = sn; return sn; }
  function cardHTML(sn, ctx) {
    remember(sn);
    /* Build .78.5: the shared product card (vpCardHTML), worked by the
       handlers below — heart = Save, + Look on the photo, Star and Not
       for me in the product sheet. */
    var m = metaFor(sn.key), inLook = boardHasKey(sn.key);
    return vpCardHTML(sn, { edit: true, cls: (m && m.star) ? "is-star edit-pc" : "edit-pc",
      overlay: '<button type="button" class="vp-look' + (inLook ? " on" : "") + '" data-edit-look>' + (inLook ? "In look" : "+ Look") + "</button>" });
  }

  /* ---------- Saved ---------- */
  var GROUPS = ["Category", "Colour", "Search", "Brand", "Store", "Price"];
  function band(p) { return typeof p !== "number" ? "No price" : p < 250 ? "Under $250" : p < 500 ? "$250–500" : p < 1000 ? "$500–1,000" : "$1,000+"; }
  var BAND_ORDER = ["Under $250", "$250–500", "$500–1,000", "$1,000+", "No price"];
  function savedList() {
    return (shopWishlist || []).map(function (w) { var sn = snap(w); sn.added = w.addedISO || ""; return sn; });
  }
  function groupName(sn, g) {
    if (g === "Category") return CAT_LABEL[sn.cat] || "Other";
    if (g === "Colour") return sn.colour || "Other";
    if (g === "Brand") return sn.brand || "Other";
    if (g === "Store") return sn.store || "Other";
    if (g === "Price") return band(sn.price);
    if (g === "Search") {
      var m = metaFor(sn.key), s = m && m.searches && m.searches.length ? searchById(m.searches[0]) : null;
      if (!s) s = editSearches.filter(function (x) { return (x.shortlist || []).some(function (y) { return y.key === sn.key; }); })[0] || null;
      return s ? s.q : "Wishlist";
    }
    return "";
  }
  function renderSaved() {
    var f = document.getElementById("edit-groups");
    if (f) f.innerHTML = '<button type="button" class="chip edit-chip" data-edit-starred aria-pressed="' + (editState.starred ? "true" : "false") + '" aria-label="Starred only">' + EDIT_STAR + "</button>" +
      GROUPS.map(function (g) { return '<button type="button" class="chip edit-chip" data-edit-group="' + g + '" aria-pressed="' + (editState.group === g ? "true" : "false") + '">' + g + "</button>"; }).join("");
    var out = document.getElementById("edit-saved-out");
    if (!out) return;
    var all = savedList();
    var q = editState.q;
    var list = all.filter(function (sn) {
      var m = metaFor(sn.key);
      if (typeof priceOK === "function" && !priceOK(sn)) return false;
      if (editState.starred && !(m && m.star)) return false;
      if (!q) return true;
      return (sn.brand + " " + sn.name + " " + sn.colour + " " + (CAT_LABEL[sn.cat] || "") + " " + sn.store + " " + groupName(sn, "Search")).toLowerCase().indexOf(q) !== -1;
    });
    if (!all.length) {
      out.innerHTML = '<div class="card empty edit-empty">Nothing saved yet.<div class="edit-empty-acts"><button type="button" class="btn-ink" data-edit-view="searches">Search the stores</button></div></div>';
      return;
    }
    var groups = {}, g = editState.group;
    /* .78.7: a saved piece with no photo anywhere is listed below the
       cards (still yours: Buy and Remove), never as an empty card. */
    var noPh = list.filter(function (sn) { return typeof vpPhotoFor === "function" && !vpPhotoFor(sn); });
    if (noPh.length) list = list.filter(function (sn) { return noPh.indexOf(sn) === -1; });
    list.forEach(function (sn) { var n = groupName(sn, g); (groups[n] = groups[n] || []).push(sn); });
    var names = Object.keys(groups);
    if (g === "Price") names.sort(function (a, b) { return BAND_ORDER.indexOf(a) - BAND_ORDER.indexOf(b); });
    else names.sort(function (a, b) { return groups[b].length - groups[a].length || a.localeCompare(b); });
    names.forEach(function (n) { groups[n].sort(function (a, b) { var ma = metaFor(a.key), mb = metaFor(b.key); return ((mb && mb.star) ? 1 : 0) - ((ma && ma.star) ? 1 : 0); }); if (typeof priceSort === "function") groups[n] = priceSort(groups[n]); });
    out.innerHTML = names.length ? names.map(function (n) {
      return '<div class="edit-sec"><h3>' + esc(n) + '</h3><span class="edit-meta">' + groups[n].length + (groups[n].length === 1 ? " piece" : " pieces") + "</span></div>" +
        '<div class="edit-grid">' + groups[n].map(function (sn) { return cardHTML(sn, "saved"); }).join("") + "</div>";
    }).join("") : (noPh.length ? "" : '<p class="empty">' + ((typeof priceRangeActive === "function" && priceRangeActive()) ? "Nothing saved in " + esc(priceRangeLabel()) + "." : "Nothing saved matches.") + "</p>");
    if (noPh.length) out.innerHTML += '<details class="edit-nophoto"><summary>' + noPh.length + (noPh.length === 1 ? " saved piece" : " saved pieces") + " without a photo</summary>" +
      noPh.map(function (sn) {
        remember(sn);
        return '<div class="edit-np" data-edit-key="' + esc(sn.key) + '"><span class="edit-np-t"><b>' + esc(sn.brand) + "</b> " + esc(sn.name) + '</span><span class="edit-np-p">' + priceText(sn) + "</span>" +
          (sn.url ? '<a class="chip" href="' + esc(sn.url) + '" target="_blank" rel="noopener">Buy</a>' : "") +
          '<button type="button" class="chip" data-edit-save aria-label="Remove from Saved">Remove</button></div>';
      }).join("") + "</details>";
  }

  /* ---------- Searches ---------- */
  function legacyFinds() {
    var list = (typeof finds !== "undefined" && Array.isArray(finds)) ? finds : [];
    return list.filter(function (f) { return f && f.desc; }).map(function (f) {
      var ms = String(f.id || "").match(/(\d{10,})/) ? parseInt(RegExp.$1, 10) : NaN;
      return { id: "f:" + (f.id || h76(f.desc)), q: f.desc, shortlist: [], at: isFinite(ms) ? new Date(ms).toISOString() : "", legacy: true };
    });
  }
  function allSearches() {
    var have = {};
    editSearches.forEach(function (s) { have[String(s.q || "").toLowerCase()] = 1; });
    return editSearches.concat(legacyFinds().filter(function (s) { return !have[String(s.q).toLowerCase()]; }));
  }
  function when(iso) { var d = iso ? new Date(iso) : null; return d && isFinite(d.getTime()) ? d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) : ""; }
  function thumbHTML(sn) {
    remember(sn);
    return '<button type="button" class="edit-thumb" data-edit-thumb="' + esc(sn.key) + '"><span class="edit-tph"><img src="' + esc(sn.img) + '" alt="" loading="lazy" decoding="async" /></span>' +
      '<span class="edit-tt"><b>' + esc(sn.brand) + '</b></span><span class="edit-tt">' + priceText(sn) + "</span></button>";
  }
  function renderSearches() {
    var out = document.getElementById("edit-search-out");
    if (!out) return;
    var open = editState.openSearch ? searchById(editState.openSearch) : null;
    var gapsHost = document.getElementById("edit-gaps"), lookHost = document.getElementById("edit-today-look");
    if (open) {
      var res = editState.results || [];
      if (!res.length || editState._resFor !== open.id) {
        res = editSearchCatalog(open.q).filter(function (e) { var m = metaFor(snap(e).key); return !(m && m.pass); });
        editState.results = res; editState._resFor = open.id;
      }
      if (typeof priceFilterSort === "function") res = priceFilterSort(res);
      var shown = res.slice(0, editState.more ? 96 : 48);
      var slShown = (typeof priceFilterSort === "function") ? priceFilterSort(open.shortlist || []) : (open.shortlist || []);
      out.innerHTML = '<div class="edit-open-h"><div><h3>' + esc(open.q) + '</h3><span class="edit-meta">' + res.length + (res.length === 1 ? " result" : " results") + " · " + (open.shortlist || []).length + " shortlisted</span></div>" +
        '<button type="button" class="chip" data-edit-close-search aria-label="Close search">Done</button></div>' +
        (slShown.length ? '<div class="edit-strip">' + slShown.map(thumbHTML).join("") + "</div>" : "") +
        (shown.length ? '<div class="edit-grid">' + shown.map(function (e) { return cardHTML(snap(e), "search"); }).join("") + "</div>" : '<p class="empty">No matches in the stores yet.</p>') +
        (res.length > shown.length ? '<div class="edit-more"><button type="button" class="btn-ghost" data-edit-more>Show more</button></div>' : "");
      if (gapsHost) gapsHost.hidden = true;
      if (lookHost) lookHost.hidden = true;
      var gch = document.getElementById("edit-gapcards"); if (gch) gch.hidden = true;
      return;
    }
    editState.results = []; editState._resFor = null; editState.more = false;
    var list = allSearches();
    out.innerHTML = list.length ? list.map(function (s) {
      var sl = (typeof priceFilterSort === "function") ? priceFilterSort(s.shortlist || []) : (s.shortlist || []);
      var range = (typeof s.lo === "number" && typeof s.hi === "number") ? " · " + money(s.lo) + "–" + money(s.hi) : "";
      var seen = typeof s.seen === "number" ? sl.length + " shortlisted of " + s.seen : (sl.length ? sl.length + " shortlisted" : "");
      var meta = [when(s.last || s.at), seen].filter(Boolean).join(" · ") + range;
      return '<article class="card edit-srch" data-edit-search="' + esc(s.id) + '"><div class="edit-srch-top"><div><h3>' + esc(s.q) + '</h3><p class="edit-meta">' + esc(meta) + "</p></div>" +
        '<div class="edit-srch-acts"><button type="button" class="chip" data-edit-open="' + esc(s.id) + '">Open</button>' +
        (s.legacy ? "" : '<button type="button" class="edit-ico" data-edit-del-search="' + esc(s.id) + '" aria-label="Delete search">' + EDIT_X + "</button>") + "</div></div>" +
        (sl.length ? '<div class="edit-strip">' + sl.map(thumbHTML).join("") + "</div>" : "") + "</article>";
    }).join("") : "";
    if (gapsHost) gapsHost.hidden = false;
    if (lookHost) lookHost.hidden = false;
    var gcs = document.getElementById("edit-gapcards"); if (gcs) gcs.hidden = false;
    renderGaps();
  }
  /* ---------- closet gaps: the verified gap fillers, trousers first ---------- */
  var GAP_ORDER = { trousers: 0, jeans: 1, shorts: 2, outerwear: 3, belt: 4, sunglasses: 5 };
  function closetIdSet() {
    var o = {};
    (typeof wardrobeItems !== "undefined" && wardrobeItems ? wardrobeItems : []).forEach(function (it) { if (it && it.id) o[it.id] = 1; });
    return o;
  }
  function gapPicks(opts) {
    opts = opts || {};
    var ids = opts.ids || closetIdSet(), seen = {};
    var out = EDIT_CATALOG.filter(function (e) {
      if (!e.gap || !e.img || seen[e.url]) return false;
      seen[e.url] = 1;
      if (typeof priceOK === "function" && !priceOK(e)) return false;
      if (opts.slot && slotOfCat(e.cat) !== opts.slot) return false;
      if (opts.cat && e.cat !== opts.cat) return false;
      var sn = snap(e), m = metaFor(sn.key);
      return !(m && m.pass) && !(opts.unsaved && isSaved(sn.key));
    }).map(function (e) {
      var pair = (e.pairs || []).filter(function (id) { return ids[id]; }).length;
      return { e: e, o: (e.cat in GAP_ORDER) ? GAP_ORDER[e.cat] : 9, pair: pair };
    });
    out.forEach(function (x) { if (LOUNGE.test(x.e.name)) x.o += 20; });
    out.sort(function (a, b) { return a.o - b.o || b.pair - a.pair || (a.e.price || 0) - (b.e.price || 0); });
    /* one colourway per style, and brands take turns within a category */
    var styles = {}, uniq = [], dup = [];
    out.forEach(function (x) { var k = (x.e.brand + "|" + String(x.e.name).split(",")[0]).toLowerCase(); if (styles[k]) dup.push(x); else { styles[k] = 1; uniq.push(x); } });
    var res = [], byO = {};
    uniq.forEach(function (x) { (byO[x.o] = byO[x.o] || []).push(x); });
    Object.keys(byO).map(Number).sort(function (a, b) { return a - b; }).forEach(function (o) {
      var grp = byO[o], brands = {}, q = [];
      grp.forEach(function (x) { (brands[x.e.brand] = brands[x.e.brand] || []).push(x); });
      var bl = Object.keys(brands), more = true;
      for (var r = 0; more; r++) { more = false; bl.forEach(function (b) { if (brands[b][r]) { q.push(brands[b][r]); more = true; } }); }
      res = res.concat(q);
    });
    return res.concat(dup).map(function (x) { return x.e; });
  }
  window.editGapPicks = function (o) { return gapPicks(o).map(snap); };
  function gapMix(n) {
    /* trousers lead; the rest of the row is one of each other gap */
    var all = gapPicks(), tr = all.filter(function (e) { return e.cat === "trousers"; }), rest = [], cats = {};
    all.forEach(function (e) { if (e.cat !== "trousers" && !cats[e.cat]) { cats[e.cat] = 1; rest.push(e); } });
    var k = Math.max(Math.ceil(n / 2), n - rest.length);
    return tr.slice(0, k).concat(rest).slice(0, n);
  }
  var GAP_SUGGEST = ["Trousers", "Chinos", "Jeans", "Shorts", "Belts", "Sunglasses", "Outerwear"];
  var DEFAULT_SUGGEST = ["Navy suede loafers", "Linen trousers", "Cashmere crewneck", "Unstructured blazer", "White sneakers", "Knit polo"];
  function renderGaps() {
    var host = document.getElementById("edit-gaps");
    if (!host) return;
    var gaps = (typeof lastWishlist !== "undefined" && lastWishlist) ? lastWishlist.slice(0, 6).map(function (w) { return w.desc; }).filter(Boolean) : [];
    var have = {};
    editSearches.forEach(function (s) { have[String(s.q).toLowerCase()] = 1; });
    var gapQ = EDIT_CATALOG.some(function (e) { return e.gap; }) ? GAP_SUGGEST : [];
    var sug = gapQ.concat(gaps, DEFAULT_SUGGEST).filter(function (q, i, a) { return a.indexOf(q) === i && !have[q.toLowerCase()]; }).slice(0, 9);
    var picks = gapMix(8), gc = document.getElementById("edit-gapcards");
    if (gc) gc.innerHTML = picks.length ? '<div class="edit-sec" id="edit-closet-gaps"><h3>Closet gaps</h3></div><div class="edit-hrow">' + picks.map(function (e) { return cardHTML(snap(e), "gap"); }).join("") + "</div>" : "";
    host.innerHTML = (sug.length ? '<div class="edit-sec"><h3>Try</h3></div><div class="edit-sug">' + sug.map(function (q) {
      return '<button type="button" class="chip" data-edit-suggest="' + esc(q) + '">' + esc(q) + "</button>";
    }).join("") + "</div>" : "");
  }

  /* ---------- Build ---------- */
  var WEAR_SLOTS = ["layer", "top", "bottom", "shoes"], ACC_SLOTS = ["belt", "eyewear", "tie"];
  var SLOTS = WEAR_SLOTS.concat(ACC_SLOTS);
  var SLOT_LABEL = { layer: "Layer", top: "Top", bottom: "Bottom", shoes: "Shoes", belt: "Belt", eyewear: "Sunglasses", tie: "Tie" };
  function optionalSlot(s) { return s === "layer" || ACC_SLOTS.indexOf(s) !== -1; }
  var board = store.get("editBoard", null);
  if (!board || typeof board !== "object") board = {};
  function saveBoard() { store.set("editBoard", board); }
  function closetPool() {
    var by = (typeof tryonClosetPool === "function") ? tryonClosetPool() : { layer: [], top: [], bottom: [], shoes: [] };
    ACC_SLOTS.forEach(function (s) { by[s] = []; });
    (typeof wardrobeItems !== "undefined" && wardrobeItems ? wardrobeItems : []).forEach(function (it) {
      var c = String((it && it.category) || "").toLowerCase();
      var s = /belt/.test(c) ? "belt" : /sunglass|eyewear|glasses/.test(c) ? "eyewear" : /\bties?\b|bow tie/.test(c) ? "tie" : null;
      if (s) by[s].push(it);
    });
    return by;
  }
  function itemSrc(it) {
    var ph = it && it.photo;
    if (ph && /^blob:[0-9a-f]{16,}/.test(ph) && window.blobStore && window.blobStore.cache && window.blobStore.cache[ph.slice(5)]) return window.blobStore.cache[ph.slice(5)];
    if (ph && ph.indexOf("idb:") === 0 && window.photoVault && window.photoVault.cache && window.photoVault.cache[ph.slice(4)]) return window.photoVault.cache[ph.slice(4)];
    return ph || "";
  }
  function slotOptions(slot) {
    var opts = optionalSlot(slot) ? [null] : [];
    (closetPool()[slot] || []).forEach(function (it) { opts.push({ t: "c", id: it.id }); });
    savedList().forEach(function (sn) { if (slotOfCat(sn.cat) === slot && (typeof priceOK !== "function" || priceOK(sn))) opts.push({ t: "p", p: sn }); });
    gapPicks({ slot: slot, ids: boardIds() }).slice(0, 6).forEach(function (e) {
      var sn = snap(e);
      if (!opts.some(function (o) { return o && o.t === "p" && o.p.key === sn.key; })) opts.push({ t: "p", p: sn });
    });
    var cur = board[slot];
    if (cur && cur.t === "p" && !opts.some(function (o) { return o && o.t === "p" && o.p.key === cur.p.key; })) opts.push(cur);
    return opts;
  }
  function sameRef(a, b) { if (!a || !b) return !a && !b; return a.t === b.t && (a.t === "c" ? a.id === b.id : a.p.key === b.p.key); }
  function resolve(ref) {
    if (!ref) return null;
    if (ref.t === "c") { var it = closetItemById(ref.id); return it ? { own: true, it: it, name: it.name || "", brand: it.brand || "", img: itemSrc(it) } : null; }
    return { own: false, p: ref.p, name: ref.p.name, brand: ref.p.brand, img: ref.p.img, saved: isSaved(ref.p.key) };
  }
  function ensureBoard() {
    var pool = closetPool();
    /* First open: a whole outfit from his closet, with his newest
       saved piece already in its slot. */
    if (!Object.keys(board).length) {
      WEAR_SLOTS.forEach(function (s) { var first = (pool[s] || []).filter(function (it) { return !itemPoolOnly(it); })[0]; if (first) board[s] = { t: "c", id: first.id }; });
      var nw = savedList().filter(function (sn) { return WEAR_SLOTS.indexOf(slotOfCat(sn.cat)) !== -1; })[0];
      if (nw) board[slotOfCat(nw.cat)] = { t: "p", p: nw };
      saveBoard();
    }
    SLOTS.forEach(function (s) {
      var r = board[s];
      if (r && !resolve(r)) { delete board[s]; r = null; }
      if (!r && !optionalSlot(s) && !(s in board)) { var first = (pool[s] || [])[0]; if (first) board[s] = { t: "c", id: first.id }; }
      /* a slot his closet can't fill starts on the best gap filler */
      if (!board[s] && !optionalSlot(s) && !(pool[s] || []).length) { var g = gapPicks({ slot: s, ids: boardIds() })[0]; if (g) board[s] = { t: "p", p: snap(g) }; }
    });
  }
  function boardIds() {
    var o = {};
    SLOTS.forEach(function (s) { if (board[s] && board[s].t === "c") o[board[s].id] = 1; });
    return Object.keys(o).length ? o : closetIdSet();
  }
  /* Build: gap fillers that pair with the pieces on the board */
  function renderGapFill() {
    var host = document.getElementById("edit-gapfill");
    if (!host) return;
    var ids = boardIds(), picks = gapPicks({ ids: ids }).filter(function (e) { var sl = slotOfCat(e.cat); return SLOTS.indexOf(sl) !== -1 && !boardHasKey(snap(e).key); });
    var tr = picks.filter(function (e) { return e.cat === "trousers"; }), rest = picks.filter(function (e) { return e.cat !== "trousers"; });
    picks = tr.slice(0, 6).concat(rest.slice(0, 4));
    if (picks.length && typeof vpRowHTML === "function") {
      /* .78.8: the shared product card; + Look puts it on the board */
      host.innerHTML = '<div class="edit-sec"><h3>Fills a gap</h3></div>' + vpRowHTML(picks.map(function (e) { return remember(snap(e)); }), function (sn) {
        return { edit: true, cls: "edit-pc", overlay: '<button type="button" class="vp-look" data-edit-gap-put="' + esc(sn.key) + '">+ Look</button>' };
      });
      return;
    }
    host.innerHTML = picks.length ? '<div class="edit-sec"><h3>Fills a gap</h3></div><div class="edit-strip">' + picks.map(function (e) {
      var sn = remember(snap(e));
      return '<button type="button" class="edit-thumb" data-edit-gap-put="' + esc(sn.key) + '"><span class="edit-tph"><img src="' + esc(sn.img) + '" alt="" loading="lazy" decoding="async" /></span>' +
        '<span class="edit-tt"><b>' + esc(sn.brand) + '</b></span><span class="edit-tt">' + priceText(sn) + "</span></button>";
    }).join("") + "</div>" : "";
  }
  function boardHasKey(key) { return SLOTS.some(function (s) { return board[s] && board[s].t === "p" && board[s].p.key === key; }); }
  function boardPieces() { return SLOTS.map(function (s) { return { slot: s, x: resolve(board[s]) }; }).filter(function (o) { return o.x; }); }
  function renderBuild() {
    ensureBoard();
    var host = document.getElementById("edit-board");
    if (!host) return;
    var shown = SLOTS.filter(function (s) { return s !== "tie" || board.tie || slotOptions("tie").length > 1; });
    host.innerHTML = shown.map(function (s) {
      var x = resolve(board[s]);
      var n = slotOptions(s).length;
      var tag = !x ? "" : x.own ? '<span class="edit-tag">Closet</span>' : (x.saved ? '<span class="edit-tag shop">Saved</span>' : '<span class="edit-tag shop">Shop</span>');
      return '<section class="card edit-slot" data-edit-slot="' + s + '"><div class="edit-slot-h"><span class="edit-kick">' + SLOT_LABEL[s] + "</span>" + tag + "</div>" +
        '<div class="edit-slot-row"><button type="button" class="edit-arrow" data-edit-step="-1" data-slot="' + s + '" aria-label="Previous ' + SLOT_LABEL[s] + '"' + (n < 2 ? " disabled" : "") + ">‹</button>" +
        (x && !x.own && typeof vpCardHTML === "function" && vpPhotoFor(x.p) ? vpCardHTML(x.p, { edit: true, h: true, cls: "edit-slot-pc" })
          : x ? '<div class="edit-sph"><img src="' + esc(x.img) + '" alt="" decoding="async" /></div><div class="edit-sm"><span class="edit-kick">' + esc(x.own ? (x.it.colourName || "") : x.brand) + "</span><h3>" + esc(x.name) + "</h3>" +
          (x.own ? "" : '<div class="edit-price">' + priceText(x.p) + (x.p.store ? " · " + esc(x.p.store) : "") + "</div>") + "</div>"
          : '<div class="edit-sph edit-none"></div><div class="edit-sm"><h3>' + (s === "layer" ? "No layer" : optionalSlot(s) ? "None" : "Nothing yet") + "</h3></div>") +
        '<button type="button" class="edit-arrow" data-edit-step="1" data-slot="' + s + '" aria-label="Next ' + SLOT_LABEL[s] + '"' + (n < 2 ? " disabled" : "") + ">›</button></div></section>";
    }).map(function (h, i) { return shown[i] === "belt" ? '<div class="edit-sec edit-acc-h"><h3>Accessories</h3></div>' + h : h; }).join("");
    var buy = boardPieces().filter(function (o) { return !o.x.own; }).map(function (o) { return o.x.p; });
    var bn = document.getElementById("edit-buy-n");
    if (bn) bn.textContent = buy.length ? buy.length + (buy.length === 1 ? " piece" : " pieces") : "All from your closet";
    var bo = document.getElementById("edit-buy-out");
    if (bo) bo.innerHTML = buy.map(function (p) {
      return '<div class="edit-buy-row"><div class="edit-bph"><img src="' + esc(p.img) + '" alt="" loading="lazy" /></div><div class="edit-sm"><span class="edit-kick">' + esc(p.brand) + "</span><h3>" + esc(p.name) + '</h3><div class="edit-store">' + priceText(p) + (p.store ? " · " + esc(p.store) : "") + "</div></div>" +
        (p.url ? '<a class="btn-ink edit-buy" href="' + esc(p.url) + '" target="_blank" rel="noopener">Buy</a>' : "") + "</div>";
    }).join("") + (buy.length ? '<div class="edit-total"><span>Total</span><span>' + totalText(buy) + "</span></div>" : "");
    var tb = document.getElementById("edit-tobuy");
    if (tb) tb.hidden = !buy.length;
    renderGapFill();
    renderBuiltLooks();
    syncOnMeCard();
  }
  function boardTitle() {
    return boardPieces().map(function (o) { return o.x.name; }).filter(Boolean).slice(0, 4).join(", ");
  }
  function boardSig() { return SLOTS.map(function (s) { var r = board[s]; return r ? (r.t === "c" ? "c:" + r.id : "p:" + r.p.key) : "-"; }).join("|"); }
  var onme = { sig: null, state: null, url: null, text: "", fallback: false };
  function syncOnMeCard() {
    var c = document.getElementById("edit-onme");
    if (!c) return;
    if (onme.sig !== boardSig() || !onme.state) { c.hidden = true; return; }
    c.hidden = false;
    var pcs = boardPieces(), own = pcs.filter(function (o) { return o.x.own; }).length, toBuy = pcs.length - own;
    var fig = onme.state === "loading" ? '<div class="edit-on-fig edit-wait"><span class="analyze-spin" aria-hidden="true"></span></div>'
      : onme.url ? '<div class="edit-on-fig"><img id="edit-onme-img" src="' + esc(onme.url) + '" alt="This outfit on you" data-popout="' + esc(onme.url) + '" /></div>'
      : '<div class="edit-on-fig edit-wait"></div>';
    c.innerHTML = '<div class="card edit-on">' + fig + '<div class="edit-on-side"><span class="edit-kick">' + (onme.fallback ? "Closest on you" : "On you") + "</span><h3>" + esc(boardTitle()) + "</h3>" +
      '<span class="edit-store" id="edit-onme-status" role="status">' + esc(onme.state === "done" && !onme.fallback ? (own + " from your closet · " + toBuy + " to buy") : onme.text) + "</span>" +
      (onme.state === "done" ? '<button type="button" class="btn-accent" id="edit-save-look">Save look</button>' : "") + "</div></div>";
  }
  var buildRun = 0;
  function seeBoard() {
    /* accessories show on the board and in To buy; the try-on dresses the garments */
    var pcs = boardPieces().filter(function (o) { return WEAR_SLOTS.indexOf(o.slot) !== -1; });
    if (!pcs.length) return;
    var run = ++buildRun, sig = boardSig();
    onme = { sig: sig, state: "loading", url: null, text: "Getting ready…", fallback: false };
    syncOnMeCard();
    var c = document.getElementById("edit-onme");
    if (c && c.scrollIntoView) try { c.scrollIntoView({ block: "center", behavior: "smooth" }); } catch (e) {}
    var products = pcs.filter(function (o) { return !o.x.own; }).map(function (o) { return o.x.p; });
    var closet = pcs.filter(function (o) { return o.x.own; }).map(function (o) { return o.x.it; });
    var items = tryonPiecesItems(products, closet);
    tryonJob(items, function (state, text, url) {
      if (run !== buildRun) return;
      if (state === "done") onme = { sig: sig, state: "done", url: url, text: "", fallback: false };
      else if (state === "error") {
        var first = products[0];
        var fb = tryonNearestOnbody(closet.map(function (i) { return i.id; }), first ? slotOfCat(first.cat) : null, first ? first.hex : null);
        onme = { sig: sig, state: fb ? "done" : "error", url: fb, text: text, fallback: !!fb };
      } else onme = { sig: sig, state: "loading", url: null, text: text, fallback: false };
      syncOnMeCard();
    }, function () { return run === buildRun; });
  }
  /* .78.8c: Pool-only closet pieces (pool slides) only on a swim board */
  function poolOkRef(ref) {
    if (!ref || ref.t !== "c") return true;
    var it = closetItemById(ref.id); if (!it || !itemPoolOnly(it)) return true;
    return SLOTS.some(function (s) { var r = board[s]; if (!r || r.t !== "c") return false; var x = closetItemById(r.id); return x && pieceIsSwim(x); });
  }
  function shuffleBoard() {
    SLOTS.forEach(function (s) {
      var o = slotOptions(s);
      if (o.length) board[s] = o[Math.floor(Math.random() * o.length)];
    });
    SLOTS.forEach(function (s) {
      if (poolOkRef(board[s])) return;
      var o = slotOptions(s).filter(poolOkRef);
      board[s] = o.length ? o[Math.floor(Math.random() * o.length)] : null;
    });
    saveBoard();
    renderBuild();
  }
  /* Built looks ride the edits collection (kind "look"). */
  function builtLooks() { return editMeta.filter(function (m) { return m && m.kind === "look"; }); }
  /* Build .78: the look's picture — this board's render when there is
     one, else his nearest on-body render, else none (a flat-lay of the
     pieces is drawn wherever the look shows). */
  function lookPicture(pcs) {
    if (onme.sig === boardSig() && onme.state === "done" && onme.url) return { url: onme.url, kind: onme.fallback ? "near" : "render" };
    var wear = pcs.filter(function (o) { return WEAR_SLOTS.indexOf(o.slot) !== -1; });
    var own = wear.filter(function (o) { return o.x.own; }).map(function (o) { return o.x.it.id; });
    var prod = wear.filter(function (o) { return !o.x.own; })[0];
    var near = typeof tryonNearestOnbody === "function" ? tryonNearestOnbody(own, prod ? slotOfCat(prod.x.p.cat) : null, prod ? prod.x.p.hex : null) : null;
    return near ? { url: near, kind: "near" } : { url: null, kind: "flat" };
  }
  function saveBuiltLook() {
    var id = "l-" + h76(boardSig());
    var pcs = boardPieces(), allOwn = pcs.length > 0 && pcs.every(function (o) { return o.x.own; });
    if (!pcs.length) { if (typeof toast === "function") toast("Put a piece on the board first."); return; }
    var pic = lookPicture(pcs);
    editMeta = editMeta.filter(function (m) { return m.id !== id; });
    editMeta.unshift({ id: id, kind: "look", home: allOwn ? "mine" : "inspo", title: boardTitle(), board: JSON.parse(JSON.stringify(board)), img: pic.url, imgKind: pic.kind, at: nowISO(), upd: nowISO() });
    store.set("editMeta", editMeta);
    renderBuiltLooks();
    /* Build .77: every piece his own -> Outfits > Mine (a saved look);
       with shop pieces -> Outfits > Inspo > On you (from this record). */
    var lid77 = "look-e77-" + h76(boardSig());
    if (allOwn && typeof saveLook === "function" && typeof savedLooks !== "undefined" && savedLooks.some(function (l) { return l && l.id === lid77; })) {
      if (typeof toast === "function") toast("Already saved — it's in Outfits → Mine.");
    } else if (allOwn && typeof saveLook === "function") {
      var its = pcs.map(function (o) { return o.x.it; });
      saveLook({ id: lid77, title: boardTitle(), imgAlt: boardTitle(), img: pic.url || "", source: "build", createdAt: Date.now(),
        fwPieces: its.map(function (it) { return { id: it.id, itemId: it.id, name: it.name || "", category: it.category || "", hex: it.colourHex || "" }; }),
        composerKey: its.map(function (it) { return it.id; }).filter(function (x, i) { return WEAR_SLOTS.indexOf(pcs[i].slot) !== -1; }).sort().join("|"),
        swatches: its.map(function (it) { return { name: String(it.colourName || "").split("\u00b7")[0].trim(), hex: it.colourHex || "#888888", role: it.category || "Piece" }; }) });
    } else if (typeof toast === "function") toast("Saved — in Outfits → Inspo.");
    if (typeof renderInspoOnYou === "function") try { renderInspoOnYou(); } catch (e) {}
  }
  window.editBuiltLooks = function () { return builtLooks(); };
  function renderBuiltLooks() {
    var host = document.getElementById("edit-looks");
    if (!host) return;
    var ls = builtLooks();
    host.innerHTML = ls.length ? '<div class="edit-sec"><h3>Your looks</h3><span class="edit-meta">' + ls.length + "</span></div>" +
      '<div class="edit-strip">' + ls.map(function (l) {
        var img = l.img || (function () { for (var i = 0; i < SLOTS.length; i++) { var x = resolve(l.board && l.board[SLOTS[i]]); if (x && x.img) return x.img; } return ""; })();
        return '<button type="button" class="edit-thumb edit-look-thumb" data-edit-load-look="' + esc(l.id) + '"><span class="edit-tph"><img src="' + esc(img) + '" alt="" loading="lazy" /></span><span class="edit-tt">' + esc(l.title || "") + "</span></button>";
      }).join("") + "</div>" : "";
  }
  function putInLook(sn) {
    var s = slotOfCat(sn.cat);
    if (SLOTS.indexOf(s) === -1) return;
    board[s] = { t: "p", p: sn };
    saveBoard();
    shortlistAdd(sn);
    show("build");
  }

  /* ---------- view switching ---------- */
  function updateCounts() {
    var a = document.getElementById("edit-n-saved"), b = document.getElementById("edit-n-search");
    if (a) a.textContent = String((shopWishlist || []).length);
    if (b) b.textContent = String(allSearches().length);
  }
  function show(v) {
    editState.view = v;
    store.set("editView", v);
    document.querySelectorAll("[data-edit-view]").forEach(function (b) { if (b.closest(".edit-tabs")) b.setAttribute("aria-pressed", String(b.getAttribute("data-edit-view") === v)); });
    ["saved", "searches", "build", "ask"].forEach(function (n) { var el = document.getElementById("edit-v-" + n); if (el) el.hidden = n !== v; });
    updateCounts();
    if (v === "saved") renderSaved();
    if (v === "searches") renderSearches();
    if (v === "build") renderBuild();
    if (v === "ask" && typeof renderAsk === "function") renderAsk(false);
    if (typeof askCheckHealth === "function") askCheckHealth();
    var p = document.getElementById("panel-find");
    if (p) p.setAttribute("data-edit-mode", v);
  }
  window.editShow = show;
  /* Build .77: shared with Ask and Inspo */
  window.editProductBySku = function (sku) {
    for (var i = 0; i < EDIT_CATALOG.length; i++) if (EDIT_CATALOG[i].sku === sku) return EDIT_CATALOG[i];
    return null;
  };
  window.editSnap = function (e) { return remember(snap(e)); };
  window.editItemSrc = itemSrc;
  window.editSlotOfCat = slotOfCat;
  /* Ask: ☆ saves into Saved with star; a card goes into its Build slot */
  window.editStarEntry = function (e, on) {
    var sn = remember(snap(e));
    putMeta(sn.key, { star: !!on, pass: false }, sn);
    if (on) saveProduct(sn);
    updateCounts();
    return sn.key;
  };
  window.editPutPiece = function (e) {
    var sn = remember(snap(e)), s = slotOfCat(sn.cat);
    if (SLOTS.indexOf(s) === -1) return null;
    board[s] = { t: "p", p: sn };
    saveBoard();
    return s;
  };
  /* Replace the board with his pieces (ids) plus shop products, open Build */
  window.editLoadOutfit = function (ownedIds, products) {
    var nb = {};
    (ownedIds || []).forEach(function (id) {
      var it = closetItemById(id); if (!it) return;
      var c = String(it.category || "").toLowerCase();
      var s = /belt/.test(c) ? "belt" : /sunglass|eyewear/.test(c) ? "eyewear" : /\bties?\b/.test(c) ? "tie" : (typeof closetSlot76 === "function" ? closetSlot76(it.category) : null);
      if (s && SLOTS.indexOf(s) !== -1 && !nb[s]) nb[s] = { t: "c", id: it.id };
    });
    (products || []).forEach(function (e) {
      if (!e) return;
      var sn = remember(snap(e)), s = slotOfCat(sn.cat);
      if (SLOTS.indexOf(s) !== -1) nb[s] = { t: "p", p: sn };
    });
    if (!nb.layer) nb.layer = null;
    ACC_SLOTS.forEach(function (s) { if (!nb[s]) nb[s] = null; });
    board = nb; saveBoard();
    onme = { sig: null, state: null, url: null, text: "", fallback: false };
    if (typeof switchTab === "function" && (typeof currentTab === "undefined" || currentTab !== "find")) switchTab("find");
    show("build");
    try { window.scrollTo(0, 0); } catch (e) {}
  };
  window.renderTheEdit = function () {
    if (typeof renderWishlist === "function") { try { renderWishlist(); } catch (e) {} }
    show(editState.view);
  };
  window.editOnSync = function () {
    if (typeof currentTab !== "undefined" && currentTab === "find") show(editState.view);
  };
  window.editBoardState = function () { return JSON.parse(JSON.stringify(board)); };

  /* ---------- events ---------- */
  function snapFromCard(el) {
    var card = el.closest("[data-edit-key]");
    if (!card) return null;
    return SNAPS[card.getAttribute("data-edit-key")] || null;
  }
  window.editRefreshPrice = function () {
    if (typeof currentTab !== "undefined" && currentTab !== "find") return;
    editState.results = []; editState._resFor = null;
    if (editState.view === "ask") { if (typeof renderAsk === "function") renderAsk(false); } else rerender();
    if (editState.view === "searches" && !editState.openSearch && typeof renderGaps === "function") renderGaps();
  };
  function rerender() { if (editState.view === "saved") renderSaved(); else if (editState.view === "searches") renderSearches(); else if (editState.view === "build") renderBuild(); updateCounts(); }
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var panel = t.closest("#panel-find");
    if (!panel) return;
    var b, sn;
    if ((b = t.closest("[data-edit-view]"))) { show(b.getAttribute("data-edit-view")); return; }
    if ((b = t.closest("[data-edit-group]"))) { editState.group = b.getAttribute("data-edit-group"); renderSaved(); return; }
    if (t.closest("[data-edit-starred]")) { editState.starred = !editState.starred; renderSaved(); return; }
    if (t.closest("[data-edit-save]")) {
      sn = snapFromCard(t); if (!sn) return;
      if (isSaved(sn.key)) { unsaveProduct(sn.key); shortlistDrop(sn.key); }
      else { saveProduct(sn); shortlistAdd(sn); putMeta(sn.key, { pass: false }, sn); }
      rerender(); return;
    }
    if (t.closest("[data-edit-star]")) {
      sn = snapFromCard(t); if (!sn) return;
      var m = metaFor(sn.key), on = !(m && m.star);
      putMeta(sn.key, { star: on, pass: false }, sn);
      if (on) { saveProduct(sn); shortlistAdd(sn); }
      rerender(); return;
    }
    if (t.closest("[data-edit-pass]")) {
      sn = snapFromCard(t); if (!sn) return;
      var wasSaved = isSaved(sn.key);
      putMeta(sn.key, { pass: true, star: false }, sn);
      if (wasSaved) unsaveProduct(sn.key);
      shortlistDrop(sn.key);
      editState.results = (editState.results || []).filter(function (x) { return snap(x).key !== sn.key; });
      rerender();
      if (typeof showUndoToast === "function") showUndoToast("Passed.", function () {
        putMeta(sn.key, { pass: false }, sn);
        if (wasSaved) saveProduct(sn);
        editState._resFor = null;
        rerender();
      });
      return;
    }
    if (t.closest("[data-edit-look]")) { sn = snapFromCard(t); if (sn) putInLook(sn); return; }
    if (t.closest("[data-edit-onme]")) { sn = snapFromCard(t); if (sn) { shortlistAdd(sn); tryonForEntry(Object.assign({ retailer: sn.store }, sn), false); } return; }
    if ((b = t.closest("[data-edit-open]"))) {
      var s = searchById(b.getAttribute("data-edit-open"));
      var q = s ? s.q : (allSearches().filter(function (x) { return x.id === b.getAttribute("data-edit-open"); })[0] || {}).q;
      if (q) runSearch(q);
      return;
    }
    if ((b = t.closest("[data-edit-gap-put]"))) { sn = SNAPS[b.getAttribute("data-edit-gap-put")]; if (sn) { putInLook(sn); renderBuild(); } return; }
    if ((b = t.closest("[data-edit-thumb]"))) {
      var srch = b.closest("[data-edit-search]");
      if (srch) { var s2 = searchById(srch.getAttribute("data-edit-search")); if (s2) runSearch(s2.q); return; }
      sn = SNAPS[b.getAttribute("data-edit-thumb")];
      if (sn) tryonForEntry(Object.assign({ retailer: sn.store }, sn), false);
      return;
    }
    if ((b = t.closest("[data-edit-del-search]"))) {
      var id = b.getAttribute("data-edit-del-search");
      var gone = searchById(id), ix = editSearches.indexOf(gone);
      editSearches = editSearches.filter(function (x) { return x.id !== id; });
      store.set("editSearches", editSearches);
      renderSearches(); updateCounts();
      if (gone && typeof showUndoToast === "function") showUndoToast("Search deleted.", function () {
        editSearches.splice(Math.max(0, ix), 0, gone); store.set("editSearches", editSearches); renderSearches(); updateCounts();
      });
      return;
    }
    if (t.closest("[data-edit-close-search]")) { editState.openSearch = null; var si = document.getElementById("edit-search-q"); if (si) si.value = ""; renderSearches(); return; }
    if (t.closest("[data-edit-more]")) { editState.more = true; renderSearches(); return; }
    if ((b = t.closest("[data-edit-suggest]"))) { runSearch(b.getAttribute("data-edit-suggest")); return; }
    if ((b = t.closest("[data-edit-step]"))) {
      var slot = b.getAttribute("data-slot"), opts = slotOptions(slot), cur = -1;
      opts.forEach(function (o, i) { if (sameRef(o, board[slot])) cur = i; });
      var nx = opts[(cur + parseInt(b.getAttribute("data-edit-step"), 10) + opts.length) % opts.length];
      if (nx) board[slot] = nx; else board[slot] = null;
      saveBoard(); renderBuild(); return;
    }
    if (t.closest("#edit-see")) { seeBoard(); return; }
    if (t.closest("#edit-shuffle")) { shuffleBoard(); return; }
    if (t.closest("#edit-save-look") || t.closest("#edit-save-board")) { saveBuiltLook(); return; }
    if ((b = t.closest("[data-edit-load-look]"))) {
      var l = editMeta.filter(function (m) { return m.id === b.getAttribute("data-edit-load-look"); })[0];
      if (l && l.board) {
        board = JSON.parse(JSON.stringify(l.board)); saveBoard(); renderBuild();
        if (l.img) { onme = { sig: boardSig(), state: "done", url: l.img, text: "", fallback: false }; syncOnMeCard(); }
      }
      return;
    }
  });
  var qTimer = null;
  document.addEventListener("input", function (e) {
    var t = e.target;
    if (!t) return;
    if (t.id === "edit-saved-q") { editState.q = t.value.trim().toLowerCase(); renderSaved(); }
    if (t.id === "edit-search-q") {
      clearTimeout(qTimer);
      var v = t.value.trim();
      if (!v) { editState.openSearch = null; renderSearches(); return; }
      if (v.length >= 3) qTimer = setTimeout(function () { runSearch(v); }, 1100);
    }
  });
  document.addEventListener("submit", function (e) {
    if (e.target && e.target.id === "edit-search-form") {
      e.preventDefault();
      clearTimeout(qTimer);
      var inp = document.getElementById("edit-search-q");
      if (inp) { runSearch(inp.value); try { inp.blur(); } catch (x) {} }
    }
  });
  editLoadCatalog();
  if (typeof currentTab !== "undefined" && currentTab === "find") renderTheEdit();
})();
    