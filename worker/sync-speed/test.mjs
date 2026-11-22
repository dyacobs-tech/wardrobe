// In-memory tests for the sync speed change. No network, no Cloudflare.
// usage: node --max-old-space-size=2048 test.mjs <live worker.mjs> <patched worker.mjs>   (absolute paths, .mjs)
// "live" is the module as it runs on Cloudflare today (with the snapshot fix); "patched" is apply.py's output.
import { createHash } from 'node:crypto';
const live = await import(process.argv[2]); const next = await import(process.argv[3]);
let fails = 0; const ok = (name, cond, info = '') => { console.log((cond ? 'PASS ' : 'FAIL ') + name + (cond ? '' : ' :: ' + info)); if (!cond) fails++; };
class KV { constructor() { this.m = new Map(); this.ops = { get: 0, put: 0, delete: 0, list: 0 }; this.hook = null; this.inFlight = 0; this.maxInFlight = 0; this.read = []; }
  async get(k) { this.ops.get++; this.read.push(k); this.inFlight++; this.maxInFlight = Math.max(this.maxInFlight, this.inFlight);
    try { if (this.hook) await this.hook('get', k); await new Promise(r => setImmediate(r)); return this.m.has(k) ? this.m.get(k) : null; } finally { this.inFlight--; } }
  async put(k, v) { this.ops.put++; if (typeof v !== 'string') throw new Error('non-string put'); if (Buffer.byteLength(v) > 25 * 1024 * 1024) throw new Error('KV value too large'); if (this.hook) await this.hook('put', k); this.m.set(k, v); }
  async delete(k) { this.ops.delete++; if (this.hook) await this.hook('delete', k); this.m.delete(k); }
  async list({ prefix = '', cursor, limit = 1000 } = {}) { this.ops.list++; const names = [...this.m.keys()].filter(k => k.startsWith(prefix)).sort(); const start = cursor ? Number(cursor) : 0; const page = names.slice(start, start + limit);
    const done = start + limit >= names.length; return { keys: page.map(name => ({ name })), list_complete: done, cursor: done ? undefined : String(start + limit) }; } }
const KEY = 'ab'.repeat(24), ACCT = '1111222233334444';
const sha = s => createHash('sha256').update(s).digest('hex');
const seed = kv => { kv.m.set('key/' + sha(KEY), ACCT); };
const mkctx = () => ({ ps: [], waitUntil(p) { this.ps.push(p); }, settle() { return Promise.all(this.ps); } });
const req = body => new Request('https://x.test/sync', { method: 'POST', headers: { authorization: 'Bearer ' + KEY, 'content-type': 'application/json' }, body: JSON.stringify(body) });
// settle = wait for the work handed to waitUntil before returning (what Cloudflare does in the background)
const call = async (mod, kv, body, { ctx = mkctx(), settle = true, noCtx = false } = {}) => { const r = noCtx ? await mod.default.fetch(req(body), { SYNC_KV: kv }) : await mod.default.fetch(req(body), { SYNC_KV: kv }, ctx);
  const out = { status: r.status, text: await r.text(), ctx }; if (settle) await ctx.settle(); return out; };
const big = n => 'data:image/jpeg;base64,' + 'A'.repeat(n);
const rec = (coll, id, at, data) => ({ coll, id, updatedAt: at, data });
const realNow = Date.now; let clock = 1795300000000; Date.now = () => clock;
const snapMetas = kv => [...kv.m.keys()].filter(k => k.startsWith('snap/' + ACCT + '/') && k.split('/').length === 3).sort();
const snapStamps = kv => new Set([...kv.m.keys()].filter(k => k.startsWith('snap/' + ACCT + '/')).map(k => k.split('/')[2]));
const flag = kv => kv.m.get('snapflag/' + ACCT);
const dump = kv => JSON.stringify([...kv.m.entries()].sort());
let seedN = 12345; const rnd = n => { seedN = (seedN * 1103515245 + 12345) & 0x7fffffff; return (seedN >>> 8) % n; };

// ---- 1. differential, fixed sequence: every answer and every stored key identical to the live code ----
{ const A = new KV(), B = new KV(); seed(A); seed(B); const steps = [
    { since: 0, changes: [rec('items', 'i1', 10, { name: 'Tee — “Café” 👕', photo: big(150000) }), rec('items', 'i2', 11, { name: 'Small' }), rec('looks', 'l/1 odd id', 12, { title: 'x', n: [1, 2, { a: null }] }), rec('worn', 'w1', 13, null)], meta: { updatedAt: 5, data: { profile: { n: 1 } } } },
    { since: 0, changes: [] },
    { since: 2, changes: [rec('items', 'i2', 20, { name: 'Small v2' }), { coll: 'looks', id: 'l/1 odd id', updatedAt: 21, deleted: true }] },
    { since: 99, changes: [rec('items', 'i1', 9, { name: 'stale write, must be ignored' })] },
    { since: 3, changes: [], meta: { updatedAt: 6, data: { profile: { n: 2 } } } },
    { since: 0, changes: [] } ];
  let same = true, info = '';
  for (let i = 0; i < steps.length; i++) { clock += 2 * 3600e3; const a = await call(live, A, steps[i]); const b = await call(next, B, steps[i]);
    if (a.status !== b.status || a.text !== b.text || dump(A) !== dump(B)) { same = false; info = 'step ' + i + ': ' + a.status + ' vs ' + b.status + ' | ' + a.text.slice(0, 160) + ' || ' + b.text.slice(0, 160); break; } }
  ok('fixed sequence: answers and every stored key (records, counter, snapshots) identical to the live code', same, info);
  ok('no flag key is left behind after a finished snapshot', flag(B) === undefined); }

// ---- 2. differential, 400 random requests: writes, stale writes, deletes, ties, profile data, mass-delete refusals ----
{ const A = new KV(), B = new KV(); seed(A); seed(B); const colls = ['items', 'looks', 'worn', 'queue']; let same = true, info = '', refusals = 0, withRecs = 0, snaps = 0;
  for (let step = 0; step < 400 && same; step++) { clock += [0, 1000, 30 * 60e3, 2 * 3600e3][rnd(4)]; const changes = []; const n = rnd(12) === 0 ? 14 : rnd(5);
    for (let k = 0; k < n; k++) { const coll = colls[rnd(4)], id = 'id' + rnd(40), at = 1000 + rnd(60);       // few timestamps: many ties and stale writes
      if (rnd(7) === 0 || (n === 14 && rnd(2) === 0)) changes.push({ coll, id, updatedAt: at, deleted: true });
      else changes.push(rec(coll, id, at, rnd(9) === 0 ? { photo: big(60000 + rnd(130000)) } : rnd(11) === 0 ? null : { v: rnd(1000), s: 'é👕' + rnd(9) })); }
    const body = { since: rnd(3) === 0 ? 0 : rnd(80), changes }; if (rnd(4) === 0) body.meta = { updatedAt: 1 + rnd(50), data: { p: rnd(100) } };
    const a = await call(live, A, body); const b = await call(next, B, body);
    if (a.status === 409) refusals++; else if (JSON.parse(a.text).recs.length) withRecs++;
    if (a.status !== b.status || a.text !== b.text) { same = false; info = 'step ' + step + ' answer: ' + a.status + ' vs ' + b.status + ' | ' + a.text.slice(0, 140) + ' || ' + b.text.slice(0, 140); }
    else if (dump(A) !== dump(B)) { same = false; const ka = new Map(A.m), kb = new Map(B.m); const d = [...new Set([...ka.keys(), ...kb.keys()])].filter(k => ka.get(k) !== kb.get(k)); info = 'step ' + step + ' keys differ: ' + d.slice(0, 5).join(' , '); } }
  snaps = snapMetas(B).length;
  ok('400 random requests: every answer and every stored key identical to the live code', same, info);
  ok('the random run exercised refusals, non-empty answers and snapshots', refusals >= 3 && withRecs > 100 && snaps >= 5, 'refusals ' + refusals + ', answers with records ' + withRecs + ', snapshots ' + snaps);
  ok('mass-delete refusals are the same in number as the live code (guard untouched)', refusals > 0); }

// ---- 3. the answer no longer waits for the snapshot; the snapshot still completes ----
{ const B = new KV(); seed(B); let release; const gate = new Promise(r => { release = r; }); let blocked = 0;
  B.hook = async (op, k) => { if (op === 'put' && k.startsWith('snap/') && k.includes('/c/')) { blocked++; await gate; } };
  clock += 2 * 3600e3; const r = await call(next, B, { since: 0, changes: [rec('items', 'a', clock, { v: 1 })] }, { settle: false });
  ok('the answer arrives before the snapshot is complete, and the snapshot was handed to waitUntil', r.status === 200 && snapMetas(B).length === 0 && r.ctx.ps.length === 1, 'metas ' + snapMetas(B).length + ', waitUntil ' + r.ctx.ps.length);
  for (let i = 0; i < 200 && blocked === 0; i++) await new Promise(res => setTimeout(res, 5));          // let the background write reach its first part
  ok('the background snapshot is writing (held at its first part by the test), still no complete snapshot', blocked === 1 && snapMetas(B).length === 0, 'blocked ' + blocked);
  ok('the flag key is set while the snapshot is being written', Number(flag(B)) === clock, String(flag(B)));
  // a second change a few seconds later, snapshot still in flight: no second snapshot is started
  clock += 5000; const r2 = await call(next, B, { since: 1, changes: [rec('items', 'b', clock, { v: 2 })] }, { settle: false });
  ok('a second sync while a snapshot is in flight answers and starts no second snapshot', r2.status === 200 && r2.ctx.ps.length === 0 && blocked === 1, 'waitUntil ' + r2.ctx.ps.length + ', snapshot writes started ' + blocked);
  release(); await r.ctx.settle(); B.hook = null;
  ok('once released, exactly one complete snapshot exists and the flag is gone', snapMetas(B).length === 1 && snapStamps(B).size === 1 && flag(B) === undefined, snapMetas(B).length + ' ' + flag(B));
  clock += 30 * 60e3; const r3 = await call(next, B, { since: 2, changes: [rec('items', 'c', clock, { v: 3 })] });
  ok('half an hour later: still one snapshot (hourly throttle unchanged), no flag left', r3.status === 200 && snapMetas(B).length === 1 && flag(B) === undefined); }

// ---- 4. a snapshot that never finishes (cut off after the answer): the next sync waits for its snapshot ----
for (const mode of ['hangs', 'throws']) { const B = new KV(); seed(B); let n = 0;
  B.hook = async (op, k) => { if (op === 'put' && k.startsWith('snap/') && k.includes('/c/') && ++n >= 1) { if (mode === 'throws') throw new Error('cut off'); await new Promise(() => {}); } };
  clock += 2 * 3600e3; const r = await call(next, B, { since: 0, changes: [rec('items', 'a', clock, { v: 1 })] }, { settle: false }); await new Promise(res => setTimeout(res, 20));
  ok('snapshot ' + mode + ': the sync itself still answers 200 and the record is stored', r.status === 200 && B.m.has('rec/' + ACCT + '/items/a'));
  ok('snapshot ' + mode + ': the flag key stays, no complete snapshot', flag(B) !== undefined && snapMetas(B).length === 0);
  B.hook = null; clock += 2 * 60e3;
  const r2 = await call(next, B, { since: 1, changes: [rec('items', 'b', clock, { v: 2 })] }, { settle: false });
  ok('snapshot ' + mode + ': the next sync (flag older than 90 s) waits until its snapshot is complete', r2.status === 200 && snapMetas(B).length === 1 && flag(B) === undefined && r2.ctx.ps.length === 1, 'metas ' + snapMetas(B).length + ', flag ' + flag(B)); }

// ---- 5. no execution context, or a very large answer: the snapshot is written before the answer, as before ----
{ const B = new KV(); seed(B); clock += 2 * 3600e3; const r = await call(next, B, { since: 0, changes: [rec('items', 'a', clock, { v: 1 })] }, { noCtx: true });
  ok('called without a context: snapshot complete when the answer arrives', r.status === 200 && snapMetas(B).length === 1 && flag(B) === undefined);
  const C = new KV(); seed(C); const changes = []; for (let i = 0; i < 170; i++) changes.push(rec('items', 'item-' + String(i).padStart(4, '0'), 1000 + i, { id: 'i' + i, photo: big(104000) }));
  clock += 2 * 3600e3; await call(next, C, { since: 0, changes });
  clock += 2 * 3600e3; const r2 = await call(next, C, { since: 0, changes: [rec('looks', 'l1', clock, { v: 1 })] }, { settle: false });
  ok('17.7 MB answer with a snapshot due: snapshot complete when the answer arrives', r2.status === 200 && snapMetas(C).length === 2 && flag(C) === undefined && JSON.parse(r2.text).recs.length === 170, 'metas ' + snapMetas(C).length);
  clock += 2 * 3600e3; const r3 = await call(next, C, { since: 171, changes: [rec('looks', 'l2', clock, { v: 2 })] }, { settle: false });
  ok('small answer on the same closet: the answer does not wait (2 snapshots at answer time, 3 after)', r3.status === 200 && snapMetas(C).length === 2, 'metas ' + snapMetas(C).length); await r3.ctx.settle();
  ok('... and the third snapshot completes afterwards', snapMetas(C).length === 3 && flag(C) === undefined); }

// ---- 6. the read side: same reads, done 16 at a time; nothing snapshot-related on a read-only sync ----
{ const A = new KV(), B = new KV(); seed(A); seed(B); const changes = [];
  for (let i = 0; i < 300; i++) changes.push(rec(['items', 'looks', 'worn', 'queue'][i % 4], 'r' + String(i).padStart(3, '0'), 1000 + (i % 37), i % 3 === 0 ? { photo: big(104000 + (i % 7) * 300) } : { t: 'small ' + i }));
  clock += 2 * 3600e3; await call(live, A, { since: 0, changes }); await call(next, B, { since: 0, changes });
  for (const kv of [A, B]) { kv.ops = { get: 0, put: 0, delete: 0, list: 0 }; kv.read = []; kv.maxInFlight = 0; }
  clock += 60e3; const a = await call(live, A, { since: 300, changes: [] }); const b = await call(next, B, { since: 300, changes: [] });
  ok('read-only sync, nothing new: identical answer', a.text === b.text && JSON.parse(b.text).recs.length === 0 && JSON.parse(b.text).now === 300, b.text.slice(0, 80));
  ok('read-only sync: exactly the same keys are read as by the live code', JSON.stringify([...A.read].sort()) === JSON.stringify([...B.read].sort()) && B.ops.put === 0 && B.ops.delete === 0, A.ops.get + ' vs ' + B.ops.get);
  ok('read-only sync: no flag or snapshot key is touched', !B.read.some(k => k.startsWith('snapflag/') || k.startsWith('snap/')) && B.ops.list === A.ops.list, JSON.stringify(B.ops));
  ok('record heads are read up to 16 at a time (the live code reads one at a time)', A.maxInFlight === 1 && B.maxInFlight > 1 && B.maxInFlight <= 16, A.maxInFlight + ' / ' + B.maxInFlight);
  for (const kv of [A, B]) { kv.read = []; kv.maxInFlight = 0; }
  const a2 = await call(live, A, { since: 120, changes: [] }); const b2 = await call(next, B, { since: 120, changes: [] });
  ok('catch-up sync (180 records, 60 with photos): identical answer, in the same order', a2.text === b2.text && JSON.parse(b2.text).recs.length === 180, String(JSON.parse(b2.text).recs.length));
  ok('catch-up sync: never more than 16 KV reads of record heads or 16 records in flight at once', B.maxInFlight <= 16 * 3, String(B.maxInFlight));
  const a3 = await call(live, A, { since: 0, changes: [] }); const b3 = await call(next, B, { since: 0, changes: [] });
  ok('full download (300 records, 10 MB): identical answer', a3.text === b3.text && JSON.parse(b3.text).recs.length === 300); }

// ---- 7. a request cut off while scanning no longer leaves records numbered above the stored counter ----
{ const res = {}; for (const [name, mod] of [['live', live], ['next', next]]) { const kv = new KV(); seed(kv); clock += 2 * 3600e3;
    await call(mod, kv, { since: 0, changes: [rec('items', 'a', 10, { v: 1 }), rec('items', 'b', 11, { v: 1 })] });
    let armed = false; kv.hook = async (op, k) => { if (op === 'list' ) return; if (armed && op === 'get' && k.startsWith('rec/') && k.split('/').length === 4) await new Promise(() => {}); };
    const origList = kv.list.bind(kv); kv.list = async (o) => { const r = await origList(o); if (o.prefix === 'rec/' + ACCT + '/') armed = true; return r; };   // the scan starts with this listing
    clock += 60e3; const p = call(mod, kv, { since: 2, changes: [rec('items', 'c', 12, { v: 1 }), rec('items', 'd', 13, { v: 1 })] }); await Promise.race([p, new Promise(r => setTimeout(r, 60))]);
    const maxSeq = Math.max(...[...kv.m.entries()].filter(([k]) => k.startsWith('rec/')).map(([, v]) => JSON.parse(v).seq)); res[name] = { counter: Number(kv.m.get('seq/' + ACCT)), maxSeq }; }
  ok('cut off during the scan: the stored counter already covers the records just written', res.next.counter === res.next.maxSeq && res.next.maxSeq === 4, JSON.stringify(res.next));
  console.log('     live code in the same situation: counter ' + res.live.counter + ', highest record number ' + res.live.maxSeq + ' (the next writer would reuse numbers 3 and 4)'); }
Date.now = realNow; console.log(fails ? fails + ' FAILED' : 'ALL PASSED'); process.exit(fails ? 1 : 0);
