
/* ================= See it on me — in-app try-on (build .76) =================
   Puts a product, a product with his own clothes, or a whole built
   look onto his standing studio template through the wardrobe-tryon
   worker (FASHN Try-On Max; one garment per step, chained server-
   side). Same Bearer sync key as wardrobe-sync; the worker caps
   garments per day and returns a cached job for a repeat request,
   and this device also remembers every finished render by request
   hash so a repeat tap never posts at all. When a try-on cannot run
   the nearest pre-rendered on-body outfit is shown instead. */
var TRYON_URL = "https://wardrobe-tryon.dyacobs.workers.dev";
try { TRYON_URL = localStorage.getItem("wardrobe.tryonurl") || TRYON_URL; } catch (e) {}
var tryonRun = 0;
var TRYON_SLOT = { top: "top", layer: "outer", outer: "outer", bottom: "bottom", shoes: "shoes", accessory: "accessory" };
var TRYON_ORDER = { under: 0, top: 1, outer: 2, bottom: 3, accessory: 4, shoes: 5 };
function tryonKey() { try { return (typeof SY !== "undefined" && SY && SY.key) ? SY.key : null; } catch (e) { return null; } }
function tryonEl(id) { return document.getElementById(id); }
function tryonHash(s) {
  var h1 = 0x811c9dc5, h2 = 0x01000193 ^ s.length;
  for (var i = 0; i < s.length; i++) { var c = s.charCodeAt(i); h1 = Math.imul(h1 ^ c, 16777619); h2 = Math.imul(h2 ^ c, 2246822507); }
  return ((h1 >>> 0).toString(16) + (h2 >>> 0).toString(16));
}
var tryonCache = {};
try { tryonCache = JSON.parse(localStorage.getItem("wardrobe.tryoncache") || "{}") || {}; } catch (e) { tryonCache = {}; }
function tryonCacheKey(items) {
  return tryonHash(items.map(function (it) { return it.slot + "=" + tryonHash(String(it.image)); }).join("&"));
}
function tryonCachePut(k, url) {
  tryonCache[k] = { u: url, t: Date.now() };
  var ks = Object.keys(tryonCache);
  if (ks.length > 300) ks.sort(function (a, b) { return tryonCache[a].t - tryonCache[b].t; }).slice(0, ks.length - 300).forEach(function (x) { delete tryonCache[x]; });
  try { localStorage.setItem("wardrobe.tryoncache", JSON.stringify(tryonCache)); } catch (e) {}
}
/* An image the worker can read: data URIs pass through, vault and
   blob references are read on this device, the app's own files are
   read in the page, retailer images go as https URLs. */
function tryonImageRef(img) {
  if (!img || typeof img !== "string") return Promise.resolve(null);
  if (img.indexOf("data:image/") === 0) return Promise.resolve(img);
  if (img.indexOf("idb:") === 0) {
    var pv = window.photoVault;
    if (!pv || !pv.fetch) return Promise.resolve(null);
    if (pv.cache && pv.cache[img.slice(4)]) return tryonImageRef(pv.cache[img.slice(4)]);
    return new Promise(function (res) { try { pv.fetch(img.slice(4), function (d) { res(d ? tryonImageRef(d) : null); }); } catch (e) { res(null); } });
  }
  if (/^blob:[0-9a-f]{16,}/.test(img) && window.blobStore && window.blobStore.fetch) {
    var bs = window.blobStore;
    return new Promise(function (res) { try { bs.fetch(img.slice(5), function (d) { res(d ? tryonImageRef(d) : null); }); } catch (e) { res(null); } });
  }
  function inPage(src) {
    return fetch(src).then(function (r) { if (!r.ok) throw new Error("http " + r.status); return r.blob(); }).then(function (b) {
      return new Promise(function (res) { var fr = new FileReader(); fr.onload = function () { res(String(fr.result)); }; fr.onerror = function () { res(null); }; fr.readAsDataURL(b); });
    }).catch(function () { return null; });
  }
  if (img.indexOf("blob:") === 0) return inPage(img);
  try {
    var u = new URL(img, location.href);
    if (u.origin === location.origin) return inPage(u.toString());
    if (u.protocol !== "https:") return Promise.resolve(null);
    return Promise.resolve(u.toString());
  } catch (e) { return Promise.resolve(null); }
}
/* Closet category -> outfit slot (layer / top / bottom / shoes). */
function closetSlot76(cat) {
  var c = String(cat || "").toLowerCase();
  if (/blazer|jacket|coat|vest|gilet|suit|outer|overshirt|cardigan/.test(c)) return "layer";
  if (/shoe|sneaker|boot|loafer|trainer|sandal|mule|espadrille|driver/.test(c)) return "shoes";
  if (/trouser|jean|short|chino|pant|swim|bathing/.test(c)) return "bottom";
  if (/shirt|button|tee|t-shirt|polo|sweater|knit|top|henley|crew/.test(c)) return "top";
  return null;
}
function tryonSlotForEntry(e) {
  var m = (typeof BUILD_CAT_MAP !== "undefined") ? BUILD_CAT_MAP[e.cat] : null;
  if (m && TRYON_SLOT[m[1]]) return TRYON_SLOT[m[1]];
  if (e.category) { var cs = closetSlot76(e.category); if (cs) return TRYON_SLOT[cs]; }
  var c = (typeof linkClassify === "function") ? linkClassify((e.name || "") + " " + (e.category || e.cat || "")) : ["", ""];
  var cat = c[0];
  if (cat === "blazer" || cat === "suit" || cat === "outerwear") return "outer";
  if (cat === "trousers" || cat === "jeans" || cat === "shorts" || cat === "swim") return "bottom";
  if (cat === "shoes") return "shoes";
  if (cat === "belt" || cat === "tie") return "accessory";
  return "top";
}
function tryonEntryName(e) { return ((e.brand ? e.brand + " " : "") + (e.name || "")).trim().slice(0, 120); }
function tryonEntryItems(e) {
  return tryonImageRef(e.img).then(function (ref) {
    if (!ref) return [];
    return [{ slot: tryonSlotForEntry(e), image: ref, name: tryonEntryName(e) }];
  });
}
/* His own photographed pieces (never built-in seed pieces unless he
   has none), by slot. */
function tryonClosetPool() {
  var own = (typeof homeOwnedPhotoPieces742 === "function") ? homeOwnedPhotoPieces742() : { own: [], withPhoto: [] };
  var list = own.own.length ? own.own : own.withPhoto;
  var by = { layer: [], top: [], bottom: [], shoes: [] };
  list.forEach(function (it) { var s = closetSlot76(it.category); if (s && by[s]) by[s].push(it); });
  return by;
}
function hexRGB76(h) {
  var m = /^#?([0-9a-f]{6})$/i.exec(String(h || "").trim());
  if (!m) return null;
  var n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function hexDist76(a, b) {
  var x = hexRGB76(a), y = hexRGB76(b);
  if (!x || !y) return 300;
  return Math.sqrt(Math.pow(x[0] - y[0], 2) + Math.pow(x[1] - y[1], 2) + Math.pow(x[2] - y[2], 2));
}
/* The nearest pre-rendered on-body outfit: most closet pieces in
   common first, then a piece in the wanted slot close in colour. */
function tryonNearestOnbody(closetIds, wantSlot, wantHex) {
  if (typeof ONBODY === "undefined" || !ONBODY.map) return null;
  var want = {};
  (closetIds || []).forEach(function (id) { if (id) want[id] = 1; });
  var best = null, bestScore = 0;
  Object.keys(ONBODY.map).forEach(function (k) {
    var ids = k.split("|"), score = 0, known = 0;
    ids.forEach(function (id) {
      var it = (typeof closetItemById === "function") ? closetItemById(id) : null;
      if (it) known++;
      if (want[id]) score += 10;
      if (wantSlot && it && closetSlot76(it.category) === wantSlot) score += 3 + Math.max(0, 2 - hexDist76(it.colourHex, wantHex) / 120);
    });
    if (!known) return;
    if (score > bestScore) { bestScore = score; best = ONBODY.map[k]; }
  });
  return best;
}
/* Product + his own clothes: the product in its slot, the rest of
   a complete outfit from his closet — the pieces of the nearest
   rendered outfit when there is one, so the pairing is one he has
   already seen on himself. */
function tryonWithClosetPieces(e) {
  var slot = tryonSlotForEntry(e);
  var mine = slot === "outer" ? "layer" : slot;
  var pool = tryonClosetPool();
  var need = mine === "layer" ? ["top", "bottom"] : mine === "top" ? ["bottom", "shoes"] : mine === "bottom" ? ["top", "shoes"] : mine === "shoes" ? ["top", "bottom"] : ["top", "bottom"];
  var hex = (typeof buildShopColour === "function") ? buildShopColour(e).hex : null;
  var picked = {};
  var ob = tryonNearestOnbody([], mine, hex);
  if (ob && typeof ONBODY !== "undefined") {
    Object.keys(ONBODY.map).forEach(function (k) {
      if (ONBODY.map[k] !== ob) return;
      k.split("|").forEach(function (id) {
        var it = closetItemById(id), s = it ? closetSlot76(it.category) : null;
        if (it && it.photo && s && need.indexOf(s) !== -1 && !picked[s]) picked[s] = it;
      });
    });
  }
  need.forEach(function (s) { if (!picked[s] && pool[s] && pool[s].length) picked[s] = pool[s][0]; });
  return need.map(function (s) { return picked[s]; }).filter(Boolean);
}
function tryonPiecesItems(products, closetPieces) {
  var jobs = [];
  (products || []).forEach(function (p) { jobs.push(tryonImageRef(p.img).then(function (ref) { return ref ? { slot: tryonSlotForEntry(p), image: ref, name: tryonEntryName(p) } : null; })); });
  (closetPieces || []).forEach(function (it) {
    var s = TRYON_SLOT[closetSlot76(it.category)] || "top";
    jobs.push(tryonImageRef(it.photo).then(function (ref) { return ref ? { slot: s, image: ref, name: String(it.name || "").slice(0, 120) } : null; }));
  });
  return Promise.all(jobs).then(function (xs) {
    var out = xs.filter(Boolean), seen = {};
    out = out.filter(function (x) { if (seen[x.slot]) return false; seen[x.slot] = 1; return true; });
    out.sort(function (a, b) { return (TRYON_ORDER[a.slot] || 0) - (TRYON_ORDER[b.slot] || 0); });
    return out;
  });
}
function tryonLookPieces(look) {
  var out = [];
  if (!look) return out;
  if (look.swapPieces && typeof PIECE_BY_ID !== "undefined") {
    var ids = Array.isArray(look.swapPieces) ? look.swapPieces : Object.keys(look.swapPieces).map(function (k) { return look.swapPieces[k]; });
    ids.forEach(function (id) {
      var pc = PIECE_BY_ID[id];
      if (pc && pc.img && TRYON_SLOT[pc.slot]) out.push({ slot: TRYON_SLOT[pc.slot], img: pc.img, name: pc.name || "" });
    });
  }
  if (!out.length && look.fwPieces) {
    look.fwPieces.forEach(function (p) {
      var it = (p && p.id && typeof closetItemById === "function") ? closetItemById(p.id) : null;
      var ph = (it && it.photo) || (p && p.photo);
      var s = closetSlot76((it && it.category) || (p && p.category));
      if (ph && s) out.push({ slot: TRYON_SLOT[s], img: ph, name: (it && it.name) || p.name || "", id: p.id });
    });
  }
  return out;
}
function tryonSyncLookBtn(look) {
  var b = tryonEl("tryon-look-btn");
  if (b) b.hidden = !tryonLookPieces(look).length;
}
function tryonLookItems(look) {
  var pcs = tryonLookPieces(look);
  return Promise.all(pcs.map(function (pc) { return tryonImageRef(pc.img); })).then(function (refs) {
    var items = [], seen = {};
    refs.forEach(function (ref, i) { if (ref && !seen[pcs[i].slot]) { seen[pcs[i].slot] = 1; items.push({ slot: pcs[i].slot, image: ref, name: pcs[i].name || "" }); } });
    items.sort(function (a, b) { return (TRYON_ORDER[a.slot] || 0) - (TRYON_ORDER[b.slot] || 0); });
    return items;
  });
}
function tryonErrorText(status, body) {
  var err = body && body.error;
  if (status === 401) return "Turn on sync in Profile first — try-on uses the same account.";
  if (err === "not_configured") return "Try-on isn't switched on yet. It will work as soon as the render service is connected.";
  if (err === "daily_cap") return "That's today's try-on limit. It resets overnight.";
  if (err === "garment_image") return "Couldn't read that product's photo. Try another listing.";
  if (body && body.message) return body.message;
  return "Couldn't render that right now. Try again in a minute.";
}
/* The job runner shared by the sheet and the Build page.
   onState(state, text, url): state is loading | done | error. */
function tryonJob(itemsPromise, onState, isLive) {
  var started = Date.now();
  function live() { return !isLive || isLive(); }
  function stepText(j) {
    if (!j || j.steps <= 1) return "Putting it on you… about 20 seconds.";
    return "Dressing you — piece " + Math.max(1, j.step) + " of " + j.steps + "…";
  }
  Promise.resolve(itemsPromise).then(function (items) {
    if (!live()) return;
    if (!items || !items.length) { onState("error", "There's no photo of this piece to try on yet."); return; }
    items = items.slice(0, 6);
    var ck = tryonCacheKey(items);
    if (tryonCache[ck] && tryonCache[ck].u) { onState("done", "", tryonCache[ck].u, true); return; }
    var key = tryonKey();
    if (!key) { onState("error", tryonErrorText(401)); return; }
    var headers = { "authorization": "Bearer " + key, "content-type": "application/json" };
    function finish(j) { tryonCachePut(ck, j.resultUrl); onState("done", "", j.resultUrl); }
    function poll(id) {
      if (!live()) return;
      if (Date.now() - started > 8 * 60 * 1000) { onState("error", "This one is taking too long. Try again later."); return; }
      fetch(TRYON_URL + "/tryon/" + id, { headers: { "authorization": "Bearer " + key } })
        .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
        .then(function (x) {
          if (!live()) return;
          if (x.status !== 200) { onState("error", tryonErrorText(x.status, x.body)); return; }
          var j = x.body;
          if (j.status === "done" && j.resultUrl) { finish(j); return; }
          if (j.status === "failed") { onState("error", j.note || "Couldn't render that one."); return; }
          onState("loading", stepText(j));
          setTimeout(function () { poll(id); }, 3000);
        })
        .catch(function () { if (live()) setTimeout(function () { poll(id); }, 5000); });
    }
    onState("loading", stepText({ steps: items.length, step: 1 }));
    return fetch(TRYON_URL + "/tryon", { method: "POST", headers: headers, body: JSON.stringify({ items: items }) })
      .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
      .then(function (x) {
        if (!live()) return;
        if (x.status !== 200 && x.status !== 202) { onState("error", tryonErrorText(x.status, x.body)); return; }
        var j = x.body;
        if (j.status === "done" && j.resultUrl) { finish(j); return; }
        if (j.status === "failed") { onState("error", j.note || "Couldn't render that one."); return; }
        onState("loading", stepText(j));
        setTimeout(function () { poll(j.id); }, 2500);
      });
  }).catch(function () { if (live()) onState("error", "No connection — try again when you're online."); });
}
function tryonShow(state, text) {
  var wait = tryonEl("tryon-wait"), img = tryonEl("tryon-img"), act = tryonEl("tryon-actions");
  tryonEl("tryon-status").textContent = text || "";
  var spin = wait.querySelector(".analyze-spin");
  if (spin) spin.hidden = state !== "loading";
  wait.hidden = state === "done";
  img.hidden = state !== "done";
  act.hidden = state !== "done";
}
function tryonClose() {
  tryonRun++;
  var s = tryonEl("tryon-sheet");
  if (s) s.hidden = true;
}
var tryonCurrent = null;
/* opts: { buyUrl, product (an entry: enables "With my clothes"),
           closetIds + slot + hex (for the on-body fallback) } */
function tryonStart(itemsPromise, title, buyUrl, opts) {
  opts = opts || {};
  var run = ++tryonRun;
  tryonCurrent = opts;
  var sheet = tryonEl("tryon-sheet");
  tryonEl("tryon-title").textContent = "On you";
  tryonEl("tryon-sub").textContent = title || "";
  var buy = tryonEl("tryon-buy");
  if (buyUrl) { buy.href = buyUrl; buy.hidden = false; } else { buy.hidden = true; buy.removeAttribute("href"); }
  var withMine = tryonEl("tryon-withmine");
  if (withMine) withMine.hidden = !(opts.product && !opts.withCloset);
  var note = tryonEl("tryon-note");
  if (note) { note.hidden = true; note.textContent = ""; }
  tryonEl("tryon-img").removeAttribute("src");
  tryonShow("loading", "Getting ready…");
  sheet.hidden = false;
  function showImg(url, fallback) {
    var img = tryonEl("tryon-img");
    img.onload = function () { if (run === tryonRun) tryonShow("done"); };
    img.onerror = function () { if (run === tryonRun) tryonShow("error", "The render finished but couldn't load. Try again."); };
    img.alt = (fallback ? "Closest outfit on you" : "You wearing ") + (fallback ? "" : (title || "this"));
    img.src = url;
    tryonEl("tryon-open").href = url;
  }
  tryonJob(itemsPromise, function (state, text, url) {
    if (state === "done") { showImg(url, false); if (opts.onDone) opts.onDone(url); return; }
    if (state === "error") {
      var fb = opts.noFallback ? null : tryonNearestOnbody(opts.closetIds || [], opts.slot || null, opts.hex || null);
      tryonShow("error", text);
      if (fb) {
        if (note) { note.textContent = text + " Closest look on you:"; note.hidden = false; }
        showImg(fb, true);
      }
      return;
    }
    tryonShow(state, text);
  }, function () { return run === tryonRun; });
}
function tryonForEntry(e, withCloset) {
  if (!e) return;
  var slot = tryonSlotForEntry(e), mine = slot === "outer" ? "layer" : slot;
  var hex = (typeof buildShopColour === "function") ? buildShopColour(e).hex : null;
  var pieces = withCloset ? tryonWithClosetPieces(e) : [];
  var title = tryonEntryName(e) + (pieces.length ? " with " + pieces.map(function (p) { return p.name; }).join(", ") : "");
  tryonStart(withCloset ? tryonPiecesItems([e], pieces) : tryonEntryItems(e), title, e.url, {
    product: e, withCloset: !!withCloset, slot: mine, hex: hex,
    closetIds: pieces.map(function (p) { return p.id; })
  });
}
document.addEventListener("click", function (e) {
  var t = e.target;
  if (!t || !t.closest) return;
  if (t.closest("#tryon-close") || t.id === "tryon-sheet") { tryonClose(); return; }
  if (t.closest("#tryon-withmine")) { if (tryonCurrent && tryonCurrent.product) tryonForEntry(tryonCurrent.product, true); return; }
  var b;
  if ((b = t.closest("[data-tryon-shop]"))) {
    tryonForEntry((typeof buildEntryByKey === "function") ? buildEntryByKey(b.getAttribute("data-tryon-shop")) : null, false);
    e.stopPropagation(); return;
  }
  if ((b = t.closest("[data-tryon-wish]"))) {
    tryonForEntry((typeof wishlistFor === "function") ? wishlistFor(b.getAttribute("data-tryon-wish")) : null, false);
    e.stopPropagation(); return;
  }
  if ((b = t.closest("[data-tryon-sale]"))) {
    tryonForEntry((typeof SALE_ITEMS !== "undefined") ? SALE_ITEMS[parseInt(b.getAttribute("data-tryon-sale"), 10)] : null, false);
    e.stopPropagation(); return;
  }
  if (t.closest("#tryon-look-btn")) {
    var lk = (typeof currentLook !== "undefined") ? currentLook : null;
    if (lk) {
      var ids = tryonLookPieces(lk).map(function (p) { return p.id; }).filter(Boolean);
      tryonStart(tryonLookItems(lk), lk.title || "This look", null, { closetIds: ids });
    }
    e.stopPropagation(); return;
  }
}, true);
document.addEventListener("keydown", function (e) {
  var s = tryonEl("tryon-sheet");
  if (e.key === "Escape" && s && !s.hidden) tryonClose();
});
    