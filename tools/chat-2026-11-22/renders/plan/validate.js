// After integration: is every new key known to the app (not hidden by a rule), dealt at a daytime level and allowed?
const { chromium } = require('playwright'); const fs = require('fs');
const S = '/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'; const DL = fs.readFileSync(S + '/sync/latest-dl.json');
const jobs = [].concat(...process.argv.slice(2).map(f => JSON.parse(fs.readFileSync(S + '/r2/' + f))));
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 430, height: 932 }, serviceWorkers: 'block' });
  await ctx.route(/workers\.dev|fashn|cloudflare/, async (route) => { const r = route.request();
    if (/\/sync$/.test(r.url()) && r.method() === 'POST') { let body = {}; try { body = JSON.parse(r.postData() || '{}'); } catch (e) {} return route.fulfill({ status: 200, contentType: 'application/json', body: !body.since ? DL : JSON.stringify({ recs: [], meta: null, now: 99999 }) }); }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }); });
  await ctx.route(/open-meteo/, r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ current: { temperature_2m: 80, apparent_temperature: 83, weather_code: 1, is_day: 1 }, daily: { time: [], temperature_2m_max: [], temperature_2m_min: [], weather_code: [] } }) }));
  await ctx.addInitScript(() => { if (!localStorage.getItem('wardrobe.sync')) localStorage.setItem('wardrobe.sync', JSON.stringify({ key: 'audit-placeholder', acct: 'SYNC_ACCOUNT_ID', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'Not synced yet' })); });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 160))); await p.goto('http://localhost:8767/', { waitUntil: 'load' });
  for (let i = 0; i < 80; i++) { const n = await p.evaluate(() => { try { return (JSON.parse(localStorage.getItem('wardrobe.items') || '[]') || []).length; } catch (e) { return -1; } }); if (n >= 165) break; await p.waitForTimeout(1000); }
  await p.waitForTimeout(4000);
  const res = await p.evaluate((keys) => { const d = composerDeck(null, 'validate'); const want = new Set(keys); const found = {};
    for (const c of d.combos) if (want.has(c.key)) found[c.key] = c;
    const lv = {}; for (const L of [2, 3, 4]) lv[L] = new Set(d.forLevel(L).filter(c => want.has(c.key)).map(c => c.key));
    return { build: window.WARDROBE_BUILD, renders: Object.keys(ONBODY.map).length, rows: keys.map(k => { const c = found[k]; const levels = [2, 3, 4].filter(L => lv[L].has(k));
      return { k, known: !!ONBODY.map[k], src: (typeof onbodySrc === 'function' ? !!onbodySrc(k) : null), inDeck: !!c, levels, allowed: c ? !!window.WardrobeRules.lookAllowed({ t: c.t, b: c.b, s: c.s, l: c.l, tuck: c.tuck }, { level: levels[0] || 3, temp: 80, dow: 3 }) : null }; }) }; }, jobs.map(j => j.key));
  const bad = res.rows.filter(r => !(r.known && r.src && r.inDeck && r.levels.length && r.allowed));
  console.log('build', res.build, '| pictures the app knows:', res.renders, '| new keys checked:', res.rows.length, '| known + dealt + allowed:', res.rows.length - bad.length, '| page errors', errs.length);
  for (const r of bad.slice(0, 12)) console.log('  PROBLEM', JSON.stringify(r));
  fs.writeFileSync(S + '/r2/validate.json', JSON.stringify(res)); await b.close(); })();
