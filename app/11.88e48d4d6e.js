
/* ================= Build .78 — Add many photos =================
   Closet → + → Add many photos: pick any number of photos. Each one
   is scaled like the single add (processPhotoFile), read by
   POST {TRYON_URL}/identify (Workers AI vision: category, name,
   brand when legible, colour + hex), and lands in an editable review
   grid. "Add all" files every card through the same record shape and
   persistAll() as the Add form, so new pieces sync and get the .77
   deliberate-delete-only protection. The original photo is kept and
   each piece is marked needsStudio for a later studio shot. */
(function () {
  var BULK_CONC = 3, BULK_MAX = 60;
  var rows = [], running = 0, seq = 0;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function cats() { return typeof CATEGORIES !== "undefined" && CATEGORIES.length ? CATEGORIES.filter(function (c) { return c !== "All"; }) : ["Shoes", "Shirts", "Tees", "Polos", "Jeans", "Shorts", "Bathing suits", "Trousers", "Button downs", "Suits", "Blazers", "Scarves", "Jackets", "Coats", "Leather jackets", "Hats", "Sunglasses", "Sweaters", "Socks", "Belts", "Gloves", "Vests", "Ties"]; }

  /* ---------- colour: snap the model's hex onto a real photo colour ---------- */
  function lab(hex) {
    var h = String(hex || "").replace("#", ""); if (h.length !== 6) return [50, 0, 0];
    var c = [0, 2, 4].map(function (i) { var u = parseInt(h.slice(i, i + 2), 16) / 255; return u > 0.04045 ? Math.pow((u + 0.055) / 1.055, 2.4) : u / 12.92; });
    var X = (c[0] * 0.4124 + c[1] * 0.3576 + c[2] * 0.1805) / 0.95047, Y = c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722, Z = (c[0] * 0.0193 + c[1] * 0.1192 + c[2] * 0.9505) / 1.08883;
    function f(v) { return v > 0.008856 ? Math.cbrt(v) : 7.787 * v + 16 / 116; }
    return [116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))];
  }
  function dE(a, b) { var A = lab(a), B = lab(b); return Math.sqrt(Math.pow(A[0] - B[0], 2) + Math.pow(A[1] - B[1], 2) + Math.pow(A[2] - B[2], 2)); }
  function hx(r, g, b) { return "#" + [r, g, b].map(function (v) { return ("0" + v.toString(16)).slice(-2); }).join(""); }
  function palette(url, done) {
    var img = new Image();
    img.onload = function () {
      try {
        var sc = Math.min(1, 96 / Math.max(img.width, img.height)), w = Math.max(1, Math.round(img.width * sc)), h = Math.max(1, Math.round(img.height * sc));
        var cv = document.createElement("canvas"); cv.width = w; cv.height = h;
        var cx = cv.getContext("2d"); cx.drawImage(img, 0, 0, w, h);
        var d = cx.getImageData(0, 0, w, h).data, buckets = {};
        for (var y = Math.floor(h * 0.12); y < Math.ceil(h * 0.88); y++) for (var x = Math.floor(w * 0.22); x < Math.ceil(w * 0.78); x++) {
          var i = (y * w + x) * 4, k = (d[i] >> 4) + "," + (d[i + 1] >> 4) + "," + (d[i + 2] >> 4);
          (buckets[k] = buckets[k] || []).push([d[i], d[i + 1], d[i + 2]]);
        }
        var out = [];
        Object.keys(buckets).sort(function (a, b) { return buckets[b].length - buckets[a].length; }).slice(0, 40).forEach(function (k) {
          if (out.length >= 6) return;
          var px = buckets[k], m = [0, 1, 2].map(function (j) { var v = px.map(function (p) { return p[j]; }).sort(function (a, b) { return a - b; }); return v[v.length >> 1]; });
          var c = hx(m[0], m[1], m[2]);
          if (out.every(function (o) { return dE(o.hex, c) > 10; })) out.push({ hex: c, n: px.length });
        });
        done(out);
      } catch (e) { done([]); }
    };
    img.onerror = function () { done([]); };
    img.src = url;
  }
  function snapHex(pal, modelHex) {
    if (!pal || !pal.length || !/^#[0-9a-f]{6}$/i.test(modelHex || "")) return modelHex;
    var best = null, bs = 1e9;
    pal.forEach(function (c) { var sc = dE(c.hex, modelHex) - 0.02 * c.n; if (sc < bs) { bs = sc; best = c; } });
    return best && dE(best.hex, modelHex) < 35 ? best.hex : modelHex;
  }

  /* ---------- brand: a misread label snaps to a brand he already owns ---------- */
  function lev(a, b) {
    var m = a.length, n = b.length, d = [], i, j;
    for (i = 0; i <= m; i++) { d[i] = [i]; }
    for (j = 1; j <= n; j++) d[0][j] = j;
    for (i = 1; i <= m; i++) for (j = 1; j <= n; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    return d[m][n];
  }
  function norm(s) { return String(s || "").toLowerCase().normalize("NFD").replace(/[^a-z0-9]/g, ""); }
  /* his brands: the brand field, else a name's first word when the second
     word varies ("Kiton Olive…", "Kiton Navy…"), else the first two words
     ("Loro Piana …"). Sent to /identify and used for the local snap. */
  function knownBrands() {
    var set = {}, by = {};
    (typeof wardrobeItems !== "undefined" ? wardrobeItems : []).forEach(function (it) {
      if (!it || typeof it !== "object") return;
      if (it.brand) { set[String(it.brand)] = 1; return; }
      var w = String(it.name || "").split(/\s+/).filter(Boolean);
      if (w.length >= 2 && w[0].length >= 2) (by[w[0]] = by[w[0]] || []).push(w[1]);
    });
    Object.keys(by).forEach(function (f) {
      var secs = by[f], uniq = secs.filter(function (x, i) { return secs.indexOf(x) === i; });
      if (secs.length >= 2 && uniq.length > 1) set[f] = 1; else set[f + " " + secs[0]] = 1;
    });
    return Object.keys(set).sort();
  }
  function fixBrand(brand) {
    var b = norm(brand); if (b.length < 3) return brand;
    var best = null, bd = 9;
    knownBrands().forEach(function (k) {
      var n = norm(k); if (n.length < 4) return;
      var dd = n === b ? 0 : lev(n, b);
      if (dd < bd && dd <= Math.max(1, Math.floor(n.length / 4))) { bd = dd; best = k; }
    });
    return best || brand;
  }

  /* ---------- identify ---------- */
  function identify(row) {
    var k = typeof tryonKey === "function" ? tryonKey() : null;
    row.status = "reading"; render(row);
    if (!k || typeof fetch !== "function") { row.status = "manual"; render(row); pump(); return; }
    running++;
    var ctl = typeof AbortController === "function" ? new AbortController() : null;
    var to = setTimeout(function () { if (ctl) ctl.abort(); }, 60000);
    var pal = [];
    /* the photo's own colours (most pixels first) and his brands go with the
       photo, so the server can snap the hex, check the colour family and
       keep brands to ones he owns */
    new Promise(function (res0) { palette(row.photo, function (p) { pal = p || []; res0(); }); })
      .then(function () {
        var brands = knownBrands().slice(0, 80);
        return fetch(TRYON_URL + "/identify", { method: "POST", headers: { "content-type": "application/json", authorization: "Bearer " + k }, body: JSON.stringify({ image: row.photo, palette: pal.map(function (c) { return c.hex; }), brands: brands }), signal: ctl ? ctl.signal : undefined });
      })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { s: r.status, j: j || {} }; }); })
      .then(function (res) {
        if (res.s !== 200 || !res.j.category) { row.status = "manual"; row.code = res.s; return; }
        var j = res.j, brand = j.brand ? fixBrand(j.brand) : "";
        var name = String(j.name || "");
        if (j.brand && brand !== j.brand && name.toLowerCase().indexOf(j.brand.toLowerCase()) === 0) name = brand + name.slice(j.brand.length);
        row.category = cats().indexOf(j.category) !== -1 ? j.category : row.category;
        row.name = name; row.brand = brand; row.colourName = j.colourName || ""; row.modelHex = j.colourHex;
        row.model = j.meta && j.meta.model || "";
        var srvHex = /^#[0-9a-f]{6}$/i.test(j.colourHex || "") && pal.length && j.meta && Array.isArray(j.meta.rules);
        row.colourHex = (srvHex ? j.colourHex : snapHex(pal, j.colourHex)) || "#888888";
      })
      .catch(function () { row.status = "manual"; })
      .then(function () { clearTimeout(to); running--; if (row.status === "reading") row.status = "done"; render(row); pump(); });
  }
  function pump() {
    while (running < BULK_CONC) {
      var next = rows.filter(function (r) { return r.status === "queued"; })[0];
      if (!next) break;
      identify(next);
    }
    renderCount();
  }

  /* ---------- the review batch survives a reload (IndexedDB) ----------
     Each row (photo data URL, fields, status) is mirrored to
     wardrobe-bulk/rows. Add all and × remove rows, so the store only ever
     holds what is still waiting for review. Nothing here syncs. */
  var BDB = null, bdbWait = [], restored = false, saveT = null;
  function bdb(cb) {
    if (BDB) return cb(BDB);
    if (typeof indexedDB === "undefined") return cb(null);
    bdbWait.push(cb); if (bdbWait.length > 1) return;
    function go(db) { BDB = db; var w = bdbWait; bdbWait = []; w.forEach(function (f) { f(db); }); }
    try {
      var rq = indexedDB.open("wardrobe-bulk", 1);
      rq.onupgradeneeded = function () { if (!rq.result.objectStoreNames.contains("rows")) rq.result.createObjectStore("rows", { keyPath: "rid" }); };
      rq.onsuccess = function () { go(rq.result); };
      rq.onerror = function () { go(null); };
    } catch (e) { go(null); }
  }
  function rowRec(r, i) { return { rid: r.rid, ord: i, status: r.status, name: r.name || "", brand: r.brand || "", category: r.category, colourName: r.colourName || "", colourHex: r.colourHex, modelHex: r.modelHex || "", model: r.model || "", code: r.code || 0, photo: r.photo }; }
  function flushRows() {
    return new Promise(function (done) {
      if (!restored) return done(false);
      bdb(function (db) {
        if (!db) return done(false);
        try {
          var tx = db.transaction("rows", "readwrite"), st = tx.objectStore("rows");
          st.clear();
          rows.forEach(function (r, i) { if (r.photo) st.put(rowRec(r, i)); });
          tx.oncomplete = function () { done(true); };
          tx.onerror = tx.onabort = function () { done(false); };
        } catch (e) { done(false); }
      });
    });
  }
  function saveRows() { clearTimeout(saveT); saveT = setTimeout(flushRows, 200); }
  function restoreRows() {
    bdb(function (db) {
      if (!db) { restored = true; return; }
      try {
        var rq = db.transaction("rows", "readonly").objectStore("rows").getAll();
        rq.onsuccess = function () {
          var have = {}; rows.forEach(function (r) { have[r.rid] = 1; });
          /* already added (Add all landed but the clear didn't): skip */
          var added = {}; (typeof wardrobeItems !== "undefined" ? wardrobeItems : []).forEach(function (it) { if (it && it.addedVia === "bulk" && it.originalPhoto) added[it.originalPhoto] = 1; });
          var back = (rq.result || []).filter(function (r) { return r && r.photo && !have[r.rid] && !added[r.photo]; })
            .sort(function (a, b) { return (a.ord || 0) - (b.ord || 0); })
            .map(function (r) { delete r.ord; if (r.status !== "done" && r.status !== "manual") r.status = "queued"; return r; });
          rows = back.concat(rows); restored = true;
          if (back.length) { render(); pump(); } else saveRows();
        };
        rq.onerror = function () { restored = true; };
      } catch (e) { restored = true; }
    });
  }

  /* ---------- review grid ---------- */
  function cardHTML(r) {
    var id = "bk-" + r.rid, reading = r.status === "reading" || r.status === "queued";
    return '<article class="card bulk-card' + (reading ? " is-reading" : "") + '" data-bulk-row="' + esc(r.rid) + '">' +
      '<div class="bulk-ph"><img src="' + esc(r.photo) + '" alt="" />' + (reading ? '<span class="bulk-spin"><span class="analyze-spin" aria-hidden="true"></span></span>' : "") + "</div>" +
      '<div class="bulk-f">' +
      '<input type="text" id="' + id + '-name" data-bk-f="name" aria-label="Name" placeholder="Name" value="' + esc(r.name) + '" />' +
      '<select data-bk-f="category" aria-label="Category">' + cats().map(function (c) { return "<option" + (c === r.category ? " selected" : "") + ">" + esc(c) + "</option>"; }).join("") + "</select>" +
      '<div class="bulk-row"><input type="text" data-bk-f="colourName" aria-label="Colour" placeholder="Colour" value="' + esc(r.colourName) + '" /><input type="color" data-bk-f="colourHex" aria-label="Pick the colour" value="' + esc(/^#[0-9a-f]{6}$/i.test(r.colourHex) ? r.colourHex : "#888888") + '" /></div>' +
      '<input type="text" data-bk-f="brand" aria-label="Brand" placeholder="Brand" value="' + esc(r.brand) + '" />' +
      "</div>" +
      '<button type="button" class="bulk-x" data-bulk-drop aria-label="Remove">×</button></article>';
  }
  function render(row) {
    var grid = document.getElementById("bulk-grid");
    if (!grid) return;
    if (row) {
      var el = grid.querySelector('[data-bulk-row="' + row.rid + '"]');
      if (el) { var tmp = document.createElement("div"); tmp.innerHTML = cardHTML(row); el.parentNode.replaceChild(tmp.firstChild, el); renderCount(); return; }
    }
    grid.innerHTML = rows.map(cardHTML).join("");
    renderCount();
  }
  /* Add all rides just above the fixed bottom nav */
  function placeBar() {
    var bb = document.getElementById("bottombar"), bar = document.querySelector("#panel-bulk .bulk-bar");
    if (!bb || !bar) return;
    if (document.documentElement.classList.contains("nav-away")) return; /* .78.2b: bar tucked; keep the last spot */
    var r = bb.getBoundingClientRect(), top = r.height ? r.top : window.innerHeight;
    var sn = document.getElementById("sync-note");
    if (sn && !sn.hidden && getComputedStyle(sn).display !== "none" && getComputedStyle(sn).visibility !== "hidden") { var q = sn.getBoundingClientRect(); if (q.height && q.top < top && q.bottom > top - 40) top = q.top - 6; }
    bar.style.bottom = Math.max(0, Math.round(window.innerHeight - top)) + "px";
  }
  window.addEventListener("resize", placeBar);
  setInterval(function () { if (typeof currentTab !== "undefined" && currentTab === "bulk") placeBar(); }, 1000);
  function renderCount() {
    placeBar(); saveRows();
    var busy = rows.filter(function (r) { return r.status === "reading" || r.status === "queued" || r.status === "scaling"; }).length;
    var ready = rows.filter(function (r) { return r.status === "done" || r.status === "manual"; }).length;
    var c = document.getElementById("bulk-count");
    if (c) c.textContent = rows.length ? (busy ? "Reading " + (rows.length - busy) + " of " + rows.length : ready + (ready === 1 ? " piece" : " pieces")) : "";
    var b = document.getElementById("bulk-add-all");
    if (b) { b.disabled = !!busy || !ready; b.textContent = ready && !busy ? "Add all " + ready : "Add all"; }
    var rs = document.getElementById("bulk-resume");
    if (rs) { rs.hidden = !rows.length; rs.textContent = rows.length ? "Review " + rows.length + (rows.length === 1 ? " piece" : " pieces") : ""; }
  }
  function rowOf(el) { var c = el && el.closest ? el.closest("[data-bulk-row]") : null; var id = c && c.getAttribute("data-bulk-row"); return rows.filter(function (r) { return r.rid === id; })[0] || null; }

  function addFiles(files) {
    files = Array.prototype.slice.call(files || []).filter(function (f) { return !f.type || f.type.indexOf("image/") === 0; }).slice(0, BULK_MAX);
    if (!files.length) return;
    var fresh = files.map(function (f) { return { rid: "r" + (++seq) + "-" + Date.now().toString(36), file: f, status: "scaling", name: "", brand: "", category: "Shirts", colourName: "", colourHex: "#888888", photo: "" }; });
    rows = rows.concat(fresh);
    if (typeof switchTab === "function") switchTab("bulk");
    render();
    /* scale one at a time — a big pick must not hold 40 full photos in memory */
    (function next(i) {
      if (i >= fresh.length) return;
      var r = fresh[i];
      processPhotoFile(r.file, function (url) {
        r.file = null;
        if (!url) { rows = rows.filter(function (x) { return x !== r; }); render(); if (typeof toast === "function") toast("A photo couldn't be read — it was skipped."); }
        else { r.photo = url; r.status = "queued"; render(r); pump(); }
        next(i + 1);
      });
    })(0);
  }
  function addAll() {
    var ready = rows.filter(function (r) { return (r.status === "done" || r.status === "manual") && String(r.name || "").trim(); });
    if (!ready.length) { if (typeof toast === "function") toast("Give each piece a name first."); return; }
    var base = Date.now();
    ready.forEach(function (r, ix) {
      var name = String(r.name).trim(), brand = String(r.brand || "").trim();
      if (brand && name.toLowerCase().indexOf(brand.toLowerCase()) !== 0) name = brand + " " + name;
      var colourHex = /^#[0-9a-f]{6}$/i.test(r.colourHex) ? r.colourHex : "#232d3f";
      var colourName = String(r.colourName || "").trim();
      var wada = nearestWada(colourHex);
      wardrobeItems.unshift({
        id: "item-" + base + "-b" + ix,
        name: name,
        category: cats().indexOf(r.category) !== -1 ? r.category : "Shirts",
        colourName: colourName || wada.name,
        colourHex: colourHex,
        extraColours: colourName ? [{ name: "Nearest Wada: " + wada.name, hex: wada.hex }] : [],
        notes: "",
        price: null,
        wearCount: 0,
        lastWorn: null,
        addedISO: localTodayISO(),
        laundry: false,
        photo: r.photo,
        originalPhoto: r.photo,
        needsStudio: true,
        brand: brand || undefined,
        addedVia: "bulk"
      });
    });
    var kept = persistAll();
    var n = ready.length;
    rows = rows.filter(function (r) { return ready.indexOf(r) === -1; });
    clearTimeout(saveT); flushRows();
    render();
    if (typeof wardFilter !== "undefined") { wardFilter = "All"; if (typeof syncWardCatLabels === "function") syncWardCatLabels(); }
    if (typeof renderWardrobe === "function") renderWardrobe();
    if (typeof toast === "function") toast(kept ? "Added " + n + (n === 1 ? " piece." : " pieces.") : "Added — storage full, not kept. Export a backup from Profile.");
    if (!rows.length && typeof switchTab === "function") switchTab("wardrobe");
  }

  var input = document.getElementById("bulk-photos");
  if (input) input.addEventListener("change", function () { var f = this.files; addFiles(f); this.value = ""; });
  document.addEventListener("click", function (ev) {
    var t = ev.target; if (!t || !t.closest) return;
    if (t.closest("#bulk-resume")) { if (typeof switchTab === "function") switchTab("bulk"); render(); return; }
    if (t.closest("#bulk-add-all")) { addAll(); return; }
    if (t.closest("[data-bulk-drop]")) { var r = rowOf(t); if (r) { rows = rows.filter(function (x) { return x !== r; }); render(); clearTimeout(saveT); flushRows(); } return; }
  });
  function onField(ev) {
    var t = ev.target; if (!t || !t.getAttribute) return;
    var f = t.getAttribute("data-bk-f"); if (!f) return;
    var r = rowOf(t); if (r) { r[f] = t.value; saveRows(); }
  }
  document.addEventListener("input", onField);
  document.addEventListener("change", onField);
  window.bulkAddFiles = addFiles;
  window.addEventListener("pagehide", function () { if (saveT) { clearTimeout(saveT); flushRows(); } });
  window.bulkFlush = function () { clearTimeout(saveT); return flushRows(); };
  window.bulkRestored = function () { return restored; };
  window.bulkBrands = knownBrands;
  restoreRows();
  window.bulkState = function () { return rows.map(function (r) { return { rid: r.rid, status: r.status, name: r.name, brand: r.brand, category: r.category, colourName: r.colourName, colourHex: r.colourHex, modelHex: r.modelHex, model: r.model, code: r.code }; }); };
  window.studioQueue78 = function () { return (typeof wardrobeItems !== "undefined" ? wardrobeItems : []).filter(function (i) { return i && i.needsStudio; }).map(function (i) { return i.id; }); };
  window.bulkSnapHex = snapHex; window.bulkPalette = palette; window.bulkFixBrand = fixBrand;
})();
    