// The real app against the REAL sync server, read-only: every /sync the page makes is forwarded with its bookmark but
// WITHOUT its uploads (changes: [], meta: null), so nothing is written to David's account. Shows whether the app
// accepts the server's new clock bookmarks: first sync (full download), a second sync, and a reload.
const { chromium } = require('playwright'); const fs = require('fs'); const { execFileSync } = require('child_process');
const S = '/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad';
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 430, height: 932 }, serviceWorkers: 'block', hasTouch: true, isMobile: true }); const log = [];
  await ctx.route(/workers\.dev|fashn|cloudflare/, async (route) => { const r = route.request();
    if (/\/sync$/.test(r.url()) && r.method() === 'POST') { let body = {}; try { body = JSON.parse(r.postData() || '{}'); } catch (e) {}
      fs.writeFileSync(S + '/phonesim/fwd.json', JSON.stringify({ since: body.since || 0, changes: [], meta: null }));
      const t0 = Date.now(); let out = ''; try { out = execFileSync('curl', ['-s', '-m', '200', '-X', 'POST', 'https://wardrobe-sync.dyacobs.workers.dev/sync', '-H', 'content-type: application/json', '--data-binary', '@' + S + '/phonesim/fwd.json'], { maxBuffer: 256 * 1024 * 1024 }).toString(); } catch (e) { out = ''; }
      let j = null; try { j = JSON.parse(out); } catch (e) {}
      log.push({ since: body.since, uploadsHeldBack: (body.changes || []).length + (body.meta ? 1 : 0), records: j ? j.recs.length : null, bookmark: j ? j.now : null, ms: Date.now() - t0 });
      return route.fulfill({ status: j ? 200 : 502, contentType: 'application/json', body: out || '{}' }); }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }); });
  await ctx.route(/open-meteo/, r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ current: { temperature_2m: 80, apparent_temperature: 83, weather_code: 1, is_day: 1 }, daily: { time: [], temperature_2m_max: [], temperature_2m_min: [], weather_code: [] } }) }));
  await ctx.addInitScript(() => { if (!localStorage.getItem('wardrobe.sync')) localStorage.setItem('wardrobe.sync', JSON.stringify({ key: 'audit-placeholder', acct: 'SYNC_ACCOUNT_ID', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'Not synced yet' })); });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 200)));
  const state = () => p.evaluate(() => { try { const a = JSON.parse(localStorage.getItem('wardrobe.items') || '[]'); const sy = JSON.parse(localStorage.getItem('wardrobe.sync') || '{}'); return { items: a.length, tees: a.filter(i => i.category === 'Tees').length, last: sy.last, status: sy.status, hasSneakers: a.some(i => /Loro Piana Cream Multicolour/.test(i.name || '')) }; } catch (e) { return { items: -1 }; } });
  await p.goto(process.argv[2], { waitUntil: 'load' });
  for (let i = 0; i < 120; i++) { const s = await state(); if (s.items >= 171 && /Synced/.test(s.status || '')) break; await p.waitForTimeout(1000); }
  await p.waitForTimeout(3000); const first = await state();
  await p.evaluate(() => { if (typeof syncNow === 'function') syncNow(); }); await p.waitForTimeout(9000); const second = await state();
  await p.reload({ waitUntil: 'load' }); for (let i = 0; i < 40; i++) { const s = await state(); if (/Synced/.test(s.status || '') && log.length >= 4) break; await p.waitForTimeout(1000); } await p.waitForTimeout(4000); const third = await state();
  console.log(JSON.stringify({ pageErrors: errs, first, second, third, requests: log }, null, 1)); await b.close(); })();
