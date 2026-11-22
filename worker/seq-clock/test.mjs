// Simulation tests for the record-numbering change. No network, no Cloudflare.
// usage: node --max-old-space-size=2048 test.mjs <live worker.mjs> <patched worker.mjs>   (absolute paths, .mjs)
// "live" is the module as it runs on Cloudflare today; "patched" is apply.py's output.
//
// The KV here behaves like the real one in the way that matters: each location ("colo") caches what it
// read for 60 s, and a write made in one location is not visible in another until a delay has passed.
// Time is virtual: every KV operation takes 15 ms, and the test moves the clock between requests.
import { createHash } from 'node:crypto';
const live = await import(process.argv[2]); const next = await import(process.argv[3]);
let fails = 0; const ok = (name, cond, info = '') => { console.log((cond ? 'PASS ' : 'FAIL ') + name + (cond ? '' : ' :: ' + info)); if (!cond) fails++; };
let T = 1795330000000; const realNow = Date.now; Date.now = () => T;
const CACHE_TTL = 60e3; let LAG_MAX = 20e3;
let seedN = 7; const rnd = n => { seedN = (seedN * 1103515245 + 12345) & 0x7fffffff; return (seedN >>> 8) % n; };
const tick = async () => { T += 15; await new Promise(r => setImmediate(r)); };
class Central { constructor() { this.h = new Map(); }
  write(k, v, colo) { if (!this.h.has(k)) this.h.set(k, []); this.h.get(k).push({ v, colo, vis: T + (LAG_MAX ? rnd(LAG_MAX) : 0) }); }
  read(k, colo) { const a = this.h.get(k); if (!a) return null; for (let i = a.length - 1; i >= 0; i--) { const e = a[i]; if (e.colo === colo || T >= e.vis) return e.v === undefined ? null : e.v; } return null; }
  keys(prefix, colo) { const out = []; for (const k of this.h.keys()) if (k.startsWith(prefix) && this.read(k, colo) !== null) out.push(k); return out.sort(); }
  latest(k) { const a = this.h.get(k); if (!a) return null; const e = a[a.length - 1]; return e.v === undefined ? null : e.v; } }
class ColoKV { constructor(central, name) { this.c = central; this.name = name; this.cache = new Map(); this.ops = 0; }
  async get(k) { await tick(); this.ops++; const c = this.cache.get(k); if (c && T - c.t < CACHE_TTL) return c.v; const v = this.c.read(k, this.name); this.cache.set(k, { t: T, v }); return v; }
  async put(k, v) { await tick(); this.ops++; if (typeof v !== 'string') throw new Error('non-string put'); this.c.write(k, v, this.name); this.cache.set(k, { t: T, v }); }
  async delete(k) { await tick(); this.ops++; this.c.write(k, undefined, this.name); this.cache.set(k, { t: T, v: null }); }
  async list({ prefix = '', cursor, limit = 1000 } = {}) { await tick(); this.ops++; const names = this.c.keys(prefix, this.name); const start = cursor ? Number(cursor) : 0; const page = names.slice(start, start + limit);
    const done = start + limit >= names.length; return { keys: page.map(name => ({ name })), list_complete: done, cursor: done ? undefined : String(start + limit) }; } }
const KEY = 'ab'.repeat(24), ACCT = '1111222233334444'; const sha = s => createHash('sha256').update(s).digest('hex');
const world = () => { const c = new Central(); c.h.set('key/' + sha(KEY), [{ v: ACCT, colo: '-', vis: 0 }]); c.h.set('acct/' + ACCT, [{ v: JSON.stringify({ created: 1 }), colo: '-', vis: 0 }]); return c; };
const mkctx = () => ({ ps: [], waitUntil(p) { this.ps.push(p); }, settle() { return Promise.all(this.ps); } });
const post = (mod, kv, body, path = '/sync', extra = {}) => mod.default.fetch(new Request('https://x.test' + path, { method: 'POST', headers: Object.assign({ authorization: 'Bearer ' + KEY, 'content-type': 'application/json' }, extra.headers || {}), body: JSON.stringify(body) }), Object.assign({ SYNC_KV: kv }, extra.env || {}), extra.ctx || mkctx());
// A device, applying downloads the way the app does: a record replaces the local one only if its updatedAt is newer.
class Device { constructor(name, central) { this.name = name; this.kv = new ColoKV(central, name); this.since = 0; this.st = new Map(); this.dirty = new Set(); this.got = new Map(); this.syncs = 0; }
  edit(id, data) { this.st.set(id, { updatedAt: T, data }); this.dirty.add(id); }
  async sync(mod) { const changes = [...this.dirty].map(id => ({ coll: 'items', id, updatedAt: this.st.get(id).updatedAt, data: this.st.get(id).data })); const sent = new Map(changes.map(c => [c.id, c.updatedAt])); const ctx = mkctx();
    const r = await post(mod, this.kv, { since: this.since, changes }, '/sync', { ctx }); const j = await r.json(); if (r.status !== 200) throw new Error('sync ' + r.status + ' ' + JSON.stringify(j).slice(0, 80));
    for (const [id, u] of sent) if (this.st.get(id).updatedAt === u) this.dirty.delete(id);
    for (const x of j.recs) { this.got.set(x.id + '@' + x.updatedAt, (this.got.get(x.id + '@' + x.updatedAt) || 0) + 1); const loc = this.st.get(x.id); if (!loc || x.updatedAt > loc.updatedAt) this.st.set(x.id, { updatedAt: x.updatedAt, data: x.data }); }
    this.since = j.now; this.syncs++; await ctx.settle(); return j; } }
const truthOf = devs => { const t = new Map(); for (const d of devs) for (const [id, r] of d.st) { const c = t.get(id); if (!c || r.updatedAt > c.updatedAt) t.set(id, r); } return t; };
const missing = devs => { const t = truthOf(devs); let n = 0; for (const d of devs) for (const [id, r] of t) { const l = d.st.get(id); if (!l || l.updatedAt !== r.updatedAt) n++; } return n; };

// ---- 1. the collision seen on 22 Nov: a phone saves, then a script elsewhere saves 28 s later with a stale counter ----
const collide = async (mod) => { T += 3600e3; const c = world(); const phone = new Device('MIA', c), script = new Device('IAD', c);
  script.edit('base', { v: 0 }); await script.sync(mod); T += 400e3; await phone.sync(mod); T += 400e3; await script.sync(mod);       // both up to date
  T += 600e3; await script.sync(mod);                       // the script reads the counter (now cached at its location for 60 s)
  T += 20e3; phone.edit('ask', { q: 'Hi' }); await phone.sync(mod);                                                              // the phone saves a record
  T += 28e3; script.edit('trousers', { photo: 'new' }); await script.sync(mod);                                                    // 28 s later the script saves, counter read from its cache
  T += 3600e3; await phone.sync(mod); T += 3600e3; await phone.sync(mod);                                                          // the phone syncs again, twice, an hour apart
  const hs = ['ask', 'trousers'].map(id => JSON.parse(c.latest('rec/' + ACCT + '/items/' + id)).seq); return { phoneHas: phone.st.has('trousers'), seqs: hs }; };
{ const a = await collide(live), b = await collide(next);
  console.log('     live code: the two records got numbers ' + a.seqs.join(' and ') + '; the phone ' + (a.phoneHas ? 'received' : 'NEVER received') + ' the script\'s record');
  ok('the 22 Nov collision reproduces on the live code (same number twice, record never delivered)', a.seqs[0] === a.seqs[1] && !a.phoneHas, JSON.stringify(a));
  ok('with the change, the phone receives the record and the two numbers differ', b.phoneHas && b.seqs[0] !== b.seqs[1], JSON.stringify(b)); }

// ---- 2. three devices in three places, 2 simulated hours of edits and syncs, some at the same moment ----
const simulate = async (mod, seed, lagMax, o = {}) => { seedN = seed; LAG_MAX = lagMax; const stepMax = o.stepMax || 45e3; T += 7200e3; const c = world(); const devs = ['MIA', 'IAD', 'EWR'].map(n => new Device(n, c)); let n = 0, errors = 0;
  for (let step = 0; step < 260; step++) { T += rnd(stepMax); const d = devs[rnd(3)]; const a = rnd(20);
    try { if (a < 9) d.edit((o.own ? d.name + '-' : '') + 'r' + rnd(25), { v: ++n, by: d.name });
      else if (a < 18) await d.sync(mod);
      else { const e = devs[(devs.indexOf(d) + 1 + rnd(2)) % 3]; await Promise.all([d.sync(mod), e.sync(mod)]); } } catch (e) { errors++; } }
  for (let k = 0; k < 3; k++) { T += 400e3; for (const d of devs) await d.sync(mod); }                    // everything settles: three more rounds, minutes apart
  let maxRepeat = 0, total = 0, distinct = 0; for (const d of devs) for (const v of d.got.values()) { maxRepeat = Math.max(maxRepeat, v); total += v; distinct++; }
  return { missing: missing(devs), errors, maxRepeat, repeatRatio: total / Math.max(1, distinct), ops: devs.reduce((s, d) => s + d.kv.ops, 0) }; };
{ let liveMiss = 0, nextMiss = 0, liveRuns = 0, worstRepeat = 0, ratio = 0, errs = 0; const seeds = [11, 23, 37, 41, 59, 67, 73, 89, 97, 101, 113, 127];
  for (const s of seeds) { const a = await simulate(live, s, 20e3); if (a.missing) liveRuns++; liveMiss += a.missing; const b = await simulate(next, s, 20e3); nextMiss += b.missing; worstRepeat = Math.max(worstRepeat, b.maxRepeat); ratio = Math.max(ratio, b.repeatRatio); errs += b.errors; }
  console.log('     live code over ' + seeds.length + ' runs: ' + liveMiss + ' device/record pairs left out of date, in ' + liveRuns + ' of the runs');
  ok('live code loses records when devices save close together (the fault being fixed)', liveMiss > 0, String(liveMiss));
  ok('with the change, every device ends with every record at its latest version, in all ' + seeds.length + ' runs', nextMiss === 0 && errs === 0, 'out of date ' + nextMiss + ', errors ' + errs);
  console.log('     with the change, devices syncing every 20 s or so: a record version is delivered ' + ratio.toFixed(2) + ' times on average in the worst run (most ' + worstRepeat + ')');
  // at a calmer pace (a sync every few minutes) the repeats nearly vanish
  let calmRatio = 0, calmWorst = 0, calmMiss = 0; for (const s of [3, 19, 31]) { const r = await simulate(next, s, 20e3, { stepMax: 600e3 }); calmRatio = Math.max(calmRatio, r.repeatRatio); calmWorst = Math.max(calmWorst, r.maxRepeat); calmMiss += r.missing; }
  ok('at a calmer pace (minutes between syncs): nothing lost, and a record version arrives about 1.5 times on average or less', calmMiss === 0 && calmWorst <= 5 && calmRatio <= 1.6, 'missing ' + calmMiss + ', worst ' + calmWorst + ', average ' + calmRatio.toFixed(2));
  console.log('     calmer pace: ' + calmRatio.toFixed(2) + ' deliveries per record version on average (most ' + calmWorst + ')');
  // slower spreading than Cloudflare documents: writes take up to 100 s to show elsewhere, on top of the 60 s cache.
  // Devices edit their own records here: two devices rewriting the SAME record inside that window is a separate,
  // older weakness (the later arrival wins on the server), which this change does not touch.
  let slowMiss = 0; for (const s of [5, 17, 29, 43]) slowMiss += (await simulate(next, s, 100e3, { own: true })).missing;
  ok('still nothing lost when writes take up to 100 s to show in other places', slowMiss === 0, String(slowMiss)); LAG_MAX = 20e3; }

// ---- 3. a device holding an old-style bookmark (a small number) moves over cleanly; the app's paged loop stops ----
{ LAG_MAX = 0; T += 7200e3; const c = world(); const w = new Device('IAD', c);
  for (let i = 0; i < 300; i++) w.edit('p' + String(i).padStart(3, '0'), { n: i, photo: 'x'.repeat(200) });
  await w.sync(live); const legacyNow = w.since; T += 3600e3;                                         // 300 records written by the live code: numbers 1..300
  const phone = new Device('MIA', c); phone.since = 120;                                             // a phone that had synced up to number 120 under the live code
  const j = await phone.sync(next);
  ok('old-style bookmark 120: exactly the 180 newer records arrive', j.recs.length === 180 && legacyNow === 300, j.recs.length + ' / ' + legacyNow);
  ok('the new bookmark is a clock time, three to four minutes behind now, on a whole minute', j.now % 60e3 === 0 && T - j.now >= 180e3 && T - j.now < 242e3, String(T - j.now));
  T += 30e3; const j2 = await phone.sync(next); ok('30 s later with nothing new: nothing is sent, the bookmark holds or moves on', j2.recs.length === 0 && j2.now >= j.now, j2.recs.length + '');
  // the app's download loop: pages of "limit 200" (the server ignores the limit), stop on 0 records, an unchanged bookmark, or fewer than 200
  T += 3600e3; for (let i = 0; i < 300; i++) w.edit('q' + String(i).padStart(3, '0'), { n: i }); await w.sync(next);                // 300 fresh records, seconds old
  T += 20e3; const fresh = new Device('EWR', c); let pages = 0, since = 0, recsSeen = 0;
  while (pages < 80) { pages++; const r = await post(next, fresh.kv, { since, changes: [], meta: null, limit: 200 }); const jj = await r.json(); recsSeen += jj.recs.length; const prev = since; since = jj.now; if (jj.recs.length === 0) break; if (jj.now === prev) break; if (jj.recs.length < 200) break; }
  ok('a new device right after a 300-record upload: the paged download stops after at most 3 pages', pages <= 3 && recsSeen >= 600, 'pages ' + pages + ', records ' + recsSeen);
  console.log('     pages ' + pages + ', records downloaded ' + recsSeen + ' (600 distinct records exist; the 300 fresh ones repeat once per page while they are within the margin)'); }

// ---- 4. going back to the previous version stays safe: its numbers start above every bookmark handed out ----
{ LAG_MAX = 0; T += 7200e3; const c = world(); const a = new Device('IAD', c), b = new Device('MIA', c);
  a.edit('x1', { v: 1 }); await a.sync(next); T += 900e3; await b.sync(next); T += 900e3; await b.sync(next); const mark = b.since;     // b holds a clock bookmark
  const stored = Number(c.latest('seq/' + ACCT)); ok('the stored counter is at or above every bookmark handed out', stored >= mark, stored + ' vs ' + mark);
  T += 900e3; a.edit('x2', { v: 2 }); await a.sync(live);                                                // rolled back: the previous version writes a record
  const seq = JSON.parse(c.latest('rec/' + ACCT + '/items/x2')).seq; T += 900e3; await b.sync(live);
  ok('after a roll-back, the previous version numbers its record above that bookmark and the other device receives it', seq > mark && b.st.has('x2'), seq + ' vs ' + mark); }

// ---- 5. everything else is unchanged: one device, requests minutes apart, compared with the live code ----
// The new code may send a record again (the device's own last upload comes back once); so the comparison is on what
// the device HOLDS after applying each answer the way the app does, plus: nothing the live code sent is missing.
{ LAG_MAX = 0; seedN = 4242; const cA = world(), cB = world(); const A = new ColoKV(cA, 'IAD'), B = new ColoKV(cB, 'IAD'); let same = true, info = '', refusals = 0, withRecs = 0, extra = 0; const t0 = T + 7200e3;
  const colls = ['items', 'looks', 'worn', 'queue']; let sinceA = 0, sinceB = 0; const holdA = new Map(), holdB = new Map(); let metaA = null, metaB = null;
  const apply = (hold, j) => { for (const x of j.recs) { const k = x.coll + '/' + x.id; const loc = hold.get(k); if (!loc || x.updatedAt > loc.updatedAt) hold.set(k, x); } };
  const applyMeta = (cur, m) => (m && (!cur || m.updatedAt > cur.updatedAt)) ? m : cur;
  const strip = c => JSON.stringify([...c.h.keys()].sort().filter(k => !k.startsWith('seq/') && !k.startsWith('snap/')).map(k => { let v = c.latest(k); if (v && ((k.startsWith('rec/') && k.split('/').length === 4) || (k.startsWith('meta/') && k.split('/').length === 2))) { try { const o = JSON.parse(v); delete o.seq; v = JSON.stringify(o); } catch (e) {} } return [k, v]; }));
  for (let step = 0; step < 220 && same; step++) { const dt = 400e3 + rnd(3600e3); const changes = []; const n = rnd(12) === 0 ? 14 : rnd(5);
    for (let k = 0; k < n; k++) { const coll = colls[rnd(4)], id = 'id' + rnd(40), at = 1000 + rnd(60);
      if (rnd(7) === 0 || (n === 14 && rnd(2) === 0)) changes.push({ coll, id, updatedAt: at, deleted: true }); else changes.push({ coll, id, updatedAt: at, data: rnd(11) === 0 ? null : { v: rnd(1000), s: 'é👕' + rnd(9) } }); }
    const full = rnd(5) === 0; const bodyA = { since: full ? 0 : sinceA, changes }, bodyB = { since: full ? 0 : sinceB, changes }; if (rnd(4) === 0) bodyA.meta = bodyB.meta = { updatedAt: 1 + rnd(50), data: { p: rnd(100) } };
    // the device already holds what it is about to upload (its own edits), as the app does
    for (const hold of [holdA, holdB]) for (const ch of changes) { const k = ch.coll + '/' + ch.id; const loc = hold.get(k); if (!loc || ch.updatedAt > loc.updatedAt) hold.set(k, ch.deleted ? { coll: ch.coll, id: ch.id, updatedAt: ch.updatedAt, deleted: true } : { coll: ch.coll, id: ch.id, updatedAt: ch.updatedAt, data: ch.data }); }
    if (bodyA.meta) { metaA = applyMeta(metaA, bodyA.meta); metaB = applyMeta(metaB, bodyB.meta); }
    T = t0 + step * 4000e3 + dt; const ca = mkctx(); const ra = await post(live, A, bodyA, '/sync', { ctx: ca }); const ja = await ra.json(); await ca.settle();
    T = t0 + step * 4000e3 + dt; const cb = mkctx(); const rb = await post(next, B, bodyB, '/sync', { ctx: cb }); const jb = await rb.json(); await cb.settle();
    if (ra.status !== rb.status || JSON.stringify(ja.error) !== JSON.stringify(jb.error)) { same = false; info = 'step ' + step + ': status ' + ra.status + '/' + rb.status; break; }
    if (ra.status === 409) { refusals++; continue; }
    if (ja.recs.length) withRecs++; if (!full) { sinceA = ja.now; sinceB = jb.now; }
    const sent = new Set(jb.recs.map(x => x.coll + '/' + x.id + '@' + x.updatedAt + (x.deleted ? 'x' : ''))); const lost = ja.recs.filter(x => !sent.has(x.coll + '/' + x.id + '@' + x.updatedAt + (x.deleted ? 'x' : '')));
    extra += jb.recs.length - ja.recs.length; apply(holdA, ja); apply(holdB, jb); metaA = applyMeta(metaA, ja.meta); metaB = applyMeta(metaB, jb.meta);
    if (lost.length) { same = false; info = 'step ' + step + ': the new code did not send ' + lost.length + ' record(s) the live code sent'; }
    else if (JSON.stringify([...holdA.entries()].sort()) !== JSON.stringify([...holdB.entries()].sort()) || JSON.stringify(metaA) !== JSON.stringify(metaB)) { same = false; info = 'step ' + step + ': the device would hold different data'; }
    else if (strip(cA) !== strip(cB)) { same = false; info = 'step ' + step + ': stored keys differ'; } }
  ok('220 requests minutes apart: the device holds the same data as with the live code after every answer, nothing the live code sent is missing, same refusals, same stored data apart from the numbers', same, info);
  ok('that run exercised non-empty answers (and mass-delete refusals, where this build refuses rather than cancels)', withRecs > 60, refusals + ' / ' + withRecs);
  console.log('     mass-delete refusals in the run: ' + refusals + ' (identical in both versions, step by step)');
  console.log('     records sent again by the new code over the run (a device\'s own last upload coming back once): ' + extra);
  const snaps = c => [...c.h.keys()].filter(k => k.startsWith('snap/') && k.split('/').length === 3 && c.latest(k) !== null).length;
  ok('same number of safety snapshots as the live code', snaps(cA) === snaps(cB) && snaps(cB) >= 5, snaps(cA) + ' vs ' + snaps(cB)); }

// ---- 6. the two server-fed lists (receipt inbox, price drops) take clock numbers too, and the app receives them ----
{ LAG_MAX = 0; T += 7200e3; const c = world(); const d = new Device('MIA', c); d.edit('a', { v: 1 }); await d.sync(next); T += 900e3; await d.sync(next); const mark = d.since;
  const src = (await import('node:fs')).readFileSync(process.argv[3], 'utf8'); ok('no counter-style numbering is left in the patched file', !src.includes('++seqCounter') && src.split('nextSeq(seqCounter)').length === 4);
  T += 900e3; const env = { RENDER_WATCHER_SECRET: 'w'.repeat(32) }; const hdr = { 'x-watcher-secret': 'w'.repeat(32) };
  const r = await post(next, new ColoKV(c, 'IAD'), { acct: ACCT, items: [{ id: 'rc1', name: 'Test shirt', brand: 'X', retailer: 'X', price: 10, currency: 'USD', orderNo: 'A1', orderDate: '2026-11-22', category: '', colourName: 'Blue', colourHex: '#112233', img: '', src: 'email' }] }, '/receipt-inbox', { env, headers: hdr });
  const body = await r.text();
  if (r.status === 200) { const keys = [...c.h.keys()].filter(k => k.startsWith('rec/' + ACCT + '/') && k.endsWith('/rc1')); const seq = keys.length ? JSON.parse(c.latest(keys[0])).seq : 0;
    ok('a receipt pushed by the server gets a clock number above the device\'s bookmark', seq > mark && Math.abs(seq - T) < 60e3, seq + ' vs ' + mark); }
  else ok('the receipt inbox accepts the test receipt', false, r.status + ' ' + body.slice(0, 100));
  T += 60e3; const j = await d.sync(next); ok('... and the device receives that receipt on its next sync', j.recs.some(x => x.coll === 'receipts' && x.id === 'rc1'), JSON.stringify(j.recs.map(x => x.coll + '/' + x.id))); }
Date.now = realNow; console.log(fails ? fails + ' FAILED' : 'ALL PASSED'); process.exit(fails ? 1 : 0);
