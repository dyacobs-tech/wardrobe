const { chromium } = require('playwright'); const fs = require('fs');
const S = '/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'; const DL = fs.readFileSync(S + '/sync/latest-dl.json');
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 430, height: 932 }, serviceWorkers: 'block' });
  await ctx.route(/workers\.dev|fashn|cloudflare/, async (route) => { const r = route.request();
    if (/\/sync$/.test(r.url()) && r.method() === 'POST') { let body = {}; try { body = JSON.parse(r.postData() || '{}'); } catch (e) {} return route.fulfill({ status: 200, contentType: 'application/json', body: !body.since ? DL : JSON.stringify({ recs: [], meta: null, now: 99999 }) }); }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }); });
  await ctx.route(/open-meteo/, r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ current: { temperature_2m: 80, apparent_temperature: 83, weather_code: 1, is_day: 1 }, daily: { time: [], temperature_2m_max: [], temperature_2m_min: [], weather_code: [] } }) }));
  await ctx.addInitScript(() => { if (!localStorage.getItem('wardrobe.sync')) localStorage.setItem('wardrobe.sync', JSON.stringify({ key: 'audit-placeholder', acct: 'SYNC_ACCOUNT_ID', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'Not synced yet' })); });
  const p = await ctx.newPage(); await p.goto('http://localhost:8767/', { waitUntil: 'load' });
  for (let i = 0; i < 80; i++) { const n = await p.evaluate(() => { try { return (JSON.parse(localStorage.getItem('wardrobe.items') || '[]') || []).length; } catch (e) { return -1; } }); if (n >= 165) break; await p.waitForTimeout(1000); }
  await p.waitForTimeout(3000);
  const out = await p.evaluate(() => { const d = composerDeck(null, 'plan');
    const cnt = {}; Object.keys(ONBODY.map).forEach(k => k.split('|').forEach(id => { cnt[id] = (cnt[id] || 0) + 1; }));
    const isNewCat = c => /^(Tees|Trousers|Jeans)$/.test(c || '');
    const newSet = new Set(wardrobeItems.filter(i => i && !String(i.id).startsWith('seed-') && isNewCat(i.category) && !cnt[i.id] && i.photo).map(i => i.id));
    const lvl = {}; for (const L of [2, 3, 4]) lvl[L] = new Set(d.forLevel(L).map(c => c.key));
    const both = []; const tee1 = [];
    for (const c of d.combos) { if (c.l || ONBODY.map[c.key]) continue; const nt = c.t && newSet.has(c.t.id), nb = c.b && newSet.has(c.b.id);
      const alexT = c.t && c.t.id === 'item-1794868007730-581626';
      const alex = false; if (!((nt || alexT) && nb)) continue;
      const levels = [2, 3, 4].filter(L => lvl[L].has(c.key)); if (!levels.length) continue;
      if (!window.WardrobeRules.lookAllowed({ t: c.t, b: c.b, s: c.s, l: c.l, tuck: c.tuck }, { level: levels[0], temp: 80, dow: 3 })) continue;
      (alex ? tee1 : both).push({ key: c.key, t: c.t.id, b: c.b.id, s: c.s.id, tuck: c.tuck, score: c.score, levels }); }
    return { both, tee1 }; });
  fs.writeFileSync(S + '/r2/plan/both.json', JSON.stringify(out));
  console.log('outfits with a new tee AND new trousers/jeans:', out.both.length, '| Alex mill tee candidates:', out.tee1.length);
  await b.close(); })();
