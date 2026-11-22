const SNAP_PART = 6 * 1024 * 1024;
const SNAP_SWEEP_MAX = 400;
const SNAP_ORPHAN_AGE_MS = 2 * 60 * 60 * 1e3;
async function writeSnapshot(kv, acct) {
  const snapPrefix = K("snap", acct) + "/";
  const idx = [];
  const partsOf = new Map();
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
  const newest = idx.length ? Number(decodeURIComponent(idx[idx.length - 1])) : NaN;
  if (Number.isFinite(newest) && Date.now() - newest < SNAP_MIN_INTERVAL_MS) {
    return;
  }
  // The snapshot is one JSON document with the same shape as before,
  //   {"at":..,"recs":{"<coll>":{"<id>":<data>,..},..},"meta":<meta|null>}
  // but it is never held in memory whole. Each live record's stored JSON
  // text is appended as it is (no parse, no re-stringify) and the text is
  // flushed to KV in a few large parts. A closet over the 25 MiB value
  // limit used to fall back to ~500 small puts of the fully assembled
  // text, and the worker was killed part-way through every time (error
  // 1102), leaving no snapshot and hundreds of orphan parts.
  // Layout is the chunked layout getChunked / deleteChunked already read:
  // parts at <prefix>/c/<i>, then the meta key { at, chunks, v: 2 } last,
  // so a snapshot whose meta key exists is always complete.
  const ts = Date.now();
  const prefix = K("snap", acct, ts);
  const recPrefix = K("rec", acct) + "/";
  const heads = [];
  for (const name of await listAll(kv, recPrefix)) {
    const segs = name.split("/");
    if (segs.length !== 4) continue;
    heads.push({ name, coll: decodeURIComponent(segs[2]), id: decodeURIComponent(segs[3]) });
  }
  heads.sort((a, b) => a.coll < b.coll ? -1 : a.coll > b.coll ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  let buf = '{"at":' + ts + ',"recs":{';
  let nParts = 0;
  let curColl = null;
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
  buf += (curColl === null ? "" : "}") + '},"meta":' + (m && m.payload != null ? m.payload : "null") + "}";
  await flush();
  await kv.put(prefix, JSON.stringify({ at: ts, chunks: nParts, v: 2 }));
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
