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
    const rendered = {}; Object.keys(ONBODY.map).forEach(k => { rendered[k] = ONBODY.map[k]; });
    const cnt = {}; Object.keys(rendered).forEach(k => k.split('|').forEach(id => { cnt[id] = (cnt[id] || 0) + 1; }));
    const isNewCat = c => /^(Tees|Trousers|Jeans)$/.test(c || '');
    const news = wardrobeItems.filter(i => i && !String(i.id).startsWith('seed-') && isNewCat(i.category) && !cnt[i.id] && i.photo).map(i => ({ id: i.id, name: i.name, category: i.category, colour: i.colourName }));
    const newSet = new Set(news.map(n => n.id));
    // rendered combos: key -> combo (for tuck / slots)
    const rcombo = {}; const idx = {};            // idx: "<slot>#<rest ids>" -> [rendered key]
    const lvl = {}; for (const L of [2, 3, 4]) lvl[L] = new Set(d.forLevel(L).map(c => c.key));
    for (const c of d.combos) { if (!rendered[c.key]) continue; rcombo[c.key] = c;
      for (const slot of ['t', 'b']) { const x = c[slot]; if (!x) continue; const rest = c.ids.filter(i => i !== x.id).slice().sort().join('|'); const kk = slot + '#' + rest + '#' + (c.l ? c.l.id : ''); (idx[kk] = idx[kk] || []).push(c.key); } }
    const cands = {}; let seen = 0;
    for (const c of d.combos) { if (rendered[c.key]) continue; const nt = c.t && newSet.has(c.t.id), nb = c.b && newSet.has(c.b.id); if (!nt && !nb) continue; if (nt && nb) continue;   // one new piece per picture in this pass
      const slot = nt ? 't' : 'b'; const x = c[slot]; if (slot === 't' && c.l) continue;                                      // new tees: no outer layer
      const rest = c.ids.filter(i => i !== x.id).slice().sort().join('|'); const bases = idx[slot + '#' + rest + '#' + (c.l ? c.l.id : '')]; if (!bases) continue;
      const levels = [2, 3, 4].filter(L => lvl[L].has(c.key)); if (!levels.length) continue;
      const okb = bases.filter(bk => rcombo[bk].tuck === c.tuck); if (!okb.length) continue;
      const allowed = window.WardrobeRules.lookAllowed({ t: c.t, b: c.b, s: c.s, l: c.l, tuck: c.tuck }, { level: levels[0], temp: 80, dow: 3 }); if (!allowed) continue;
      seen++; const arr = (cands[x.id] = cands[x.id] || []);
      arr.push({ key: c.key, slot, score: c.score, levels, tuck: c.tuck, t: c.t.id, b: c.b.id, s: c.s.id, l: c.l ? c.l.id : null, bases: okb.slice(0, 6).map(bk => ({ k: bk, f: rendered[bk].split('/').pop(), rep: rcombo[bk][slot].id, repCat: rcombo[bk][slot].category, repName: rcombo[bk][slot].name })) }); }
    const names = {}; wardrobeItems.forEach(i => { names[i.id] = { name: i.name, category: i.category, colour: i.colourName }; });
    Object.keys(cands).forEach(id => { cands[id].sort((a, b) => b.score - a.score); cands[id] = cands[id].slice(0, 400); });
    return { news, seen, per: Object.fromEntries(Object.entries(cands).map(([k, v]) => [k, v.length])), cands, names, rendered: Object.keys(rendered).length }; });
  fs.writeFileSync(S + '/r2/plan/cands.json', JSON.stringify(out));
  console.log('new pieces without a picture on him:', out.news.length, '| candidate outfits:', out.seen, '| rendered keys', out.rendered);
  for (const n of out.news) console.log(' ', n.category.padEnd(9), (n.name || '').slice(0, 48).padEnd(48), 'candidates', out.per[n.id] || 0);
 await b.close(); })();
