
/* ================= Build .78.8c — Pool-only pieces, the safety net =================
   The composer and the closet pickers already keep Pool-only pieces
   (pool slides) out of non-swim looks; every look generator is also
   checked on the way out, so no path can deal slides with regular
   clothes: lists are filtered, a single look is re-dealt or has the
   Pool-only piece swapped for another of his shoes. */
(function poolOnly788() {
  if (typeof lookOccasionOk !== "function") return;
  function altShoe(look) {
    var have = {}; lookItems788(look).forEach(function (i) { have[i.id] = 1; });
    var list = (typeof wardrobeItems !== "undefined" ? wardrobeItems : []).filter(function (i) { return i && i.category === "Shoes" && !i.laundry && !itemPoolOnly(i) && !have[i.id]; });
    list.sort(function (a, b) { return (b.photo ? 1 : 0) - (a.photo ? 1 : 0); });
    return list[0] || null;
  }
  function repair(look) {
    if (!look || lookOccasionOk(look)) return look;
    var alt = altShoe(look), changed = false;
    if (look.fwPieces) {
      look.fwPieces = look.fwPieces.map(function (p) {
        var it = p && (typeof closetItemById === "function" ? closetItemById(p.id) : null) || p;
        if (!itemPoolOnly(it)) return p;
        changed = true;
        return alt ? { id: alt.id, name: alt.name, photo: alt.photo || null, colourHex: alt.colourHex || null, category: alt.category } : null;
      }).filter(Boolean);
    }
    if (look.composerKey) { look.composerKey = (look.fwPieces || []).map(function (p) { return p.id; }).sort().join("|"); }
    ["itemIds", "ids"].forEach(function (k) { if (Array.isArray(look[k])) look[k] = look[k].filter(function (id) { var x = typeof closetItemById === "function" ? closetItemById(id) : null; return !(x && itemPoolOnly(x)); }).concat(alt && changed ? [alt.id] : []); });
    return look;
  }
  window.poolOnlyRepair788 = repair;
  function wrapList(name) {
    var f = window[name]; if (typeof f !== "function") return;
    window[name] = function () {
      var r = f.apply(this, arguments);
      return Array.isArray(r) ? r.filter(function (l) { return !l || typeof l !== "object" || lookOccasionOk(l); }) : r;
    };
  }
  function wrapOne(name) {
    var f = window[name]; if (typeof f !== "function") return;
    window[name] = function () {
      var r = f.apply(this, arguments), n = 0;
      if (Array.isArray(r)) return r.map(repair);
      while (r && typeof r === "object" && !lookOccasionOk(r) && n++ < 4) r = f.apply(this, arguments);
      return repair(r);
    };
  }
  /* lists: the composer (Home OOTD / Next, Outfits feed), closet looks, six-look builds */
  ["composerLooks", "homeComposerLooks75", "buildClosetLooks", "buildSixLooks"].forEach(wrapList);
  /* single looks: the deals, combos, ideas, the day's look */
  ["dealerLook", "dealerLookSafe56", "generateComboLook", "styleComboLook", "buildComboLook", "styleFwPairLook", "buildLook", "ideaAsLook", "dailyLook", "openingLook"].forEach(wrapOne);
  /* a look already on Home (restored from yesterday's store) is checked too */
  try { if (typeof todayLook !== "undefined" && todayLook && !lookOccasionOk(todayLook)) { repair(todayLook); if (typeof renderToday === "function") renderToday(); } } catch (e) {}
  /* write the flag onto the pieces themselves, so it rides sync and backups */
  try {
    var changed = false;
    (typeof wardrobeItems !== "undefined" ? wardrobeItems : []).forEach(function (i) { if (i && !Array.isArray(i.occasionOnly) && i.occasionOnly !== false && itemOccasionOnly(i)) { i.occasionOnly = itemOccasionOnly(i); changed = true; } });
    if (changed && typeof store !== "undefined" && !store.poisoned("items")) store.set("items", wardrobeItems.filter(function (i) { return String(i.id).indexOf("seed-") !== 0; }));
  } catch (e) {}
})();
    