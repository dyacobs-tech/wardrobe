// In-memory tests for the patched snapshot writer. No network, no Cloudflare.
// Differential: the same request sequence goes to the LIVE worker code and the PATCHED code on separate
// in-memory KVs; every response and every non-snapshot key must be identical. Then the new snapshot
// layout, ring trim, orphan sweep and a 32 MB closet are checked on the patched code alone.
import { createHash } from 'node:crypto';
// usage: node --max-old-space-size=2048 test.mjs <live worker.mjs> <patched worker.mjs>   (absolute paths, .mjs)
const live = await import(process.argv[2]); const next = await import(process.argv[3]);
let fails = 0; const ok = (name, cond, info = '') => { console.log((cond ? 'PASS ' : 'FAIL ') + name + (cond ? '' : ' :: ' + info)); if (!cond) fails++; };
class KV { constructor() { this.m = new Map(); this.ops = { get: 0, put: 0, delete: 0, list: 0 }; this.maxPut = 0; }
  async get(k) { this.ops.get++; return this.m.has(k) ? this.m.get(k) : null; }
  async put(k, v) { this.ops.put++; if (typeof v !== 'string') throw new Error('non-string put'); const b = Buffer.byteLength(v); if (b > 25 * 1024 * 1024) throw new Error('KV value too large: ' + b); this.maxPut = Math.max(this.maxPut, b); this.m.set(k, v); }
  async delete(k) { this.ops.delete++; this.m.delete(k); }
  async list({ prefix = '', cursor, limit = 1000 } = {}) { this.ops.list++; const names = [...this.m.keys()].filter(k => k.startsWith(prefix)).sort(); const start = cursor ? Number(cursor) : 0; const page = names.slice(start, start + limit);
    const done = start + limit >= names.length; return { keys: page.map(name => ({ name })), list_complete: done, cursor: done ? undefined : String(start + limit) }; } }
const KEY = 'ab'.repeat(24), ACCT = '1111222233334444', OTHER = 'ffffeeeeddddcccc';
const sha = s => createHash('sha256').update(s).digest('hex');
const seed = kv => { kv.m.set('key/' + sha(KEY), ACCT); };
// Work handed to ctx.waitUntil (the snapshot, since the sync speed change) is awaited before the call returns.
const call = async (mod, kv, body) => { const ps = []; const r = await mod.default.fetch(new Request('https://x.test/sync', { method: 'POST', headers: { authorization: 'Bearer ' + KEY, 'content-type': 'application/json' }, body: JSON.stringify(body) }), { SYNC_KV: kv }, { waitUntil(p) { ps.push(p); } }); const out = { status: r.status, text: await r.text() }; await Promise.all(ps); return out; };
const big = n => 'data:image/jpeg;base64,' + 'A'.repeat(n);
const rec = (coll, id, at, data) => ({ coll, id, updatedAt: at, data });
const realNow = Date.now; let clock = 1795300000000; Date.now = () => clock;
const snapKeys = kv => [...kv.m.keys()].filter(k => k.startsWith('snap/' + ACCT + '/'));
const metas = kv => snapKeys(kv).filter(k => k.split('/').length === 3).sort();
const readSnap = kv => { const mk = metas(kv).pop(); const meta = JSON.parse(kv.m.get(mk)); if (meta.inline !== undefined) return { meta, doc: JSON.parse(meta.inline) }; let t = ''; for (let i = 0; i < meta.chunks; i++) t += kv.m.get(mk + '/c/' + i); return { meta, doc: JSON.parse(t), parts: meta.chunks }; };

// ---- 1. differential on a small closet (inline-size records, chunked records, unicode, deletes, meta) ----
{ const A = new KV(), B = new KV(); seed(A); seed(B); const steps = [
    { since: 0, changes: [rec('items', 'i1', 10, { name: 'Tee — “Café” 👕', photo: big(150000) }), rec('items', 'i2', 11, { name: 'Small' }), rec('looks', 'l/1 odd id', 12, { title: 'x', n: [1, 2, { a: null }] }), rec('worn', 'w1', 13, null)], meta: { updatedAt: 5, data: { profile: { n: 1 } } } },
    { since: 0, changes: [] },
    { since: 2, changes: [rec('items', 'i2', 20, { name: 'Small v2' }), { coll: 'looks', id: 'l/1 odd id', updatedAt: 21, deleted: true }] },
    { since: 99, changes: [rec('items', 'i1', 9, { name: 'stale write, must be ignored' })] },
    { since: 0, changes: [] } ];
  let same = true, info = '';
  for (let i = 0; i < steps.length; i++) { clock += 2 * 3600e3; const a = await call(live, A, steps[i]); const b = await call(next, B, steps[i]); if (a.status !== b.status || a.text !== b.text) { same = false; info = 'step ' + i + ': ' + a.status + ' vs ' + b.status + ' | ' + a.text.slice(0, 160) + ' || ' + b.text.slice(0, 160); break; } }
  ok('responses identical to the live code over a write / read / delete / stale sequence', same, info);
  const ns = kv => [...kv.m.entries()].filter(([k]) => !k.startsWith('snap/')).sort();
  ok('every non-snapshot key identical to the live code', JSON.stringify(ns(A)) === JSON.stringify(ns(B)));
  const sa = readSnap(A), sb = readSnap(B);
  ok('new snapshot is the chunked layout with v: 2', sb.meta.v === 2 && sb.meta.chunks >= 1 && sb.meta.inline === undefined, JSON.stringify(sb.meta).slice(0, 100));
  ok('new snapshot content equals the live code\'s snapshot (recs and meta)', JSON.stringify(sa.doc.recs) === JSON.stringify(sb.doc.recs) && JSON.stringify(sa.doc.meta) === JSON.stringify(sb.doc.meta), JSON.stringify(sb.doc).slice(0, 200));
  ok('deleted record is not in the snapshot; null-data record is', !('looks' in sb.doc.recs && 'l/1 odd id' in sb.doc.recs.looks) && sb.doc.recs.worn.w1 === null);
  ok('same number of snapshots as the live code (hourly throttle unchanged)', metas(A).length === metas(B).length, metas(A).length + ' vs ' + metas(B).length); }

// ---- 2. throttle, empty account, ring trim (legacy inline + v2), orphan sweep, other accounts untouched ----
{ const B = new KV(); seed(B);
  await call(next, B, { since: 0, changes: [], meta: { updatedAt: 1, data: { only: 'meta' } } });
  let s = readSnap(B); ok('account with no records: snapshot is valid JSON with empty recs', JSON.stringify(s.doc.recs) === '{}' && s.doc.meta.only === 'meta', JSON.stringify(s.doc));
  const n0 = metas(B).length; clock += 10 * 60e3; await call(next, B, { since: 0, changes: [rec('items', 'a', clock, { v: 1 })] });
  ok('second change within the hour writes no snapshot', metas(B).length === n0);
  // 9 legacy snapshots: 8 inline, 1 legacy-chunked with 3 parts; plus orphan parts (old and fresh) and another account's keys
  // (timestamps are 13 digits, as real ones are: the ring sorts them as text, exactly like the live code)
  const T0 = 1795000000000;
  for (let i = 1; i <= 8; i++) B.m.set('snap/' + ACCT + '/' + (T0 + 1000 + i), JSON.stringify({ at: T0 + 1000 + i, inline: '{"at":1,"recs":{},"meta":null}' }));
  B.m.set('snap/' + ACCT + '/' + (T0 + 900), JSON.stringify({ at: T0 + 900, chunks: 3 })); for (let i = 0; i < 3; i++) B.m.set('snap/' + ACCT + '/' + (T0 + 900) + '/c/' + i, 'x');
  clock += 3 * 3600e3;
  for (let i = 0; i < 500; i++) B.m.set('snap/' + ACCT + '/' + (clock - 5 * 3600e3) + '/c/' + i, 'orphan');           // died 5 h ago
  for (let i = 0; i < 7; i++) B.m.set('snap/' + ACCT + '/' + (clock - 10 * 60e3) + '/c/' + i, 'in flight');            // 10 min ago: may still be writing
  B.m.set('snap/' + OTHER + '/' + (clock - 9 * 3600e3) + '/c/0', 'someone else'); B.m.set('snap/' + OTHER + '/5', JSON.stringify({ at: 5, inline: '{}' }));
  B.ops = { get: 0, put: 0, delete: 0, list: 0 };
  await call(next, B, { since: 0, changes: [rec('items', 'b', clock, { v: 2 })] });
  const mk = metas(B).map(k => k.split('/')[2]);
  ok('ring trimmed to 10 complete snapshots, oldest first', mk.length === 10 && !mk.includes(String(T0 + 900)) && mk.includes(String(T0 + 1001)), mk.join(','));
  ok('the trimmed legacy snapshot\'s parts are gone', !snapKeys(B).some(k => k.startsWith('snap/' + ACCT + '/' + (T0 + 900) + '/')));
  const orphanLeft = snapKeys(B).filter(k => B.m.get(k) === 'orphan').length, flight = snapKeys(B).filter(k => B.m.get(k) === 'in flight').length;
  ok('old orphan parts swept, bounded per run', orphanLeft > 0 && orphanLeft < 500 && B.ops.delete <= 121, 'left ' + orphanLeft + ', deletes ' + B.ops.delete);
  ok('parts of a write that may still be in flight are kept', flight === 7);
  ok('another account\'s snapshot keys are untouched', B.m.get('snap/' + OTHER + '/5') !== undefined && [...B.m.keys()].some(k => k.startsWith('snap/' + OTHER + '/') && k.endsWith('/c/0')));
  clock += 2 * 3600e3; await call(next, B, { since: 0, changes: [rec('items', 'c', clock, { v: 3 })] });
  let runs = 2; while (snapKeys(B).some(k => B.m.get(k) === 'orphan') && runs < 12) { clock += 2 * 3600e3; await call(next, B, { since: 0, changes: [rec('items', 'c', clock, { v: 3, n: runs })] }); runs++; }
  ok('later runs finish the sweep (500 orphans at up to 120 per run)', snapKeys(B).filter(k => B.m.get(k) === 'orphan').length === 0 && runs <= 6, 'runs ' + runs);
  ok('the ring still holds 10 complete snapshots after those runs', metas(B).length === 10, String(metas(B).length));
  s = readSnap(B); ok('latest snapshot holds the three items', Object.keys(s.doc.recs.items).sort().join() === 'a,b,c'); }

// ---- 3. a closet over the old limit: 320 records, about 32 MB ----
{ const B = new KV(), A = new KV(); seed(B); seed(A); const changes = [];
  for (let i = 0; i < 300; i++) changes.push(rec('items', 'item-' + String(i).padStart(4, '0'), 1000 + i, { id: 'item-' + i, name: 'Piece ' + i, photo: big(104000 + (i % 7) * 300) }));
  for (let i = 0; i < 20; i++) changes.push(rec(['looks', 'worn', 'queue', 'receipts'][i % 4], 'r' + i, 2000 + i, { t: 'small ' + i }));
  B.ops = { get: 0, put: 0, delete: 0, list: 0 }; const before = process.memoryUsage().heapUsed; clock += 2 * 3600e3;
  const r = await call(next, B, { since: 0, changes });
  ok('32 MB closet: the write returns 200', r.status === 200, r.status + ' ' + r.text.slice(0, 100));
  const s = readSnap(B); const total = snapKeys(B).filter(k => k.includes('/c/')).reduce((a, k) => a + B.m.get(k).length, 0);
  ok('32 MB closet: snapshot complete in a few large parts', s.meta.v === 2 && s.parts >= 4 && s.parts <= 8, 'parts ' + s.parts);
  ok('32 MB closet: every record is in the snapshot, byte-for-byte', Object.keys(s.doc.recs.items).length === 300 && changes.every(c => JSON.stringify(s.doc.recs[c.coll][c.id]) === JSON.stringify(c.data)));
  ok('32 MB closet: no value over the KV limit, largest part about 6 MB', B.maxPut < 8 * 1024 * 1024, 'max ' + B.maxPut);
  console.log('     snapshot ' + (total / 1e6).toFixed(1) + ' MB in ' + s.parts + ' parts; KV ops for the whole request', JSON.stringify(B.ops));
  // the live code on the same input: confirm it takes the 500-put fallback this fix removes
  A.ops = { get: 0, put: 0, delete: 0, list: 0 }; let liveErr = ''; try { await call(live, A, { since: 0, changes }); } catch (e) { liveErr = String(e).slice(0, 80); }
  const liveSnapPuts = [...A.m.keys()].filter(k => k.startsWith('snap/') && k.includes('/c/')).length;
  console.log('     live code on the same closet: snapshot written as ' + liveSnapPuts + ' small parts' + (liveErr ? ' (' + liveErr + ')' : ''));
  ok('the live code needs hundreds of small puts for the same snapshot (the failure being fixed)', liveSnapPuts > 300, String(liveSnapPuts)); }
Date.now = realNow; console.log(fails ? fails + ' FAILED' : 'ALL PASSED'); process.exit(fails ? 1 : 0);
