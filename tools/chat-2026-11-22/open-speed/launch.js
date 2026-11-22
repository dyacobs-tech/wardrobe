// Record what the screen does when the app is opened with David's data already on the device.
// Sync goes to the REAL server read-only (uploads held back), like phonesim/real.js. Usage: node launch.js <url> <label>   env SW=1 to allow the service worker.
const { chromium } = require('playwright'); const fs = require('fs'); const { execFileSync } = require('child_process');
const S = '/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'; const URL0 = process.argv[2]; const LABEL = process.argv[3] || 'run'; const OUT = S + '/flick/' + LABEL; fs.mkdirSync(OUT, { recursive: true });
const TRACE = () => { const T = (window.__T = []); const t0 = performance.now(); const tag = (e) => { try { return (e.id ? '#' + e.id : '') + (e.className && typeof e.className === 'string' ? '.' + e.className.split(/\s+/).slice(0, 2).join('.') : '') || e.tagName; } catch (x) { return '?'; } };
  const d = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML'); Object.defineProperty(Element.prototype, 'innerHTML', { get: d.get, set: function (v) { const n = String(v == null ? '' : v).length; if (n > 1500) { let st = ''; try { st = (new Error().stack || '').split('\n').slice(2, 6).map(s => (s.match(/at ([^\s(]+)/) || [,'?'])[1]).join('<'); } catch (x) {} T.push({ t: Math.round(performance.now() - t0), k: 'html', el: tag(this), n: n, by: st }); } return d.set.call(this, v); }, configurable: true });
  try { new PerformanceObserver(l => l.getEntries().forEach(e => { if (!e.hadRecentInput) T.push({ t: Math.round(e.startTime), k: 'shift', v: +e.value.toFixed(4) }); })).observe({ type: 'layout-shift', buffered: true }); } catch (x) {}
  try { new PerformanceObserver(l => l.getEntries().forEach(e => T.push({ t: Math.round(e.startTime), k: 'long', ms: Math.round(e.duration) }))).observe({ type: 'longtask', buffered: true }); } catch (x) {}
  window.addEventListener('beforeunload', () => { try { sessionStorage.setItem('__unload', String(Date.now())); } catch (x) {} }); };
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 1, serviceWorkers: process.env.SW === '1' ? 'allow' : 'block', hasTouch: true, isMobile: true }); const syncLog = [];
  await ctx.route(/workers\.dev|fashn|cloudflare/, async (route) => { const r = route.request();
    if (/\/sync$/.test(r.url()) && r.method() === 'POST') { let body = {}; try { body = JSON.parse(r.postData() || '{}'); } catch (e) {}
      const f = S + '/flick/fwd-' + LABEL + '.json'; fs.writeFileSync(f, JSON.stringify({ since: body.since || 0, changes: [], meta: null })); const t0 = Date.now(); let out = '';
      try { out = execFileSync('curl', ['-s', '-m', '200', '-X', 'POST', 'https://wardrobe-sync.dyacobs.workers.dev/sync', '-H', 'content-type: application/json', '--data-binary', '@' + f], { maxBuffer: 256 * 1024 * 1024 }).toString(); } catch (e) { out = ''; }
      let j = null; try { j = JSON.parse(out); } catch (e) {}
      syncLog.push({ since: body.since, held: (body.changes || []).length, recs: j ? j.recs.length : null, ids: j ? j.recs.slice(0, 8).map(x => x.coll + ':' + x.id) : null, ms: Date.now() - t0 });
      return route.fulfill({ status: j ? 200 : 502, contentType: 'application/json', body: out || '{}' }); }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }); });
  await ctx.route(/open-meteo/, r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ current: { temperature_2m: 80, apparent_temperature: 83, weather_code: 1, is_day: 1 }, daily: { time: [], temperature_2m_max: [], temperature_2m_min: [], weather_code: [] } }) }));
  await ctx.addInitScript(() => { if (!localStorage.getItem('wardrobe.sync')) localStorage.setItem('wardrobe.sync', JSON.stringify({ key: 'audit-placeholder', acct: 'SYNC_ACCOUNT_ID', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'Not synced yet' })); });
  await ctx.addInitScript(TRACE);
  const st = (p) => p.evaluate(() => { try { const a = JSON.parse(localStorage.getItem('wardrobe.items') || '[]'); const sy = JSON.parse(localStorage.getItem('wardrobe.sync') || '{}'); return { items: a.length, status: sy.status, last: sy.last }; } catch (e) { return { items: -1 }; } });
  // first run: fill the device
  const p1 = await ctx.newPage(); await p1.goto(URL0, { waitUntil: 'load' }); for (let i = 0; i < 150; i++) { const s = await st(p1); if (s.items >= 172 && /Synced/.test(s.status || '')) break; await p1.waitForTimeout(1000); } await p1.waitForTimeout(8000); const filled = await st(p1); await p1.close();
  const res = { filled, opens: [] };
  for (let n = 1; n <= 2; n++) { const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 160))); const navs = []; p.on('framenavigated', f => { if (f === p.mainFrame()) navs.push(Date.now()); });
    const cdp = await ctx.newCDPSession(p); const frames = []; cdp.on('Page.screencastFrame', async (ev) => { frames.push({ ts: ev.metadata.timestamp, data: ev.data }); try { await cdp.send('Page.screencastFrameAck', { sessionId: ev.sessionId }); } catch (e) {} });
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 70, everyNthFrame: 1 }); const before = syncLog.length; const tStart = Date.now();
    await p.goto(URL0, { waitUntil: 'commit' }); await p.waitForTimeout(Number(process.env.WATCH || 14000));
    try { await cdp.send('Page.stopScreencast'); } catch (e) {}
    const T = await p.evaluate(() => window.__T || []); const dir = OUT + '/open' + n; fs.mkdirSync(dir, { recursive: true }); const t0 = frames.length ? frames[0].ts : 0;
    frames.forEach((f, i) => fs.writeFileSync(dir + '/f' + String(i).padStart(4, '0') + '_' + String(Math.round((f.ts - t0) * 1000)).padStart(6, '0') + '.jpg', Buffer.from(f.data, 'base64')));
    res.opens.push({ n, frames: frames.length, navigations: navs.map(x => x - tStart), errs, sync: syncLog.slice(before), trace: T, end: await st(p) }); await p.close(); }
  fs.writeFileSync(OUT + '/result.json', JSON.stringify(res, null, 1)); const o = res.opens.map(x => ({ n: x.n, frames: x.frames, navigations: x.navigations, errs: x.errs, sync: x.sync, htmlSets: x.trace.filter(e => e.k === 'html').length, shifts: x.trace.filter(e => e.k === 'shift').length, shiftSum: +x.trace.filter(e => e.k === 'shift').reduce((a, e) => a + e.v, 0).toFixed(3), long: x.trace.filter(e => e.k === 'long').map(e => e.t + ':' + e.ms + 'ms') }));
  console.log(JSON.stringify({ filled, opens: o }, null, 1)); await b.close(); })();
