// Round-trip tests for wardrobe-sync, run against a local server.
// Usage: deno run --allow-net --allow-env test.ts [baseUrl]
// The dev server must run with the test secrets/cap as vars:
//   npx wrangler dev --var RENDER_WATCHER_SECRET:test-watcher-secret \
//     --var REGISTER_SECRET:test-register-secret \
//     --var RENDER_CAP_PER_DAY:3 --persist-to <a FRESH state dir>
const BASE = Deno.args[0] || "http://localhost:8787";

let pass = 0, fail = 0;
function check(name: string, cond: boolean, extra = "") {
  if (cond) { pass++; console.log("  ok  " + name); }
  else { fail++; console.log("  FAIL " + name + (extra ? " — " + extra : "")); }
}
const eq = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

async function sync(key: string | null, body: unknown) {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (key) headers.authorization = "Bearer " + key;
  const r = await fetch(BASE + "/sync", {
    method: "POST", headers, body: JSON.stringify(body),
  });
  return { status: r.status, j: await r.json().catch(() => null) };
}

// 1. Root + auth behaviour
{
  const r = await fetch(BASE + "/");
  const j = await r.json();
  check("GET / identifies the service", r.status === 200 && j.ok === true && j.service === "wardrobe-sync");
  const bad = await sync("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", { since: 0, changes: [], meta: null });
  check("wrong key -> 401 unauthorized", bad.status === 401 && bad.j?.error === "unauthorized");
  const none = await sync(null, { since: 0, changes: [], meta: null });
  check("no key -> 401 unauthorized", none.status === 401 && none.j?.error === "unauthorized");
  const malformed = await sync("not-a-key", { since: 0, changes: [], meta: null });
  check("malformed key -> 401", malformed.status === 401);
}

// 2. Register (gated by the REGISTER_SECRET worker secret)
const REG_SECRET = Deno.env.get("REGISTER_SECRET") || "test-register-secret";
async function register(secret?: string) {
  const headers: Record<string, string> = {};
  if (secret !== undefined) headers["x-register-secret"] = secret;
  const r = await fetch(BASE + "/register", { method: "POST", headers });
  return { status: r.status, j: await r.json().catch(() => null) };
}
{
  const noCode = await register();
  check("register without the code -> 403", noCode.status === 403 && noCode.j?.error === "register_code_required");
  const wrongCode = await register("not-the-code");
  check("register with a wrong code -> 403", wrongCode.status === 403);
}
const regRes = await register(REG_SECRET);
const reg = regRes.j;
check("register with the code returns a 48-hex key", regRes.status === 200 && /^[0-9a-f]{48}$/.test(reg.key));
check("register returns an account id", typeof reg.acct === "string" && reg.acct.length >= 8);
const KEY = reg.key;

// A photo-sized payload: ~250 KB data URI, like a closet item photo.
const bigPhoto = "data:image/jpeg;base64," + "QUJD".repeat(65000);
const lookA = { id: "look-1", title: "Navy knit & white jeans", verdict: "like" };
const itemA = { id: "item-1", name: "Isaia cream polo", photo: bigPhoto };
const metaA = { profile: { city: "Palm Beach" }, deletedIds: [], overrides: {}, dislikedImgs: ["imgX"] };
const T = 1_700_000_000_000;

// 3. Device A uploads (first sync)
{
  const r = await sync(KEY, {
    since: 0,
    changes: [
      { coll: "looks", id: "look-1", updatedAt: T + 1, data: lookA },
      { coll: "items", id: "item-1", updatedAt: T + 2, data: itemA },
    ],
    meta: { updatedAt: T + 3, data: metaA },
  });
  check("A upload accepted", r.status === 200);
  check("A gets no echo of its own writes", (r.j?.recs || []).length === 0, JSON.stringify(r.j?.recs?.length));
  check("A meta not echoed", r.j?.meta === null);
  check("A receives a sequence horizon", typeof r.j?.now === "number" && r.j.now >= 3);
}

// 4. Device B (same key, fresh) pulls everything
let bNow = 0;
{
  const r = await sync(KEY, { since: 0, changes: [], meta: null });
  const recs = r.j?.recs || [];
  const look = recs.find((x: { id: string }) => x.id === "look-1");
  const item = recs.find((x: { id: string }) => x.id === "item-1");
  check("B receives both records", recs.length === 2);
  check("B look matches A's", eq(look?.data, lookA));
  check("B photo payload byte-identical (>64KB chunking)", item?.data?.photo === bigPhoto,
    "len " + (item?.data?.photo?.length || 0) + " vs " + bigPhoto.length);
  check("B meta matches A's", eq(r.j?.meta?.data, metaA));
  bNow = r.j?.now || 0;
}

// 5. B edits the look with a newer timestamp; A pulls and sees it
{
  const edited = { ...lookA, verdict: "love", comment: "wore it Friday" };
  const up = await sync(KEY, { since: bNow, changes: [{ coll: "looks", id: "look-1", updatedAt: T + 10, data: edited }], meta: null });
  check("B edit accepted, no echo", up.status === 200 && (up.j?.recs || []).length === 0);
  const down = await sync(KEY, { since: 3, changes: [], meta: null });
  const look = (down.j?.recs || []).find((x: { id: string }) => x.id === "look-1");
  check("A receives B's newer edit", eq(look?.data, edited));
}

// 6. Stale write must not regress (last-writer-wins)
{
  await sync(KEY, { since: 0, changes: [{ coll: "looks", id: "look-1", updatedAt: T + 5, data: lookA }], meta: null });
  const r = await sync(KEY, { since: 0, changes: [], meta: null });
  const look = (r.j?.recs || []).find((x: { id: string }) => x.id === "look-1");
  check("stale write ignored, newer data kept", look?.data?.verdict === "love");
}

// 7. Tombstone: A deletes the item; B learns of the deletion
{
  await sync(KEY, { since: 0, changes: [{ coll: "items", id: "item-1", updatedAt: T + 20, deleted: true }], meta: null });
  const r = await sync(KEY, { since: 0, changes: [], meta: null });
  const item = (r.j?.recs || []).find((x: { id: string }) => x.id === "item-1");
  check("tombstone delivered", item?.deleted === true && item?.data === undefined);
  const look = (r.j?.recs || []).find((x: { id: string }) => x.id === "look-1");
  check("other records unaffected", look?.data?.verdict === "love");
}

// 8. A second account is fully isolated
{
  const reg2 = (await register(REG_SECRET)).j;
  const r = await sync(reg2.key, { since: 0, changes: [], meta: null });
  check("fresh account sees nothing", (r.j?.recs || []).length === 0 && r.j?.meta === null);
}

// 8b. Mass-delete guard: a pass deleting >20% of a collection is
// refused without an explicit confirmation, then allowed with it.
{
  const acct = (await register(REG_SECRET)).j;
  const up = [];
  for (let i = 0; i < 10; i++) {
    up.push({ coll: "items", id: "bulk-" + i, updatedAt: T + 100 + i, data: { id: "bulk-" + i } });
  }
  const seed = await sync(acct.key, { since: 0, changes: up, meta: null });
  check("bulk seed accepted", seed.status === 200);
  const dels = up.slice(0, 8).map((u, i) => ({ coll: "items", id: u.id, updatedAt: T + 200 + i, deleted: true }));
  const blocked = await sync(acct.key, { since: 0, changes: dels, meta: null });
  check("deleting 8 of 10 without confirmation -> 409 mass_delete",
    blocked.status === 409 && blocked.j?.error === "mass_delete" && blocked.j?.deletions === 8 && blocked.j?.live === 10,
    JSON.stringify(blocked.j));
  const peek = await sync(acct.key, { since: 0, changes: [], meta: null });
  check("blocked pass deleted nothing", (peek.j?.recs || []).filter((x: { deleted?: boolean }) => x.deleted).length === 0);
  // confirmMassDelete alone is no longer enough to tombstone live
  // records (server-truth). The Nov 18 hole is closed.
  const unproven = await sync(acct.key, { since: 0, changes: dels, meta: null, confirmMassDelete: true });
  check("confirm without baseline cancels live deletes",
    unproven.status === 200 && (unproven.j?.cancelled || []).length === 8,
    JSON.stringify(unproven.j?.cancelled));
  const still = await sync(acct.key, { since: 0, changes: [], meta: null });
  const stillLive = (still.j?.recs || []).filter((x: { data?: unknown; deleted?: boolean }) => x.data && !x.deleted).length;
  check("unproven confirm left all 10 live", stillLive === 10, "live=" + stillLive);
  // A matching baseline is the proof a new client must send.
  const ids = up.map((u) => u.id).sort();
  const bytes = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(ids.join("\n"))));
  const h = [...bytes].map((x) => x.toString(16).padStart(2, "0")).join("");
  const allowed = await sync(acct.key, {
    since: 0, changes: dels, meta: null, confirmMassDelete: true,
    baseline: { items: { n: ids.length, h } },
  });
  check("confirmed mass delete with matching baseline accepted", allowed.status === 200, JSON.stringify(allowed.j));
  const after = await sync(acct.key, { since: 0, changes: [], meta: null });
  const liveLeft = (after.j?.recs || []).filter((x: { data?: unknown; deleted?: boolean }) => x.data && !x.deleted).length;
  check("confirmed pass leaves the other 2 records", liveLeft === 2, "live=" + liveLeft);
  const small = await sync(acct.key, {
    since: 0,
    changes: [{ coll: "items", id: "bulk-8", updatedAt: T + 300, deleted: true }],
    meta: null,
  });
  check("a single ordinary delete needs no confirmation", small.status === 200);
}

// 9. Render queue (swap-rendering)
const WATCHER = Deno.env.get("RENDER_WATCHER_SECRET") || "test-watcher-secret";

async function rq(path: string, opts: {
  method?: string; key?: string | null; watcher?: string | null; body?: unknown;
} = {}) {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (opts.key) headers.authorization = "Bearer " + opts.key;
  if (opts.watcher) headers["x-watcher-secret"] = opts.watcher;
  const r = await fetch(BASE + path, {
    method: opts.method || "GET",
    headers,
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  });
  return { status: r.status, j: await r.json().catch(() => null) };
}

// The documented canonicalisation, reimplemented client-side exactly
// as the app must do it: sorted piece ids joined by "+", then "|",
// then the watch id or "" — first 16 hex chars of the SHA-256.
async function comboIdFor(pieces: string[], watchId: string | null) {
  const canonical = [...pieces].sort().join("+") + "|" + (watchId ?? "");
  const digest = await crypto.subtle.digest(
    "SHA-256", new TextEncoder().encode(canonical),
  );
  return [...new Uint8Array(digest)]
    .map((x) => x.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

const combo1 = {
  pieces: ["top-navy-knit", "bottom-white-jeans", "shoes-suede-loafer"],
  watchId: "vc-overseas",
  formality: "smart casual",
};
const cid1 = await comboIdFor(combo1.pieces, combo1.watchId);
const combo2 = { pieces: ["top-linen-shirt", "bottom-olive-shorts"], watchId: null };
const cid2 = await comboIdFor(combo2.pieces, null);

{
  check("comboId is 16 lowercase hex", /^[a-f0-9]{16}$/.test(cid1));
  const reordered = await comboIdFor([...combo1.pieces].reverse(), combo1.watchId);
  check("comboId is piece-order insensitive (sorted canonical)", reordered === cid1);
  const otherWatch = await comboIdFor(combo1.pieces, null);
  check("comboId changes with the watch", otherWatch !== cid1);
}

{
  const r = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: cid1, combo: combo1 } });
  check("enqueue accepted", r.status === 200, JSON.stringify(r.j));
  check("job starts queued", r.j?.status === "queued" && r.j?.comboId === cid1);
  check("job echoes the combo", eq(r.j?.combo?.pieces, combo1.pieces) && r.j?.combo?.watchId === "vc-overseas" && r.j?.combo?.formality === "smart casual");
  check("job carries requestedAt", typeof r.j?.requestedAt === "number");
  const again = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: cid1, combo: { pieces: ["a-different-piece"] } } });
  check("duplicate enqueue is a no-op (original kept)", again.status === 200 && again.j?.status === "queued" && eq(again.j?.combo?.pieces, combo1.pieces) && again.j?.requestedAt === r.j?.requestedAt);
}

{
  const r = await rq("/render-queue/" + cid1, { key: KEY });
  check("user GET round-trips the job", r.status === 200 && r.j?.comboId === cid1 && r.j?.status === "queued");
  const missing = await rq("/render-queue/0123456789abcdef", { key: KEY });
  check("unknown comboId -> 404", missing.status === 404);
}

{
  const list = await rq("/render-jobs", { watcher: WATCHER });
  check("watcher list shows the queued job", list.status === 200 && (list.j?.jobs || []).some((x: { comboId: string; status: string }) => x.comboId === cid1 && x.status === "queued"));
  const rend = await rq(`/render-jobs/${cid1}/status`, { method: "POST", watcher: WATCHER, body: { status: "rendering" } });
  check("watcher marks rendering", rend.status === 200 && rend.j?.status === "rendering");
  const list2 = await rq("/render-jobs", { watcher: WATCHER });
  check("rendering job leaves the queued list", !(list2.j?.jobs || []).some((x: { comboId: string }) => x.comboId === cid1));
  const done = await rq(`/render-jobs/${cid1}/status`, { method: "POST", watcher: WATCHER, body: { status: "done", note: "published" } });
  check("watcher marks done (note kept)", done.status === 200 && done.j?.status === "done" && done.j?.note === "published");
  const after = await rq("/render-queue/" + cid1, { key: KEY });
  check("user GET sees the done job", after.status === 200 && after.j?.status === "done");
  const requeue = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: cid1, combo: combo1 } });
  check("re-enqueue of a done job returns it unchanged", requeue.status === 200 && requeue.j?.status === "done");
}

{
  await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: cid2, combo: combo2 } });
  const list = await rq("/render-jobs", { watcher: WATCHER });
  check("second job appears in the queued list", (list.j?.jobs || []).some((x: { comboId: string }) => x.comboId === cid2));
  const failed = await rq(`/render-jobs/${cid2}/status`, { method: "POST", watcher: WATCHER, body: { status: "failed", note: "gate failed" } });
  check("watcher marks failed", failed.status === 200 && failed.j?.status === "failed");
  const list2 = await rq("/render-jobs", { watcher: WATCHER });
  check("failed job leaves the queued list", !(list2.j?.jobs || []).some((x: { comboId: string }) => x.comboId === cid2));
}

// A failed job is the one non-absorbing terminal state: an explicit
// re-submit revives it to queued (fresh timestamps, note cleared,
// back in the watcher index); a further re-submit is idempotent.
{
  const revived = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: cid2, combo: combo2 } });
  check("re-enqueue of a failed job revives it to queued", revived.status === 200 && revived.j?.status === "queued" && revived.j?.note === undefined);
  const list = await rq("/render-jobs", { watcher: WATCHER });
  check("revived job is back in the queued list", (list.j?.jobs || []).some((x: { comboId: string }) => x.comboId === cid2));
  const again = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: cid2, combo: combo2 } });
  check("re-enqueue of the revived job is idempotent", again.status === 200 && again.j?.status === "queued" && again.j?.requestedAt === revived.j?.requestedAt);
}

// The two auth surfaces must reject each other's credentials.
{
  const noAuth = await rq("/render-queue", { method: "POST", body: { comboId: cid1, combo: combo1 } });
  check("enqueue without a key -> 401", noAuth.status === 401);
  const watcherAsUser = await rq("/render-queue", { method: "POST", key: WATCHER, body: { comboId: cid1, combo: combo1 } });
  check("watcher secret as Bearer -> 401 on user endpoints", watcherAsUser.status === 401);
  const getAsWatcher = await rq("/render-queue/" + cid1, { watcher: WATCHER });
  check("user GET with only the watcher header -> 401", getAsWatcher.status === 401);
  const listNoAuth = await rq("/render-jobs", {});
  check("watcher list without the secret -> 401", listNoAuth.status === 401);
  const listWrong = await rq("/render-jobs", { watcher: "wrong-secret" });
  check("watcher list with a wrong secret -> 401", listWrong.status === 401);
  const listKey = await rq("/render-jobs", { watcher: KEY });
  check("sync key as watcher secret -> 401 on watcher endpoints", listKey.status === 401);
  const statusKey = await rq(`/render-jobs/${cid1}/status`, { method: "POST", key: KEY, body: { status: "done" } });
  check("status update with a sync key, no watcher secret -> 401", statusKey.status === 401);
}

// Validation (runs before the idempotency check, so existing ids are
// safe to reuse as targets here).
{
  const badId = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: "XYZ-not-hex", combo: combo1 } });
  check("bad comboId -> 400", badId.status === 400);
  const upper = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: "0123456789ABCDEF", combo: combo1 } });
  check("uppercase comboId -> 400", upper.status === 400);
  const empty = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: cid2, combo: { pieces: [] } } });
  check("empty pieces -> 400", empty.status === 400);
  const tooMany = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: cid2, combo: { pieces: ["a", "b", "c", "d", "e", "f", "g", "h", "i"] } } });
  check("nine pieces -> 400", tooMany.status === 400);
  const notArray = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: cid2, combo: { pieces: "top" } } });
  check("non-array pieces -> 400", notArray.status === 400);
  const numeric = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: cid2, combo: { pieces: [42] } } });
  check("non-string piece -> 400", numeric.status === 400);
  const big = await rq("/render-queue", { method: "POST", key: KEY, body: { comboId: cid2, combo: { pieces: ["x".repeat(5000)] } } });
  check("combo over the ~4 KB cap -> 400", big.status === 400);
  const badGet = await rq("/render-queue/nope", { key: KEY });
  check("malformed id on user GET -> 400", badGet.status === 400);
  const badStatus = await rq(`/render-jobs/${cid1}/status`, { method: "POST", watcher: WATCHER, body: { status: "queued" } });
  check("watcher cannot set status back to queued -> 400", badStatus.status === 400);
  const ghost = await rq("/render-jobs/0123456789abcdef/status", { method: "POST", watcher: WATCHER, body: { status: "done" } });
  check("status for an unknown job -> 404", ghost.status === 404);
}

// 10. Per-day render cap (dev server runs with RENDER_CAP_PER_DAY=3):
// new jobs count, idempotent re-submits of a live job do not.
{
  const acct = (await register(REG_SECRET)).j;
  const mk = async (n: number) => {
    const pieces = ["cap-top-" + n, "cap-bottom-" + n];
    return { comboId: await comboIdFor(pieces, null), combo: { pieces, watchId: null } };
  };
  const j1 = await mk(1), j2 = await mk(2), j3 = await mk(3), j4 = await mk(4);
  const e1 = await rq("/render-queue", { method: "POST", key: acct.key, body: j1 });
  const e2 = await rq("/render-queue", { method: "POST", key: acct.key, body: j2 });
  const e3 = await rq("/render-queue", { method: "POST", key: acct.key, body: j3 });
  check("three new jobs under the cap accepted", e1.status === 200 && e2.status === 200 && e3.status === 200,
    JSON.stringify([e1.status, e2.status, e3.status]));
  const dup = await rq("/render-queue", { method: "POST", key: acct.key, body: j1 });
  check("re-submit of a live job is not capped", dup.status === 200 && dup.j?.status === "queued");
  const e4 = await rq("/render-queue", { method: "POST", key: acct.key, body: j4 });
  check("fourth new job in a day -> 429 render_cap", e4.status === 429 && e4.j?.error === "render_cap",
    JSON.stringify(e4.j));
}

// 11. Analyze queue (build .40): enqueue -> watcher list (with the
// photo) -> analyzing -> done with validated items; failed revives.
{
  const aid1 = "aaaa0000bbbb1111", aid2 = "aaaa0000bbbb2222";
  const photo = "data:image/jpeg;base64," + "QUJD".repeat(500);
  const aq = async (path: string, opts: { method?: string; key?: string; watcher?: string; body?: unknown }) => {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (opts.key) headers.authorization = "Bearer " + opts.key;
    if (opts.watcher) headers["x-watcher-secret"] = opts.watcher;
    const r = await fetch(BASE + path, {
      method: opts.method || "GET", headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
    return { status: r.status, j: await r.json().catch(() => null) };
  };
  const badId = await aq("/analyze-queue", { method: "POST", key: KEY, body: { analyzeId: "nope", image: photo } });
  check("analyze: bad analyzeId -> 400", badId.status === 400);
  const badImg = await aq("/analyze-queue", { method: "POST", key: KEY, body: { analyzeId: aid1, image: "https://example.com/x.jpg" } });
  check("analyze: non-data-URI image -> 400", badImg.status === 400);
  const noAuth = await aq("/analyze-queue", { method: "POST", body: { analyzeId: aid1, image: photo } });
  check("analyze: enqueue without a key -> 401", noAuth.status === 401);
  const listNoAuth = await aq("/analyze-jobs", {});
  check("analyze: watcher list without the secret -> 401", listNoAuth.status === 401);

  const enq = await aq("/analyze-queue", { method: "POST", key: KEY, body: { analyzeId: aid1, image: photo } });
  check("analyze: enqueue accepted as queued", enq.status === 200 && enq.j?.status === "queued");
  const dup = await aq("/analyze-queue", { method: "POST", key: KEY, body: { analyzeId: aid1, image: photo } });
  check("analyze: re-enqueue of a live job is idempotent", dup.status === 200 && dup.j?.requestedAt === enq.j?.requestedAt);
  const list = await aq("/analyze-jobs", { watcher: WATCHER });
  const listed = (list.j?.jobs || []).find((x: { analyzeId: string }) => x.analyzeId === aid1);
  check("analyze: queued job listed for the watcher WITH its photo", !!listed && listed.image === photo);
  const got = await aq("/analyze-queue/" + aid1, { key: KEY });
  check("analyze: user GET sees queued job (no photo echoed)", got.status === 200 && got.j?.status === "queued" && got.j?.image === undefined);

  const badItems = await aq(`/analyze-jobs/${aid1}/status`, { method: "POST", watcher: WATCHER, body: { status: "done", items: [{ name: "X", category: "NotACategory", colourName: "red", colourHex: "#ff0000", brand: "", img: `assets/analyze/${aid1}-0.jpg` }] } });
  check("analyze: done with an off-list category -> 400", badItems.status === 400);
  const badImgPath = await aq(`/analyze-jobs/${aid1}/status`, { method: "POST", watcher: WATCHER, body: { status: "done", items: [{ name: "X", category: "Tees", colourName: "red", colourHex: "#ff0000", brand: "", img: "assets/analyze/other-0.jpg" }] } });
  check("analyze: done with a mismatched img path -> 400", badImgPath.status === 400);
  const items = [{ name: "Charcoal pocket tee", category: "Tees", colourName: "charcoal grey", colourHex: "#39393e", brand: "", img: `assets/analyze/${aid1}-0.jpg` }];
  const done = await aq(`/analyze-jobs/${aid1}/status`, { method: "POST", watcher: WATCHER, body: { status: "done", items } });
  check("analyze: watcher marks done with items", done.status === 200 && done.j?.status === "done" && eq(done.j?.items, items));
  const after = await aq("/analyze-queue/" + aid1, { key: KEY });
  check("analyze: user GET sees done + items", after.status === 200 && after.j?.status === "done" && eq(after.j?.items, items));
  const list2 = await aq("/analyze-jobs", { watcher: WATCHER });
  check("analyze: done job leaves the watcher list", !(list2.j?.jobs || []).some((x: { analyzeId: string }) => x.analyzeId === aid1));

  await aq("/analyze-queue", { method: "POST", key: KEY, body: { analyzeId: aid2, image: photo } });
  const failed = await aq(`/analyze-jobs/${aid2}/status`, { method: "POST", watcher: WATCHER, body: { status: "failed", note: "vision error" } });
  check("analyze: watcher marks failed with note", failed.status === 200 && failed.j?.status === "failed" && failed.j?.note === "vision error");
  const revived = await aq("/analyze-queue", { method: "POST", key: KEY, body: { analyzeId: aid2, image: photo } });
  check("analyze: re-enqueue of a failed job revives it", revived.status === 200 && revived.j?.status === "queued" && revived.j?.note === undefined);
  const list3 = await aq("/analyze-jobs", { watcher: WATCHER });
  check("analyze: revived job is back in the watcher list", (list3.j?.jobs || []).some((x: { analyzeId: string }) => x.analyzeId === aid2));
}

// 12. Receipt inbox (build .41): watcher push -> records land in the
// account's "receipts" sync collection -> the app pulls them via
// /sync; re-push is skipped in ANY state (append-only); the app owns
// status transitions through /sync; the watcher GET is the dedupe
// read.
{
  const ri = async (path: string, opts: { method?: string; key?: string; watcher?: string; body?: unknown }) => {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (opts.key) headers.authorization = "Bearer " + opts.key;
    if (opts.watcher) headers["x-watcher-secret"] = opts.watcher;
    const r = await fetch(BASE + path, {
      method: opts.method || "GET", headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
    return { status: r.status, j: await r.json().catch(() => null) };
  };
  const acct2 = (await register(REG_SECRET)).j;
  const item1 = {
    id: "rcpt-testorder1-0", name: "Cashmere Crew Neck Sweater", brand: "Sunspel",
    retailer: "Sunspel", price: 425, currency: "USD", orderNo: "TESTORDER1",
    orderDate: "2026-11-02", category: "Sweaters", colourName: "navy",
    colourHex: "#1f2a44", img: "", src: "msg-test-1",
  };
  const item2 = { ...item1, id: "rcpt-testorder1-1", name: "Suede Loafers", category: "Shoes", price: 595 };

  const noAuth = await ri("/receipt-inbox", { method: "POST", body: { acct: acct2.acct, items: [item1] } });
  check("receipts: push without the watcher secret -> 401", noAuth.status === 401);
  const keyAsWatcher = await ri("/receipt-inbox", { method: "POST", watcher: acct2.key, body: { acct: acct2.acct, items: [item1] } });
  check("receipts: sync key as watcher secret -> 401", keyAsWatcher.status === 401);
  const ghost = await ri("/receipt-inbox", { method: "POST", watcher: WATCHER, body: { acct: "0123456789abcdef", items: [item1] } });
  check("receipts: unknown account -> 404", ghost.status === 404);
  const badCat = await ri("/receipt-inbox", { method: "POST", watcher: WATCHER, body: { acct: acct2.acct, items: [{ ...item1, category: "NotACategory" }] } });
  check("receipts: off-list category -> 400", badCat.status === 400);
  const badImg = await ri("/receipt-inbox", { method: "POST", watcher: WATCHER, body: { acct: acct2.acct, items: [{ ...item1, img: "javascript:alert(1)" }] } });
  check("receipts: non-https image -> 400", badImg.status === 400);
  const tooMany = await ri("/receipt-inbox", { method: "POST", watcher: WATCHER, body: { acct: acct2.acct, items: Array(101).fill(item1) } });
  check("receipts: over the per-push item cap -> 400", tooMany.status === 400);

  const push = await ri("/receipt-inbox", { method: "POST", watcher: WATCHER, body: { acct: acct2.acct, items: [item1, item2] } });
  check("receipts: push accepted, 2 written", push.status === 200 && push.j?.written === 2 && (push.j?.skipped || []).length === 0,
    JSON.stringify(push.j));
  const repush = await ri("/receipt-inbox", { method: "POST", watcher: WATCHER, body: { acct: acct2.acct, items: [item1, item2] } });
  check("receipts: re-push is fully skipped (append-only)", repush.status === 200 && repush.j?.written === 0 && (repush.j?.skipped || []).length === 2);

  const list = await ri("/receipt-inbox?acct=" + acct2.acct, { watcher: WATCHER });
  const listed = (list.j?.items || []).find((x: { id: string }) => x.id === item1.id);
  check("receipts: watcher GET lists the pushed record as pending",
    list.status === 200 && !!listed && listed.data?.status === "pending" && listed.data?.orderNo === "TESTORDER1");

  // The app pulls the candidates through the normal /sync path.
  const pull = await sync(acct2.key, { since: 0, changes: [], meta: null });
  const got = (pull.j?.recs || []).filter((x: { coll: string }) => x.coll === "receipts");
  check("receipts: /sync delivers both candidates to the app", got.length === 2,
    "got " + got.length);
  check("receipts: delivered data carries the parsed fields",
    got.some((x: { data?: { name?: string; price?: number } }) => x.data?.name === "Suede Loafers" && x.data?.price === 595));

  // The app confirms one through /sync; a scan re-push must not
  // resurrect or overwrite the confirmed state.
  const confirmed = { ...(got.find((x: { id: string }) => x.id === item1.id)?.data || {}), status: "confirmed", closetItemId: "rcptbuy-x" };
  const up = await sync(acct2.key, { since: 0, changes: [{ coll: "receipts", id: item1.id, updatedAt: Date.now() + 60000, data: confirmed }], meta: null });
  check("receipts: app confirm via /sync accepted", up.status === 200);
  const repush2 = await ri("/receipt-inbox", { method: "POST", watcher: WATCHER, body: { acct: acct2.acct, items: [item1] } });
  check("receipts: re-push after confirm still skipped", repush2.status === 200 && repush2.j?.written === 0);
  const list2 = await ri("/receipt-inbox?acct=" + acct2.acct, { watcher: WATCHER });
  const after = (list2.j?.items || []).find((x: { id: string }) => x.id === item1.id);
  check("receipts: confirmed state survives the re-push", after?.data?.status === "confirmed" && after?.data?.closetItemId === "rcptbuy-x");

  // Isolation: the main test account never sees acct2's receipts.
  const other = await sync(KEY, { since: 0, changes: [], meta: null });
  check("receipts: other accounts see none of them",
    !(other.j?.recs || []).some((x: { coll: string }) => x.coll === "receipts"));
}

// 13. Link extract (build .45): user-surface fetch of a product
// page's meta/JSON-LD facts. Local checks cover auth + the SSRF
// guards (which refuse before any fetch happens) and one live
// fetch of a plain page (title-only extraction).
{
  const lx = async (opts: { key?: string; body?: unknown }) => {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (opts.key) headers.authorization = "Bearer " + opts.key;
    const r = await fetch(BASE + "/link-extract", {
      method: "POST", headers, body: JSON.stringify(opts.body ?? {}),
    });
    return { status: r.status, j: await r.json().catch(() => null) };
  };
  const noKey = await lx({ body: { url: "https://example.com/" } });
  check("link: no sync key -> 401", noKey.status === 401);
  const badKey = await lx({ key: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", body: { url: "https://example.com/" } });
  check("link: wrong key -> 401", badKey.status === 401);
  const notUrl = await lx({ key: KEY, body: { url: "not a url" } });
  check("link: unparseable url -> 400", notUrl.status === 400 && notUrl.j?.error === "bad url");
  const loopback = await lx({ key: KEY, body: { url: "http://127.0.0.1/admin" } });
  check("link: loopback IP literal -> 400 blocked", loopback.status === 400 && loopback.j?.error === "blocked url");
  const priv = await lx({ key: KEY, body: { url: "https://192.168.1.10/product" } });
  check("link: private IP literal -> 400 blocked", priv.status === 400 && priv.j?.error === "blocked url");
  const lh = await lx({ key: KEY, body: { url: "https://localhost:8787/x" } });
  check("link: localhost -> 400 blocked", lh.status === 400 && lh.j?.error === "blocked url");
  const scheme = await lx({ key: KEY, body: { url: "file:///etc/passwd" } });
  check("link: file scheme -> 400 blocked", scheme.status === 400 && scheme.j?.error === "blocked url");
  const creds = await lx({ key: KEY, body: { url: "https://user:pass@example.com/p" } });
  check("link: credentials in url -> 400 blocked", creds.status === 400 && creds.j?.error === "blocked url");
  const live = await lx({ key: KEY, body: { url: "https://example.com/" } });
  check("link: plain page extracts its title, no price",
    live.status === 200 && live.j?.ok === true && /Example Domain/.test(live.j?.title || "") && live.j?.price === null,
    JSON.stringify(live.j).slice(0, 160));
  // The watcher credential opens the same path (the price watch
  // script holds no user keys); a wrong one does not. The blocked
  // URL proves the auth path without any live fetch.
  const wlx = async (watcher: string, url: string) => {
    const r = await fetch(BASE + "/link-extract", {
      method: "POST",
      headers: { "content-type": "application/json", "x-watcher-secret": watcher },
      body: JSON.stringify({ url }),
    });
    return { status: r.status, j: await r.json().catch(() => null) };
  };
  const wOk = await wlx(WATCHER, "http://127.0.0.1/admin");
  check("link: watcher secret reaches the SSRF guard", wOk.status === 400 && wOk.j?.error === "blocked url");
  const wBad = await wlx("not-the-secret", "https://example.com/");
  check("link: wrong watcher secret -> 401", wBad.status === 401);
}

// 14. Price watch (build .45): the app syncs "shopwish" records;
// the watcher lists them via /price-watch and posts current prices
// to /price-drops; records land in the "pricedrops" collection and
// reach the app via /sync; a newer checkedAt replaces, a stale or
// equal one is skipped.
{
  const pw = async (path: string, opts: { method?: string; key?: string; watcher?: string; body?: unknown }) => {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (opts.key) headers.authorization = "Bearer " + opts.key;
    if (opts.watcher) headers["x-watcher-secret"] = opts.watcher;
    const r = await fetch(BASE + path, {
      method: opts.method || "GET", headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
    return { status: r.status, j: await r.json().catch(() => null) };
  };
  const acct3 = (await register(REG_SECRET)).j;
  const wishKey = "Sunspel|Cashmere Crew Neck|https://www.sunspel.com/products/test-crew";
  const wishRec = {
    key: wishKey, brand: "Sunspel", name: "Cashmere Crew Neck", price: 425,
    wasPrice: null, retailer: "Sunspel", url: "https://www.sunspel.com/products/test-crew",
    img: "", cat: "knitwear", category: "Sweaters", addedISO: "2026-11-10",
  };
  const up = await sync(acct3.key, { since: 0, changes: [{ coll: "shopwish", id: wishKey, updatedAt: Date.now(), data: wishRec }], meta: null });
  check("price: app syncs a shopwish record", up.status === 200);

  const noAuth = await pw("/price-watch?acct=" + acct3.acct, {});
  check("price: watch list without the watcher secret -> 401", noAuth.status === 401);
  const list = await pw("/price-watch?acct=" + acct3.acct, { watcher: WATCHER });
  check("price: watcher lists the wishlisted item with its saved price",
    list.status === 200 && (list.j?.items || []).some((x: { data?: { price?: number } }) => x.data?.price === 425));

  const drop1 = { id: wishKey, key: wishKey, url: wishRec.url, priceWas: 425, priceNow: 340, checkedAt: 1763000000000 };
  const noAuthPush = await pw("/price-drops", { method: "POST", body: { acct: acct3.acct, items: [drop1] } });
  check("price: drop push without the watcher secret -> 401", noAuthPush.status === 401);
  const ghost = await pw("/price-drops", { method: "POST", watcher: WATCHER, body: { acct: "0123456789abcdef", items: [drop1] } });
  check("price: unknown account -> 404", ghost.status === 404);
  const badItem = await pw("/price-drops", { method: "POST", watcher: WATCHER, body: { acct: acct3.acct, items: [{ ...drop1, priceNow: -5 }] } });
  check("price: negative price -> 400", badItem.status === 400);
  const push = await pw("/price-drops", { method: "POST", watcher: WATCHER, body: { acct: acct3.acct, items: [drop1] } });
  check("price: drop push accepted, 1 written", push.status === 200 && push.j?.written === 1);

  const pull = await sync(acct3.key, { since: 0, changes: [], meta: null });
  const drops = (pull.j?.recs || []).filter((x: { coll: string }) => x.coll === "pricedrops");
  check("price: /sync delivers the drop to the app",
    drops.length === 1 && drops[0].data?.priceNow === 340 && drops[0].data?.priceWas === 425);

  const sameCheck = await pw("/price-drops", { method: "POST", watcher: WATCHER, body: { acct: acct3.acct, items: [drop1] } });
  check("price: same checkedAt re-push is skipped", sameCheck.status === 200 && sameCheck.j?.written === 0 && (sameCheck.j?.skipped || []).length === 1);
  const cleared = { ...drop1, priceNow: 425, checkedAt: 1763000100000 };
  const push2 = await pw("/price-drops", { method: "POST", watcher: WATCHER, body: { acct: acct3.acct, items: [cleared] } });
  check("price: newer check replaces (drop clears)", push2.status === 200 && push2.j?.written === 1);
  const stale = { ...drop1, priceNow: 300, checkedAt: 1763000050000 };
  const push3 = await pw("/price-drops", { method: "POST", watcher: WATCHER, body: { acct: acct3.acct, items: [stale] } });
  check("price: stale check is skipped", push3.status === 200 && push3.j?.written === 0);
  const pull2 = await sync(acct3.key, { since: 0, changes: [], meta: null });
  const drops2 = (pull2.j?.recs || []).filter((x: { coll: string }) => x.coll === "pricedrops");
  check("price: app sees the cleared price, not the stale one",
    drops2.length === 1 && drops2[0].data?.priceNow === 425);

  const other = await sync(KEY, { since: 0, changes: [], meta: null });
  check("price: other accounts see no pricedrops",
    !(other.j?.recs || []).some((x: { coll: string }) => x.coll === "pricedrops"));
}

// 15. Shop catalogue (build .52): the shop database served by the
// worker. Snapshot push is watcher-gated; search is user-surface
// (Bearer) and mirrors the app's brand/cat/tier/keys semantics.
{
  const ss = async (key: string | null, qs: string) => {
    const headers: Record<string, string> = {};
    if (key) headers.authorization = "Bearer " + key;
    const r = await fetch(BASE + "/shop/search" + qs, { headers });
    return { status: r.status, j: await r.json().catch(() => null) };
  };
  const snap = async (opts: { watcher?: string; body?: unknown }) => {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (opts.watcher) headers["x-watcher-secret"] = opts.watcher;
    const r = await fetch(BASE + "/shop-snapshot", {
      method: "POST", headers, body: JSON.stringify(opts.body ?? []),
    });
    return { status: r.status, j: await r.json().catch(() => null) };
  };
  const rec = (brand: string, name: string, cat: string, tier: string, keys: string[], price: number) => ({
    brand, cat, img: "", keys, name, price, retailer: brand, tier,
    url: "https://example.com/" + name.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
    st: "brand_direct", sq: "elite",
  });
  const fixture = [
    rec("Rubato", "Navy Wool Crew Neck Sweater", "knitwear", "luxury", ["navy", "wool", "crew neck"], 495),
    rec("Rubato", "Charcoal Flannel Trousers", "trousers", "luxury", ["charcoal", "flannel", "wool"], 425),
    rec("Rubato", "Suede Tassel Loafer", "shoes", "insensitive", ["brown", "suede", "tassel loafer"], 890),
    rec("Sunspel", "Navy Cotton Polo Shirt", "knitwear", "accessible", ["navy", "cotton", "polo shirt"], 180),
    rec("Velasca", "Brown Leather Derby", "shoes", "luxury", ["brown", "leather", "derby"], 340),
  ];

  const noKey = await ss(null, "");
  check("shop: search without a key -> 401", noKey.status === 401);
  const badKey = await ss("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "");
  check("shop: search with a wrong key -> 401", badKey.status === 401);
  const empty = await ss(KEY, "");
  check("shop: search before any snapshot -> 404 no_snapshot",
    empty.status === 404 && empty.j?.error === "no_snapshot");
  const noSecret = await snap({ body: fixture });
  check("shop: snapshot push without the watcher secret -> 401", noSecret.status === 401);
  const badRec = await snap({ watcher: WATCHER, body: [{ brand: "X", name: "Y", price: 10 }] });
  check("shop: snapshot record without a url -> 400", badRec.status === 400 && badRec.j?.error === "bad record");
  const push = await snap({ watcher: WATCHER, body: fixture });
  check("shop: snapshot push accepted, count 5", push.status === 200 && push.j?.count === 5);

  const all = await ss(KEY, "");
  check("shop: unfiltered search returns the whole snapshot",
    all.status === 200 && all.j?.total === 5 && all.j?.snapshot?.count === 5);
  const rub = await ss(KEY, "?brand=Rubato");
  check("shop: brand filter", rub.j?.total === 3);
  const rubLc = await ss(KEY, "?brand=rubato");
  check("shop: brand match is case-insensitive", rubLc.j?.total === 3);
  const rubPart = await ss(KEY, "?brand=Rubat");
  check("shop: brand containment (app rule, 5+ chars)", rubPart.j?.total === 3);
  const knit = await ss(KEY, "?cat=knitwear");
  check("shop: category filter", knit.j?.total === 2);
  const knitLux = await ss(KEY, "?cat=knitwear&tier=luxury");
  check("shop: category + tier filter", knitLux.j?.total === 1 && knitLux.j?.records?.[0]?.brand === "Rubato");
  const navy = await ss(KEY, "?cat=knitwear&keys=navy");
  check("shop: keys intersect within category", navy.j?.total === 2);
  const wool = await ss(KEY, "?keys=wool");
  check("shop: keys intersect across categories", wool.j?.total === 2);
  const polo = await ss(KEY, "?keys=polo");
  check("shop: name-word evidence matches (polo vs 'polo shirt' key)",
    polo.j?.total === 1 && polo.j?.records?.[0]?.brand === "Sunspel");
  const q = await ss(KEY, "?q=loafer");
  check("shop: free-text q over name/brand/keys", q.j?.total === 1 && q.j?.records?.[0]?.brand === "Rubato");
  const qNone = await ss(KEY, "?q=cashmere");
  check("shop: q with no hits -> total 0", qNone.j?.total === 0);
  const page1 = await ss(KEY, "?limit=2");
  check("shop: pagination page 1", page1.j?.total === 5 && page1.j?.count === 2);
  const page3 = await ss(KEY, "?limit=2&offset=4");
  check("shop: pagination last page", page3.j?.count === 1);
  const clamp = await ss(KEY, "?limit=5000");
  check("shop: limit clamps to 1000", clamp.j?.limit === 1000 && clamp.j?.count === 5);

  const httpRec = { ...fixture[4], name: "Plain Http Url Derby", url: "http://example.com/plain-http-derby" };
  const httpPush = await snap({ watcher: WATCHER, body: [...fixture, httpRec] });
  check("shop: http:// source urls accepted (side-file parity)",
    httpPush.status === 200 && httpPush.j?.count === 6);
  const replace = await snap({ watcher: WATCHER, body: [fixture[3]] });
  check("shop: replacement push accepted, count 1", replace.status === 200 && replace.j?.count === 1);
  const after = await ss(KEY, "");
  check("shop: search sees the replacement, not the old snapshot", after.j?.total === 1);
  const rubGone = await ss(KEY, "?brand=Rubato");
  check("shop: replaced brand no longer matches", rubGone.j?.total === 0);
}

console.log(`\n${pass} passed, ${fail} failed`);
Deno.exit(fail ? 1 : 0);
