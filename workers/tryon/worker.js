// src/ask.ts
var CATALOG_KEY = "catalog:v1";
var DEFAULT_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
var DEFAULT_FALLBACK_MODEL = "@cf/meta/llama-3.1-8b-instruct";
var ASK_CAP_DEFAULT = 200;
var MAX_ASK_BODY = 512 * 1024;
var MAX_CLOSET = 400;
var MAX_CLOSET_TO_LLM = 110;
var N_CANDIDATES = 24;
var DAY = 24 * 3600;
var CACHE = null;
function skuFor(raw) {
  if (typeof raw.sku === "string" && raw.sku) return raw.sku;
  const m = /(db-[0-9a-f]{8,})\.(?:jpe?g|png|webp)$/.exec(String(raw.img || ""));
  if (m) return m[1];
  return "";
}
function normaliseCatalog(raw) {
  const arr = Array.isArray(raw) ? raw : raw?.items;
  if (!Array.isArray(arr)) throw new Error("catalog must be an array");
  const out = [];
  const seen = /* @__PURE__ */ new Set();
  for (const r of arr) {
    if (!r || typeof r !== "object") continue;
    const sku = skuFor(r);
    if (!sku || seen.has(sku)) continue;
    if (typeof r.url !== "string" || !/^https:\/\//.test(r.url)) continue;
    if (typeof r.name !== "string" || typeof r.cat !== "string") continue;
    const price = Number(r.price);
    if (!isFinite(price) || price <= 0) continue;
    seen.add(sku);
    out.push({ ...r, sku, price });
  }
  return out;
}
function resetCatalogCache() {
  CACHE = null;
}
async function loadCatalog(env) {
  if (CACHE && Date.now() - CACHE.at < 5 * 60 * 1e3) return CACHE.items;
  const raw = await env.TRYON_KV.get(CATALOG_KEY);
  if (!raw) return [];
  const items = normaliseCatalog(JSON.parse(raw));
  CACHE = { at: Date.now(), items, bySku: new Map(items.map((i) => [i.sku, i])) };
  return items;
}
var STOP = new Set(
  "a an the and or but with for to of in on at my me i im i'm what which who whats should could would can do does go goes going wear wearing something some any need want get find show give looking look like pair pairs pairing good great best nice is are be it this that these those your you under below less than over above more about around from into fill gaps gap closet wardrobe please some new buy option options ideas idea".split(/\s+/)
);
var CAT_WORDS = [
  [/^(trousers?|pants?|slacks|chinos?|5-pocket|five-pocket)$/, "trousers"],
  [/^(jeans?|denim)$/, "jeans"],
  [/^(shorts?|swim|swimshorts|trunks)$/, "shorts"],
  [/^(shoes?|sneakers?|trainers?|loafers?|boots?|espadrilles?|drivers?|mules?|slippers?|footwear|runners?)$/, "shoes"],
  [/^(sweaters?|knits?|knitwear|cardigans?|crewnecks?|turtlenecks?|quarter-zips?|half-zips?|jumpers?)$/, "knitwear"],
  [/^(polos?)$/, "knitwear", "polo"],
  [/^(shirts?|oxfords?|button-?downs?|overshirts?|shackets?)$/, "shirt"],
  [/^(jackets?|coats?|outerwear|bombers?|parkas?|gilets?|vests?|overcoats?|chore)$/, "outerwear"],
  [/^(blazers?|sportcoats?|tailoring)$/, "blazer"],
  [/^(belts?)$/, "belt"],
  [/^(sunglasses|shades|sunnies|glasses)$/, "sunglasses"]
];
var SUBCAT_HINT = {
  sneaker: "sneaker",
  sneakers: "sneaker",
  trainer: "sneaker",
  trainers: "sneaker",
  runner: "sneaker",
  runners: "sneaker",
  loafer: "loafer",
  loafers: "loafer",
  chino: "chinos",
  chinos: "chinos",
  overshirt: "overshirt",
  overshirts: "overshirt"
};
var COLOURS = [
  "white",
  "ivory",
  "cream",
  "ecru",
  "off-white",
  "beige",
  "stone",
  "sand",
  "khaki",
  "tan",
  "camel",
  "taupe",
  "oatmeal",
  "brown",
  "espresso",
  "chocolate",
  "tobacco",
  "cognac",
  "olive",
  "green",
  "sage",
  "forest",
  "navy",
  "blue",
  "indigo",
  "denim",
  "grey",
  "gray",
  "charcoal",
  "black",
  "burgundy",
  "red",
  "pink",
  "yellow",
  "orange",
  "teal",
  "mint",
  "slate"
];
var COLOUR_FAMILY = {
  white: ["white", "optic", "bianco", "chalk"],
  ivory: ["ivory", "cream", "ecru", "off-white", "natural"],
  cream: ["cream", "ivory", "ecru", "off-white", "natural"],
  beige: ["beige", "stone", "sand", "khaki", "oatmeal", "natural"],
  tan: ["tan", "camel", "sand", "khaki"],
  brown: ["brown", "espresso", "chocolate", "tobacco", "cognac", "dark brown"],
  grey: ["grey", "gray", "charcoal", "slate", "heather"],
  gray: ["grey", "gray", "charcoal", "slate", "heather"],
  blue: ["blue", "navy", "indigo", "denim", "chambray"],
  green: ["green", "olive", "sage", "forest", "army"]
};
var VIBES = [
  [/palm\s*beach|resort|beach|summer|vacation|holiday|miami|hamptons|riviera|capri|st\.?\s*barts|warm|hot/, ["palm-beach", "linen", "resort", "summer", "lightweight", "cotton", "pleated"]],
  [/dinner|date|evening|night|restaurant|cocktail/, ["smart-casual", "pleated", "wool", "tailored", "loafer", "dress"]],
  [/office|work|meeting|business|client/, ["work", "wool", "tailored", "dress", "smart-casual"]],
  [/weekend|casual|errands|brunch|relaxed/, ["weekend", "chino", "denim", "sneaker"]],
  [/travel|flight|plane|airport/, ["travel", "stretch", "knit", "jersey"]],
  [/quiet|quieter|understated|minimal|clean|subtle|stealth|no logo|logo-?less/, ["minimal", "clean", "suede", "leather", "tonal"]],
  [/wedding|formal|black.?tie/, ["tailored", "wool", "dress", "loafer"]],
  [/winter|cold|fall|autumn|cozy/, ["wool", "cashmere", "flannel", "suede", "corduroy", "knit"]]
];
function tokenize(s) {
  return s.toLowerCase().replace(/[’']/g, "'").split(/[^a-z0-9$&.'-]+/).map((t) => t.replace(/^[.'-]+|[.'-]+$/g, "")).filter(Boolean);
}
function parsePrice(q) {
  const out = {};
  const num = (s, k) => Number(s.replace(/,/g, "")) * (k ? 1e3 : 1);
  let m = /(?:under|below|less than|max(?:imum)?|up to|no more than|<=?|cheaper than|budget(?: of)?)\s*\$?\s*(\d[\d,]*)(k)?/i.exec(q);
  if (m) out.max = num(m[1], m[2]);
  m = /\$\s*(\d[\d,]*)(k)?\s*(?:or less|or under|max|tops)/i.exec(q);
  if (m && out.max === void 0) out.max = num(m[1], m[2]);
  m = /(?:over|above|more than|at least|>=?)\s*\$?\s*(\d[\d,]*)(k)?/i.exec(q);
  if (m) out.min = num(m[1], m[2]);
  return out;
}
function myPhrase(q) {
  const m = /\bmy\s+([^,.;!?]+)/i.exec(q);
  if (!m) return "";
  return m[1].split(/\s+(?:for|on|at|in|to|this|next|when|while|that|which|under|below|but|so|from|during|without)\s+/i)[0].trim().toLowerCase();
}
function findAnchors(q, closet) {
  const phrase = myPhrase(q);
  const qt = new Set(tokenize(phrase || q).filter((t) => t.length >= 3 && !STOP.has(t)));
  if (!qt.size) return [];
  const scored = [];
  for (const it of closet) {
    const nt = tokenize(it.name + " " + (it.color || ""));
    const brandToks = nt.slice(0, 2);
    let s = 0;
    const seen = /* @__PURE__ */ new Set();
    for (const t of nt) {
      if (seen.has(t)) continue;
      seen.add(t);
      if (qt.has(t) || t.endsWith("s") && qt.has(t.slice(0, -1)) || qt.has(t + "s")) s++;
    }
    const brand = brandToks.some((b) => b.length >= 3 && qt.has(b));
    if (phrase ? s >= 3 || s >= 2 && brand : s >= 3 && brand) scored.push({ it, s: s + (brand ? 1 : 0), brand });
  }
  if (!scored.length) return [];
  scored.sort((a, b) => b.s - a.s);
  const top = scored[0].s;
  return scored.filter((x) => x.s >= top - 0).slice(0, 3).map((x) => x.it);
}
function parseQuery(q, closet) {
  const lower = q.toLowerCase();
  const anchors = findAnchors(q, closet);
  const anchorTok = new Set(!myPhrase(q) && !anchors.length ? [] : anchors.flatMap((a) => tokenize(a.name + " " + (a.color || ""))));
  const phraseTok = new Set(tokenize(myPhrase(q)));
  const tokens = tokenize(q);
  const negTok = /* @__PURE__ */ new Set();
  for (const m of lower.matchAll(/\b(?:not|no|except|avoid|without|anything but|nothing)\s+([a-z-]+)/g)) negTok.add(m[1]);
  const free = tokens.filter((t) => !phraseTok.has(t) && !anchorTok.has(t) && !anchorTok.has(t.replace(/s$/, "")) && !negTok.has(t));
  const cats = [];
  for (const t of free) {
    for (const [re, cat, sub] of CAT_WORDS) {
      if (re.test(t)) {
        const subcat = sub || SUBCAT_HINT[t];
        if (!cats.some((c) => c.cat === cat && c.subcat === subcat)) cats.push({ cat, subcat });
      }
    }
  }
  for (let i = cats.length - 1; i >= 0; i--) {
    if (!cats[i].subcat && cats.some((c) => c.cat === cats[i].cat && c.subcat)) cats.splice(i, 1);
  }
  const colours = free.filter((t) => COLOURS.includes(t));
  const notColours = [...negTok].filter((t) => COLOURS.includes(t));
  const brands = [];
  const bm = /(?:like|similar to|alternative to|instead of|vs\.?)\s+([a-z0-9&.' -]{3,30})/i.exec(q);
  if (bm) brands.push(bm[1].replace(/\b(but|and|that|which|for|under|with)\b.*$/i, "").trim().toLowerCase());
  const vibes = VIBES.filter(([re]) => re.test(lower)).flatMap(([, w]) => w);
  const gap = /\bgaps?\b|missing|fill (?:in|out)|round out|lacking|what (?:should|do) i (?:buy|need|get)|holes? in/.test(lower);
  const pr = parsePrice(q);
  return {
    tokens: free.filter((t) => t.length >= 3 && !STOP.has(t) && !/^\$?\d/.test(t)),
    cats,
    colours,
    notColours,
    phrase: myPhrase(q),
    maxPrice: pr.max,
    minPrice: pr.min,
    gap,
    vibes,
    anchors,
    brands
  };
}
function closetCat(it) {
  const s = ((it.cat || "") + " " + it.name).toLowerCase();
  if (/sunglass/.test(s)) return "sunglasses";
  if (/\bbelt/.test(s)) return "belt";
  if (/short(s)?\b/.test(s) && !/sleeve/.test(s)) return "shorts";
  if (/jean|denim pant/.test(s) && !/shirt/.test(s)) return "jeans";
  if (/trouser|pant|chino|twill|5-pocket/.test(s)) return "trousers";
  if (/shoe|sneaker|loafer|boot|espadrille|slipper|slip-on/.test(s)) return "shoes";
  if (/blazer|sport ?coat/.test(s)) return "blazer";
  if (/jacket|coat|outerwear|bomber|gilet|vest/.test(s)) return "outerwear";
  if (/sweater|knit|cardigan|crewneck|polo/.test(s)) return "knitwear";
  return "shirt";
}
var IDEAL = {
  trousers: 10,
  jeans: 4,
  shorts: 4,
  knitwear: 10,
  shirt: 16,
  shoes: 10,
  outerwear: 4,
  blazer: 5,
  belt: 3,
  sunglasses: 2
};
function closetGaps(closet) {
  const have = {};
  for (const it of closet) have[closetCat(it)] = (have[closetCat(it)] || 0) + 1;
  return Object.entries(IDEAL).map(([cat, ideal]) => ({ cat, have: have[cat] || 0, ideal, score: Math.max(0, ideal - (have[cat] || 0)) / ideal })).sort((a, b) => b.score - a.score);
}
function hay(it) {
  return [it.brand, it.name, it.cat, it.subcat, it.colourName, it.retailer, it.tags?.occasion, ...it.keys || []].join(" ").toLowerCase();
}
var NEAR = {
  white: ["off-white", "cream", "ivory", "ecru", "natural", "panna", "milk"],
  navy: ["blue", "indigo", "midnight"],
  black: ["charcoal", "ink"],
  olive: ["green", "militare", "sage", "khaki"],
  beige: ["tan", "cream", "panna", "ivory"],
  cream: ["white", "beige", "panna"]
};
function colourHit(it, c) {
  const h = ((it.colourName || "") + " " + it.name).toLowerCase();
  const fam = COLOUR_FAMILY[c] || [c];
  if (fam.some((f) => h.includes(f))) return 1;
  if ((NEAR[c] || []).some((f) => h.includes(f))) return 0.5;
  return 0;
}
function retrieve(catalog, pq, closet, prefs, n = N_CANDIDATES) {
  const gaps = closetGaps(closet);
  const gapScore = Object.fromEntries(gaps.map((g) => [g.cat, g.score]));
  const likedItems = catalog.filter((c) => prefs.liked.has(c.sku));
  const dislikedItems = catalog.filter((c) => prefs.disliked.has(c.sku));
  const likedBrands = new Set(likedItems.map((i) => i.brand.toLowerCase()));
  const likedCats = new Set(likedItems.map((i) => i.cat));
  const badBrands = /* @__PURE__ */ new Map();
  for (const d of dislikedItems) badBrands.set(d.brand.toLowerCase(), (badBrands.get(d.brand.toLowerCase()) || 0) + 1);
  const anchorIds = new Set(pq.anchors.map((a) => a.id));
  const closetIds = new Set(closet.map((c) => c.id));
  const ownedNames = new Set(closet.map((c) => c.name.toLowerCase()));
  const pass = (it, strictCat) => {
    if (prefs.disliked.has(it.sku)) return false;
    if (pq.notColours.some((c) => colourHit(it, c) === 1)) return false;
    if (pq.maxPrice !== void 0 && it.price > pq.maxPrice) return false;
    if (pq.minPrice !== void 0 && it.price < pq.minPrice) return false;
    if (ownedNames.has((it.brand + " " + it.name).toLowerCase())) return false;
    if (strictCat && pq.cats.length) {
      return pq.cats.some((c) => it.cat === c.cat && (!c.subcat || it.subcat === c.subcat || c.subcat === "polo" && /polo/i.test(it.name)));
    }
    if (strictCat && !pq.cats.length && pq.anchors.length) {
      return !pq.anchors.some((a) => closetCat(a) === it.cat);
    }
    return true;
  };
  const score = (it) => {
    const h = hay(it);
    let s = 0;
    for (const t of pq.tokens) if (h.includes(t)) s += 1.2;
    for (const c of pq.colours) s += 3 * colourHit(it, c);
    for (const v of pq.vibes) if (h.includes(v)) s += 0.8;
    for (const b of pq.brands) {
      for (const w of b.split(/\s+/)) if (w.length > 3 && h.includes(w)) s += 1;
    }
    if (pq.gap) {
      s += 5 * (gapScore[it.cat] || 0);
      if (it.tags?.gapFiller === "yes") s += 1.5;
    } else if (it.tags?.gapFiller === "yes") s += 0.3;
    const pw = (it.tags?.pairsWith || []).filter((id) => closetIds.has(id));
    if (pw.some((id) => anchorIds.has(id))) s += 3;
    s += Math.min(pw.length, 5) * 0.15;
    if (likedBrands.has(it.brand.toLowerCase())) s += 1;
    if (likedCats.has(it.cat)) s += 0.4;
    if (prefs.liked.has(it.sku)) s -= 2;
    s -= (badBrands.get(it.brand.toLowerCase()) || 0) * 0.8;
    if (it.sq === "elite") s += 0.2;
    return s;
  };
  let pool = catalog.filter((it) => pass(it, true));
  if (pool.length < 4) pool = catalog.filter((it) => pass(it, false));
  const ranked = pool.map((it) => ({ it, s: score(it) })).sort((a, b) => b.s - a.s || a.it.price - b.it.price);
  const out = [];
  const seenName = /* @__PURE__ */ new Set();
  const perBrand = /* @__PURE__ */ new Map();
  const perCat = /* @__PURE__ */ new Map();
  const multiCat = pq.gap || pq.cats.length !== 1;
  const catCap = pq.gap ? 5 : multiCat ? 8 : n;
  for (const { it } of ranked) {
    if (out.length >= n) break;
    const b = it.brand.toLowerCase();
    const nk = (b + "|" + it.name + "|" + (it.colourName || "")).toLowerCase();
    if (seenName.has(nk)) continue;
    if ((perBrand.get(b) || 0) >= 4) continue;
    if ((perCat.get(it.cat) || 0) >= catCap) continue;
    out.push(it);
    seenName.add(nk);
    perBrand.set(b, (perBrand.get(b) || 0) + 1);
    perCat.set(it.cat, (perCat.get(it.cat) || 0) + 1);
  }
  for (const { it } of ranked) {
    if (out.length >= n) break;
    const nk = (it.brand + "|" + it.name + "|" + (it.colourName || "")).toLowerCase();
    if (!out.includes(it) && !seenName.has(nk)) {
      out.push(it);
      seenName.add(nk);
    }
  }
  return { items: out, gaps };
}
var SCHEMA = {
  type: "object",
  properties: {
    answer: { type: "string" },
    picks: {
      type: "array",
      items: {
        type: "object",
        properties: {
          code: { type: "string" },
          why: { type: "string" },
          pairsWith: { type: "array", items: { type: "string" } }
        },
        required: ["code", "why", "pairsWith"]
      }
    },
    outfit: {
      type: "object",
      properties: {
        owned: { type: "array", items: { type: "string" } },
        buy: { type: "array", items: { type: "string" } }
      },
      required: ["owned", "buy"]
    }
  },
  required: ["answer", "picks", "outfit"]
};
function clip(s, n) {
  return String(s ?? "").replace(/\s+/g, " ").trim().slice(0, n);
}
function buildPrompt(query, pq, cands, closet, gaps, history, prefs, catalog) {
  const want = new Set(cands.map((c) => c.cat));
  const order = [...closet].sort((a, b) => {
    const ra = pq.anchors.includes(a) ? 0 : want.has(closetCat(a)) ? 2 : 1;
    const rb = pq.anchors.includes(b) ? 0 : want.has(closetCat(b)) ? 2 : 1;
    return ra - rb;
  });
  const shown = order.slice(0, MAX_CLOSET_TO_LLM);
  const cCode = /* @__PURE__ */ new Map();
  const closetLines = shown.map((it, i) => {
    const code = "c" + (i + 1);
    cCode.set(code, it.id);
    return `${code} | ${clip(it.name, 80)} | ${closetCat(it)} | ${clip(it.color, 24)}`;
  });
  const sCode = /* @__PURE__ */ new Map();
  const candLines = cands.map((it, i) => {
    const code = "s" + (i + 1);
    sCode.set(code, it.sku);
    return `${code} | ${it.brand} \u2014 ${clip(it.name, 70).replace(/"/g, "in")} | ${it.cat}/${it.subcat} | ${clip(it.colourName, 24)} | $${Math.round(it.price)} | ${it.tags?.occasion || ""}`;
  });
  const gapLine = gaps.filter((g) => g.score > 0.25).map((g) => `${g.cat} (owns ${g.have})`).join(", ");
  const likedTxt = catalog.filter((c) => prefs.liked.has(c.sku)).slice(0, 10).map((c) => `${c.brand} ${c.name}`).join("; ");
  const badTxt = catalog.filter((c) => prefs.disliked.has(c.sku)).slice(0, 10).map((c) => `${c.brand} ${c.name}`).join("; ");
  const anchorTxt = pq.anchors.map((a) => [...cCode].find(([, id]) => id === a.id)?.[0]).filter(Boolean).join(", ");
  const constraints = [
    pq.maxPrice !== void 0 ? `budget: each item \u2264 $${pq.maxPrice}` : "",
    pq.minPrice !== void 0 ? `each item \u2265 $${pq.minPrice}` : "",
    pq.phrase ? `he described his own piece(s) as "${clip(pq.phrase, 80)}"` + (anchorTxt ? ` \u2014 closest in his closet: ${anchorTxt} (build around the best match; if none is exact, name the one you used)` : " \u2014 not found in his closet") : "",
    pq.notColours.length ? `avoid colours: ${pq.notColours.join(", ")}` : ""
  ].filter(Boolean).join("; ");
  const system = `You are Vesper, David's personal menswear stylist inside his wardrobe app. You talk TO David ("you", never "David" or "he"). He is 42, dresses refined smart-casual (Brunello Cucinelli, Loro Piana, Kiton, Armani) and splits time between NYC and Palm Beach. Be direct, warm and specific, like the best associate at a top menswear store. Never invent products: recommend ONLY candidate codes (s1, s2, ...) from CANDIDATES and refer to his clothes ONLY via CLOSET codes (c1, c2, ...) in the JSON fields.
Return JSON: {"answer": exactly 2-3 sentences (40-75 words) naming your top pick by brand and name and explaining why it works with specific pieces he owns, called by their names \u2014 NEVER write a code like s3 or c12 in the answer, and never talk about "candidates", "codes" or "the list"; "picks": AT LEAST 4 and at most 6 objects {"code": candidate code, "why": one specific sentence of 10-22 words (colour, fabric or occasion logic, naming a piece he owns), "pairsWith": 1-3 closet codes worn WITH it in the same outfit (different slots: never another top with a top, another pair of shoes with shoes, or trousers with trousers)}, best first, varied in colour/brand; "outfit": {"owned": 2-4 closet codes, "buy": 1-2 codes from your picks} = ONE complete wearable look (one top, optional jacket/blazer, one bottom, one pair of shoes)}.
Respect budget and colour asks exactly. If nothing matches exactly (e.g. the colour he asked for isn't available), say so in one short clause and offer the closest real options. Mention prices only if he asked about budget.`;
  const user = `QUESTION: ${clip(query, 600)}
` + (constraints ? `CONSTRAINTS: ${constraints}
` : "") + (pq.gap || /gap/i.test(query) ? `CLOSET GAPS (thin categories): ${gapLine || "none"}
` : "") + (likedTxt ? `HE STARRED: ${likedTxt}
` : "") + (badTxt ? `HE THUMBED DOWN (avoid similar): ${badTxt}
` : "") + `
CLOSET (code | name | category | colour):
${closetLines.join("\n")}

CANDIDATES (code | brand \u2014 name | category | colour | price | occasion):
${candLines.join("\n")}`;
  const msgs = [{ role: "system", content: system }];
  for (const h of history.slice(-6)) {
    if ((h.role === "user" || h.role === "assistant") && typeof h.content === "string") {
      msgs.push({ role: h.role, content: clip(h.content, 500) });
    }
  }
  msgs.push({ role: "user", content: user });
  return { messages: msgs, cCode, sCode };
}
// .86.82 (David, 23 Nov 2026: "Let's integrate muse / Claude / chatgpt though", then "yes deploy the assistant"):
// Ask answers with OpenAI first, using the key saved as a Cloudflare secret; Workers AI stays as the fallback.
var OPENAI_DEFAULT_MODELS = ["gpt-5-mini", "gpt-4.1-mini", "gpt-4o-mini"];
var OPENAI_OK_MODEL = null;
var KEY_NAMES = ["OPENAI_API_KEY", "key_BE3gX1OPxUqH6jDL", "apikey_01D4TB6uBd1x13y3rvuqqSez", "ANTHROPIC_API_KEY"];
function keyKind(v) {
  const t = typeof v === "string" ? v.trim() : "";
  if (!t) return "empty";
  if (/^sk-ant-/.test(t)) return "anthropic";
  if (/^sk-/.test(t)) return "openai";
  return "other";
}
function keyNames(env) {
  const names = KEY_NAMES.filter((n) => env[n] !== void 0);
  for (const n of Object.keys(env)) if (!names.includes(n) && typeof env[n] === "string" && /key|openai/i.test(n)) names.push(n);
  return names;
}
function openaiKey(env) {
  for (const n of keyNames(env)) if (keyKind(env[n]) === "openai") return env[n].trim();
  return null;
}
function keyShapes(env) {
  return keyNames(env).map((n) => {
    const raw = String(env[n] || ""), t = raw.trim();
    return { name: n, kind: keyKind(raw), length: t.length, innerSpace: /\s/.test(t), outerSpace: raw !== t, quoted: /^["']|["']$/.test(t), prefix: t.slice(0, t.startsWith("sk-proj-") ? 8 : 3) };
  });
}
function openaiModels(env) {
  const list = [];
  if (env.OPENAI_MODEL) list.push(String(env.OPENAI_MODEL));
  if (OPENAI_OK_MODEL) list.push(OPENAI_OK_MODEL);
  for (const m of OPENAI_DEFAULT_MODELS) list.push(m);
  return [...new Set(list)];
}
async function openaiChat(env, model, messages, schema, maxTokens) {
  const body = { model, messages, max_completion_tokens: maxTokens || 1200 };
  if (!/^gpt-5|^o\d/.test(model)) body.temperature = 0.35;
  if (schema) body.response_format = { type: "json_schema", json_schema: { name: "donna_answer", schema, strict: false } };
  const r = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: "Bearer " + openaiKey(env) },
    body: JSON.stringify(body)
  });
  const txt = await r.text();
  if (!r.ok) {
    let code = "";
    try { code = JSON.parse(txt)?.error?.code || JSON.parse(txt)?.error?.type || ""; } catch {}
    const e = new Error("openai " + r.status + " " + code);
    e.status = r.status; e.code = code;
    throw e;
  }
  const j = JSON.parse(txt);
  const content = j?.choices?.[0]?.message?.content;
  if (typeof content !== "string" || !content.trim()) throw new Error("openai empty reply");
  return content;
}
async function handleAskPing(env, json2) {
  if (!openaiKey(env)) return json2({ ok: false, reason: "no_key", keys: keyShapes(env) });
  const day = (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
  const ck = "askping/" + day;
  const used = Number(await env.TRYON_KV.get(ck)) || 0;
  if (used >= 30) return json2({ ok: false, reason: "daily_cap" }, 429);
  await env.TRYON_KV.put(ck, String(used + 1), { expirationTtl: 2 * DAY });
  const tried = [];
  for (const m of openaiModels(env)) {
    const t0 = Date.now();
    try {
      const out = await openaiChat(env, m, [{ role: "user", content: "Reply with the single word: ready" }], null, 400);
      OPENAI_OK_MODEL = m;
      return json2({ ok: true, provider: "openai", model: m, ms: Date.now() - t0, reply: clip(out, 40), tried });
    } catch (e) {
      tried.push(m + ": " + clip(e.message, 80));
    }
  }
  return json2({ ok: false, reason: "all_models_failed", tried, keys: keyShapes(env) });
}
function parseModelJson(res) {
  let r = res?.response ?? res?.result?.response ?? res;
  if (r && typeof r === "object" && !Array.isArray(r)) return r;
  if (typeof r === "string") {
    const s = r.indexOf("{"), e = r.lastIndexOf("}");
    if (s >= 0 && e > s) return JSON.parse(r.slice(s, e + 1));
  }
  const c = res?.choices?.[0]?.message?.content;
  if (typeof c === "string") return JSON.parse(c.slice(c.indexOf("{"), c.lastIndexOf("}") + 1));
  throw new Error("no json in model output");
}
var unCode = (m, v) => {
  const k = String(v ?? "").trim().toLowerCase().replace(/[^a-z0-9]/g, "");
  return m.get(k) ?? null;
};
function validate(out, cCode, sCode, bySku, closetById) {
  const picks = [];
  const seen = /* @__PURE__ */ new Set();
  for (const p of Array.isArray(out?.picks) ? out.picks : []) {
    let sku = unCode(sCode, p?.code ?? p?.sku);
    if (!sku && typeof p?.sku === "string" && bySku.has(p.sku) && [...sCode.values()].includes(p.sku)) sku = p.sku;
    if (!sku || seen.has(sku)) continue;
    seen.add(sku);
    const pw = (Array.isArray(p.pairsWith) ? p.pairsWith : []).map((c) => unCode(cCode, c) ?? (closetById.has(String(c)) ? String(c) : null)).filter((x) => !!x);
    picks.push({ sku, why: clip(p.why, 240), pairsWith: [...new Set(pw)].slice(0, 3) });
    if (picks.length >= 6) break;
  }
  const ownedIds = [...new Set(
    (Array.isArray(out?.outfit?.owned) ? out.outfit.owned : []).map((c) => unCode(cCode, c) ?? (closetById.has(String(c)) ? String(c) : null)).filter(Boolean)
  )].slice(0, 5);
  const skuIds = [...new Set(
    (Array.isArray(out?.outfit?.buy) ? out.outfit.buy : []).map((c) => unCode(sCode, c)).filter(Boolean)
  )].slice(0, 3);
  return { answer: clip(out?.answer, 700), picks, outfit: ownedIds.length || skuIds.length ? { ownedIds, skuIds } : void 0 };
}
function fallbackPicks(cands, pq, closet) {
  const closetIds = new Set(closet.map((c) => c.id));
  return cands.slice(0, 4).map((it) => {
    let pw = (it.tags?.pairsWith || []).filter((id) => closetIds.has(id)).slice(0, 3);
    if (pq.anchors.length) pw = [.../* @__PURE__ */ new Set([...pq.anchors.map((a) => a.id), ...pw])].slice(0, 3);
    return {
      sku: it.sku,
      why: `${it.colourName || ""} ${it.subcat || it.cat} from ${it.brand}${it.tags?.gapFiller === "yes" ? " \u2014 fills a thin spot in your closet" : ""}.`.trim(),
      pairsWith: pw
    };
  });
}
function card(it) {
  return {
    sku: it.sku,
    brand: it.brand,
    name: it.name,
    cat: it.cat,
    subcat: it.subcat,
    price: it.price,
    priceDisplay: it.priceDisplay || `$${it.price}`,
    currency: it.currency || "USD",
    retailer: it.retailer,
    url: it.url,
    imgUrl: it.imgUrl,
    colourName: it.colourName,
    hex: it.hex,
    tier: it.tier,
    verified: it.verified
  };
}
function slotOf(cat) {
  if (cat === "shirt" || cat === "knitwear") return "top";
  if (cat === "blazer" || cat === "outerwear") return "layer";
  if (cat === "trousers" || cat === "jeans" || cat === "shorts") return "bottom";
  if (cat === "shoes") return "shoes";
  return "acc:" + cat;
}
function sanitiseOutfit(o, bySku, closetById) {
  const taken = /* @__PURE__ */ new Set();
  const skuIds = [];
  for (const s of o.skuIds) {
    const it = bySku.get(s);
    if (!it) continue;
    const sl = slotOf(it.cat);
    if (taken.has(sl)) continue;
    taken.add(sl);
    skuIds.push(s);
  }
  const ownedIds = [];
  for (const id of o.ownedIds) {
    const it = closetById.get(id);
    if (!it) continue;
    const sl = slotOf(closetCat(it));
    if (taken.has(sl)) continue;
    taken.add(sl);
    ownedIds.push(id);
  }
  return { ownedIds, skuIds };
}
function scrubCodes(text, cCode, sCode, bySku, closetById) {
  return text.replace(/\(?\b([cs]\d{1,3})\b\)?,?\s*/gi, (m, code) => {
    const k = code.toLowerCase();
    const name = k[0] === "c" ? closetById.get(cCode.get(k) || "")?.name : (() => {
      const it = bySku.get(sCode.get(k) || "");
      return it ? it.brand + " " + it.name : void 0;
    })();
    if (!name) return m;
    return m.trim().startsWith("(") ? "" : name + (m.endsWith(" ") ? " " : "");
  }).replace(/\s+([,.])/g, "$1").replace(/\s{2,}/g, " ").trim();
}
async function handleAsk(req, env, acct, json2) {
  if (!env.AI && !openaiKey(env)) return json2({ error: "not_configured", message: "Ask isn't switched on (no AI binding)." }, 503);
  const raw = await req.text();
  if (raw.length > MAX_ASK_BODY) return json2({ error: "too large" }, 413);
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return json2({ error: "bad json" }, 400);
  }
  const query = typeof body?.query === "string" ? body.query.trim() : "";
  if (!query || query.length > 1e3) return json2({ error: "bad_request", message: "query must be 1\u20131000 characters" }, 400);
  const closet = (Array.isArray(body.closet) ? body.closet : []).filter((c) => c && typeof c.id === "string" && typeof c.name === "string").slice(0, MAX_CLOSET).map((c) => ({ id: c.id.slice(0, 80), name: clip(c.name, 120), cat: clip(c.cat, 40), color: clip(c.color, 40), hex: clip(c.hex, 9) }));
  const ids = (v) => new Set((Array.isArray(v) ? v : []).filter((x) => typeof x === "string").slice(0, 500));
  const prefs = { liked: ids(body.liked), disliked: ids(body.disliked) };
  const history = (Array.isArray(body.history) ? body.history : []).filter((h) => h && typeof h.content === "string");
  const catalog = await loadCatalog(env);
  if (!catalog.length) return json2({ error: "not_configured", message: "The Edit catalog isn't loaded yet." }, 503);
  const cap = Math.max(1, Number(env.ASK_CAP_PER_DAY) || ASK_CAP_DEFAULT);
  const day = (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
  const ck = "askcap/" + acct + "/" + day;
  const used = Number(await env.TRYON_KV.get(ck)) || 0;
  if (used >= cap) {
    return json2({ error: "daily_cap", message: "You've hit today's Ask limit. It resets at midnight UTC.", cap, used }, 429);
  }
  await env.TRYON_KV.put(ck, String(used + 1), { expirationTtl: 3 * DAY });
  let pq = parseQuery(query, closet);
  const lastUser = [...history].reverse().find((h) => h.role === "user")?.content;
  if (lastUser && !pq.cats.length && !pq.gap) {
    const prev = parseQuery(lastUser, closet);
    pq = {
      ...pq,
      cats: prev.cats,
      anchors: pq.anchors.length ? pq.anchors : prev.anchors,
      phrase: pq.phrase || prev.phrase,
      vibes: [.../* @__PURE__ */ new Set([...pq.vibes, ...prev.vibes])],
      colours: pq.colours.length ? pq.colours : prev.colours,
      maxPrice: pq.maxPrice ?? prev.maxPrice
    };
  }
  if (/cheaper|less expensive|more affordable|lower price|budget/i.test(query) && pq.maxPrice === void 0) {
    const lastAsst = [...history].reverse().find((h) => h.role === "assistant")?.content;
    const prices = [...String(lastAsst || "").matchAll(/\$\s?(\d[\d,]*)/g)].map((m) => Number(m[1].replace(/,/g, "")));
    pq.maxPrice = prices.length ? Math.max(100, Math.round(Math.min(...prices) * 0.6)) : 400;
  }
  if (!pq.cats.length && !pq.gap && prefs.liked.size && /star|liked|saved|favou?rite|more like (these|those|them)/i.test(query)) {
    const likedCats = [...new Set(catalog.filter((c) => prefs.liked.has(c.sku)).map((c) => c.cat))];
    pq.cats = likedCats.map((cat) => ({ cat }));
  }
  const { items: cands, gaps } = retrieve(catalog, pq, closet, prefs);
  const bySku = CACHE?.bySku ?? new Map(catalog.map((i) => [i.sku, i]));
  const closetById = new Map(closet.map((c) => [c.id, c]));
  const { messages, cCode, sCode } = buildPrompt(query, pq, cands, closet, gaps, history, prefs, catalog);
  const models = [env.ASK_MODEL || DEFAULT_MODEL, env.ASK_FALLBACK_MODEL || DEFAULT_FALLBACK_MODEL];
  let result = null;
  let modelUsed = "";
  const errors = [];
  const t0 = Date.now();
  if (openaiKey(env)) {
    for (const model of openaiModels(env)) {
      try {
        const content = await openaiChat(env, model, messages, SCHEMA, 1500);
        const v = validate(parseModelJson(content), cCode, sCode, bySku, closetById);
        OPENAI_OK_MODEL = model;
        if (v.picks.length && v.answer) {
          result = v;
          modelUsed = "openai:" + model;
          break;
        }
        errors.push("openai:" + model + ": no valid picks");
        break;
      } catch (e) {
        errors.push("openai:" + model + ": " + clip(e.message, 120));
        if (e.status && e.status !== 404 && e.status !== 400) break;
      }
    }
  }
  for (const model of result ? [] : models) {
    if (!env.AI) break;
    try {
      const res = await env.AI.run(model, {
        messages,
        response_format: { type: "json_schema", json_schema: SCHEMA },
        max_tokens: 1e3,
        temperature: 0.35
      });
      const v = validate(parseModelJson(res), cCode, sCode, bySku, closetById);
      if (v.picks.length && v.answer) {
        result = v;
        modelUsed = model;
        break;
      }
      errors.push(model + ": no valid picks");
    } catch (e) {
      errors.push(model + ": " + clip(e.message, 160));
    }
  }
  let fallback = false;
  if (!result) {
    fallback = true;
    const picks = fallbackPicks(cands, pq, closet);
    const top = picks[0] && bySku.get(picks[0].sku);
    result = {
      answer: top ? `Here are the closest matches from The Edit${pq.maxPrice ? ` under $${pq.maxPrice}` : ""}. ${top.brand}'s ${top.name} leads the list.` : "Nothing in The Edit matches that yet.",
      picks,
      outfit: picks.length && picks[0].pairsWith.length ? { ownedIds: picks[0].pairsWith.slice(0, 3), skuIds: [picks[0].sku] } : void 0
    };
  } else if (result.picks.length < 3) {
    for (const p of fallbackPicks(cands, pq, closet)) {
      if (result.picks.length >= 3) break;
      if (!result.picks.some((x) => x.sku === p.sku)) result.picks.push(p);
    }
  }
  const finalPicks = result.picks.filter((p) => bySku.has(p.sku)).filter((p) => pq.maxPrice === void 0 || bySku.get(p.sku).price <= pq.maxPrice).map((p) => {
    const it = bySku.get(p.sku);
    const pickSlot = slotOf(it.cat);
    const pairsWith = p.pairsWith.filter((id) => closetById.has(id) && slotOf(closetCat(closetById.get(id))) !== pickSlot);
    return { sku: p.sku, why: scrubCodes(p.why, cCode, sCode, bySku, closetById), pairsWith, product: card(it) };
  });
  const outfit = result.outfit ? sanitiseOutfit(result.outfit, bySku, closetById) : void 0;
  result.answer = scrubCodes(result.answer, cCode, sCode, bySku, closetById);
  const wanted = pq.colours.filter((c) => !finalPicks.some((p) => colourHit(bySku.get(p.sku), c) === 1));
  if (wanted.length && finalPicks.length && !/(isn't|aren't|no |not (in|available)|closest|don't (have|carry))/i.test(result.answer)) {
    result.answer = `Nothing in The Edit comes in ${wanted.join(" or ")} right now, so these are the closest. ` + result.answer;
  }
  if (env.TRYON_KV && !fallback) console.log("ask ok", modelUsed, Date.now() - t0, "ms");
  if (errors.length) console.log("ask model errors", errors.join(" | "));
  return json2({
    answer: result.answer,
    picks: finalPicks,
    ...outfit && (outfit.ownedIds.length || outfit.skuIds.length) ? { outfit } : {},
    meta: {
      model: modelUsed || null,
      fallback,
      ms: Date.now() - t0,
      candidates: cands.length,
      parsed: {
        cats: pq.cats,
        colours: pq.colours,
        maxPrice: pq.maxPrice ?? null,
        minPrice: pq.minPrice ?? null,
        gap: pq.gap,
        anchors: pq.anchors.map((a) => a.id)
      },
      remaining: Math.max(0, cap - used - 1)
    }
  });
}
async function handleCatalog(env, json2) {
  const items = await loadCatalog(env);
  return json2({ version: "v1", count: items.length, items: items.map(card) });
}
async function handleAdminCatalog(req, env, json2) {
  const raw = await req.text();
  if (raw.length > 5 * 1024 * 1024) return json2({ error: "too large" }, 413);
  let items;
  try {
    items = normaliseCatalog(JSON.parse(raw));
  } catch (e) {
    return json2({ error: "bad_request", message: e.message }, 400);
  }
  if (!items.length) return json2({ error: "bad_request", message: "no valid items" }, 400);
  await env.TRYON_KV.put(CATALOG_KEY, JSON.stringify(items));
  resetCatalogCache();
  return json2({ ok: true, count: items.length });
}

// src/identify.ts
var IDENTIFY_MODEL = "@cf/mistralai/mistral-small-3.1-24b-instruct";
var IDENTIFY_FALLBACK = "@cf/meta/llama-4-scout-17b-16e-instruct";
var ID_CATEGORIES = [
  "Shoes",
  "Shirts",
  "Tees",
  "Polos",
  "Jeans",
  "Shorts",
  "Bathing suits",
  "Trousers",
  "Button downs",
  "Suits",
  "Blazers",
  "Scarves",
  "Jackets",
  "Coats",
  "Leather jackets",
  "Hats",
  "Sunglasses",
  "Sweaters",
  "Socks",
  "Belts",
  "Gloves",
  "Vests",
  "Ties"
];
var ID_MODELS = [IDENTIFY_MODEL, IDENTIFY_FALLBACK, "@cf/google/gemma-3-12b-it", "@cf/meta/llama-3.2-11b-vision-instruct"];
var MATERIALS = ["suede", "linen", "denim", "cashmere", "cotton", "wool", "leather", "silk", "corduroy", "flannel", "tweed", "knit", "canvas", "nylon", "velvet", "seersucker", "jersey", "merino", "mohair", "chambray"];
var MAX_IMAGE_CHARS = 2e6;
var ID_CAP_DEFAULT = 300;
var DAY2 = 24 * 3600;
var SCHEMA2 = {
  type: "object",
  properties: {
    category: { type: "string", enum: ID_CATEGORIES },
    garment: { type: "string" },
    brand: { type: "string" },
    colourName: { type: "string" },
    colourHex: { type: "string" },
    material: { type: "string" },
    confidence: { type: "number" },
    collar: { type: "boolean" },
    placket: { type: "string", enum: ["short", "full", "none"] },
    knit: { type: "boolean" },
    outerwear: { type: "boolean" },
    laces: { type: "boolean" },
    moccasinStitch: { type: "boolean" },
    siping: { type: "boolean" },
    pennyStrap: { type: "boolean" },
    brandSource: { type: "string", enum: ["label", "logo", "none"] },
    openingToHem: { type: "boolean" },
    westernYoke: { type: "boolean" }
  },
  required: ["category", "garment", "colourName", "colourHex"]
};
var SYSTEM = `You catalogue men's clothing for a wardrobe app from one photo.
Identify the single main garment (on a hanger, laid flat, or worn: pick the most prominent piece; ignore the background and other clothes on the rail).
Look before you name it:
- Front opening: does it have a collar? Follow the button line down: does the opening reach the hem (openingToHem true, a shirt) or stop at the chest with 2-3 buttons (openingToHem false, placket "short")? A collared top whose opening stops at the chest is a polo even with long sleeves and a smooth knit \u2014 never a button-down or shirt.
- Western details: a pointed yoke seam across the chest/shoulders, snap buttons, flap chest pockets = westernYoke true; that is a western shirt (category Shirts), even in suede or heavy cotton.
- Fabric: knitted (jersey, piqu\xE9, sweater knit) or woven (poplin, oxford, denim, corduroy, twill)?
- Is it outerwear worn over other clothes (coat, jacket, blazer), or a shirt? A western or work shirt with snaps or buttons and chest pockets is a shirt, not a jacket.
- Shoes: laces? moccasin-style stitched toe (a raised seam around the top of the toe)? siped/white rubber sole? a penny strap across the vamp? Laces + moccasin toe = boat shoes. Penny strap, no laces = penny loafers.
- Colour: name the hue family honestly. Burgundy, wine and oxblood are reds, not browns. Camel and tan are browns, not mustard/yellow. Teal and petrol are blue-greens, not plain blue.
Reply with one JSON object only, no prose, no code fence, keys: category, garment, brand, brandSource, colourName, colourHex, material, confidence, collar, placket, openingToHem, knit, outerwear, westernYoke, laces, moccasinStitch, siping, pennyStrap.
- category: exactly one of ${ID_CATEGORIES.join(", ")}. Knit crewnecks/cardigans are Sweaters. Tailored jackets are Blazers. Denim trousers are Jeans. Woven shirts with a full button front are Shirts (Button downs only if the collar points are buttoned down).
- garment: 1-4 words, plain, e.g. "boat shoes", "penny loafers", "crewneck sweater", "long-sleeve polo", "western shirt", "bootcut jeans".
- brand: only if you can actually READ a label or logo in the photo; brandSource "label"/"logo" then, else brand "" and brandSource "none". Never guess a brand from the style.
- colourName: one or two plain words, e.g. "dark olive", "navy", "burgundy", "camel", "teal", "dark brown", "mid blue".
- colourHex: the garment's main colour as #rrggbb, sampled from the fabric under normal light (not shadows or highlights).
- material: one word if obvious (suede, linen, denim, cashmere, cotton, wool, leather, corduroy), else "".
- collar/openingToHem/knit/outerwear/westernYoke/laces/moccasinStitch/siping/pennyStrap: true/false; placket: "short", "full" or "none".
- confidence: 0-1.`;
var NAMED = {
  black: "#1c1c1c",
  white: "#f4f1ea",
  cream: "#efe6d2",
  ivory: "#f1ead8",
  navy: "#232b3e",
  blue: "#3d5a80",
  "light blue": "#a9c1db",
  grey: "#8a8a8a",
  gray: "#8a8a8a",
  charcoal: "#3d3d3f",
  brown: "#5a4032",
  "dark brown": "#4a3834",
  tan: "#b08a5f",
  beige: "#d8c6a5",
  camel: "#b78f5d",
  olive: "#5c6140",
  "dark olive": "#444f35",
  green: "#3f5e3a",
  burgundy: "#6e2f35",
  red: "#a33a32",
  pink: "#e2a9b1",
  yellow: "#e3c565",
  orange: "#d97a33",
  purple: "#5b4470",
  taupe: "#8b7d6b",
  stone: "#cfc4ae"
};
function hexFor(name, hex) {
  const h = String(hex || "").trim().toLowerCase();
  if (/^#[0-9a-f]{6}$/.test(h)) return h;
  if (/^#[0-9a-f]{3}$/.test(h)) return "#" + h.slice(1).split("").map((c) => c + c).join("");
  const n = name.toLowerCase().trim();
  if (NAMED[n]) return NAMED[n];
  const last = n.split(/\s+/).pop() || "";
  return NAMED[last] || "#888888";
}
var cap1 = (s) => s.replace(/\s+/g, " ").trim().replace(/\b([a-z])/g, (m) => m.toUpperCase());
function rgbOf(h) {
  const x = h.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(x.slice(i, i + 2), 16));
}
function hsv(h) {
  const [r, g, b] = rgbOf(h).map((v) => v / 255), mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  let hue = 0;
  if (d) hue = mx === r ? (g - b) / d % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  hue = (hue * 60 + 360) % 360;
  return { h: hue, s: mx ? d / mx : 0, v: mx, r: r * 255, g: g * 255, b: b * 255 };
}
function lab(h) {
  const c = rgbOf(h).map((u) => {
    u /= 255;
    return u > 0.04045 ? Math.pow((u + 0.055) / 1.055, 2.4) : u / 12.92;
  });
  const X = (c[0] * 0.4124 + c[1] * 0.3576 + c[2] * 0.1805) / 0.95047, Y = c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722, Z = (c[0] * 0.0193 + c[1] * 0.1192 + c[2] * 0.9505) / 1.08883;
  const f = (v) => v > 8856e-6 ? Math.cbrt(v) : 7.787 * v + 16 / 116;
  return [116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))];
}
function deltaE(a, b) {
  const A = lab(a), B = lab(b);
  return Math.hypot(A[0] - B[0], A[1] - B[1], A[2] - B[2]);
}
function nearestInPalette(hex, palette) {
  if (!/^#[0-9a-f]{6}$/i.test(hex) || !Array.isArray(palette)) return "";
  const pal = palette.map((p) => String(p).toLowerCase()).filter((p) => /^#[0-9a-f]{6}$/.test(p)).slice(0, 8);
  if (!pal.length) return "";
  let best = "", bd = 1e9;
  pal.forEach((p) => {
    const d = deltaE(p, hex);
    if (d < bd) {
      bd = d;
      best = p;
    }
  });
  if (best !== pal[0] && deltaE(pal[0], hex) <= bd + 12) return pal[0];
  return best;
}
function snapToPalette(hex, palette) {
  const best = nearestInPalette(hex, palette);
  return best && deltaE(best, hex) < 35 ? best : hex;
}
var FAM_WORDS = {
  brown: ["brown", "tan", "camel", "chocolate", "cognac", "caramel", "chestnut", "mocha", "tobacco", "coffee", "espresso"],
  yellow: ["mustard", "yellow", "ochre", "gold", "saffron"],
  red: ["red", "burgundy", "wine", "oxblood", "maroon", "bordeaux", "claret", "crimson", "brick", "cranberry"],
  blue: ["blue", "navy", "denim", "indigo", "cobalt", "chambray"],
  teal: ["teal", "petrol", "aqua", "turquoise"]
};
function famOf(name) {
  const words = name.toLowerCase().split(/[^a-z]+/).filter(Boolean);
  for (const f of Object.keys(FAM_WORDS)) if (FAM_WORDS[f].some((w) => words.indexOf(w) !== -1)) return f;
  return "";
}
var POLO_FROM = ["Shirts", "Button downs", "Tees", "Polos", "Sweaters", "Jackets"];
function lev(a, b) {
  const d = [];
  for (let i = 0; i <= a.length; i++) d[i] = [i];
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[a.length][b.length];
}
var nb = (s) => s.toLowerCase().normalize("NFD").replace(/[^a-z0-9]/g, "");
function matchBrand(brand, brands) {
  if (!brand || !Array.isArray(brands)) return "";
  const b = nb(brand);
  if (b.length < 3) return "";
  let best = "", bd = 99;
  brands.map(String).slice(0, 300).forEach((k) => {
    const n = nb(k);
    if (n.length < 3) return;
    const d = n === b ? 0 : b.length >= 5 && (b.indexOf(n) === 0 || n.indexOf(b) === 0) ? 0.5 : lev(n, b);
    if (d < bd && d <= Math.max(1, Math.floor(n.length / 4))) {
      bd = d;
      best = k;
    }
  });
  return best;
}
function applyRules(raw, palette, brands) {
  const r = { ...raw || {} }, rules = [];
  const cat = String(r.category || ""), g = String(r.garment || "").toLowerCase();
  const yes = (v) => v === true || v === "true";
  const shortOpening = r.placket === "short" || r.openingToHem === false || r.openingToHem === "false";
  if (yes(r.collar) && shortOpening && POLO_FROM.includes(cat) && cat !== "Polos" || cat !== "Polos" && /\bpolo\b/.test(g) && POLO_FROM.includes(cat)) {
    r.category = "Polos";
    r.garment = /long/.test(g) ? "long-sleeve polo" : /knit/.test(g) || yes(r.knit) ? "knit polo" : "polo";
    rules.push("polo");
  } else if (cat === "Polos" && /shirt|button/.test(g)) {
    r.garment = /long/.test(g) ? "long-sleeve polo" : "polo";
    rules.push("polo-name");
  }
  if (r.category === "Shoes") {
    if (yes(r.laces) && yes(r.moccasinStitch)) {
      if (!/boat/.test(g)) {
        r.garment = "boat shoes";
        rules.push("boat");
      }
    } else if (yes(r.pennyStrap) && !yes(r.laces)) {
      if (!/penny/.test(g)) {
        r.garment = "penny loafers";
        rules.push("penny");
      }
    } else if (/boat/.test(g) && (r.laces === false || r.laces === "false")) {
      r.garment = "loafers";
      rules.push("not-boat");
    }
  }
  if (yes(r.westernYoke) && ["Jackets", "Coats", "Button downs", "Shirts"].includes(String(r.category)) && r.category !== "Polos") {
    if (r.category !== "Shirts" || !/western/.test(String(r.garment))) {
      r.category = "Shirts";
      r.garment = "western shirt";
      rules.push("western");
    }
  }
  if (r.category === "Jackets" && !yes(r.outerwear) && r.placket === "full") {
    r.category = "Shirts";
    r.garment = /western/.test(g) ? "western shirt" : g.replace(/jacket/, "shirt") || "shirt";
    rules.push("shirt-not-jacket");
  }
  if (/jacket/.test(String(r.garment)) && r.category === "Shirts") r.garment = String(r.garment).replace(/jacket/, "shirt");
  if (r.brandSource === "none" && r.brand) {
    r.brand = "";
    rules.push("brand-unread");
  }
  if (r.brand && Array.isArray(brands) && brands.length) {
    const m = matchBrand(String(r.brand), brands);
    if (m && m !== r.brand) {
      r.brand = m;
      rules.push("brand-his");
    } else if (!m && r.brandSource !== "label") {
      r.brand = "";
      rules.push("brand-guess");
    }
  }
  const hex0 = String(r.colourHex || "").toLowerCase();
  const hex = snapToPalette(/^#[0-9a-f]{6}$/.test(hex0) ? hex0 : "", palette);
  if (hex && hex !== hex0) {
    r.colourHex = hex;
    rules.push("hex-snap");
  }
  const famHex = nearestInPalette(hex, palette);
  if (famHex) {
    const pal0 = Array.isArray(palette) && /^#[0-9a-f]{6}$/i.test(String(palette[0])) ? String(palette[0]).toLowerCase() : "";
    const cands = [famHex].concat(pal0 && pal0 !== famHex && deltaE(pal0, famHex) < 25 ? [pal0] : []);
    const fam = famOf(String(r.colourName || ""));
    for (const ch of cands) {
      const c = hsv(ch);
      if ((fam === "brown" || fam === "") && (c.h < 10 || c.h > 345) && c.s >= 0.3 && !/olive|green|grey|gray|black|white|cream|navy/i.test(String(r.colourName))) {
        r.colourName = c.v < 0.6 || c.s < 0.5 ? "Burgundy" : "Red";
        rules.push("colour:red");
        break;
      } else if (fam === "yellow" && c.h >= 15 && c.h <= 40 && c.s >= 0.4) {
        r.colourName = c.v > 0.75 ? "Tan" : "Camel";
        rules.push("colour:camel");
        break;
      } else if (fam === "blue" && c.h >= 150 && c.h <= 200 && c.g >= c.b - 2 && !/navy/i.test(String(r.colourName))) {
        r.colourName = "Teal";
        rules.push("colour:teal");
        break;
      }
    }
  }
  return { raw: r, rules };
}
function normaliseIdentity(raw) {
  const cat = ID_CATEGORIES.find((c) => c.toLowerCase() === String(raw?.category || "").toLowerCase().trim()) || "Shirts";
  const colourName = cap1(String(raw?.colourName || "").slice(0, 30)) || "";
  const colourHex = hexFor(colourName, raw?.colourHex);
  let brand = String(raw?.brand || "").replace(/\s+/g, " ").trim().slice(0, 40);
  if (/^(unknown|none|n\/a|no brand|unbranded|not visible)$/i.test(brand)) brand = "";
  const garment = String(raw?.garment || "").replace(/\s+/g, " ").trim().slice(0, 40).toLowerCase() || cat.toLowerCase().replace(/s$/, "");
  const mraw = String(raw?.material || "").toLowerCase();
  const material = MATERIALS.find((m) => new RegExp("\\b" + m + "\\b").test(mraw)) || "";
  const g = material && garment.indexOf(material) === -1 ? material + " " + garment : garment;
  const name = cap1([brand, colourName, g].filter(Boolean).join(" ")).slice(0, 80);
  const confidence = Math.max(0, Math.min(1, Number(raw?.confidence) || 0));
  return { category: cat, name, brand, colourName: colourName || "Unknown", colourHex, garment, material, confidence };
}
function parseOut(res) {
  const r = res?.response ?? res?.result?.response ?? res;
  if (r && typeof r === "object" && !Array.isArray(r) && (r.category || r.garment)) return r;
  const s = typeof r === "string" ? r : res?.choices?.[0]?.message?.content ?? "";
  if (typeof s === "string" && s.indexOf("{") >= 0) return JSON.parse(s.slice(s.indexOf("{"), s.lastIndexOf("}") + 1));
  throw new Error("no json");
}
async function handleIdentify(req, env, acct, json2) {
  if (!env.AI) return json2({ error: "not_configured", message: "Photo reading isn't available right now." }, 503);
  const len = Number(req.headers.get("content-length") || 0);
  if (len > MAX_IMAGE_CHARS + 4096) return json2({ error: "too_large" }, 413);
  let body;
  try {
    body = await req.json();
  } catch {
    return json2({ error: "bad_request" }, 400);
  }
  const image = String(body?.image || "");
  if (image.length > MAX_IMAGE_CHARS) return json2({ error: "too_large" }, 413);
  if (!/^data:image\/(jpeg|jpg|png|webp);base64,[A-Za-z0-9+/=]{200,}$/.test(image)) return json2({ error: "bad_request", message: "Send the photo as a JPEG, PNG or WebP data URI." }, 400);
  const day = (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
  const capN = Number(env.IDENTIFY_CAP_PER_DAY || ID_CAP_DEFAULT) || ID_CAP_DEFAULT;
  const ck = "idcap/" + acct + "/" + day;
  const used = Number(await env.TRYON_KV.get(ck)) || 0;
  if (used >= capN) return json2({ error: "daily_cap", message: "That's today's photo reads \u2014 the rest tomorrow." }, 429);
  await env.TRYON_KV.put(ck, String(used + 1), { expirationTtl: 2 * DAY2 });
  const model = ID_MODELS.includes(String(body?.model)) ? String(body.model) : env.IDENTIFY_MODEL || IDENTIFY_MODEL;
  const plan = body?.mode === "schema" ? [[model, "schema"], [model, "plain"]] : body?.mode === "plain-only" ? [[model, "plain"]] : [[model, "plain"], [model === IDENTIFY_FALLBACK ? IDENTIFY_MODEL : IDENTIFY_FALLBACK, "plain"]];
  let used_model = model;
  const t0 = Date.now();
  const hint = String(body?.hint || "").slice(0, 200);
  const brandHint = Array.isArray(body?.brands) ? body.brands.map((b) => String(b).replace(/[^\p{L}\p{N} &'.-]/gu, "").slice(0, 30)).filter(Boolean).slice(0, 80).join(", ") : "";
  let raw = null;
  const tries = [];
  for (const [m, mode] of plan) {
    if (raw) break;
    const ta = Date.now();
    try {
      const input = {
        messages: [
          { role: "system", content: SYSTEM },
          { role: "user", content: [{ type: "text", text: "Catalogue this garment." + (hint ? " Owner's note: " + hint : "") + (brandHint ? " Brands he owns (use this spelling if the label is one of them): " + brandHint + "." : "") }, { type: "image_url", image_url: { url: image } }] }
        ],
        max_tokens: 400,
        temperature: 0
      };
      if (mode === "schema") input.response_format = { type: "json_schema", json_schema: SCHEMA2 };
      raw = parseOut(await env.AI.run(m, input));
      used_model = m;
      tries.push({ mode, ms: Date.now() - ta });
    } catch (e) {
      tries.push({ mode: m.split("/").pop() + ":" + mode, ms: Date.now() - ta, err: String(e?.message || e).slice(0, 300) });
    }
  }
  if (!raw) {
    console.log("identify failed", JSON.stringify(tries));
    return json2({ error: "model_failed", message: "Couldn't read that photo.", tries }, 502);
  }
  const ruled = applyRules(raw, body?.palette, body?.brands);
  const seen = {};
  ["collar", "placket", "knit", "outerwear", "laces", "moccasinStitch", "siping", "pennyStrap", "brandSource"].forEach((k) => {
    if (raw && raw[k] !== void 0) seen[k] = raw[k];
  });
  return json2({ ...normaliseIdentity(ruled.raw), meta: { model: used_model, rules: ruled.rules, seen, ms: Date.now() - t0, tries, remaining: Math.max(0, capN - used - 1) } });
}

// src/worker.ts
var SLOTS = ["under", "top", "outer", "bottom", "accessory", "shoes"];
var MAX_ITEMS = 6;
var MAX_IMAGE_BYTES = 10 * 1024 * 1024;
var MAX_BODY = 40 * 1024 * 1024;
var CAP_DEFAULT = 100;
var STEP_RETRIES = 2;
var JOB_TIMEOUT_MS = 15 * 60 * 1e3;
var MAX_TRANSIENT = 20;
var DAY3 = 24 * 3600;
var FASHN_KEY_KV = "config:fashn_api_key";
var MAX_FASHN_KEY_CHARS = 512;
var MAIN_ACCT = "8aae436e68826044";
var enc = new TextEncoder();
async function sha256hex(s) {
  const b = await crypto.subtle.digest("SHA-256", enc.encode(s));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}
var CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, PUT, OPTIONS",
  "access-control-allow-headers": "authorization, content-type"
};
var json = (obj, status = 200) => new Response(JSON.stringify(obj), {
  status,
  headers: { "content-type": "application/json", "cache-control": "no-store", ...CORS }
});
async function acctFor(env, req) {
  const auth = req.headers.get("authorization") || "";
  const key = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  if (!/^[0-9a-f]{48}$/.test(key)) return null;
  const h = await sha256hex(key);
  return await env.SYNC_KV.get("key/" + h);
}
async function fashnKey(env) {
  return env.FASHN_API_KEY || await env.TRYON_KV.get(FASHN_KEY_KV) || null;
}
function bytesToB64(bytes) {
  let s = "";
  const CH = 32768;
  for (let i = 0; i < bytes.length; i += CH) {
    s += String.fromCharCode(...bytes.subarray(i, i + CH));
  }
  return btoa(s);
}
function b64ToBytes(b64) {
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}
var DATA_URI_RE = /^data:image\/(jpeg|jpg|png|webp);base64,([A-Za-z0-9+/=\s]+)$/;
function hostBlocked(u) {
  if (u.protocol !== "https:") return true;
  if (u.username || u.password) return true;
  const h = u.hostname.toLowerCase();
  if (h === "localhost" || h.endsWith(".localhost") || h.endsWith(".local") || h.endsWith(".internal")) return true;
  if (/^\d+\.\d+\.\d+\.\d+$/.test(h) || h.includes(":") || h.startsWith("[")) return true;
  return false;
}
async function toDataUri(image, fetcher = fetch) {
  const m = DATA_URI_RE.exec(image);
  if (m) {
    const approx = Math.floor(m[2].length * 0.75);
    if (approx > MAX_IMAGE_BYTES) throw new Error("image too large");
    return image.replace(/\s/g, "");
  }
  let u;
  try {
    u = new URL(image);
  } catch {
    throw new Error("image must be an https URL or an image data URI");
  }
  if (hostBlocked(u)) throw new Error("image URL not allowed");
  const r = await fetcher(u.toString(), {
    headers: { "user-agent": "Mozilla/5.0 (wardrobe-tryon)", accept: "image/*" },
    redirect: "follow"
  });
  if (!r.ok) throw new Error("could not fetch image (HTTP " + r.status + ")");
  let ct = (r.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
  const buf = new Uint8Array(await r.arrayBuffer());
  if (buf.length > MAX_IMAGE_BYTES) throw new Error("image too large");
  if (buf.length < 100) throw new Error("image empty");
  if (!/^image\/(jpeg|jpg|png|webp)$/.test(ct)) {
    if (buf[0] === 255 && buf[1] === 216) ct = "image/jpeg";
    else if (buf[0] === 137 && buf[1] === 80) ct = "image/png";
    else if (buf[8] === 87 && buf[9] === 69 && buf[10] === 66 && buf[11] === 80) ct = "image/webp";
    else throw new Error("URL is not a jpeg/png/webp image");
  }
  if (ct === "image/jpg") ct = "image/jpeg";
  return "data:" + ct + ";base64," + bytesToB64(buf);
}
function planSteps(items) {
  const hasOuter = items.some((i) => i.slot === "outer");
  const groups = { under: [], outer: [], top: [], bottom: [], accessory: [], shoes: [] };
  items.forEach((it, i) => {
    if (it.slot === "top" || it.slot === "under") groups[hasOuter ? "under" : it.slot === "under" ? "under" : "top"].push(i);
    else groups[it.slot].push(i);
  });
  const order = [...groups.under, ...groups.outer, ...groups.top, ...groups.bottom, ...groups.accessory, ...groups.shoes];
  const underNames = groups.under.map((i) => items[i].name || "shirt");
  const steps = order.map((i) => {
    const it = items[i];
    const parts = [];
    if (it.slot === "outer" && underNames.length) parts.push("worn over the " + underNames[underNames.length - 1]);
    if (it.prompt) parts.push(it.prompt);
    return { slot: it.slot, name: (it.name || it.slot).slice(0, 120), prompt: parts.join("; ").slice(0, 300) };
  });
  return { order, steps };
}
function validateItems(v) {
  if (!Array.isArray(v) || v.length === 0) return "items must be a non-empty array";
  if (v.length > MAX_ITEMS) return "at most " + MAX_ITEMS + " items per try-on";
  const out = [];
  for (const x of v) {
    if (!x || typeof x !== "object") return "bad item";
    const it = x;
    if (!SLOTS.includes(it.slot)) return "slot must be one of " + SLOTS.join(", ");
    if (typeof it.image !== "string" || it.image.length < 10) return "image required";
    if (it.name !== void 0 && typeof it.name !== "string") return "bad name";
    if (it.prompt !== void 0 && typeof it.prompt !== "string") return "bad prompt";
    out.push({ slot: it.slot, image: it.image, name: it.name, prompt: it.prompt });
  }
  return out;
}
function fashnBase(env) {
  return env.FASHN_API || "https://api.fashn.ai/v1";
}
async function fashnSubmit(env, modelImage, productImage, prompt, seed) {
  const inputs = {
    model_image: modelImage,
    product_image: productImage,
    resolution: env.FASHN_RESOLUTION || "1k",
    generation_mode: env.FASHN_MODE || "balanced",
    num_images: 1,
    output_format: "jpeg",
    return_base64: true,
    seed
  };
  if (prompt) inputs.prompt = prompt;
  const key = await fashnKey(env);
  const r = await fetch(fashnBase(env) + "/run", {
    method: "POST",
    headers: { authorization: "Bearer " + key, "content-type": "application/json" },
    body: JSON.stringify({ model_name: "tryon-max", inputs })
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok || !body.id) {
    const err = new Error("fashn submit HTTP " + r.status + " " + JSON.stringify(body.error ?? "").slice(0, 160));
    err.transient = r.status === 429 || r.status >= 500;
    throw err;
  }
  return body.id;
}
async function fashnStatus(env, id) {
  const key = await fashnKey(env);
  const r = await fetch(fashnBase(env) + "/status/" + encodeURIComponent(id), {
    headers: { authorization: "Bearer " + key }
  });
  if (!r.ok) {
    const err = new Error("fashn status HTTP " + r.status);
    err.transient = true;
    throw err;
  }
  return await r.json();
}
var jobKey = (id) => "job/" + id;
var garmKey = (id, i) => "garm/" + id + "/" + i;
var stepImgKey = (id) => "step/" + id;
var imgKey = (id) => "img/" + id;
var capKey = (acct, day) => "cap/" + acct + "/" + day;
var templateKey = (acct) => "template/" + acct;
async function getJob(env, id) {
  const raw = await env.TRYON_KV.get(jobKey(id));
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}
var putJob = (env, job) => env.TRYON_KV.put(jobKey(job.id), JSON.stringify(job));
async function getTemplate(env, acct) {
  const own = await env.TRYON_KV.get(templateKey(acct));
  const uri = own ?? await env.TRYON_KV.get(templateKey("default"));
  if (!uri) return null;
  return { uri, ver: (await sha256hex(uri)).slice(0, 16) };
}
function publicJob(job, origin) {
  return {
    id: job.id,
    status: job.status,
    step: Math.min(job.step + (job.status === "done" ? 0 : 1), job.steps.length),
    steps: job.steps.length,
    slots: job.steps.map((s) => s.slot),
    resultUrl: job.status === "done" ? origin + "/r/" + job.id + ".jpg" : null,
    note: job.note ?? null,
    createdAt: job.createdAt,
    updatedAt: job.updatedAt
  };
}
function capFor(env) {
  const n = Number(env.TRYON_CAP_PER_DAY);
  return env.TRYON_CAP_PER_DAY !== void 0 && Number.isFinite(n) && n >= 0 ? Math.floor(n) : CAP_DEFAULT;
}
var notConfigured = () => json({
  error: "not_configured",
  message: "Try-on isn't switched on yet: the server is waiting for its FASHN API key."
}, 503);
async function handleCreate(req, env, origin) {
  const acct = await acctFor(env, req);
  if (!acct) return json({ error: "unauthorized" }, 401);
  if (!await fashnKey(env)) return notConfigured();
  const raw = await req.text();
  if (raw.length > MAX_BODY) return json({ error: "too large" }, 413);
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  const items = validateItems(body.items);
  if (typeof items === "string") return json({ error: "bad_request", message: items }, 400);
  const template = await getTemplate(env, acct);
  if (!template) {
    return json({ error: "not_configured", message: "No person photo is set up for try-on yet." }, 503);
  }
  const { order, steps } = planSteps(items);
  const garments = [];
  for (const i of order) {
    try {
      garments.push(await toDataUri(items[i].image));
    } catch (e) {
      return json({ error: "garment_image", message: e.message, slot: items[i].slot }, 422);
    }
  }
  const mode = (env.FASHN_MODE || "balanced") + "/" + (env.FASHN_RESOLUTION || "1k");
  const garmHashes = await Promise.all(garments.map((g) => sha256hex(g)));
  const canonical = JSON.stringify({ acct, t: template.ver, mode, steps, g: garmHashes });
  const id = (await sha256hex(canonical)).slice(0, 32);
  const existing = await getJob(env, id);
  if (existing && existing.status !== "failed") return json(publicJob(existing, origin), 200);
  const cap = capFor(env);
  const day = (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
  const used = Number(await env.TRYON_KV.get(capKey(acct, day))) || 0;
  if (used + steps.length > cap) {
    return json({ error: "daily_cap", message: "Daily try-on limit reached. It resets at midnight UTC.", cap, used }, 429);
  }
  await env.TRYON_KV.put(capKey(acct, day), String(used + steps.length), { expirationTtl: 3 * DAY3 });
  for (let i = 0; i < garments.length; i++) {
    await env.TRYON_KV.put(garmKey(id, i), garments[i], { expirationTtl: DAY3 });
  }
  const now = Date.now();
  const job = {
    id,
    acct,
    status: "running",
    steps,
    step: 0,
    predictionId: null,
    attempts: 0,
    transient: 0,
    createdAt: now,
    updatedAt: now
  };
  try {
    job.predictionId = await fashnSubmit(env, template.uri, garments[0], steps[0].prompt, 42);
    job.attempts = 1;
  } catch (e) {
    if (!e.transient) {
      job.status = "failed";
      job.note = "The try-on service rejected the request.";
      console.log("submit failed", id, e.message);
    } else {
      job.transient = 1;
    }
  }
  await putJob(env, job);
  return json(publicJob(job, origin), 202);
}
async function advance(env, job) {
  if (job.status !== "running") return job;
  const now = Date.now();
  if (now - job.createdAt > JOB_TIMEOUT_MS) {
    job.status = "failed";
    job.note = "Timed out.";
    job.updatedAt = now;
    await putJob(env, job);
    return job;
  }
  const personFor = async (step) => {
    if (step === 0) return (await getTemplate(env, job.acct))?.uri ?? null;
    return await env.TRYON_KV.get(stepImgKey(job.id));
  };
  try {
    if (!job.predictionId) {
      const person = await personFor(job.step);
      const garment = await env.TRYON_KV.get(garmKey(job.id, job.step));
      if (!person || !garment) throw Object.assign(new Error("inputs expired"), { transient: false });
      job.predictionId = await fashnSubmit(env, person, garment, job.steps[job.step].prompt, 42 + 1e3 * job.attempts);
      job.attempts++;
      job.transient = 0;
    } else {
      const st = await fashnStatus(env, job.predictionId);
      job.transient = 0;
      if (st.status === "completed" && st.output && st.output[0]) {
        let out = st.output[0];
        if (!out.startsWith("data:")) {
          out = await toDataUri(out);
        }
        job.step++;
        job.predictionId = null;
        job.attempts = 0;
        if (job.step >= job.steps.length) {
          const m = DATA_URI_RE.exec(out);
          if (!m) throw new Error("unexpected output format");
          await env.TRYON_KV.put(imgKey(job.id), b64ToBytes(m[2].replace(/\s/g, "")), {
            metadata: { ct: "image/" + (m[1] === "jpg" ? "jpeg" : m[1]) }
          });
          job.status = "done";
          await env.TRYON_KV.delete(stepImgKey(job.id)).catch(() => {
          });
        } else {
          await env.TRYON_KV.put(stepImgKey(job.id), out, { expirationTtl: DAY3 });
          const garment = await env.TRYON_KV.get(garmKey(job.id, job.step));
          if (!garment) throw Object.assign(new Error("inputs expired"), { transient: false });
          job.predictionId = await fashnSubmit(env, out, garment, job.steps[job.step].prompt, 42);
          job.attempts = 1;
        }
      } else if (st.status === "failed" || st.status === "canceled") {
        console.log("prediction failed", job.id, JSON.stringify(st.error ?? "").slice(0, 200));
        job.predictionId = null;
        if (job.attempts > STEP_RETRIES) {
          job.status = "failed";
          job.note = "The try-on service couldn't render this piece.";
        }
      }
    }
  } catch (e) {
    const transient = e.transient !== false;
    console.log("advance error", job.id, e.message.slice(0, 200));
    if (!transient || ++job.transient > MAX_TRANSIENT) {
      job.status = "failed";
      job.note = "Render failed.";
    }
  }
  job.updatedAt = Date.now();
  await putJob(env, job);
  return job;
}
async function handleGet(req, env, origin, id) {
  const acct = await acctFor(env, req);
  if (!acct) return json({ error: "unauthorized" }, 401);
  if (!/^[0-9a-f]{32}$/.test(id)) return json({ error: "not found" }, 404);
  let job = await getJob(env, id);
  if (!job || job.acct !== acct) return json({ error: "not found" }, 404);
  if (job.status === "running") {
    if (!await fashnKey(env)) return notConfigured();
    job = await advance(env, job);
  }
  return json(publicJob(job, origin));
}
async function handleTemplate(req, env) {
  const acct = await acctFor(env, req);
  if (!acct) return json({ error: "unauthorized" }, 401);
  let body;
  try {
    body = await req.json();
  } catch {
    return json({ error: "bad json" }, 400);
  }
  if (typeof body.image !== "string" || !DATA_URI_RE.test(body.image)) {
    return json({ error: "bad_request", message: "image must be a jpeg/png/webp data URI" }, 400);
  }
  if (body.image.length > MAX_IMAGE_BYTES * 1.4) return json({ error: "too large" }, 413);
  await env.TRYON_KV.put(templateKey(acct), body.image.replace(/\s/g, ""));
  return json({ ok: true });
}
async function handleAdminFashnKey(req, env) {
  const acct = await acctFor(env, req);
  if (!acct) return json({ error: "unauthorized" }, 401);
  if (acct !== MAIN_ACCT) return json({ error: "forbidden" }, 403);
  const raw = (await req.text()).trim();
  if (!raw || raw.length > MAX_FASHN_KEY_CHARS) {
    return json({ error: "bad_request" }, 400);
  }
  await env.TRYON_KV.put(FASHN_KEY_KV, raw);
  return json({ ok: true });
}
async function handleResult(env, id) {
  if (!/^[0-9a-f]{32}$/.test(id)) return new Response("not found", { status: 404, headers: CORS });
  const buf = await env.TRYON_KV.get(imgKey(id), "arrayBuffer");
  if (!buf) return new Response("not found", { status: 404, headers: CORS });
  return new Response(buf, {
    headers: {
      "content-type": "image/jpeg",
      "cache-control": "public, max-age=31536000, immutable",
      ...CORS
    }
  });
}
async function handler(req, env) {
  const url = new URL(req.url);
  const origin = url.origin;
  const p = url.pathname.replace(/\/+$/, "") || "/";
  try {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (req.method === "GET" && (p === "/" || p === "/health")) {
      return json({
        ok: true,
        service: "wardrobe-tryon",
        engine: "fashn/tryon-max",
        configured: !!await fashnKey(env),
        ask: { configured: !!env.AI || !!openaiKey(env), provider: openaiKey(env) ? "openai" : "workers-ai", model: openaiKey(env) ? (OPENAI_OK_MODEL || openaiModels(env)[0]) : (env.ASK_MODEL || DEFAULT_MODEL) },
        identify: { configured: !!env.AI, model: env.IDENTIFY_MODEL || IDENTIFY_MODEL }
      });
    }
    if (p === "/tryon" && req.method === "POST") return await handleCreate(req, env, origin);
    let m = /^\/tryon\/([^/]+)$/.exec(p);
    if (m && req.method === "GET") return await handleGet(req, env, origin, m[1]);
    if (p === "/template" && req.method === "PUT") return await handleTemplate(req, env);
    if (p === "/admin/fashn-key" && req.method === "PUT") return await handleAdminFashnKey(req, env);
    if (p === "/ask" && req.method === "POST") {
      const acct = await acctFor(env, req);
      if (!acct) return json({ error: "unauthorized" }, 401);
      return await handleAsk(req, env, acct, json);
    }
    if (p === "/identify" && req.method === "POST") {
      const acct = await acctFor(env, req);
      if (!acct) return json({ error: "unauthorized" }, 401);
      return await handleIdentify(req, env, acct, json);
    }
    if (p === "/ask/ping" && req.method === "GET") return await handleAskPing(env, json);
    if (p === "/ask/catalog" && req.method === "GET") {
      const acct = await acctFor(env, req);
      if (!acct) return json({ error: "unauthorized" }, 401);
      return await handleCatalog(env, json);
    }
    if (p === "/admin/catalog" && req.method === "PUT") {
      const acct = await acctFor(env, req);
      if (!acct) return json({ error: "unauthorized" }, 401);
      if (acct !== MAIN_ACCT) return json({ error: "forbidden" }, 403);
      return await handleAdminCatalog(req, env, json);
    }
    m = /^\/r\/([0-9a-f]+)\.jpg$/.exec(p);
    if (m && (req.method === "GET" || req.method === "HEAD")) return await handleResult(env, m[1]);
    return json({ error: "not found" }, 404);
  } catch (e) {
    console.log("unhandled", e.message);
    return json({ error: "server_error" }, 500);
  }
}
var worker_default = {
  fetch: (req, env) => handler(req, env)
};
export {
  MAIN_ACCT,
  SLOTS,
  acctFor,
  advance,
  b64ToBytes,
  bytesToB64,
  worker_default as default,
  fashnKey,
  handler,
  planSteps,
  sha256hex,
  toDataUri,
  validateItems
};
