
/* Build .75 — IA cuts: Outfits toggle, The Edit, Advanced, Home next */
(function () {
  function moveNode(id, hostId) {
    var src = document.getElementById(id);
    var host = document.getElementById(hostId);
    if (!src || !host) return;
    while (src.firstChild) host.appendChild(src.firstChild);
  }
  (function () {
    var tc = document.getElementById("theme-card"), pc = document.getElementById("panel-pcloud");
    if (tc && pc) pc.insertBefore(tc, pc.firstChild);
  })();
  var rec = document.getElementById("panel-receipts");
  var recHost = document.getElementById("plus-receipts-host");
  if (rec && recHost) {
    recHost.appendChild(rec);
    rec.hidden = false;
    rec.style.display = "block";
  }

  window.openAdvanced = function () { if (typeof switchTab === "function") switchTab("pcloud"); };

  var plus = document.getElementById("shop-plus");
  var sheet = document.getElementById("shop-plus-sheet");
  var plusClose = document.getElementById("shop-plus-close");
  function openPlus(on) {
    if (!sheet) return;
    sheet.hidden = !on;
    if (on && typeof renderReceipts === "function") renderReceipts();
  }
  if (plus) plus.addEventListener("click", function () { openPlus(true); });
  if (plusClose) plusClose.addEventListener("click", function () { openPlus(false); });
  if (sheet) sheet.addEventListener("click", function (e) { if (e.target === sheet) openPlus(false); });

  var next = document.getElementById("today-next");
  if (next) next.addEventListener("click", function () {
    if (typeof dealAnotherToday === "function") dealAnotherToday();
  });
  window.outfitsMode = "mine";
  window.syncOutfitsToggle = function () {
    var mine = document.getElementById("outfits-mine");
    var inspo = document.getElementById("outfits-inspo");
    var mv = document.getElementById("outfits-mine-view");
    var iv = document.getElementById("outfits-inspo-view");
    var isMine = window.outfitsMode !== "inspo";
    if (mine) mine.setAttribute("aria-pressed", isMine ? "true" : "false");
    if (inspo) inspo.setAttribute("aria-pressed", isMine ? "false" : "true");
    if (mv) mv.hidden = !isMine;
    var osh = document.getElementById("outfits-shuffle");
    if (osh) osh.hidden = !isMine;
    if (iv) iv.hidden = isMine;
    if (isMine) {
      if (typeof renderSaved === "function") renderSaved();
    } else {
      showInspoView(window.inspoView || "icons");
    }
    /* .79.4: switching to Outfits (or Mine/Inspo) keeps the feed it already
       built — it is rebuilt only when the closet, level or source changed
       (Shuffle still deals a fresh one) */
    if (typeof composerSyncFeed === "function") composerSyncFeed(false);
  };
  window.inspoView = "icons";
  window.showInspoView = function (v) {
    var host = document.getElementById("inspo-host");
    if (!host) return;
    window.inspoView = v;
    ["onyou", "icons", "palettes", "myinspo"].forEach(function (n) {
      var pn = document.getElementById("panel-" + n);
      if (!pn) return;
      if (pn.parentNode !== host) host.appendChild(pn);
      pn.hidden = n !== v;
    });
    document.querySelectorAll("[data-inspo-view]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-inspo-view") === v ? "true" : "false");
    });
    try {
      if (v === "onyou" && typeof renderInspoOnYou === "function") renderInspoOnYou();
      if (v === "icons" && typeof renderIcons === "function") renderIcons();
      if (v === "palettes" && typeof renderPlates === "function") renderPlates();
      if (v === "myinspo" && typeof renderMyInspo === "function") renderMyInspo();
    } catch (err) {}
  };
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-inspo-view]");
    if (b) showInspoView(b.getAttribute("data-inspo-view"));
    var bl = e.target.closest && e.target.closest("#outfits-build");
    if (bl && typeof showBuildSheet === "function") showBuildSheet("build-sheet");
    var sh = e.target.closest && e.target.closest("#outfits-shuffle");
    if (sh) { var cf = document.getElementById("cf-shuffle"); if (cf) cf.click(); }
  });
  var mineBtn = document.getElementById("outfits-mine");
  var inspoBtn = document.getElementById("outfits-inspo");
  if (mineBtn) mineBtn.addEventListener("click", function () { window.outfitsMode = "mine"; syncOutfitsToggle(); });
  if (inspoBtn) inspoBtn.addEventListener("click", function () { window.outfitsMode = "inspo"; syncOutfitsToggle(); });

  window.renderTheEdit = function () {
    if (typeof renderWishlist === "function") renderWishlist();
    var gaps = document.getElementById("edit-gaps");
    if (gaps) {
      var items = (typeof lastWishlist !== "undefined" && lastWishlist) ? lastWishlist.slice(0, 8) : [];
      if (!items.length) {
        gaps.innerHTML = "";
      } else {
        gaps.innerHTML = '<h3 class="fav-head">Closet gaps</h3>' + items.map(function (w, i) {
          return '<div class="card wish-row edit-card"><span class="cdot" style="background:' + (w.hex || "transparent") + '"></span>' +
            '<span class="w-main"><span class="w-name">' + esc(w.desc) + '</span>' +
            '<span class="w-sub">' + esc(w.cat) + " · completes " + w.count + (w.count === 1 ? " outfit" : " outfits") + "</span></span>" +
            '<button type="button" class="btn-ghost" data-wish-find="' + i + '">Shop</button></div>';
        }).join("");
      }
    }
    var list = document.getElementById("edit-list");
    if (!list) return;
    var edits = (typeof finds !== "undefined" && finds && finds.length) ? finds.slice() : [];
    if (typeof shopWishlist !== "undefined" && shopWishlist && shopWishlist.length) {
      edits = edits.concat([{
        id: "wishlist-edit",
        desc: "Wishlist",
        _count: shopWishlist.length,
        _date: shopWishlist[0] && shopWishlist[0].added ? shopWishlist[0].added : null,
        _kind: "wishlist"
      }]);
    }
    if (!edits.length && !(typeof lastWishlist !== "undefined" && lastWishlist && lastWishlist.length)) {
      list.innerHTML = '<div class="card empty">No edits yet — tap + to paste a link or file a receipt.</div>';
      return;
    }
    if (!edits.length) { list.innerHTML = ""; return; }
    list.innerHTML = '<h3 class="fav-head">Edits</h3>' + edits.map(function (f) {
      var count = f._count || 1;
      var ms = f._date ? Date.parse(f._date) : (String(f.id || "").match(/(\d{10,})/) ? parseInt(RegExp.$1, 10) : NaN);
      var when = isFinite(ms) ? new Date(ms).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "";
      var kind = f._kind || "find";
      return '<article class="card edit-card" data-edit-id="' + esc(f.id) + '">' +
        "<h3>" + esc(f.desc || "Edit") + "</h3>" +
        '<p class="edit-meta">' + count + (count === 1 ? " piece" : " pieces") + (when ? " · " + when : "") + "</p>" +
        '<div class="edit-actions">' +
        '<button type="button" class="btn-ink" data-edit-continue="' + esc(f.id) + '" data-edit-kind="' + kind + '">Continue</button>' +
        '<button type="button" class="btn-ghost" data-edit-archive="' + esc(f.id) + '" data-edit-kind="' + kind + '">Archive</button>' +
        "</div></article>";
    }).join("");
  };
  document.addEventListener("click", function (e) {
    var cont = e.target.closest && e.target.closest("[data-edit-continue]");
    if (cont) {
      var kind = cont.getAttribute("data-edit-kind");
      if (kind === "wishlist") {
        var first = (shopWishlist && shopWishlist[0] && (shopWishlist[0].url || shopWishlist[0].href));
        if (first) window.open(first, "_blank", "noopener");
        else if (typeof renderShopWishlist === "function") { /* stay on The Edit */ }
        return;
      }
      var id = cont.getAttribute("data-edit-continue");
      var btn = document.querySelector('[data-brief-search="' + id + '"]');
      if (btn) btn.click();
      else {
        var f = (finds || []).filter(function (x) { return x.id === id; })[0];
        if (f && typeof findQuery === "function") {
          window.open("https://www.ebay.com/sch/i.html?_nkw=" + encodeURIComponent(findQuery(f)), "_blank", "noopener");
        }
      }
      return;
    }
    var arch = e.target.closest && e.target.closest("[data-edit-archive]");
    if (arch) {
      var kind = arch.getAttribute("data-edit-kind");
      var id = arch.getAttribute("data-edit-archive");
      if (kind === "wishlist") {
        if (typeof shopWishlist !== "undefined") { shopWishlist = []; if (typeof saveShopWishlist === "function") saveShopWishlist(); }
      } else {
        finds = (finds || []).filter(function (x) { return x.id !== id; });
        if (typeof store !== "undefined") store.set("finds", finds);
      }
      if (typeof renderTheEdit === "function") renderTheEdit();
    }
  });

  if (typeof syncPageTitle === "function") syncPageTitle(typeof currentTab !== "undefined" ? currentTab : "today");
  if (typeof onbodyRefresh === "function") onbodyRefresh();
})();
