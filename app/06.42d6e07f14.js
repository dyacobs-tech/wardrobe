
/* ================= Build .73 — endless closet outfits: app glue =================
   Ideas: in Wardrobe mode the grid IS the endless closet feed
   (infinite scroll, Shuffle, Like / Dislike per card); in Combo
   mode the same feed runs under the six combo takes; Inspo mode
   never shows closet pieces. Home: Wardrobe mode deals the outfit
   of the day from the composer (buildClosetLooks hands off to it),
   shown as a flat-lay of his own cleaned item photos with the
   watch. Verdicts feed the composer's weights. */
(function closetComposer73() {
  if (!window.WardrobeComposer || typeof composerLooks !== "function") return;

  /* Piece photos are never "looks": a verdict path that resolves a
     closet look to its first piece photo must not ban that photo
     (it would hide the item's own picture app-wide). */
  if (typeof recordDislike === "function") {
    var _recordDislike73 = recordDislike;
    recordDislike = function (img) {
      if (typeof img === "string" && (img.indexOf("data:") === 0 || img.indexOf("blob:") === 0 || img.indexOf("idb:") === 0)) img = null;
      return _recordDislike73(img);
    };
  }
  if (typeof likeLook === "function") {
    var _likeLook73 = likeLook;
    likeLook = function (look) {
      var ok = _likeLook73(look);
      if (ok && look && look.composer) composerVerdict(look, "like");
      return ok;
    };
  }

  function watchFor(look) {
    try {
      var r = (typeof resolveWatch === "function") ? resolveWatch(look) : null;
      return r && r.state === "watch" && r.watch ? r.watch : null;
    } catch (e) { return null; }
  }
  function itemPhoto(p) {
    var it = (typeof closetItemById === "function" && p.id) ? closetItemById(p.id) : null;
    return (it && it.photo) || p.photo || null;
  }
  /* The flat-lay: every piece's own cleaned photograph on cream,
     outer layer first, then top, bottom, shoes, the watch last. */
  function flatlayHTML(look, withWatch) {
    var ob = (typeof onbodyForLook === "function") ? onbodyForLook(look) : null;
    var cells = (look.fwPieces || []).map(function (p) {
      var ph = itemPhoto(p);
      /* Build .74.2: every synced closet photo is held as a vault
         reference ("idb:<key>", or a "blob:<sha>" sync ref) after a
         reload. Those used to fall through to a colour block, so
         his studio photos never reached Home. Resolve from memory
         when cached; otherwise emit the reference — the vault and
         blob observers swap the bytes in, exactly as the Closet
         grid does. */
      if (ph && ph.indexOf("idb:") === 0) {
        var pvh = window.photoVault;
        var hit = pvh && pvh.cache ? pvh.cache[ph.slice(4)] : undefined;
        if (hit) ph = hit;
        else if (pvh && pvh.fetch) { try { pvh.fetch(ph.slice(4), function () {}); } catch (e) {} }
      } else if (ph && /^blob:[0-9a-f]{16,}/.test(ph)) {
        var bsh = window.blobStore;
        var bhit = bsh && bsh.cache ? bsh.cache[ph.slice(5)] : undefined;
        if (bhit) ph = bhit;
      }
      if (ph) return '<span class="fl-cell"><img src="' + esc(ph) + '" alt="' + esc(p.name || "") + '" decoding="async" /></span>';
      return '<span class="fl-cell fl-swatch" style="background:' + esc(p.colourHex || "#d9cfbd") + '" role="img" aria-label="' + esc(p.name || "") + '"></span>';
    });
    var w = withWatch ? watchFor(look) : null;
    if (w && w.photo) cells.push('<span class="fl-cell fl-watch"><img src="' + esc(w.photo) + '" alt="' + esc(w.name || "") + '" loading="lazy" decoding="async" /></span>');
    if (ob) {
      /* Build .75: David wearing it, with the pieces beside him. */
      var side = cells.filter(function (c) { return c.indexOf("fl-swatch") === -1; }).slice(0, 4);
      return '<span class="flatlay onbody-split ob-n' + side.length + '"><span class="ob-figure"><img src="' + esc(ob) + '" alt="' + esc((look.title || "Outfit") + " on David") + '" data-onbody="1" decoding="async" /></span>' +
        '<span class="ob-pieces">' + side.join("") + "</span></span>";
    }
    return '<span class="flatlay fl-n' + cells.length + '">' + cells.join("") + "</span>";
  }
  window.composerFlatlayHTML = flatlayHTML;

  /* The look layer: a composed look's media is its flat-lay, never
     its first piece standing in for the outfit. */
  if (typeof lookCardHTML === "function") {
    var _lookCardHTML73 = lookCardHTML;
    lookCardHTML = function (look) {
      var html = _lookCardHTML73.apply(this, arguments);
      if (!look || !look.composer || look.fwRender) return html;
      var m = html.indexOf("look-media");
      if (m === -1) return html;
      var a = html.indexOf("<img ", m);
      if (a === -1) return html;
      var b = html.indexOf(">", a);
      if (b === -1) return html;
      return html.slice(0, a) + '<span class="cf-media layer-flatlay">' + flatlayHTML(look, true) + "</span>" + html.slice(b + 1);
    };
  }

  /* ---------- Home ---------- */
  if (typeof renderToday === "function") {
    var _renderToday73 = renderToday;
    renderToday = function () {
      _renderToday73();
      if (!todayLook || !todayLook.composer || todayLook.fwRender) {
        var c0 = document.getElementById("today-collage");
        if (c0) c0.classList.remove("flatlay-host");
        return;
      }
      var img = document.getElementById("today-img");
      var collage = document.getElementById("today-collage");
      if (img) img.hidden = true;
      if (collage) {
        collage.innerHTML = flatlayHTML(todayLook, true);
        collage.classList.add("flatlay-host");
        collage.hidden = false;
      }
      composerMarkSeen([todayLook]);
    };
  }
  /* Hero Dislike on a closet look: the pairing is dropped from the
     composer and the next look deals — no photo ban, no Recently
     removed entry carrying piece photos. */
  var heroDislike = document.getElementById("today-dislike");
  if (heroDislike) heroDislike.addEventListener("click", function (e) {
    if (!todayLook || !todayLook.composer) return;
    e.stopImmediatePropagation();
    composerVerdict(todayLook, "dislike");
    if (typeof dealAnotherToday === "function") dealAnotherToday();
  }, true);
  /* Verdicts inside the look layer. */
  document.addEventListener("click", function (e) {
    var v = e.target.closest ? e.target.closest("[data-verdict]") : null;
    if (!v || typeof currentLook === "undefined" || !currentLook || !currentLook.composer) return;
    composerVerdict(currentLook, v.getAttribute("data-verdict") === "dislike" ? "dislike" : "like");
  }, true);

  /* ---------- Ideas feed ---------- */
  var result = document.getElementById("look-result");
  var mineHost = document.getElementById("outfits-mine-view");
  if (!result && !mineHost) return;
  var feed = document.createElement("section");
  feed.className = "closet-feed";
  feed.id = "closet-feed";
  feed.hidden = true;
  feed.setAttribute("aria-label", "From your closet");
  feed.innerHTML = '<div class="cf-head"><h3 class="fav-head">From your closet</h3><button type="button" class="btn-ghost" id="cf-shuffle">Shuffle</button></div>' +
    '<div class="options-grid cf-grid" id="cf-grid" role="list"></div><div class="cf-sentinel" id="cf-sentinel" aria-hidden="true"></div>';
  if (mineHost) mineHost.insertBefore(feed, mineHost.firstChild);
  else result.parentNode.insertBefore(feed, result.nextSibling);
  var grid = feed.querySelector("#cf-grid");
  var sentinel = feed.querySelector("#cf-sentinel");
  var feedLooks = [];
  var feedSig = null;
  function feedLevel() { return (typeof studioTypeAny !== "undefined" && studioTypeAny) ? null : ((typeof formalityLevel !== "undefined") ? formalityLevel : 4); }
  function feedWanted() {
    if (typeof currentTab !== "undefined" && currentTab === "looks") {
      return window.outfitsMode !== "inspo";
    }
    var src = (typeof studioSource !== "undefined") ? studioSource : "combo";
    return src === "wardrobe" || src === "combo";
  }
  function stateSig() { return [studioSource, feedLevel(), composerDeckCache.sig ? composerDeckCache.sig.length : 0, (typeof wardrobeItems !== "undefined" ? wardrobeItems.length : 0)].join("/"); }
  function cardHTML(look, idx) {
    return '<article class="card option-card cf-card" role="listitem" data-cf-idx="' + idx + '">' +
      '<button type="button" class="cf-media" data-cf-open="' + idx + '" aria-label="' + esc(look.title) + '">' + flatlayHTML(look, true) + "</button>" +
      '<span class="oc-body"><span class="oc-title">' + esc(look.title) + "</span></span>" +
      '<span class="cf-actions"><button type="button" class="chip" data-cf-like="' + idx + '" aria-pressed="' + (look.verdict === "like" ? "true" : "false") + '">Like</button>' +
      '<button type="button" class="chip" data-cf-dislike="' + idx + '" aria-pressed="false">Dislike</button></span>' +
      "</article>";
  }
  function appendLooks(n) {
    var exclude = feedLooks.map(function (l) { return l.composerKey; });
    var feedPool = (typeof homeOwnedPhotoPieces742 === "function") ? homeOwnedPhotoPieces742() : null;
    var feedOnly = feedPool ? (feedPool.own.length >= 3 ? feedPool.own : feedPool.withPhoto) : null;
    var looks = composerLooks({ count: n, level: feedLevel(), exclude: exclude, only: feedOnly && feedOnly.length >= 3 ? feedOnly : null, slot: "feed", renderedFirst: true, temp: (typeof currentWeather !== "undefined" && currentWeather && typeof currentWeather.temp === "number") ? currentWeather.temp : undefined });
    if (!looks.length) return 0;
    var html = "";
    looks.forEach(function (l) { html += cardHTML(l, feedLooks.length); feedLooks.push(l); });
    grid.insertAdjacentHTML("beforeend", html);
    composerMarkSeen(looks);
    return looks.length;
  }
  function resetFeed() {
    feedLooks = [];
    grid.innerHTML = "";
    feedSig = stateSig();
    appendLooks(12);
  }
  function syncFeed(force) {
    var want = feedWanted();
    feed.hidden = !want;
    var wardrobeMode = (typeof studioSource !== "undefined" && studioSource === "wardrobe");
    feed.classList.toggle("cf-solo", wardrobeMode);
    if (result) result.classList.toggle("cf-replaced", wardrobeMode);
    if (!want) return;
    var looksPanel = document.getElementById("panel-looks");
    var panel = document.getElementById("panel-studio");
    if (!(looksPanel && !looksPanel.hidden) && panel && panel.hidden && !force) return;
    if (force || !feedLooks.length || feedSig !== stateSig()) resetFeed();
  }
  window.composerSyncFeed = syncFeed;
  window.__cfKeyFor = function (btn) { var l = feedLooks[parseInt(btn.getAttribute("data-cf-dislike"), 10)]; return l ? l.composerKey : null; };
  feed.querySelector("#cf-shuffle").addEventListener("click", function () { resetFeed(); feed.scrollIntoView({ block: "start", behavior: "smooth" }); });
  grid.addEventListener("click", function (e) {
    var like = e.target.closest("[data-cf-like]");
    if (like) {
      var lk = feedLooks[parseInt(like.getAttribute("data-cf-like"), 10)];
      if (!lk) return;
      if (lk.verdict === "like") return;
      if (likeLook(lk)) {
        like.setAttribute("aria-pressed", "true");
        toast("Liked — saved to " + (typeof savedHomeName === "function" ? savedHomeName(lk) : "My Outfits") + ".");
      }
      return;
    }
    var dis = e.target.closest("[data-cf-dislike]");
    if (dis) {
      var di = parseInt(dis.getAttribute("data-cf-dislike"), 10);
      var dl = feedLooks[di];
      if (!dl) return;
      composerVerdict(dl, "dislike");
      var card = dis.closest(".cf-card");
      var exclude = feedLooks.map(function (l) { return l.composerKey; });
      var rep = composerLooks({ count: 1, level: feedLevel(), exclude: exclude })[0];
      if (rep && card) {
        feedLooks[di] = rep;
        card.outerHTML = cardHTML(rep, di);
        composerMarkSeen([rep]);
      } else if (card) { card.remove(); }
      return;
    }
    var open = e.target.closest("[data-cf-open]");
    if (open) {
      var ol = feedLooks[parseInt(open.getAttribute("data-cf-open"), 10)];
      if (ol && typeof openLookLayer === "function") openLookLayer(ol);
    }
  });
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      if (!entries[0].isIntersecting || feed.hidden || !feedLooks.length) return;
      appendLooks(8);
    }, { rootMargin: "900px 0px" }).observe(sentinel);
  } else {
    window.addEventListener("scroll", function () {
      if (feed.hidden || !feedLooks.length) return;
      if (sentinel.getBoundingClientRect().top < window.innerHeight + 900) appendLooks(8);
    }, { passive: true });
  }

  /* Wardrobe mode: Give me ideas / Six more ideas / a source tap
     shuffle the endless feed instead of dealing six renders. */
  if (typeof dealWardrobeSix === "function") {
    dealWardrobeSix = function () {
      if (!composerLooks({ count: 1 }).length) return false;
      syncFeed(true);
      return true;
    };
  }
  if (typeof window.setSource === "function") {
    var _setSource73 = window.setSource;
    window.setSource = function (s) { _setSource73(s); syncFeed(false); };
    try { setSource = window.setSource; } catch (e) {}
  }
  if (typeof setFormality === "function") {
    var _setFormality73 = setFormality;
    setFormality = function (level, o) { var r = _setFormality73(level, o); setTimeout(function () { syncFeed(false); }, 0); return r; };
  }
  document.addEventListener("click", function (e) {
    if (e.target.closest && e.target.closest("[data-studio-type-any], [data-studio-type]")) setTimeout(function () { syncFeed(false); }, 0);
  });
  if (typeof window.switchTab === "function") {
    var _switchTab73 = window.switchTab;
    window.switchTab = function (name, o) { _switchTab73(name, o); if (name === "studio") syncFeed(false); };
    try { switchTab = window.switchTab; } catch (e) {}
  }

  /* Saved closet looks (My Outfits) show their flat-lay too —
     named pieces = pictured pieces. */
  function decorateSaved(root) {
    if (!root) return;
    root.querySelectorAll("article.saved-card").forEach(function (card) {
      if (card.getAttribute("data-fl73")) return;
      var ref = card.querySelector("[data-open-look], [data-fav-open], [data-delete-look]");
      if (!ref) return;
      var id = ref.getAttribute("data-open-look") || ref.getAttribute("data-fav-open") || ref.getAttribute("data-delete-look");
      var look = null;
      [savedLooks, (typeof queueLooks !== "undefined" ? queueLooks : [])].forEach(function (arr) { arr.forEach(function (l) { if (!look && l.id === id) look = l; }); });
      if (!look || !look.composer) return;
      var img = card.querySelector(":scope > img");
      if (!img) return;
      var wrap = document.createElement("div");
      wrap.className = "cf-media saved-flatlay";
      wrap.setAttribute("data-open-look", id);
      wrap.innerHTML = flatlayHTML(look, true);
      img.replaceWith(wrap);
      card.setAttribute("data-fl73", "1");
    });
  }
  ["saved-grid", "outfit-ideas-grid"].forEach(function (gid) {
    var g = document.getElementById(gid);
    if (!g) return;
    decorateSaved(g);
    new MutationObserver(function () { decorateSaved(g); }).observe(g, { childList: true });
  });

  /* Boot: Home was dealt before this block ran — re-render so a
     closet look shows as its flat-lay; the Ideas feed fills the
     first time Ideas is open. */
  try {
    if (todayLook && (todayLook.composer || (todayLook.source === "wardrobe" && todayLook.fwPieces))) renderToday();
    else if (!todayTouched && typeof dealHeroForSource === "function" && (!todayLook || (typeof lookIsMine === "function" && !lookIsMine(todayLook)))) {
      dealHeroForSource();
    }
  } catch (e) {}
  syncFeed(false);
  window.WARDROBE_COMPOSER_READY = true;
})();

    