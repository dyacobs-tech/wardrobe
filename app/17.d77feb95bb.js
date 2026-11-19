
/* Build .79.1: the closet search widens across its row while in use */
(function closetSearchRow789() {
  var row = document.querySelector(".closet-row789"), inp = document.getElementById("ward-search");
  if (!row || !inp) return;
  function set() { row.classList.toggle("cs-open", document.activeElement === inp || !!inp.value); }
  inp.addEventListener("focus", set); inp.addEventListener("blur", function () { setTimeout(set, 120); }); inp.addEventListener("input", set);
  set();
})();
    