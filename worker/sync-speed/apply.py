"""Apply the sync speed change to a copy of the live wardrobe-sync module.

usage: python3 apply.py <live worker.js> <patched worker.js>

<live worker.js> is the module downloaded read-only from Cloudflare. It must
already carry the snapshot fix (../snapshot-fix). handleSync, its callers and
three lines of writeSnapshot change; each old text must be found exactly once or the
script stops without writing anything.
"""
import sys
src, dst = sys.argv[1], sys.argv[2]
js = open(src).read()
assert "SNAP_PART" in js, "the snapshot fix must be in the file first"
assert "SCAN_BATCH" not in js, "this file already has the speed change"
EDITS = [
 # 1. the read side: record heads are read 16 at a time instead of one by one
 ('''  const recs = [];
  const recPrefix = K("rec", acct) + "/";
  for (const name of await listAll(kv, recPrefix)) {
    const segs = name.split("/");
    if (segs.length !== 4) continue;
    const coll = decodeURIComponent(segs[2]);
    const id = decodeURIComponent(segs[3]);
    const v = await getMeta(kv, name);
    if (!v || typeof v.seq !== "number" || !(v.seq > since)) continue;
    if (written.has(coll + "\\0" + id + "\\0" + v.updatedAt)) continue;
    if (v.deleted) {
      recs.push({ coll, id, updatedAt: v.updatedAt, deleted: true });
    } else {
      const full = await getChunked(kv, name);
      recs.push({
        coll,
        id,
        updatedAt: v.updatedAt,
        data: full && full.payload != null ? JSON.parse(full.payload) : null
      });
    }
  }
  recs.sort((a, b) => a.updatedAt - b.updatedAt);
''',
  '''  // The counter is stored as soon as the writes are done (it used to be
  // stored after the scan below), so a request that is cut off while
  // scanning never leaves records numbered above the stored counter.
  if (seqAllocated) await kv.put(seqKey, String(seqCounter));
  // Record heads are read SCAN_BATCH at a time. They used to be read one
  // by one, which made every sync of a 500-record closet wait for about
  // 500 round trips to KV. What is returned, and in what order, is the same.
  const recs = [];
  let outChars = 0;
  const recPrefix = K("rec", acct) + "/";
  const recNames = [];
  for (const name of await listAll(kv, recPrefix)) {
    if (name.split("/").length === 4) recNames.push(name);
  }
  for (let i = 0; i < recNames.length; i += SCAN_BATCH) {
    const group = recNames.slice(i, i + SCAN_BATCH);
    const heads = await Promise.all(group.map((name) => getMeta(kv, name)));
    const picked = [];
    for (let j = 0; j < group.length; j++) {
      const segs = group[j].split("/");
      const coll = decodeURIComponent(segs[2]);
      const id = decodeURIComponent(segs[3]);
      const v = heads[j];
      if (!v || typeof v.seq !== "number" || !(v.seq > since)) continue;
      if (written.has(coll + "\\0" + id + "\\0" + v.updatedAt)) continue;
      picked.push({ name: group[j], coll, id, v });
    }
    const fulls = await Promise.all(
      picked.map((p) => p.v.deleted ? null : getChunked(kv, p.name))
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
          data: full && full.payload != null ? JSON.parse(full.payload) : null
        });
      }
    }
  }
  recs.sort((a, b) => a.updatedAt - b.updatedAt);
'''),
 # 2. the counter is no longer stored here (moved up, see 1), and the hourly
 #    safety snapshot no longer holds the answer back
 ('''  if (seqAllocated) await kv.put(seqKey, String(seqCounter));
  const now = seqCounter;
  if (dirty) {
    try {
      await writeSnapshot(kv, acct);
    } catch (_) {
    }
  }
  return json({ recs, meta, now });
''',
  '''  const now = seqCounter;
  if (dirty) await snapshotAfterSync(kv, acct, ctx, outChars >= SNAP_DEFER_MAX_CHARS);
  return json({ recs, meta, now });
'''),
 # 3. handleSync and the entry point pass the execution context through
 ('''async function handleSync(kv, req) {
''', '''const SCAN_BATCH = 16;
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
async function snapshotAfterSync(kv, acct, ctx, mustWait) {
  const canDefer = !!(ctx && typeof ctx.waitUntil === "function");
  const flagKey = K("snapflag", acct);
  const flagRaw = await kv.get(flagKey);
  const flagAt = flagRaw ? Number(flagRaw) || 0 : 0;
  const age = Date.now() - flagAt;
  if (flagAt && age >= 0 && age < SNAP_FLAG_FRESH_MS) return;
  const snap = writeSnapshot(kv, acct, flagKey).catch(() => {
  });
  if (canDefer) ctx.waitUntil(snap);
  if (!canDefer || mustWait || flagAt) await snap;
}
async function handleSync(kv, req, ctx) {
'''),
 # 4. writeSnapshot keeps the flag key while it is writing
 ('''async function writeSnapshot(kv, acct) {
''', '''async function writeSnapshot(kv, acct, flagKey) {
'''),
 ('''  const ts = Date.now();
  const prefix = K("snap", acct, ts);
''', '''  const ts = Date.now();
  const prefix = K("snap", acct, ts);
  if (flagKey) await kv.put(flagKey, String(ts));
'''),
 ('''  await kv.put(prefix, JSON.stringify({ at: ts, chunks: nParts, v: 2 }));
''', '''  await kv.put(prefix, JSON.stringify({ at: ts, chunks: nParts, v: 2 }));
  if (flagKey) await kv.delete(flagKey);
'''),
 ('''async function handler(req, env) {
''', '''async function handler(req, env, ctx) {
'''),
 ('''    return handleSync(kv, req);
''', '''    return handleSync(kv, req, ctx);
'''),
 ('''  fetch(req, env) {
    return handler(req, env);
  }
''', '''  fetch(req, env, ctx) {
    return handler(req, env, ctx);
  }
'''),
]
out = js
for old, new in EDITS:
    assert out.count(old) == 1, "expected exactly one match for:\n" + old[:200]
    out = out.replace(old, new)
open(dst, "w").write(out)
print("patched:", dst, "| %d -> %d characters; %d places changed" % (len(js), len(out), len(EDITS)))
