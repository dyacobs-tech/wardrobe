
/* ================= Build .80.1 — the figure stands still on Next =================
   Every cut-out is the same 362x1200 file, but he stands a little higher or
   lower (feet 37-65px above the bottom) and a few px left or right in each.
   assets/onbody-cut/feet.json holds each file's feet line and centre; the
   hero (and the outgoing crossfade copy) is drawn with an object-position
   offset so his feet sit on one floor line and his centre on one axis —
   no transform, nothing animated but opacity. */
(function () {
  "use strict";
  var hero = document.getElementById("today-hero"), img = document.getElementById("today-img");
  if (!hero || !img) return;
  var FEET = null, BASE_BOT = 50;
  function idOf(u) { var m = String(u || "").match(/onbody-cut\/([^\/?#]+?)\.(webp|png)/i); return m ? m[1] : ""; }
  function place(el) {
    if (!FEET || !el) return;
    var f = FEET[idOf(el.getAttribute("src"))];
    if (!f) { if (el.style.objectPosition) el.style.objectPosition = ""; return; }
    var cs = getComputedStyle(el), w = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight), h = el.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    if (!(w > 0 && h > 0)) return;
    var s = Math.min(w / 362, h / 1200);
    var dy = Math.round((f[0] - BASE_BOT) * s * 10) / 10, dx = Math.round(-f[1] * s * 10) / 10;
    var v = "calc(50% + " + dx + "px) calc(100% + " + dy + "px)";
    if (el.style.objectPosition !== v) el.style.setProperty("object-position", v, "important");
  }
  function all() { place(img); hero.querySelectorAll(".hero-xfade").forEach(place); }
  window.heroFeet801 = function () { return FEET; };
  new MutationObserver(function (ms) {
    ms.forEach(function (m) {
      if (m.type === "attributes") place(m.target);
      else m.addedNodes.forEach(function (n) { if (n.nodeType === 1 && n.classList.contains("hero-xfade")) place(n); });
    });
  }).observe(hero, { subtree: true, childList: true, attributes: true, attributeFilter: ["src"] });
  var rt = 0;
  window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(all, 80); }, { passive: true });
  /* a fixed hero box: the look's name stays on one line (shrunk to fit,
     never below 19px), so a long name never wraps, grows the caption and
     shrinks the figure */
  var nm = document.getElementById("today-name");
  function fit() {
    if (!nm) return;
    nm.style.fontSize = "";
    var cw = nm.clientWidth, sw = nm.scrollWidth;
    if (cw > 0 && sw > cw + 1) {
      var fs = parseFloat(getComputedStyle(nm).fontSize) || 28;
      nm.style.fontSize = Math.max(19, Math.floor(fs * cw / sw * 10) / 10) + "px";
    }
  }
  if (nm) {
    new MutationObserver(fit).observe(nm, { childList: true, characterData: true, subtree: true });
    window.addEventListener("resize", fit, { passive: true });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
    fit();
  }
  fetch("assets/onbody-cut/feet.json").then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
    if (j && j.feet) { FEET = j.feet; all(); }
  }).catch(function () {});
})();
    