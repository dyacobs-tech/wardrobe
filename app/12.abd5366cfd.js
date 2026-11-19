
/* Build .78.2b — the bottom nav tucks away while scrolling down and comes
   back on scroll up or when scrolling stops. One passive listener, reads
   only scrollY (no layout), flips one class; CSS does the motion. */
(function () {
  var root = document.documentElement, lastY = window.scrollY || 0, idle = 0, ticking = false;
  var mq = window.matchMedia ? window.matchMedia("(max-width: 899px)") : null;
  function show() { if (root.classList.contains("nav-away")) root.classList.remove("nav-away"); }
  function typing() { var a = document.activeElement; return !!(a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA" || a.isContentEditable)); }
  function step() {
    ticking = false;
    var y = window.scrollY || 0, dy = y - lastY;
    if (mq && !mq.matches) { show(); lastY = y; return; }
    if (dy > 4 && y > 60 && !typing()) root.classList.add("nav-away");
    else if (dy < -4 || y <= 60) show();
    lastY = y;
  }
  window.addEventListener("scroll", function () {
    if (!ticking) { ticking = true; requestAnimationFrame(step); }
    clearTimeout(idle); idle = setTimeout(show, 250);
  }, { passive: true });
  ["touchend", "touchcancel"].forEach(function (t) { window.addEventListener(t, function () { clearTimeout(idle); idle = setTimeout(show, 250); }, { passive: true }); });
  window.__navShow = show;
  if (typeof window.switchTab === "function") {
    var _st = window.switchTab;
    window.switchTab = function () { show(); return _st.apply(this, arguments); };
  }
})();
    