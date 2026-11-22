// wardrobe-sync — cloud sync service for the Wardrobe app.
// Cloudflare Workers port of the Deno Deploy original (main.ts), which
// stays in this folder as the legacy implementation. The HTTP contract
// is identical to Padel Log sync and to the Deno version — same routes,
// same auth model, same merge semantics — so the app client cannot
// tell which host serves it:
//
//   GET  /          -> { ok: true, service: "wardrobe-sync" }
//   POST /register  -> { key, acct }        (key = 48 hex chars)
//                      gated by the REGISTER_SECRET worker secret
//                      (header x-register-secret); 403 without it.
//   POST /sync      -> Bearer <key>; body { since, changes, meta }
//                      returns { recs, meta, now }; 401 on a bad key.
//                      Deletes of live records need server-truth
//                      (baseUpdatedAt or a matching baseline).
//                      A mass-delete is refused 409 unless
//                      confirmMassDelete is set; confirm cannot
//                      bypass server-truth or a baseline mismatch.
//   POST /render-queue            -> Bearer <key>; body { comboId, combo }
//                                    returns the render job; idempotent.
//   GET  /render-queue/<comboId>  -> Bearer <key>; the job, or 404.
//   GET  /render-jobs             -> x-watcher-secret; queued jobs.
//   POST /render-jobs/<comboId>/status -> x-watcher-secret;
//                                    body { status, note? }.
//   POST /link-extract  -> Bearer <key>; body { url }; fetches the
//                      product page server-side and returns its
//                      meta/JSON-LD facts (build .45, see below).
//   GET  /price-watch   -> x-watcher-secret; the account's
//                      "shopwish" records for the price watch.
//   POST /price-drops   -> x-watcher-secret; writes "pricedrops"
//                      records (checkedAt last-writer-wins).
//   GET  /shop/search   -> Bearer <key>; filtered queries over the
//                      shop catalogue snapshot (build .52): brand,
//                      cat, tier, q/keys text, limit/offset. Returns
//                      compact records in the app-export shape.
//   POST /shop-snapshot -> x-watcher-secret; replaces the shop
//                      catalogue snapshot with the app-export JSON
//                      array (the weekly ingest refresh pushes here,
//                      so the catalogue updates with no app build).
//
// Merge rule: last-writer-wins per record by client-supplied
// `updatedAt` (ms); deletes travel as tombstones
// ({ coll, id, updatedAt, deleted: true }). The server assigns every
// accepted write a per-account sequence number; `since`/`now` page
// through that sequence so a client only receives what it has not seen.
//
// Storage: Workers KV (binding SYNC_KV). The key layout mirrors the
// Deno KV key arrays, serialised as "/"-joined, URI-encoded segments:
//
//   key/<sha256(key)>            -> acct            (plain text)
//   acct/<acct>                  -> { createdAt }
//   seq/<acct>                   -> number (text)
//   rec/<acct>/<coll>/<id>       -> record meta JSON (see chunking)
//   meta/<acct>                  -> meta-doc meta JSON
//   snap/<acct>/<ts>             -> snapshot meta JSON
//   <any of the above>/c/<i>     -> payload chunk i
//   renderq:<comboId>            -> render job JSON (see render queue)
//   renderq-index                -> comboIds queued/rendering
//   shopdb                       -> shop catalogue snapshot meta JSON
//                                   (chunked payload, build .52)
//
// Chunking: a stored value is a small meta JSON holding either
// `inline: "<json>"` or `chunks: n`, with the payload split across
// <key>/c/<i> entries. The Deno version chunked because a Deno KV
// value is capped at 64 KiB; Workers KV allows 25 MiB, but records
// and the meta doc keep the chunk layout — it keeps their handling
// uniform with the original and costs nothing. Snapshots are the one
// exception: each is written as a single inline value (one KV write,
// not one per 60,000-char chunk), falling back to the chunked layout
// only if a snapshot ever outgrows the 25 MiB value limit. The
// reader (getChunked) accepts both forms, so chunked snapshots
// written by earlier versions stay readable. One deliberate
// difference from the Deno version: the payload is sliced by
// characters (60,000 per chunk), not by UTF-8 bytes, so a
// multi-byte character can never be split across chunks (the Deno
// version's byte slicing could corrupt non-ASCII text that straddled
// a boundary; base64 photo payloads are ASCII and were unaffected).
//
// Data safety: after any sync that changes something, the server keeps
// a full last-known-good snapshot of the account's live state in a
// ring of the 10 most recent snapshots — throttled to at most one
// snapshot per hour, since an unthrottled snapshot per sync is the
// fastest way to burn the free plan's 1,000 KV writes a day.
// Tombstones are stored, not erased, so history is never deleted
// silently.
//
// Workers KV has no transactions, so multi-key writes are ordered to
// fail safe: on an upsert the chunks land before the meta key that
// references them; on a tombstone the meta lands before the chunk
// deletes. KV is eventually consistent globally — a just-written
// record can take a few seconds to be visible everywhere; the client
// syncs on a retry cadence and treats a stale read as "nothing new",
// never as data loss.

const CHUNK = 60000; // characters of JSON per KV value
const SNAP_KEEP = 10;
const SNAP_MIN_INTERVAL_MS = 60 * 60 * 1000; // at most one snapshot per hour
const KV_VALUE_MAX = 25 * 1024 * 1024; // Workers KV per-value limit, bytes
const MAX_BODY = 64 * 1024 * 1024;

// Minimal structural types so this file needs no @cloudflare/workers-types.
interface KVNamespace {
  get(key: string): Promise<string | null>;
  put(key: string, value: string): Promise<void>;
  delete(key: string): Promise<void>;
  list(options?: {
    prefix?: string;
    cursor?: string;
    limit?: number;
  }): Promise<{
    keys: { name: string }[];
    list_complete: boolean;
    cursor?: string;
  }>;
}
export interface Env {
  SYNC_KV: KVNamespace;
  // Secret for the render-queue watcher surface (see the render queue
  // section). Set with `wrangler secret put RENDER_WATCHER_SECRET` —
  // never a wrangler.toml var, never committed. When unset, the
  // watcher endpoints refuse every request (503).
  RENDER_WATCHER_SECRET?: string;
  // Shared secret required on POST /register (header
  // `x-register-secret`). Registration used to be open to anyone,
  // which let any stranger mint accounts on the owner's KV. When
  // unset, /register refuses every request (503) — fail closed.
  // Existing accounts are unaffected: their keys keep working on
  // every other endpoint.
  REGISTER_SECRET?: string;
  // Per-account, per-day render-job cap (see the render queue
  // section). A plain string var; unset or unparsable means the
  // default of 200. Exists so tests can run with a tiny cap.
  RENDER_CAP_PER_DAY?: string;
}

const enc = new TextEncoder();

function sha256hex(s: string): Promise<string> {
  return crypto.subtle.digest("SHA-256", enc.encode(s)).then((b) =>
    [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("")
  );
}
const randHex = (bytes: number) =>
  [...crypto.getRandomValues(new Uint8Array(bytes))]
    .map((x) => x.toString(16).padStart(2, "0")).join("");

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "authorization, content-type, x-watcher-secret, x-register-secret",
};
const json = (obj: unknown, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json", ...CORS },
  });

// Serialise a key path. Components are URI-encoded so a "/" or other
// separator inside an id can never break the segment-depth checks.
const K = (...parts: (string | number)[]) =>
  parts.map((p) => encodeURIComponent(String(p))).join("/");
// Chunk key for an already-serialised prefix ("c" and digits need no
// encoding, and the prefix must NOT be re-encoded).
const CK = (prefix: string, i: number) => prefix + "/c/" + i;

async function listAll(kv: KVNamespace, prefix: string): Promise<string[]> {
  const names: string[] = [];
  let cursor: string | undefined;
  do {
    const page = await kv.list({ prefix, cursor, limit: 1000 });
    for (const k of page.keys) names.push(k.name);
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return names;
}

// ---------- chunked value helpers ----------
// A stored entry is either { ..., inline: "<json>" } or
// { ..., chunks: n } with payloads at <prefix>/c/<i>.

type StoredMeta = {
  inline?: string;
  chunks?: number;
  [k: string]: unknown;
};

async function getMeta(
  kv: KVNamespace,
  prefix: string,
): Promise<StoredMeta | null> {
  const raw = await kv.get(prefix);
  if (raw == null) return null;
  try {
    return JSON.parse(raw) as StoredMeta;
  } catch {
    return null;
  }
}

async function putChunked(
  kv: KVNamespace,
  prefix: string,
  meta: Record<string, unknown>,
  payload: string,
) {
  const old = await getMeta(kv, prefix);
  const oldChunks = old?.chunks || 0;
  if (payload.length <= CHUNK) {
    await kv.put(prefix, JSON.stringify({ ...meta, inline: payload }));
    for (let i = 0; i < oldChunks; i++) await kv.delete(CK(prefix, i));
    return;
  }
  const n = Math.ceil(payload.length / CHUNK);
  // Chunks first, meta key last: a reader who can see the meta can
  // always resolve the chunks it points at.
  for (let i = 0; i < n; i++) {
    await kv.put(CK(prefix, i), payload.slice(i * CHUNK, (i + 1) * CHUNK));
  }
  await kv.put(prefix, JSON.stringify({ ...meta, chunks: n }));
  for (let i = n; i < oldChunks; i++) await kv.delete(CK(prefix, i));
}

async function getChunked(kv: KVNamespace, prefix: string) {
  const e = await getMeta(kv, prefix);
  if (!e) return null;
  if (e.inline !== undefined) return { meta: e, payload: e.inline };
  if (e.chunks) {
    const parts = await Promise.all(
      Array.from({ length: e.chunks }, (_, i) => kv.get(CK(prefix, i))),
    );
    return { meta: e, payload: parts.map((p) => p ?? "").join("") };
  }
  return { meta: e, payload: null as string | null };
}

async function deleteChunked(kv: KVNamespace, prefix: string) {
  const e = await getMeta(kv, prefix);
  await kv.delete(prefix);
  for (let i = 0; i < (e?.chunks || 0); i++) await kv.delete(CK(prefix, i));
}

// ---------- accounts ----------

async function acctForKey(
  kv: KVNamespace,
  key: string | null,
): Promise<string | null> {
  if (!key || !/^[0-9a-f]{48}$/.test(key)) return null;
  const h = await sha256hex(key);
  return await kv.get(K("key", h));
}

// ---------- snapshots (last-known-good ring) ----------

// Snapshot parts: characters of JSON per KV value. Well under the 25 MiB
// value limit even if every character were three bytes.
const SNAP_PART = 6 * 1024 * 1024;
// At most this many deletes (ring trim + orphan sweep) per snapshot run.
const SNAP_SWEEP_MAX = 120;
// Parts with no meta key are swept only once they are this old, so a
// write that is still in flight is never touched.
const SNAP_ORPHAN_AGE_MS = 2 * 60 * 60 * 1000;

async function writeSnapshot(kv: KVNamespace, acct: string, flagKey?: string) {
  const snapPrefix = K("snap", acct) + "/";
  // Index the ring first; the trim and the sweep reuse this listing.
  const idx: string[] = []; // complete snapshots: their meta key exists
  const partsOf = new Map<string, string[]>(); // ts -> part key names
  for (const name of await listAll(kv, snapPrefix)) {
    const segs = name.split("/");
    if (segs.length === 3) idx.push(segs[2]);
    else if (segs.length === 5 && segs[3] === "c") {
      const a = partsOf.get(segs[2]);
      if (a) a.push(name);
      else partsOf.set(segs[2], [name]);
    }
  }
  idx.sort();
  // Throttle: a snapshot is insurance, not a journal — at most one an
  // hour. A state-changing sync whose newest snapshot is fresher than
  // that writes nothing at all.
  const newest = idx.length
    ? Number(decodeURIComponent(idx[idx.length - 1]))
    : NaN;
  if (Number.isFinite(newest) && Date.now() - newest < SNAP_MIN_INTERVAL_MS) {
    return;
  }
  // The snapshot is one JSON document with the same shape as before,
  //   {"at":..,"recs":{"<coll>":{"<id>":<data>,..},..},"meta":<meta|null>}
  // but it is never held in memory whole. Each live record's stored JSON
  // text is appended as it is (no parse, no re-stringify) and the text is
  // flushed to KV in a few large parts.
  //
  // Why (Nov 21 2026): once the closet passed the 25 MiB value limit the
  // old code fell back to putChunked on the fully assembled text: about
  // 500 puts of 60,000 characters, on top of three in-memory copies of
  // the closet. The worker was killed part-way through every time (error
  // 1102: about 170 parts written, never the meta key), so every
  // state-changing sync returned 503 after the records were stored, no
  // snapshot was kept, and each attempt left its parts behind.
  //
  // Layout is the chunked layout getChunked / deleteChunked already read:
  // parts at <prefix>/c/<i>, then the meta key { at, chunks, v: 2 } last,
  // so a snapshot whose meta key exists is always complete.
  const ts = Date.now();
  const prefix = K("snap", acct, ts);
  if (flagKey) await kv.put(flagKey, String(ts));
  const recPrefix = K("rec", acct) + "/";
  const heads: { name: string; coll: string; id: string }[] = [];
  for (const name of await listAll(kv, recPrefix)) {
    const segs = name.split("/");
    if (segs.length !== 4) continue; // skip chunk keys (6 segments)
    heads.push({
      name,
      coll: decodeURIComponent(segs[2]),
      id: decodeURIComponent(segs[3]),
    });
  }
  heads.sort((a, b) =>
    a.coll < b.coll ? -1 : a.coll > b.coll ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0
  );
  let buf = '{"at":' + ts + ',"recs":{';
  let nParts = 0;
  let curColl: string | null = null;
  let firstInColl = true;
  const flush = async () => {
    await kv.put(CK(prefix, nParts), buf);
    nParts++;
    buf = "";
  };
  const BATCH = 8;
  for (let i = 0; i < heads.length; i += BATCH) {
    const group = heads.slice(i, i + BATCH);
    const fulls = await Promise.all(group.map((h) => getChunked(kv, h.name)));
    for (let j = 0; j < group.length; j++) {
      const h = group[j], full = fulls[j];
      if (!full || full.meta.deleted || full.payload == null) continue;
      if (h.coll !== curColl) {
        buf += (curColl === null ? "" : "},") + JSON.stringify(h.coll) + ":{";
        curColl = h.coll;
        firstInColl = true;
      }
      buf += (firstInColl ? "" : ",") + JSON.stringify(h.id) + ":" + full.payload;
      firstInColl = false;
      if (buf.length >= SNAP_PART) await flush();
    }
  }
  const m = await getChunked(kv, K("meta", acct));
  buf += (curColl === null ? "" : "}") + '},"meta":' +
    (m && m.payload != null ? m.payload : "null") + "}";
  await flush();
  await kv.put(prefix, JSON.stringify({ at: ts, chunks: nParts, v: 2 }));
  if (flagKey) await kv.delete(flagKey);
  // Trim the ring to the newest SNAP_KEEP snapshots. The parts of an old
  // snapshot are known from the listing above, so nothing is read back
  // (reading a 25 MiB inline snapshot only to delete it is wasteful).
  // Meta key first: a reader never sees a meta that points at missing parts.
  let deletes = 0;
  idx.push(String(ts));
  idx.sort();
  for (const old of idx.slice(0, Math.max(0, idx.length - SNAP_KEEP))) {
    await kv.delete(K("snap", acct) + "/" + old);
    deletes++;
    for (const part of partsOf.get(old) || []) {
      await kv.delete(part);
      deletes++;
    }
    partsOf.delete(old);
  }
  // Sweep parts left behind by snapshot writes that died before their
  // meta key was written. Only parts with no meta key, and only once they
  // are well past any write that could still be in flight. Bounded per run.
  const complete = new Set(idx);
  for (const [tsEnc, parts] of partsOf) {
    if (deletes >= SNAP_SWEEP_MAX) break;
    if (complete.has(tsEnc)) continue;
    const t = Number(decodeURIComponent(tsEnc));
    if (!Number.isFinite(t) || ts - t < SNAP_ORPHAN_AGE_MS) continue;
    for (const part of parts) {
      if (deletes >= SNAP_SWEEP_MAX) break;
      await kv.delete(part);
      deletes++;
    }
  }
}

// ---------- handlers ----------

async function handleRegister(
  kv: KVNamespace,
  req: Request,
  env: Env,
): Promise<Response> {
  // Registration is gated by a shared secret the app supplies from
  // the user's own entry (Profile → Cloud sync), never from a value
  // embedded in the shipped page. No secret configured → closed;
  // wrong or missing header → 403. Already-registered devices never
  // call this endpoint, so their sync is untouched.
  const secret = env.REGISTER_SECRET;
  if (!secret) return json({ error: "register_closed" }, 503);
  if (req.headers.get("x-register-secret") !== secret) {
    return json({ error: "register_code_required" }, 403);
  }
  const key = randHex(24); // 48 hex chars, same shape as Padel Log keys
  const acct = randHex(8);
  const h = await sha256hex(key);
  await kv.put(K("key", h), acct);
  await kv.put(K("acct", acct), JSON.stringify({ createdAt: Date.now() }));
  await kv.put(K("seq", acct), "0");
  return json({ key, acct });
}

interface Change {
  coll: string;
  id: string;
  updatedAt: number;
  data?: unknown;
  deleted?: boolean;
  // The live `updatedAt` the client last saw for this record.
  // Required (or a matching collection baseline) to tombstone a
  // currently-live server record.
  baseUpdatedAt?: number;
}

interface BaselineEntry {
  n: number;
  h: string;
}

/** sha256 of the sorted live ids, joined by newline. Exported for tests. */
export async function liveIdManifest(ids: string[]): Promise<BaselineEntry> {
  const sorted = ids.slice().sort();
  return { n: sorted.length, h: await sha256hex(sorted.join("\n")) };
}

async function liveIdsForColl(
  kv: KVNamespace,
  acct: string,
  coll: string,
): Promise<string[]> {
  const ids: string[] = [];
  const pfx = K("rec", acct, coll) + "/";
  for (const name of await listAll(kv, pfx)) {
    if (name.split("/").length !== 4) continue;
    const head = await getMeta(kv, name);
    if (head && !head.deleted) ids.push(decodeURIComponent(name.split("/")[3]));
  }
  return ids;
}

const SCAN_BATCH = 16;
const SNAP_DEFER_MAX_CHARS = 16e6;
const SNAP_FLAG_FRESH_MS = 90 * 1e3;

// The hourly safety snapshot, started at the end of a sync that changed
// something. It is handed to ctx.waitUntil, so the answer is not held back
// for it and a phone that drops the connection cannot cut it off; waitUntil
// allows 30 seconds after the answer. writeSnapshot keeps a flag key while
// it is writing and removes it once the snapshot is complete, so:
// - no flag: start the snapshot and answer at once;
// - a flag younger than 90 seconds: one is being written right now, do nothing;
// - an older flag: the last attempt did not finish, so this time the answer
//   waits for the snapshot, as every sync did before this change.
// The answer also waits when there is no ctx, or when the answer itself is
// very large (mustWait), so the two are not in memory together.
async function snapshotAfterSync(
  kv: KVNamespace,
  acct: string,
  ctx: { waitUntil?: (p: Promise<unknown>) => void } | undefined,
  mustWait: boolean,
) {
  const canDefer = !!(ctx && typeof ctx.waitUntil === "function");
  const flagKey = K("snapflag", acct);
  const flagRaw = await kv.get(flagKey);
  const flagAt = flagRaw ? Number(flagRaw) || 0 : 0;
  const age = Date.now() - flagAt;
  if (flagAt && age >= 0 && age < SNAP_FLAG_FRESH_MS) return;
  const snap = writeSnapshot(kv, acct, flagKey).catch(() => {});
  if (canDefer) ctx!.waitUntil!(snap);
  if (!canDefer || mustWait || flagAt) await snap;
}

async function handleSync(
  kv: KVNamespace,
  req: Request,
  ctx?: { waitUntil?: (p: Promise<unknown>) => void },
): Promise<Response> {
  const auth = req.headers.get("authorization") || "";
  const key = auth.startsWith("Bearer ") ? auth.slice(7) : null;
  const acct = await acctForKey(kv, key);
  if (!acct) return json({ error: "unauthorized" }, 401);

  const raw = await req.text();
  if (raw.length > MAX_BODY) return json({ error: "too large" }, 413);
  let body: {
    since?: number;
    changes?: Change[];
    meta?: unknown;
    confirmMassDelete?: boolean;
    // Optional per-collection live-id manifest the client believes
    // is current: { n, h } where h is sha256(sorted ids joined by \n).
    baseline?: Record<string, BaselineEntry>;
  };
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  const since = typeof body.since === "number" ? body.since : 0;
  const changes = Array.isArray(body.changes) ? body.changes : [];

  // Delete hardening (Nov 18, 2026). Three layers, in order:
  //
  // 1. Baseline-manifest gate. If the client sends baseline[coll] =
  //    { n, h } and it does not match the server's live id-set, every
  //    delete for that collection is cancelled (not 409). The live
  //    records are returned so the client can heal. confirmMassDelete
  //    cannot override a mismatch. Old clients that omit baseline
  //    skip this gate.
  // 2. Circuit breaker. A verified (or no-baseline) pass that would
  //    tombstone too much of a collection is refused 409 unless the
  //    user confirmed. Old clients: the original floor-6 / 20% rule.
  //    Clients that sent a matching baseline: tighter (>3 records or
  //    >10% of live). confirmMassDelete loosens the breaker only.
  // 3. Server-truth. A delete of a currently-live record is applied
  //    only if the client proves it saw that version (baseUpdatedAt
  //    equals the live updatedAt) or sent a matching baseline for
  //    the collection. confirmMassDelete alone is not proof — that
  //    was the hole that would have let 54 "now"-stamped tombs wipe
  //    a still-intact server snapshot.
  const delByColl = new Map<string, Change[]>();
  for (const ch of changes) {
    if (ch && ch.deleted && typeof ch.coll === "string" && typeof ch.id === "string") {
      const arr = delByColl.get(ch.coll) || [];
      arr.push(ch);
      delByColl.set(ch.coll, arr);
    }
  }
  const unverified = new Set<string>();
  const neededConfirm = new Set<string>();
  for (const [coll, dels] of delByColl) {
    const liveIds = await liveIdsForColl(kv, acct, coll);
    const man = await liveIdManifest(liveIds);
    const liveN = liveIds.length;
    const delN = new Set(dels.map((d) => d.id)).size;
    const provided = body.baseline &&
        Object.prototype.hasOwnProperty.call(body.baseline, coll)
      ? body.baseline[coll]
      : undefined;
    if (provided) {
      const nOk = typeof provided.n === "number" && provided.n === man.n;
      const hOk = typeof provided.h === "string" && provided.h === man.h;
      if (!nOk || !hOk) {
        unverified.add(coll);
        continue; // cancel those deletes later; do not 409
      }
    }
    const tripsTight = provided !== undefined &&
      (delN > 3 || (liveN > 0 && delN > liveN * 0.1));
    const tripsLegacy = delN >= 6 && liveN > 0 && delN > liveN * 0.2;
    if (tripsTight || tripsLegacy) {
      if (body.confirmMassDelete !== true) {
        return json({ error: "mass_delete", coll, deletions: delN, live: liveN }, 409);
      }
      neededConfirm.add(coll);
    }
  }

  // Sequence numbers: read the per-account counter once, allocate in
  // memory, and persist it once at the end if anything was allocated
  // (the old code did a KV get+put per accepted change). This is safe
  // because the numbers themselves live on the record metas and the
  // delivery scan below reads those, not the counter: a counter that
  // briefly lags the stored records can only make a client receive a
  // record twice, never lose one, and last-writer-wins absorbs
  // duplicates. The counter was never atomic (KV has no
  // compare-and-swap), so concurrent requests could already
  // interleave allocations; batching per request widens that window
  // without changing the failure class. See README, "Eventual
  // consistency".
  const seqKey = K("seq", acct);
  const seqRaw = await kv.get(seqKey);
  let seqCounter = seqRaw ? Number(seqRaw) || 0 : 0;
  let seqAllocated = false;
  const allocSeq = () => {
    seqAllocated = true;
    return ++seqCounter;
  };

  const written = new Set<string>(); // "coll\0id\0updatedAt" written this request
  let dirty = false;
  const cancelled: { coll: string; id: string; reason: string }[] = [];
  const healPrefixes = new Set<string>();

  for (const ch of changes) {
    if (
      !ch || typeof ch.coll !== "string" || typeof ch.id !== "string" ||
      typeof ch.updatedAt !== "number"
    ) continue;
    const prefix = K("rec", acct, ch.coll, ch.id);
    const cur = await getMeta(kv, prefix);
    if (cur && typeof cur.updatedAt === "number" && ch.updatedAt <= cur.updatedAt) {
      continue; // stale or duplicate write: last-writer-wins says no
    }
    // Server-truth / baseline cancellation for deletes of live records.
    if (ch.deleted && cur && !cur.deleted) {
      let reason: string | null = null;
      if (unverified.has(ch.coll)) reason = "baseline_mismatch";
      else if (typeof ch.baseUpdatedAt === "number" && ch.baseUpdatedAt !== cur.updatedAt) {
        reason = "server_truth";
      } else if (typeof ch.baseUpdatedAt !== "number") {
        const sentBaseline = !!(body.baseline &&
          Object.prototype.hasOwnProperty.call(body.baseline, ch.coll));
        // A matching baseline is proof of the live id-set. Without
        // that proof, confirmMassDelete alone cannot tombstone a
        // live record (Nov 18 hole). Ordinary old-client deletes
        // that never tripped the breaker still follow LWW.
        if (!sentBaseline && neededConfirm.has(ch.coll)) reason = "server_truth";
      }
      if (reason) {
        cancelled.push({ coll: ch.coll, id: ch.id, reason });
        healPrefixes.add(prefix);
        continue;
      }
    }
    const seq = allocSeq();
    if (ch.deleted) {
      const oldChunks = (cur as StoredMeta | null)?.chunks || 0;
      // Tombstone meta first, chunk deletes after: a reader never sees
      // a live record pointing at half-deleted chunks.
      await kv.put(
        prefix,
        JSON.stringify({ updatedAt: ch.updatedAt, deleted: true, seq }),
      );
      for (let i = 0; i < oldChunks; i++) await kv.delete(CK(prefix, i));
    } else {
      await putChunked(
        kv,
        prefix,
        { updatedAt: ch.updatedAt, seq },
        JSON.stringify(ch.data ?? null),
      );
    }
    written.add(ch.coll + "\0" + ch.id + "\0" + ch.updatedAt);
    dirty = true;
  }

  // Meta: a single last-writer-wins document per account.
  const inMeta = body.meta as { updatedAt?: number; data?: unknown } | null;
  const inMetaAt = inMeta && typeof inMeta.updatedAt === "number"
    ? inMeta.updatedAt
    : null;
  if (inMeta && inMetaAt !== null) {
    const cur = await getMeta(kv, K("meta", acct));
    if (!cur || inMetaAt > ((cur.updatedAt as number) || 0)) {
      const seq = allocSeq();
      await putChunked(
        kv,
        K("meta", acct),
        { updatedAt: inMetaAt, seq },
        JSON.stringify(inMeta.data ?? null),
      );
      dirty = true;
    }
  }

  // Collect everything this client has not seen (seq > since), minus the
  // records it just wrote itself in this request.
  // The counter is stored as soon as the writes are done (it used to be
  // stored after the scan below), so a request that is cut off while
  // scanning never leaves records numbered above the stored counter.
  if (seqAllocated) await kv.put(seqKey, String(seqCounter));

  // Record heads are read SCAN_BATCH at a time. They used to be read one
  // by one, which made every sync of a 300-record closet wait for 300
  // round trips to KV (about 25 s). What is returned, and in what order,
  // is the same.
  const recs: Record<string, unknown>[] = [];
  let outChars = 0;
  const recPrefix = K("rec", acct) + "/";
  const recNames: string[] = [];
  for (const name of await listAll(kv, recPrefix)) {
    if (name.split("/").length === 4) recNames.push(name);
  }
  for (let i = 0; i < recNames.length; i += SCAN_BATCH) {
    const group = recNames.slice(i, i + SCAN_BATCH);
    const heads = await Promise.all(group.map((name) => getMeta(kv, name)));
    const picked: { name: string; coll: string; id: string; v: any }[] = [];
    for (let j = 0; j < group.length; j++) {
      const segs = group[j].split("/");
      const coll = decodeURIComponent(segs[2]);
      const id = decodeURIComponent(segs[3]);
      const v = heads[j];
      if (!v || typeof v.seq !== "number" || !(v.seq > since)) continue;
      if (written.has(coll + "\0" + id + "\0" + v.updatedAt)) continue;
      picked.push({ name: group[j], coll, id, v });
    }
    const fulls = await Promise.all(
      picked.map((p) => (p.v.deleted ? null : getChunked(kv, p.name))),
    );
    for (let j = 0; j < picked.length; j++) {
      const p = picked[j];
      if (p.v.deleted) {
        recs.push({ coll: p.coll, id: p.id, updatedAt: p.v.updatedAt, deleted: true });
      } else {
        const full = fulls[j];
        if (full && full.payload != null) outChars += full.payload.length;
        recs.push({
          coll: p.coll,
          id: p.id,
          updatedAt: p.v.updatedAt,
          data: full && full.payload != null ? JSON.parse(full.payload) : null,
        });
      }
    }
  }
  recs.sort((a, b) => (a.updatedAt as number) - (b.updatedAt as number));

  // Force-include live records whose deletes were cancelled, even if
  // the client already has a current `since` (it needs to overwrite
  // a local tomb). Old clients ignore unknown response fields.
  const seen = new Set(recs.map((r) => String(r.coll) + "\0" + String(r.id)));
  for (const prefix of healPrefixes) {
    const segs = prefix.split("/");
    if (segs.length !== 4) continue;
    const coll = decodeURIComponent(segs[2]);
    const id = decodeURIComponent(segs[3]);
    if (seen.has(coll + "\0" + id)) continue;
    const v = await getMeta(kv, prefix);
    if (!v) continue;
    if (v.deleted) {
      recs.push({ coll, id, updatedAt: v.updatedAt, deleted: true });
    } else {
      const full = await getChunked(kv, prefix);
      recs.push({
        coll,
        id,
        updatedAt: v.updatedAt,
        data: full && full.payload != null ? JSON.parse(full.payload) : null,
      });
    }
  }

  let meta: unknown = null;
  const m = await getChunked(kv, K("meta", acct));
  if (m && m.payload != null) {
    const mv = m.meta as { updatedAt: number; seq: number };
    // Skip the echo when the stored meta is exactly the version this
    // request just carried; the client already has it.
    if (mv.seq > since && mv.updatedAt !== inMetaAt) {
      meta = { updatedAt: mv.updatedAt, data: JSON.parse(m.payload) };
    }
  }

  const now = seqCounter;

  // Last-known-good snapshot of the post-sync live state. A snapshot
  // failure never fails the sync itself; see snapshotAfterSync.
  if (dirty) await snapshotAfterSync(kv, acct, ctx, outChars >= SNAP_DEFER_MAX_CHARS);

  return json({ recs, meta, now, cancelled });
}

// ---------- render queue (swap-rendering) ----------
//
// The app assembles outfit combinations client-side from the piece
// library; a combination the user wants to SEE rendered is queued
// here, and an off-platform watcher fulfils it through the render
// pipeline and reports status back. The rendered image never travels
// through this worker — the app polls a deterministic URL for it;
// this queue is only the work order.
//
// comboId — the content address of a combination, computed
// identically by the app and here (computeComboId):
//
//   canonical = pieces.slice().sort().join("+") + "|" + (watchId ?? "")
//   comboId   = first 16 hex chars of SHA-256(canonical)
//
// `pieces` are the combination's piece ids; the sort is JavaScript's
// default lexicographic (UTF-16 code unit) ordering, applied to a
// copy — the stored combo keeps the caller's piece order. watchId is
// the selected watch's id, or "" when no watch is chosen (null and
// absent both canonicalise to ""). Because the id is a hash of the
// contents, anyone presenting a comboId already knows the
// combination it names, so job reads are not scoped per account.
//
// Storage is plain KV values (no chunking — a job is capped at
// ~4 KB of combo JSON):
//
//   renderq:<comboId>   -> job JSON { comboId, status, combo,
//                          requestedAt, updatedAt, note?, acct }
//   renderq-index       -> JSON array of the comboIds whose status
//                          is "queued" or "rendering"
//
// The index is a single read-modify-write key, like the seq counter:
// KV has no transactions, and the traffic is one user plus one
// watcher, so the worst case of a race is a stale index entry — the
// watcher list tolerates those (it skips ids whose job is gone or no
// longer queued) and the next enqueue/status write repairs it.
//
// Auth is two disjoint surfaces, on purpose: user endpoints take the
// same Bearer sync key as /sync; watcher endpoints take the
// RENDER_WATCHER_SECRET worker secret as the `x-watcher-secret`
// header. Neither credential works on the other surface.

const COMBO_ID_RE = /^[a-f0-9]{16}$/;
const MAX_COMBO_JSON = 4096; // ~4 KB cap on the stored combo JSON
const MAX_RENDER_BODY = 16384;
const RENDERQ_INDEX_KEY = "renderq-index";
const renderqKey = (comboId: string) => "renderq:" + comboId;

export async function computeComboId(
  pieces: string[],
  watchId: string | null | undefined,
): Promise<string> {
  const canonical = [...pieces].sort().join("+") + "|" + (watchId ?? "");
  return (await sha256hex(canonical)).slice(0, 16);
}

interface RenderCombo {
  pieces: string[];
  watchId: string | null;
  formality?: string;
}

interface RenderJob {
  comboId: string;
  status: "queued" | "rendering" | "done" | "failed";
  combo: RenderCombo;
  requestedAt: number;
  updatedAt: number;
  note?: string;
  acct: string;
}

async function getRenderJob(
  kv: KVNamespace,
  comboId: string,
): Promise<RenderJob | null> {
  const raw = await kv.get(renderqKey(comboId));
  if (raw == null) return null;
  try {
    return JSON.parse(raw) as RenderJob;
  } catch {
    return null;
  }
}

async function getRenderIndex(kv: KVNamespace): Promise<string[]> {
  const raw = await kv.get(RENDERQ_INDEX_KEY);
  if (raw == null) return [];
  try {
    const v: unknown = JSON.parse(raw);
    return Array.isArray(v)
      ? v.filter((x): x is string => typeof x === "string")
      : [];
  } catch {
    return [];
  }
}

async function indexAddRender(kv: KVNamespace, comboId: string) {
  const idx = await getRenderIndex(kv);
  if (!idx.includes(comboId)) {
    idx.push(comboId);
    await kv.put(RENDERQ_INDEX_KEY, JSON.stringify(idx));
  }
}

async function indexRemoveRender(kv: KVNamespace, comboId: string) {
  const idx = await getRenderIndex(kv);
  if (idx.includes(comboId)) {
    await kv.put(
      RENDERQ_INDEX_KEY,
      JSON.stringify(idx.filter((x) => x !== comboId)),
    );
  }
}

// The user-surface auth, identical to /sync: Bearer <48-hex key>.
async function userAcct(kv: KVNamespace, req: Request): Promise<string | null> {
  const auth = req.headers.get("authorization") || "";
  const key = auth.startsWith("Bearer ") ? auth.slice(7) : null;
  return acctForKey(kv, key);
}

// The watcher-surface gate: null when the request may proceed, else
// the refusal response. An unset worker secret closes the surface.
function watcherGate(req: Request, env: Env): Response | null {
  const secret = env.RENDER_WATCHER_SECRET;
  if (!secret) return json({ error: "watcher not configured" }, 503);
  if (req.headers.get("x-watcher-secret") !== secret) {
    return json({ error: "unauthorized" }, 401);
  }
  return null;
}

// Per-day render cap: new jobs and revivals of failed jobs count
// against the submitting account's daily allowance; idempotent
// re-submits of a live job do not (they create no work). The cap
// exists because a client bug once dealt — and submitted — renders
// nobody had asked for; 200/day sits far above the watcher's real
// fulfilment rate (≤3 jobs per 10 minutes) and any legitimate use.
const RENDER_CAP_DEFAULT = 200;
function renderCapFor(env: Env): number {
  const n = Number(env.RENDER_CAP_PER_DAY);
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : RENDER_CAP_DEFAULT;
}

async function handleRenderEnqueue(
  kv: KVNamespace,
  req: Request,
  env: Env,
): Promise<Response> {
  const acct = await userAcct(kv, req);
  if (!acct) return json({ error: "unauthorized" }, 401);

  const raw = await req.text();
  if (raw.length > MAX_RENDER_BODY) return json({ error: "too large" }, 413);
  let body: { comboId?: unknown; combo?: unknown };
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  if (typeof body.comboId !== "string" || !COMBO_ID_RE.test(body.comboId)) {
    return json({ error: "bad comboId" }, 400);
  }
  const comboId = body.comboId;

  const c = body.combo as Record<string, unknown> | null;
  if (!c || typeof c !== "object" || Array.isArray(c)) {
    return json({ error: "bad combo" }, 400);
  }
  if (
    !Array.isArray(c.pieces) || c.pieces.length === 0 || c.pieces.length > 8 ||
    !c.pieces.every((p) => typeof p === "string" && p.length > 0)
  ) {
    return json({ error: "bad combo" }, 400);
  }
  if (
    c.watchId !== undefined && c.watchId !== null &&
    typeof c.watchId !== "string"
  ) {
    return json({ error: "bad combo" }, 400);
  }
  if (c.formality !== undefined && typeof c.formality !== "string") {
    return json({ error: "bad combo" }, 400);
  }
  const combo: RenderCombo = {
    pieces: c.pieces as string[],
    watchId: (c.watchId as string | null | undefined) ?? null,
  };
  if (typeof c.formality === "string") combo.formality = c.formality;
  if (JSON.stringify(combo).length > MAX_COMBO_JSON) {
    return json({ error: "bad combo" }, 400);
  }

  // Idempotent for live jobs: a job with this comboId in status
  // queued / rendering / done is returned unchanged — a re-tap
  // never resets a render already in flight or already done.
  const existing = await getRenderJob(kv, comboId);
  if (existing && existing.status !== "failed") return json(existing);
  // Everything past this point creates work (a new job, or the
  // revival of a failed one), so it counts against the daily cap.
  const cap = renderCapFor(env);
  if (cap > 0) {
    const capKey = K("rendercap", acct, new Date().toISOString().slice(0, 10));
    const used = Number(await kv.get(capKey)) || 0;
    if (used >= cap) return json({ error: "render_cap", cap }, 429);
    await kv.put(capKey, String(used + 1));
  }
  if (existing) {
    // A FAILED job is revived by an explicit re-submit. "Failed"
    // used to be absorbing, which permanently poisoned a
    // combination after any transient watcher failure (Nov 16:
    // two jobs died on a dropped connection and the app could only
    // ever revert those swaps to the original photo). Reset to
    // queued with fresh timestamps, the failure note cleared, and
    // the combo re-added to the render index for the watcher.
    const now = Date.now();
    const revived: RenderJob = {
      ...existing,
      status: "queued",
      requestedAt: now,
      updatedAt: now,
    };
    delete revived.note;
    await kv.put(renderqKey(comboId), JSON.stringify(revived));
    await indexAddRender(kv, comboId);
    return json(revived);
  }

  const now = Date.now();
  const job: RenderJob = {
    comboId,
    status: "queued",
    combo,
    requestedAt: now,
    updatedAt: now,
    acct,
  };
  await kv.put(renderqKey(comboId), JSON.stringify(job));
  await indexAddRender(kv, comboId);
  return json(job);
}

async function handleRenderGet(
  kv: KVNamespace,
  req: Request,
  comboId: string,
): Promise<Response> {
  const acct = await userAcct(kv, req);
  if (!acct) return json({ error: "unauthorized" }, 401);
  if (!COMBO_ID_RE.test(comboId)) return json({ error: "bad comboId" }, 400);
  const job = await getRenderJob(kv, comboId);
  if (!job) return json({ error: "not found" }, 404);
  return json(job);
}

async function handleRenderJobs(kv: KVNamespace): Promise<Response> {
  const jobs: RenderJob[] = [];
  for (const comboId of await getRenderIndex(kv)) {
    const job = await getRenderJob(kv, comboId);
    if (job && job.status === "queued") jobs.push(job);
  }
  return json({ jobs });
}

async function handleRenderStatus(
  kv: KVNamespace,
  req: Request,
  comboId: string,
): Promise<Response> {
  if (!COMBO_ID_RE.test(comboId)) return json({ error: "bad comboId" }, 400);
  let body: { status?: unknown; note?: unknown };
  try {
    body = JSON.parse(await req.text());
  } catch {
    return json({ error: "bad json" }, 400);
  }
  if (
    body.status !== "rendering" && body.status !== "done" &&
    body.status !== "failed"
  ) {
    return json({ error: "bad status" }, 400);
  }
  if (body.note !== undefined && typeof body.note !== "string") {
    return json({ error: "bad note" }, 400);
  }
  const job = await getRenderJob(kv, comboId);
  if (!job) return json({ error: "not found" }, 404);
  job.status = body.status;
  job.updatedAt = Date.now();
  if (typeof body.note === "string") job.note = body.note;
  await kv.put(renderqKey(comboId), JSON.stringify(job));
  if (job.status === "rendering") await indexAddRender(kv, comboId);
  else await indexRemoveRender(kv, comboId);
  return json(job);
}

// ---------------------------------------------------------------------
// ANALYZE QUEUE (build .40) — auto-categorize closet uploads.
// Mirrors the render queue's two-surface auth and lifecycle: the app
// enqueues ONE photo (data URI, downscaled client-side) under a
// client-chosen 16-hex analyzeId; the watcher claims it, runs vision
// detection off-platform, publishes each detected item's cleaned
// photo into the wardrobe repo at assets/analyze/<analyzeId>-<n>.jpg
// and posts the item metadata back with the done status. The app
// polls the job and shows a confirm sheet — nothing files into the
// Closet without the user's per-item tap in the app.
// The photo rides its own KV key so job records stay small; it is
// deleted when the job settles (done/failed).

const ANALYZE_ID_RE = /^[a-f0-9]{16}$/;
const MAX_ANALYZE_BODY = 1800000; // ~1.3 MB binary photo as base64
const ANALYZEQ_INDEX_KEY = "analyzeq-index";
const analyzeqKey = (id: string) => "analyzeq:" + id;
const analyzeqImgKey = (id: string) => "analyzeqimg:" + id;
const ANALYZE_CATEGORIES = [
  "Shoes", "Shirts", "Tees", "Polos", "Jeans", "Shorts",
  "Bathing suits", "Trousers", "Button downs", "Suits", "Blazers",
  "Scarves", "Jackets", "Coats", "Leather jackets", "Hats",
  "Sunglasses", "Sweaters", "Socks", "Belts", "Gloves", "Vests",
  "Ties",
];

interface AnalyzeItem {
  name: string;
  category: string;
  colourName: string;
  colourHex: string;
  brand: string;
  img: string;
}

interface AnalyzeJob {
  analyzeId: string;
  status: "queued" | "analyzing" | "done" | "failed";
  requestedAt: number;
  updatedAt: number;
  note?: string;
  items?: AnalyzeItem[];
  acct: string;
}

async function getAnalyzeJob(
  kv: KVNamespace,
  id: string,
): Promise<AnalyzeJob | null> {
  const raw = await kv.get(analyzeqKey(id));
  if (raw == null) return null;
  try {
    return JSON.parse(raw) as AnalyzeJob;
  } catch {
    return null;
  }
}

async function getAnalyzeIndex(kv: KVNamespace): Promise<string[]> {
  const raw = await kv.get(ANALYZEQ_INDEX_KEY);
  if (raw == null) return [];
  try {
    const v: unknown = JSON.parse(raw);
    return Array.isArray(v)
      ? v.filter((x): x is string => typeof x === "string")
      : [];
  } catch {
    return [];
  }
}

async function indexAddAnalyze(kv: KVNamespace, id: string) {
  const idx = await getAnalyzeIndex(kv);
  if (!idx.includes(id)) {
    idx.push(id);
    await kv.put(ANALYZEQ_INDEX_KEY, JSON.stringify(idx));
  }
}

async function indexRemoveAnalyze(kv: KVNamespace, id: string) {
  const idx = await getAnalyzeIndex(kv);
  if (idx.includes(id)) {
    await kv.put(
      ANALYZEQ_INDEX_KEY,
      JSON.stringify(idx.filter((x) => x !== id)),
    );
  }
}

async function handleAnalyzeEnqueue(
  kv: KVNamespace,
  req: Request,
  env: Env,
): Promise<Response> {
  const acct = await userAcct(kv, req);
  if (!acct) return json({ error: "unauthorized" }, 401);

  const raw = await req.text();
  if (raw.length > MAX_ANALYZE_BODY) return json({ error: "too large" }, 413);
  let body: { analyzeId?: unknown; image?: unknown };
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  if (typeof body.analyzeId !== "string" || !ANALYZE_ID_RE.test(body.analyzeId)) {
    return json({ error: "bad analyzeId" }, 400);
  }
  const id = body.analyzeId;
  if (
    typeof body.image !== "string" ||
    !/^data:image\/(jpeg|png|webp);base64,/.test(body.image) ||
    body.image.length < 100
  ) {
    return json({ error: "bad image" }, 400);
  }

  // Idempotent for live jobs, exactly like the render queue; a
  // FAILED job is revived by an explicit re-submit (the app's retry
  // button re-sends the same analyzeId + photo).
  const existing = await getAnalyzeJob(kv, id);
  if (existing && existing.status !== "failed") return json(existing);
  const cap = renderCapFor(env);
  if (cap > 0) {
    const capKey = K("analyzecap", acct, new Date().toISOString().slice(0, 10));
    const used = Number(await kv.get(capKey)) || 0;
    if (used >= cap) return json({ error: "render_cap", cap }, 429);
    await kv.put(capKey, String(used + 1));
  }
  const now = Date.now();
  const job: AnalyzeJob = {
    analyzeId: id,
    status: "queued",
    requestedAt: now,
    updatedAt: now,
    acct,
  };
  await kv.put(analyzeqImgKey(id), body.image);
  await kv.put(analyzeqKey(id), JSON.stringify(job));
  await indexAddAnalyze(kv, id);
  return json(job);
}

async function handleAnalyzeGet(
  kv: KVNamespace,
  req: Request,
  id: string,
): Promise<Response> {
  const acct = await userAcct(kv, req);
  if (!acct) return json({ error: "unauthorized" }, 401);
  if (!ANALYZE_ID_RE.test(id)) return json({ error: "bad analyzeId" }, 400);
  const job = await getAnalyzeJob(kv, id);
  if (!job) return json({ error: "not found" }, 404);
  return json(job);
}

async function handleAnalyzeJobs(kv: KVNamespace): Promise<Response> {
  const jobs: (AnalyzeJob & { image?: string })[] = [];
  for (const id of await getAnalyzeIndex(kv)) {
    if (jobs.length >= 3) break;
    const job = await getAnalyzeJob(kv, id);
    if (job && job.status === "queued") {
      const image = await kv.get(analyzeqImgKey(id));
      if (image) jobs.push({ ...job, image });
    }
  }
  return json({ jobs });
}

function validAnalyzeItems(v: unknown, id: string): v is AnalyzeItem[] {
  if (!Array.isArray(v) || v.length === 0 || v.length > 12) return false;
  return v.every((it, n) => {
    if (!it || typeof it !== "object" || Array.isArray(it)) return false;
    const o = it as Record<string, unknown>;
    return (
      typeof o.name === "string" && o.name.length > 0 && o.name.length <= 120 &&
      typeof o.category === "string" &&
      ANALYZE_CATEGORIES.includes(o.category) &&
      typeof o.colourName === "string" && o.colourName.length <= 60 &&
      typeof o.colourHex === "string" && /^#[0-9a-fA-F]{6}$/.test(o.colourHex) &&
      typeof o.brand === "string" && o.brand.length <= 60 &&
      o.img === "assets/analyze/" + id + "-" + n + ".jpg"
    );
  });
}

async function handleAnalyzeStatus(
  kv: KVNamespace,
  req: Request,
  id: string,
): Promise<Response> {
  if (!ANALYZE_ID_RE.test(id)) return json({ error: "bad analyzeId" }, 400);
  let body: { status?: unknown; note?: unknown; items?: unknown };
  try {
    body = JSON.parse(await req.text());
  } catch {
    return json({ error: "bad json" }, 400);
  }
  if (
    body.status !== "analyzing" && body.status !== "done" &&
    body.status !== "failed"
  ) {
    return json({ error: "bad status" }, 400);
  }
  if (body.note !== undefined && typeof body.note !== "string") {
    return json({ error: "bad note" }, 400);
  }
  if (body.status === "done" && !validAnalyzeItems(body.items, id)) {
    return json({ error: "bad items" }, 400);
  }
  const job = await getAnalyzeJob(kv, id);
  if (!job) return json({ error: "not found" }, 404);
  job.status = body.status;
  job.updatedAt = Date.now();
  if (typeof body.note === "string") job.note = body.note;
  if (body.status === "done") job.items = body.items as AnalyzeItem[];
  await kv.put(analyzeqKey(id), JSON.stringify(job));
  if (job.status === "analyzing") {
    await indexAddAnalyze(kv, id);
  } else {
    await indexRemoveAnalyze(kv, id);
    if (job.status === "done" || job.status === "failed") {
      await kv.delete(analyzeqImgKey(id));
    }
  }
  return json(job);
}

// ---------------------------------------------------------------------
// RECEIPT INBOX (build .41) — receipt / order-email auto-import.
// Alta imports order emails so purchases land in the closet. Here a
// Luna-side scan script parses the user's own order mail locally
// (raw bodies never leave that script) and pushes candidate line
// items through this watcher-surface endpoint. Each item becomes a
// record in the account's "receipts" sync collection, written with
// the same chunked layout + sequence allocation as handleSync, so
// the app's next /sync delivers it like any other record and the
// app's confirm sheet takes it from there — nothing files into the
// Closet without the user's tap in the app.
//
// The surface is APPEND-ONLY and idempotent: an id that already
// exists in the collection (in ANY state) is skipped, never
// overwritten. The app owns the state transitions
// (pending -> confirmed / dismissed) through the normal /sync path,
// so a re-run of the scan can never resurrect a dismissed candidate
// or duplicate a confirmed one. The GET is the scan's dedupe read:
// every live receipts record for the account.
//
//   POST /receipt-inbox            x-watcher-secret;
//                                  body { acct, items: [...] }
//                                  -> { written, skipped: [id] }
//   GET  /receipt-inbox?acct=<id>  x-watcher-secret
//                                  -> { items: [{ id, updatedAt, data }] }

const RECEIPT_COLL = "receipts";
const RECEIPT_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/;
const ACCT_RE = /^[0-9a-f]{16}$/;
const MAX_RECEIPT_BODY = 512 * 1024;
const MAX_RECEIPT_ITEMS = 100;
const MAX_RECEIPT_LIST = 500;

interface ReceiptItem {
  id: string;
  name: string;
  brand: string;
  retailer: string;
  price: number | null;
  currency: string;
  orderNo: string;
  orderDate: string;
  category: string;
  colourName: string;
  colourHex: string;
  img: string;
  src: string;
}

function validReceiptItem(v: unknown): v is ReceiptItem {
  if (!v || typeof v !== "object" || Array.isArray(v)) return false;
  const o = v as Record<string, unknown>;
  const str = (x: unknown, max: number) =>
    typeof x === "string" && x.length <= max;
  return (
    typeof o.id === "string" && RECEIPT_ID_RE.test(o.id) &&
    str(o.name, 200) && (o.name as string).length > 0 &&
    str(o.brand, 80) &&
    str(o.retailer, 80) && (o.retailer as string).length > 0 &&
    (o.price === null ||
      (typeof o.price === "number" && Number.isFinite(o.price) &&
        o.price >= 0 && o.price < 10000000)) &&
    str(o.currency, 8) &&
    str(o.orderNo, 64) &&
    str(o.orderDate, 10) &&
    (o.orderDate === "" || /^\d{4}-\d{2}-\d{2}$/.test(o.orderDate as string)) &&
    str(o.category, 40) &&
    (o.category === "" ||
      ANALYZE_CATEGORIES.includes(o.category as string)) &&
    str(o.colourName, 60) &&
    str(o.colourHex, 9) &&
    (o.colourHex === "" || /^#[0-9a-fA-F]{6}$/.test(o.colourHex as string)) &&
    str(o.img, 1000) &&
    (o.img === "" ||
      (/^https:\/\//.test(o.img as string) && !/["'<>`]/.test(o.img as string))) &&
    str(o.src, 64)
  );
}

async function handleReceiptPush(
  kv: KVNamespace,
  req: Request,
): Promise<Response> {
  const raw = await req.text();
  if (raw.length > MAX_RECEIPT_BODY) return json({ error: "too large" }, 413);
  let body: { acct?: unknown; items?: unknown };
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  if (typeof body.acct !== "string" || !ACCT_RE.test(body.acct)) {
    return json({ error: "bad acct" }, 400);
  }
  const acct = body.acct;
  if ((await kv.get(K("acct", acct))) == null) {
    return json({ error: "unknown account" }, 404);
  }
  if (
    !Array.isArray(body.items) || body.items.length === 0 ||
    body.items.length > MAX_RECEIPT_ITEMS
  ) {
    return json({ error: "bad items" }, 400);
  }
  for (const it of body.items) {
    if (!validReceiptItem(it)) return json({ error: "bad item" }, 400);
  }

  // Same sequence discipline as handleSync: read the counter once,
  // allocate in memory, persist once at the end if anything was
  // allocated.
  const seqKey = K("seq", acct);
  const seqRaw = await kv.get(seqKey);
  let seqCounter = seqRaw ? Number(seqRaw) || 0 : 0;
  let seqAllocated = false;

  const now = Date.now();
  const skipped: string[] = [];
  let written = 0;
  for (const it of body.items as ReceiptItem[]) {
    const prefix = K("rec", acct, RECEIPT_COLL, it.id);
    const cur = await getMeta(kv, prefix);
    if (cur) {
      // Any existing record — pending, confirmed, dismissed, even a
      // tombstone — means this candidate was already delivered.
      // Never resurrect, never duplicate.
      skipped.push(it.id);
      continue;
    }
    seqAllocated = true;
    const seq = ++seqCounter;
    const data = {
      id: it.id,
      name: it.name,
      brand: it.brand,
      retailer: it.retailer,
      price: it.price,
      currency: it.currency || "USD",
      orderNo: it.orderNo,
      orderDate: it.orderDate,
      category: it.category,
      colourName: it.colourName,
      colourHex: it.colourHex,
      img: it.img,
      src: it.src,
      status: "pending",
      importedAt: now,
    };
    await putChunked(kv, prefix, { updatedAt: now, seq }, JSON.stringify(data));
    written++;
  }
  if (seqAllocated) await kv.put(seqKey, String(seqCounter));
  if (written > 0) {
    try {
      await writeSnapshot(kv, acct);
    } catch (_) {
      // A snapshot failure must never fail the push itself.
    }
  }
  return json({ written, skipped });
}

async function handleReceiptList(
  kv: KVNamespace,
  url: URL,
): Promise<Response> {
  const acct = url.searchParams.get("acct") || "";
  if (!ACCT_RE.test(acct)) return json({ error: "bad acct" }, 400);
  if ((await kv.get(K("acct", acct))) == null) {
    return json({ error: "unknown account" }, 404);
  }
  const items: { id: string; updatedAt: unknown; data: unknown }[] = [];
  const recPrefix = K("rec", acct, RECEIPT_COLL) + "/";
  for (const name of await listAll(kv, recPrefix)) {
    if (items.length >= MAX_RECEIPT_LIST) break;
    const segs = name.split("/");
    if (segs.length !== 4) continue; // skip chunk keys
    const head = await getMeta(kv, name);
    if (!head || head.deleted) continue;
    const full = await getChunked(kv, name);
    if (!full || full.payload == null) continue;
    items.push({
      id: decodeURIComponent(segs[3]),
      updatedAt: head.updatedAt,
      data: JSON.parse(full.payload),
    });
  }
  return json({ items });
}

// ---------------------------------------------------------------------
// LINK EXTRACT (build .45) — paste-a-link import for the Shop.
// The app sends a product URL; the worker fetches the page
// server-side (retailers block the app's own fetches with CORS)
// and returns the product facts carried in the page's own meta
// tags / JSON-LD: title, brand, price, currency, image. The app
// shows a candidate card and runs its sense-checks locally —
// nothing files anywhere from this endpoint; it stores nothing.
//
// Posture, matching the rest of the worker: user-surface Bearer
// auth (the caller's own sync key), https product pages only in
// practice (http is upgraded for the returned image), a hard cap
// on the fetched bytes, and SSRF guards — no credentials in the
// URL, no localhost / .local / .internal hosts, no IP-literal
// hosts in private, loopback or link-local ranges.
//
//   POST /link-extract   Bearer <key>; body { url }
//     -> 200 { ok, url, title, brand, retailer, price, currency, img }
//     -> 400 { error: "bad url" | "blocked url" }
//     -> 422 { error: "unreachable" | "not a product page" | "no product found" }

const LINK_MAX_BODY = 4096;
const LINK_FETCH_CAP = 1500 * 1024;
const LINK_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36";

function ipLiteralBlocked(host: string): boolean {
  const v4 = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (v4) {
    const a = Number(v4[1]), b = Number(v4[2]);
    if (a === 10 || a === 127 || a === 0) return true;
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 192 && b === 168) return true;
    if (a === 169 && b === 254) return true;
    if (a === 100 && b >= 64 && b <= 127) return true; // CGNAT
    return false;
  }
  const h = host.toLowerCase();
  if (h === "::1" || h === "[::1]") return true;
  if (/^\[?f[cd][0-9a-f]{2}:/.test(h)) return true; // unique-local fc00::/7
  if (/^\[?fe[89ab][0-9a-f]:/.test(h)) return true; // link-local fe80::/10
  return false;
}

function linkUrlBlocked(u: URL): boolean {
  if (u.protocol !== "https:" && u.protocol !== "http:") return true;
  if (u.username || u.password) return true;
  const host = u.hostname.toLowerCase();
  if (!host || host === "localhost") return true;
  if (host.endsWith(".local") || host.endsWith(".internal")) return true;
  if (ipLiteralBlocked(host)) return true;
  return false;
}

function htmlUnescape(s: string): string {
  return s
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#0?39;|&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, n) =>
      String.fromCodePoint(parseInt(n, 16))
    );
}

function metaMap(html: string): Map<string, string> {
  const map = new Map<string, string>();
  const tagRe = /<meta\b[^>]*>/gi;
  let m: RegExpExecArray | null;
  while ((m = tagRe.exec(html)) !== null) {
    const tag = m[0];
    const keyM = tag.match(/(?:property|name)\s*=\s*["']([^"']+)["']/i);
    const valM = tag.match(/content\s*=\s*["']([^"']*)["']/i);
    if (keyM && valM) {
      const k = keyM[1].toLowerCase();
      if (!map.has(k)) map.set(k, htmlUnescape(valM[1]).trim());
    }
  }
  return map;
}

interface LdProduct {
  name?: string;
  brand?: string;
  price?: number;
  currency?: string;
  img?: string;
}

function ldProducts(html: string): LdProduct[] {
  const out: LdProduct[] = [];
  const re =
    /<script\b[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  let m: RegExpExecArray | null;
  const walk = (v: unknown) => {
    if (!v || typeof v !== "object") return;
    if (Array.isArray(v)) {
      v.forEach(walk);
      return;
    }
    const o = v as Record<string, unknown>;
    if (o["@graph"]) walk(o["@graph"]);
    const t = o["@type"];
    const isProduct = t === "Product" ||
      (Array.isArray(t) && t.includes("Product"));
    if (isProduct) {
      const p: LdProduct = {};
      if (typeof o.name === "string") p.name = o.name.trim();
      const b = o.brand;
      if (typeof b === "string") p.brand = b.trim();
      else if (b && typeof b === "object" &&
        typeof (b as Record<string, unknown>).name === "string") {
        p.brand = ((b as Record<string, unknown>).name as string).trim();
      }
      const offers = Array.isArray(o.offers) ? o.offers[0] : o.offers;
      if (offers && typeof offers === "object") {
        const of = offers as Record<string, unknown>;
        const price = typeof of.price === "number"
          ? of.price
          : typeof of.lowPrice === "number"
          ? of.lowPrice
          : typeof of.price === "string"
          ? Number(of.price)
          : NaN;
        if (Number.isFinite(price) && price >= 0) p.price = price;
        if (typeof of.priceCurrency === "string") {
          p.currency = of.priceCurrency.toUpperCase();
        }
      }
      const img = Array.isArray(o.image) ? o.image[0] : o.image;
      if (typeof img === "string") p.img = img;
      else if (img && typeof img === "object" &&
        typeof (img as Record<string, unknown>).url === "string") {
        p.img = (img as Record<string, unknown>).url as string;
      }
      out.push(p);
    }
    Object.values(o).forEach(walk);
  };
  while ((m = re.exec(html)) !== null) {
    try {
      walk(JSON.parse(m[1]));
    } catch {
      // A malformed JSON-LD block is ignored, never fatal.
    }
  }
  return out;
}

async function handleLinkExtract(
  kv: KVNamespace,
  req: Request,
  env: Env,
): Promise<Response> {
  // Two callers: the app (Bearer sync key) and Luna's own price
  // watch script (x-watcher-secret — it holds no user keys, and
  // retailer sites that block this VM's direct fetches answer the
  // worker's edge fetch). Either credential opens the same code
  // path; neither is stored or logged.
  let acct = await userAcct(kv, req);
  if (!acct) {
    const secret = env.RENDER_WATCHER_SECRET;
    if (secret && req.headers.get("x-watcher-secret") === secret) {
      acct = "watcher";
    }
  }
  if (!acct) return json({ error: "unauthorized" }, 401);
  const raw = await req.text();
  if (raw.length > LINK_MAX_BODY) return json({ error: "too large" }, 413);
  let body: { url?: unknown };
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  if (typeof body.url !== "string" || body.url.length > 2000) {
    return json({ error: "bad url" }, 400);
  }
  let u: URL;
  try {
    u = new URL(body.url.trim());
  } catch {
    return json({ error: "bad url" }, 400);
  }
  if (linkUrlBlocked(u)) return json({ error: "blocked url" }, 400);

  let resp: Response;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 12000);
  try {
    resp = await fetch(u.toString(), {
      headers: {
        "user-agent": LINK_UA,
        "accept": "text/html,application/xhtml+xml",
        "accept-language": "en-US,en;q=0.9",
      },
      redirect: "follow",
      signal: ctl.signal,
    });
  } catch {
    clearTimeout(timer);
    return json({ error: "unreachable" }, 422);
  }
  clearTimeout(timer);
  if (!resp.ok) return json({ error: "unreachable", status: resp.status }, 422);
  const ctype = (resp.headers.get("content-type") || "").toLowerCase();
  if (!ctype.includes("html") && !ctype.includes("text/")) {
    return json({ error: "not a product page" }, 422);
  }
  // Read with a hard cap — product pages can be megabytes of app
  // shell; the meta/JSON-LD facts live at the top.
  let html = "";
  try {
    const reader = resp.body?.getReader();
    if (reader) {
      const dec = new TextDecoder();
      let n = 0;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        n += value.byteLength;
        html += dec.decode(value, { stream: true });
        if (n >= LINK_FETCH_CAP) {
          await reader.cancel().catch(() => {});
          break;
        }
      }
    } else {
      html = (await resp.text()).slice(0, LINK_FETCH_CAP);
    }
  } catch {
    return json({ error: "unreachable" }, 422);
  }
  const finalUrl = resp.url || u.toString();
  const meta = metaMap(html);
  const ld = ldProducts(html)[0] || {};

  const titleTag = (html.match(/<title[^>]*>([\s\S]*?)<\/title>/i) || [])[1];
  const title = (ld.name || meta.get("og:title") || meta.get("twitter:title") ||
    (titleTag ? htmlUnescape(titleTag).trim() : "")).slice(0, 300);
  if (!title) return json({ error: "no product found" }, 422);

  let price = ld.price;
  if (price === undefined) {
    const pm = meta.get("product:price:amount") || meta.get("og:price:amount") ||
      meta.get("product:price");
    if (pm) {
      const n = Number(String(pm).replace(/[^0-9.]/g, ""));
      if (Number.isFinite(n) && n > 0) price = n;
    }
  }
  const currency = (ld.currency || meta.get("product:price:currency") ||
    meta.get("og:price:currency") || "").toUpperCase().slice(0, 3);

  let img = ld.img || meta.get("og:image") || meta.get("twitter:image") || "";
  if (img) {
    try {
      const iu = new URL(img, finalUrl);
      iu.protocol = "https:";
      img = iu.toString();
    } catch {
      img = "";
    }
    if (img.length > 1000 || /["'<>`]/.test(img)) img = "";
  }

  let host = "";
  try {
    host = new URL(finalUrl).hostname.replace(/^www\./, "");
  } catch { /* finalUrl came from the fetch; keep empty on surprise */ }
  const retailer = (meta.get("og:site_name") || host).slice(0, 80);
  const brand = (ld.brand || "").slice(0, 120);

  return json({
    ok: true,
    url: finalUrl.slice(0, 2000),
    title,
    brand,
    retailer,
    price: price === undefined ? null : price,
    currency,
    img,
  });
}

// ---------------------------------------------------------------------
// SHOP CATALOGUE (build .52) — the shop database, served by the
// worker instead of shipped as a ~5 MB side file in the repo.
// One account-independent snapshot of the app-export catalogue
// (the same compact records the side file carries: brand, cat,
// img, keys, name, price, retailer, sq, st, tier, url) lives
// under the `shopdb` key in the chunked layout. The weekly
// ingest pushes a fresh snapshot with POST /shop-snapshot
// (watcher surface), so the catalogue updates with no app build;
// the app reads it per piece / per brand with GET /shop/search
// (user surface, same Bearer key as /sync) and falls back to the
// published side file whenever the endpoint cannot serve it.
//
//   GET  /shop/search?brand=&cat=&tier=&keys=a,b&q=&limit=&offset=
//                        Bearer <key>
//                        -> { total, offset, limit, count,
//                             snapshot: { count, updatedAt },
//                             records: [...] }
//                        404 { error: "no_snapshot" } until the
//                        first snapshot lands.
//   POST /shop-snapshot  x-watcher-secret; body = the app-export
//                        JSON array (or { records: [...] })
//                        -> { ok: true, count }
//
// Search semantics mirror the app's own filters so endpoint and
// fallback results agree: brand uses the app's normalised brand
// match (case/diacritic-insensitive, containment for names of
// 5+ chars); cat and tier are exact; `keys` keeps records whose
// key set intersects the query set (a name containing a query
// key as a word also counts, mirroring the app's name-evidence
// colour gate); `q` is free text over name + brand + keys.
// Results order by match strength (key overlap + text hits)
// descending, then name A–Z; with no keys/q they keep snapshot
// order within the filters. The app re-scores whatever it gets
// through its strict gates, so the endpoint may return a
// superset — it must never return a subset of what the side
// file would have matched.

const SHOPDB_KEY = "shopdb";
const MAX_SHOP_BODY = 16 * 1024 * 1024;
const MAX_SHOP_RECORDS = 100000;
const SHOP_SEARCH_DEFAULT_LIMIT = 100;
const SHOP_SEARCH_MAX_LIMIT = 1000;

type ShopRecord = Record<string, unknown>;

// The parsed snapshot, cached in module scope across requests on
// the same isolate and keyed by the stored meta's stamp: a search
// that re-read ~85 chunks and re-parsed ~5 MB on every call would
// burn CPU on data that changes weekly. The stamp check itself
// is one small KV get (the meta key), so a fresh snapshot push
// is picked up as soon as its meta lands.
let shopCache: { stamp: string; updatedAt: number; records: ShopRecord[] } | null = null;

async function loadShopSnapshot(
  kv: KVNamespace,
): Promise<{ records: ShopRecord[]; updatedAt: number } | null> {
  const meta = await getMeta(kv, SHOPDB_KEY);
  if (!meta) {
    shopCache = null;
    return null;
  }
  const updatedAt = typeof meta.updatedAt === "number" ? meta.updatedAt : 0;
  const stamp = updatedAt + ":" + String(meta.count ?? "");
  if (shopCache && shopCache.stamp === stamp) {
    return { records: shopCache.records, updatedAt: shopCache.updatedAt };
  }
  const full = await getChunked(kv, SHOPDB_KEY);
  if (!full || full.payload == null) return null;
  let records: ShopRecord[];
  try {
    const parsed: unknown = JSON.parse(full.payload);
    if (!Array.isArray(parsed)) return null;
    records = parsed as ShopRecord[];
  } catch {
    return null;
  }
  shopCache = { stamp, updatedAt, records };
  return { records, updatedAt };
}

// The app's brandNormName, mirrored: lowercase, strip diacritics,
// non-alphanumerics collapse to single spaces.
function shopBrandNorm(s: unknown): string {
  return String(s ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function shopBrandMatch(recBrand: unknown, queryNorm: string): boolean {
  const b = shopBrandNorm(recBrand);
  if (!b || !queryNorm) return false;
  return b === queryNorm ||
    (Math.min(b.length, queryNorm.length) >= 5 &&
      (b.includes(queryNorm) || queryNorm.includes(b)));
}

async function handleShopSearch(
  kv: KVNamespace,
  req: Request,
  url: URL,
): Promise<Response> {
  const acct = await userAcct(kv, req);
  if (!acct) return json({ error: "unauthorized" }, 401);
  const snap = await loadShopSnapshot(kv);
  if (!snap) return json({ error: "no_snapshot" }, 404);

  const sp = url.searchParams;
  const brandQ = sp.get("brand") ? shopBrandNorm(sp.get("brand")) : "";
  const catQ = (sp.get("cat") || "").trim().toLowerCase();
  const tierQ = (sp.get("tier") || "").trim().toLowerCase();
  const keysQ = (sp.get("keys") || "")
    .split(",")
    .map((k) => k.trim().toLowerCase().replace(/-/g, " "))
    .filter(Boolean);
  const qTokens = (sp.get("q") || "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length >= 3);
  let limit = Number(sp.get("limit"));
  if (!Number.isFinite(limit) || limit <= 0) limit = SHOP_SEARCH_DEFAULT_LIMIT;
  limit = Math.min(Math.floor(limit), SHOP_SEARCH_MAX_LIMIT);
  let offset = Number(sp.get("offset"));
  if (!Number.isFinite(offset) || offset < 0) offset = 0;
  offset = Math.floor(offset);

  const scored: { e: ShopRecord; s: number }[] = [];
  for (const e of snap.records) {
    if (brandQ && !shopBrandMatch(e.brand, brandQ)) continue;
    if (catQ && String(e.cat ?? "").toLowerCase() !== catQ) continue;
    if (tierQ && String(e.tier ?? "").toLowerCase() !== tierQ) continue;
    let s = 0;
    if (keysQ.length) {
      const eKeys = Array.isArray(e.keys)
        ? e.keys.map((k) => String(k).toLowerCase().replace(/-/g, " "))
        : [];
      let overlap = 0;
      for (const k of eKeys) if (keysQ.includes(k)) overlap++;
      if (!overlap) {
        // Name evidence: a query key appearing as a word in the
        // product name counts as a match (the app's colour gate
        // accepts in-family words from the name the same way).
        const nameWords = String(e.name ?? "").toLowerCase().split(/[^a-z0-9]+/);
        if (!keysQ.some((k) => !k.includes(" ") && nameWords.includes(k))) continue;
        overlap = 1;
      }
      s += overlap;
    }
    if (qTokens.length) {
      const hay = (String(e.name ?? "") + " " + String(e.brand ?? "") + " " +
        (Array.isArray(e.keys) ? e.keys.join(" ") : "")).toLowerCase();
      let hits = 0;
      for (const t of qTokens) if (hay.includes(t)) hits++;
      if (!hits) continue;
      s += hits;
    }
    scored.push({ e, s });
  }
  if (keysQ.length || qTokens.length) {
    scored.sort((a, b) =>
      b.s - a.s || String(a.e.name ?? "").localeCompare(String(b.e.name ?? ""))
    );
  }
  const total = scored.length;
  const page = scored.slice(offset, offset + limit).map((x) => x.e);
  return json({
    total,
    offset,
    limit,
    count: page.length,
    snapshot: { count: snap.records.length, updatedAt: snap.updatedAt },
    records: page,
  });
}

function validShopRecord(v: unknown): v is ShopRecord {
  if (!v || typeof v !== "object" || Array.isArray(v)) return false;
  const o = v as Record<string, unknown>;
  const str = (x: unknown, max: number) =>
    typeof x === "string" && x.length > 0 && x.length <= max;
  return (
    str(o.brand, 200) && str(o.name, 500) && str(o.url, 2000) &&
    // http: included — a handful of source catalogue URLs (7 of
    // 14,286) are plain http, and the side file serves them as-is;
    // the endpoint must accept a superset of the fallback's data.
    /^https?:\/\//.test(o.url as string) &&
    typeof o.price === "number" && Number.isFinite(o.price) &&
    o.price >= 0 && o.price < 10000000
  );
}

async function handleShopSnapshot(
  kv: KVNamespace,
  req: Request,
): Promise<Response> {
  const raw = await req.text();
  if (raw.length > MAX_SHOP_BODY) return json({ error: "too large" }, 413);
  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  const records: unknown = Array.isArray(body)
    ? body
    : (body as { records?: unknown } | null)?.records;
  if (!Array.isArray(records) || records.length === 0 ||
    records.length > MAX_SHOP_RECORDS) {
    return json({ error: "bad records" }, 400);
  }
  for (let i = 0; i < records.length; i++) {
    if (!validShopRecord(records[i])) {
      return json({ error: "bad record", index: i }, 400);
    }
  }
  const payload = JSON.stringify(records);
  const updatedAt = Date.now();
  await putChunked(kv, SHOPDB_KEY, {
    count: records.length,
    updatedAt,
    source: "shop-snapshot",
  }, payload);
  shopCache = null; // the next search re-reads under the new stamp
  return json({ ok: true, count: records.length, updatedAt });
}

// ---------------------------------------------------------------------
// PRICE WATCH (build .45) — wishlist price-drop alerts.
// The app syncs its product wishlist as the "shopwish" collection
// (records carry the price at save time). A Luna-side weekly watch
// script reads that collection here, re-fetches each product page,
// and posts the current price back as "pricedrops" records; the
// app's next /sync delivers them and the wishlist rows show the
// drop. Mirrors the receipt inbox: watcher-secret surface, records
// written with the same chunked layout + sequence allocation as
// handleSync. One deliberate difference from receipts: a drop
// record is REPLACED when a newer check (higher checkedAt) lands —
// prices move both ways and the app must see a drop clear, not
// just appear. Stale or equal checks are skipped.
//
//   GET  /price-watch?acct=<id>  x-watcher-secret
//                                -> { items: [{ id, updatedAt, data }] }
//   POST /price-drops            x-watcher-secret;
//                                body { acct, items: [...] }
//                                -> { written, skipped: [id] }

const SHOPWISH_COLL = "shopwish";
const PRICEDROPS_COLL = "pricedrops";
const MAX_DROP_BODY = 512 * 1024;
const MAX_DROP_ITEMS = 200;
const MAX_WATCH_LIST = 500;

interface DropItem {
  id: string;
  key: string;
  url: string;
  priceWas: number;
  priceNow: number;
  checkedAt: number;
}

function validDropItem(v: unknown): v is DropItem {
  if (!v || typeof v !== "object" || Array.isArray(v)) return false;
  const o = v as Record<string, unknown>;
  const str = (x: unknown, max: number) =>
    typeof x === "string" && x.length > 0 && x.length <= max &&
    !/[\u0000-\u001f\u007f]/.test(x);
  const num = (x: unknown) =>
    typeof x === "number" && Number.isFinite(x) && x >= 0 && x < 10000000;
  return (
    str(o.id, 800) && str(o.key, 800) &&
    str(o.url, 1000) && /^https:\/\//.test(o.url as string) &&
    num(o.priceWas) && num(o.priceNow) &&
    typeof o.checkedAt === "number" && Number.isFinite(o.checkedAt) &&
    o.checkedAt > 0 && o.checkedAt < 10000000000000
  );
}

async function handlePriceWatchList(
  kv: KVNamespace,
  url: URL,
): Promise<Response> {
  const acct = url.searchParams.get("acct") || "";
  if (!ACCT_RE.test(acct)) return json({ error: "bad acct" }, 400);
  if ((await kv.get(K("acct", acct))) == null) {
    return json({ error: "unknown account" }, 404);
  }
  const items: { id: string; updatedAt: unknown; data: unknown }[] = [];
  const recPrefix = K("rec", acct, SHOPWISH_COLL) + "/";
  for (const name of await listAll(kv, recPrefix)) {
    if (items.length >= MAX_WATCH_LIST) break;
    const segs = name.split("/");
    if (segs.length !== 4) continue; // skip chunk keys
    const head = await getMeta(kv, name);
    if (!head || head.deleted) continue;
    const full = await getChunked(kv, name);
    if (!full || full.payload == null) continue;
    items.push({
      id: decodeURIComponent(segs[3]),
      updatedAt: head.updatedAt,
      data: JSON.parse(full.payload),
    });
  }
  return json({ items });
}

async function handlePriceDrops(
  kv: KVNamespace,
  req: Request,
): Promise<Response> {
  const raw = await req.text();
  if (raw.length > MAX_DROP_BODY) return json({ error: "too large" }, 413);
  let body: { acct?: unknown; items?: unknown };
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  if (typeof body.acct !== "string" || !ACCT_RE.test(body.acct)) {
    return json({ error: "bad acct" }, 400);
  }
  const acct = body.acct;
  if ((await kv.get(K("acct", acct))) == null) {
    return json({ error: "unknown account" }, 404);
  }
  if (
    !Array.isArray(body.items) || body.items.length === 0 ||
    body.items.length > MAX_DROP_ITEMS
  ) {
    return json({ error: "bad items" }, 400);
  }
  for (const it of body.items) {
    if (!validDropItem(it)) return json({ error: "bad item" }, 400);
  }

  const seqKey = K("seq", acct);
  const seqRaw = await kv.get(seqKey);
  let seqCounter = seqRaw ? Number(seqRaw) || 0 : 0;
  let seqAllocated = false;

  const now = Date.now();
  const skipped: string[] = [];
  let written = 0;
  for (const it of body.items as DropItem[]) {
    const prefix = K("rec", acct, PRICEDROPS_COLL, it.id);
    const cur = await getChunked(kv, prefix);
    if (cur && cur.payload != null) {
      try {
        const prev = JSON.parse(cur.payload) as { checkedAt?: unknown };
        if (typeof prev.checkedAt === "number" && prev.checkedAt >= it.checkedAt) {
          skipped.push(it.id);
          continue;
        }
      } catch { /* an unreadable record is replaced, never kept */ }
    }
    seqAllocated = true;
    const seq = ++seqCounter;
    const data = {
      id: it.id,
      key: it.key,
      url: it.url,
      priceWas: it.priceWas,
      priceNow: it.priceNow,
      checkedAt: it.checkedAt,
    };
    await putChunked(kv, prefix, { updatedAt: now, seq }, JSON.stringify(data));
    written++;
  }
  if (seqAllocated) await kv.put(seqKey, String(seqCounter));
  if (written > 0) {
    try {
      await writeSnapshot(kv, acct);
    } catch (_) {
      // A snapshot failure must never fail the push itself.
    }
  }
  return json({ written, skipped });
}

export async function handler(
  req: Request,
  env: Env,
  ctx?: { waitUntil?: (p: Promise<unknown>) => void },
): Promise<Response> {
  const kv = env.SYNC_KV;
  const url = new URL(req.url);
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
  if (req.method === "GET" && url.pathname === "/") {
    return json({ ok: true, service: "wardrobe-sync" });
  }
  if (req.method === "POST" && url.pathname === "/register") {
    return handleRegister(kv, req, env);
  }
  if (req.method === "POST" && url.pathname === "/sync") {
    return handleSync(kv, req, ctx);
  }
  if (req.method === "POST" && url.pathname === "/render-queue") {
    return handleRenderEnqueue(kv, req, env);
  }
  const rq = url.pathname.match(/^\/render-queue\/([^/]+)$/);
  if (req.method === "GET" && rq) {
    return handleRenderGet(kv, req, decodeURIComponent(rq[1]));
  }
  if (req.method === "GET" && url.pathname === "/render-jobs") {
    const gate = watcherGate(req, env);
    if (gate) return gate;
    return handleRenderJobs(kv);
  }
  const rj = url.pathname.match(/^\/render-jobs\/([^/]+)\/status$/);
  if (req.method === "POST" && rj) {
    const gate = watcherGate(req, env);
    if (gate) return gate;
    return handleRenderStatus(kv, req, decodeURIComponent(rj[1]));
  }
  if (req.method === "POST" && url.pathname === "/analyze-queue") {
    return handleAnalyzeEnqueue(kv, req, env);
  }
  const aq = url.pathname.match(/^\/analyze-queue\/([^/]+)$/);
  if (req.method === "GET" && aq) {
    return handleAnalyzeGet(kv, req, decodeURIComponent(aq[1]));
  }
  if (req.method === "GET" && url.pathname === "/analyze-jobs") {
    const gate = watcherGate(req, env);
    if (gate) return gate;
    return handleAnalyzeJobs(kv);
  }
  const aj = url.pathname.match(/^\/analyze-jobs\/([^/]+)\/status$/);
  if (req.method === "POST" && aj) {
    const gate = watcherGate(req, env);
    if (gate) return gate;
    return handleAnalyzeStatus(kv, req, decodeURIComponent(aj[1]));
  }
  if (req.method === "POST" && url.pathname === "/receipt-inbox") {
    const gate = watcherGate(req, env);
    if (gate) return gate;
    return handleReceiptPush(kv, req);
  }
  if (req.method === "GET" && url.pathname === "/receipt-inbox") {
    const gate = watcherGate(req, env);
    if (gate) return gate;
    return handleReceiptList(kv, url);
  }
  if (req.method === "POST" && url.pathname === "/link-extract") {
    return handleLinkExtract(kv, req, env);
  }
  if (req.method === "GET" && url.pathname === "/price-watch") {
    const gate = watcherGate(req, env);
    if (gate) return gate;
    return handlePriceWatchList(kv, url);
  }
  if (req.method === "POST" && url.pathname === "/price-drops") {
    const gate = watcherGate(req, env);
    if (gate) return gate;
    return handlePriceDrops(kv, req);
  }
  if (req.method === "GET" && url.pathname === "/shop/search") {
    return handleShopSearch(kv, req, url);
  }
  if (req.method === "POST" && url.pathname === "/shop-snapshot") {
    const gate = watcherGate(req, env);
    if (gate) return gate;
    return handleShopSnapshot(kv, req);
  }
  return json({ error: "not found" }, 404);
}

export default {
  fetch(
    req: Request,
    env: Env,
    ctx?: { waitUntil?: (p: Promise<unknown>) => void },
  ): Promise<Response> {
    return handler(req, env, ctx);
  },
};
