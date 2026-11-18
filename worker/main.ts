// wardrobe-sync — cloud sync service for the Wardrobe app.
//
// Mirrors the Padel Log sync contract exactly (same routes, same auth
// model, same merge semantics), generalised over collection names:
//
//   GET  /          -> { ok: true, service: "wardrobe-sync" }
//   POST /register  -> { key, acct }        (key = 48 hex chars)
//   POST /sync      -> Bearer <key>; body { since, changes, meta }
//                      returns { recs, meta, now }; 401 on a bad key.
//
// Merge rule (identical to Padel Log): last-writer-wins per record by
// client-supplied `updatedAt` (ms); deletes travel as tombstones
// ({ coll, id, updatedAt, deleted: true }). The server assigns every
// accepted write a per-account sequence number; `since`/`now` page
// through that sequence so a client only receives what it has not seen.
//
// Storage: Deno KV. Record values are JSON; values larger than ~60 KB
// (Wardrobe closet/inspo records embed photos as data URIs) are split
// into chunk entries, because a single KV value is capped at 64 KiB.
//
// Data safety: after any sync that changes something, the server keeps
// a full last-known-good snapshot of the account's live state in a
// ring of the 10 most recent snapshots (["snap", acct, ts] index +
// ["snapchunk", ...] payloads). A bad client push can therefore be
// rolled back by hand from KV; the sync contract itself never deletes
// history silently — tombstones are stored, not erased.

const CHUNK = 60000; // bytes of JSON per KV value, safely under 64 KiB
const SNAP_KEEP = 10;
const MAX_BODY = 64 * 1024 * 1024;

const kv = await Deno.openKv(Deno.env.get("KV_PATH") || undefined);

const enc = new TextEncoder();
const dec = new TextDecoder();

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
  "access-control-allow-headers": "authorization, content-type",
};
const json = (obj: unknown, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json", ...CORS },
  });

// ---------- chunked value helpers ----------
// A stored entry is either { ..., inline: "<json>" } or
// { ..., chunks: n } with payloads at [...prefix, "c", i].

async function putChunked(
  prefix: Deno.KvKey,
  meta: Record<string, unknown>,
  payload: string,
) {
  const bytes = enc.encode(payload);
  const old = (await kv.get(prefix)).value as { chunks?: number } | null;
  const oldChunks = old?.chunks || 0;
  if (bytes.length <= CHUNK) {
    const op = kv.atomic().set(prefix, { ...meta, inline: payload });
    for (let i = 0; i < oldChunks; i++) op.delete([...prefix, "c", i]);
    await op.commit();
    return;
  }
  const n = Math.ceil(bytes.length / CHUNK);
  const op = kv.atomic().set(prefix, { ...meta, chunks: n });
  for (let i = 0; i < n; i++) {
    op.set(
      [...prefix, "c", i],
      dec.decode(bytes.subarray(i * CHUNK, (i + 1) * CHUNK)),
    );
  }
  for (let i = n; i < oldChunks; i++) op.delete([...prefix, "c", i]);
  await op.commit();
}

async function getChunked(prefix: Deno.KvKey) {
  const e = (await kv.get(prefix)).value as
    | { inline?: string; chunks?: number }
    | null;
  if (!e) return null;
  if (e.inline !== undefined) return { meta: e, payload: e.inline };
  if (e.chunks) {
    const keys = Array.from({ length: e.chunks }, (_, i) => [...prefix, "c", i]);
    const parts = await kv.getMany(keys);
    return { meta: e, payload: parts.map((p) => p.value as string).join("") };
  }
  return { meta: e, payload: null };
}

// ---------- accounts ----------

async function acctForKey(key: string | null): Promise<string | null> {
  if (!key || !/^[0-9a-f]{48}$/.test(key)) return null;
  const h = await sha256hex(key);
  const e = await kv.get(["key", h]);
  return (e.value as string) || null;
}

async function nextSeq(acct: string): Promise<number> {
  const cur = (await kv.get(["seq", acct])).value as number | null;
  const n = (cur || 0) + 1;
  await kv.set(["seq", acct], n);
  return n;
}

// ---------- snapshots (last-known-good ring) ----------

async function writeSnapshot(acct: string) {
  // Assemble the full live state: every non-deleted record + meta.
  const state: Record<string, Record<string, unknown>> = {};
  for await (const e of kv.list({ prefix: ["rec", acct] })) {
    const [, , coll, id] = e.key as string[];
    const v = e.value as { deleted?: boolean };
    if (v.deleted) continue;
    const full = await getChunked(["rec", acct, coll, id]);
    if (!full || full.payload == null) continue;
    (state[coll] ||= {})[id] = JSON.parse(full.payload);
  }
  const m = await getChunked(["meta", acct]);
  const snap = {
    at: Date.now(),
    recs: state,
    meta: m && m.payload != null ? JSON.parse(m.payload) : null,
  };
  const ts = snap.at;
  await putChunked(["snap", acct, String(ts)], { at: ts }, JSON.stringify(snap));
  // Trim the ring to the newest SNAP_KEEP snapshots.
  const idx: string[] = [];
  for await (const e of kv.list({ prefix: ["snap", acct] })) {
    if (e.key.length === 3) idx.push(e.key[2] as string);
  }
  idx.sort();
  for (const old of idx.slice(0, Math.max(0, idx.length - SNAP_KEEP))) {
    const e = (await kv.get(["snap", acct, old])).value as
      | { chunks?: number }
      | null;
    const op = kv.atomic().delete(["snap", acct, old]);
    for (let i = 0; i < (e?.chunks || 0); i++) {
      op.delete(["snap", acct, old, "c", i]);
    }
    await op.commit();
  }
}

// ---------- handlers ----------

async function handleRegister(): Promise<Response> {
  const key = randHex(24); // 48 hex chars, same shape as Padel Log keys
  const acct = randHex(8);
  const h = await sha256hex(key);
  await kv.atomic()
    .set(["key", h], acct)
    .set(["acct", acct], { createdAt: Date.now() })
    .set(["seq", acct], 0)
    .commit();
  return json({ key, acct });
}

interface Change {
  coll: string;
  id: string;
  updatedAt: number;
  data?: unknown;
  deleted?: boolean;
}

async function handleSync(req: Request): Promise<Response> {
  const auth = req.headers.get("authorization") || "";
  const key = auth.startsWith("Bearer ") ? auth.slice(7) : null;
  const acct = await acctForKey(key);
  if (!acct) return json({ error: "unauthorized" }, 401);

  const raw = await req.text();
  if (raw.length > MAX_BODY) return json({ error: "too large" }, 413);
  let body: { since?: number; changes?: Change[]; meta?: unknown };
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  const since = typeof body.since === "number" ? body.since : 0;
  const changes = Array.isArray(body.changes) ? body.changes : [];

  const written = new Set<string>(); // "coll\0id\0updatedAt" written this request
  let dirty = false;

  for (const ch of changes) {
    if (
      !ch || typeof ch.coll !== "string" || typeof ch.id !== "string" ||
      typeof ch.updatedAt !== "number"
    ) continue;
    const prefix = ["rec", acct, ch.coll, ch.id];
    const cur = (await kv.get(prefix)).value as
      | { updatedAt?: number }
      | null;
    if (cur && typeof cur.updatedAt === "number" && ch.updatedAt <= cur.updatedAt) {
      continue; // stale or duplicate write: last-writer-wins says no
    }
    const seq = await nextSeq(acct);
    if (ch.deleted) {
      const old = cur as { chunks?: number } | null;
      const op = kv.atomic().set(prefix, {
        updatedAt: ch.updatedAt,
        deleted: true,
        seq,
      });
      for (let i = 0; i < (old?.chunks || 0); i++) op.delete([...prefix, "c", i]);
      await op.commit();
    } else {
      await putChunked(prefix, { updatedAt: ch.updatedAt, seq }, JSON.stringify(ch.data ?? null));
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
    const cur = (await kv.get(["meta", acct])).value as
      | { updatedAt?: number }
      | null;
    if (!cur || inMetaAt > (cur.updatedAt || 0)) {
      const seq = await nextSeq(acct);
      await putChunked(
        ["meta", acct],
        { updatedAt: inMetaAt, seq },
        JSON.stringify(inMeta.data ?? null),
      );
      dirty = true;
    }
  }

  // Collect everything this client has not seen (seq > since), minus the
  // records it just wrote itself in this request.
  const recs: Record<string, unknown>[] = [];
  for await (const e of kv.list({ prefix: ["rec", acct] })) {
    if (e.key.length !== 4) continue;
    const [, , coll, id] = e.key as string[];
    const v = e.value as { updatedAt: number; deleted?: boolean; seq: number };
    if (!(v.seq > since)) continue;
    if (written.has(coll + "\0" + id + "\0" + v.updatedAt)) continue;
    if (v.deleted) {
      recs.push({ coll, id, updatedAt: v.updatedAt, deleted: true });
    } else {
      const full = await getChunked(["rec", acct, coll, id]);
      recs.push({
        coll,
        id,
        updatedAt: v.updatedAt,
        data: full && full.payload != null ? JSON.parse(full.payload) : null,
      });
    }
  }
  recs.sort((a, b) => (a.updatedAt as number) - (b.updatedAt as number));

  let meta: unknown = null;
  const m = await getChunked(["meta", acct]);
  if (m && m.payload != null) {
    const mv = m.meta as { updatedAt: number; seq: number };
    // Skip the echo when the stored meta is exactly the version this
    // request just carried; the client already has it.
    if (mv.seq > since && mv.updatedAt !== inMetaAt) {
      meta = { updatedAt: mv.updatedAt, data: JSON.parse(m.payload) };
    }
  }

  const now = (await kv.get(["seq", acct])).value as number | null;

  if (dirty) {
    // Last-known-good snapshot of the post-sync live state.
    try {
      await writeSnapshot(acct);
    } catch (_) {
      // A snapshot failure must never fail the sync itself.
    }
  }

  return json({ recs, meta, now: now || 0 });
}

export async function handler(req: Request): Promise<Response> {
  const url = new URL(req.url);
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
  if (req.method === "GET" && url.pathname === "/") {
    return json({ ok: true, service: "wardrobe-sync" });
  }
  if (req.method === "POST" && url.pathname === "/register") {
    return handleRegister();
  }
  if (req.method === "POST" && url.pathname === "/sync") {
    return handleSync(req);
  }
  return json({ error: "not found" }, 404);
}

if (import.meta.main) {
  const port = Number(Deno.env.get("PORT") || 8000);
  Deno.serve({ port }, handler);
}
