
/* Build .78.2c — Home's action row reads Thumbs up · Thumbs down · Next ·
   occasion on one line. Thumbs up is the existing Like. Thumbs down is the
   existing Dislike (the composer ban / not-for-me photo list) plus the
   render itself on the synced not-for-me list (dislikedImgs), so that
   look never returns to Home, Outfits, or a later rotation; Undo puts it
   back. Nothing in the closet is deleted. */
(function () {
  var row = document.getElementById("today-simple-actions");
  var like = document.getElementById("today-like"), dis = document.getElementById("today-dislike");
  if (!row || !like || !dis) return;
  like.classList.add("thumb-btn"); like.textContent = "Like"; like.setAttribute("aria-label", "Like");
  dis.classList.add("thumb-btn", "thumb-down"); dis.textContent = "Dislike"; dis.setAttribute("aria-label", "Dislike — remove this look");
  var lc = like.closest(".hero-icon-cell"), dc = dis.closest(".hero-icon-cell"), nc = (document.getElementById("today-next") || {}).closest ? document.getElementById("today-next").closest(".hero-icon-cell") : null;
  if (dc) { dc.hidden = false; if (lc && lc.nextSibling !== dc) row.insertBefore(dc, lc.nextSibling); }
  var tb = document.getElementById("today-type-btn"), tdd = tb && tb.closest(".cdd");
  if (tdd && nc) {
    var cell = document.createElement("div"); cell.className = "hero-icon-cell hero-type-cell";
    cell.appendChild(tdd); row.insertBefore(cell, nc.nextSibling);
  }
  /* the ••• (Share this look / Upload a look) moves off the hero into the outfit view header */
  var corner = document.querySelector("#today-hero .hero-corner"), top = document.querySelector("#outfit-view .ov-top");
  if (corner && top) top.appendChild(corner);

  function unban(img) {
    if (!img || typeof dislikedImgs === "undefined") return;
    var i = dislikedImgs.indexOf(img);
    if (i !== -1) { dislikedImgs.splice(i, 1); try { store.set("dislikedImgs", dislikedImgs); } catch (e) {} }
  }
  function unbanComposer(look) {
    if (!look || !look.composer || typeof composerPrefs !== "function") return;
    try { var p = composerPrefs(); if (p.banned) delete p.banned[look.composerKey]; composerSavePrefs(p); } catch (e) {}
  }
  var pending = null;
  document.addEventListener("click", function (e) {
    if (!e.target || !e.target.closest || !e.target.closest("#today-dislike")) return;
    if (typeof todayLook === "undefined" || !todayLook) return;
    var snap = JSON.parse(JSON.stringify(todayLook));
    var rsrc = typeof window.renderFor782 === "function" ? window.renderFor782(todayLook) : null;
    var pimg = typeof lookImg === "function" ? lookImg(snap) : null;
    pending = { look: snap, render: rsrc, img: pimg, had: typeof dislikedImgs !== "undefined" && pimg ? dislikedImgs.indexOf(pimg) !== -1 : false };
    setTimeout(function () {
      var p = pending; pending = null; if (!p) return;
      if (p.render && typeof recordDislike === "function") recordDislike(p.render);
      if (typeof window.fillOutfitView782 === "function") window.fillOutfitView782();
      if (typeof showUndoToast === "function") showUndoToast("Look removed.", function () {
        unban(p.render); if (!p.had) unban(p.img); unbanComposer(p.look);
        p.look.verdict = null;
        todayLook = p.look;
        try { if (typeof saveToday === "function") saveToday(); } catch (x) {}
        if (typeof renderToday === "function") renderToday();
        if (typeof syncTodayVerdict === "function") syncTodayVerdict();
        if (typeof toast === "function") toast("Undone — that look is back.");
      });
    }, 0);
  }, true);

  /* Outfits cards: thumbs down removes the card (a fresh one takes its place); Undo returns the pairing to the rotation */
  document.addEventListener("click", function (e) {
    var d = e.target && e.target.closest ? e.target.closest("#cf-grid [data-cf-dislike]") : null;
    if (!d) return;
    var card = d.closest(".cf-card"), title = card ? (card.querySelector(".oc-title") || {}).textContent : "";
    var key = null;
    try { var k = window.__cfKeyFor ? window.__cfKeyFor(d) : null; key = k; } catch (x) {}
    setTimeout(function () {
      if (typeof showUndoToast === "function") showUndoToast("Removed" + (title ? " — " + title : "") + ".", function () {
        if (key) unbanComposer({ composer: true, composerKey: key });
        if (typeof toast === "function") toast("Undone — it's back in the rotation.");
      });
    }, 0);
  }, true);
})();
    