// Live app with David's synced data (served from the local copy; nothing is written to his account).
const { chromium } = require('playwright'); const fs = require('fs');
const S = '/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'; const DL = fs.readFileSync(S + '/sync/latest-dl.json');
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 2, serviceWorkers: 'block', hasTouch: true, isMobile: true });
  await ctx.route(/workers\.dev|fashn|cloudflare/, async (route) => { const r = route.request();
    if (/\/sync$/.test(r.url()) && r.method() === 'POST') { let body = {}; try { body = JSON.parse(r.postData() || '{}'); } catch (e) {} return route.fulfill({ status: 200, contentType: 'application/json', body: !body.since ? DL : JSON.stringify({ recs: [], meta: null, now: JSON.parse(DL).now }) }); }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }); });
  await ctx.route(/open-meteo/, r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ current: { temperature_2m: 80, apparent_temperature: 83, weather_code: 1, is_day: 1 }, daily: { time: [], temperature_2m_max: [], temperature_2m_min: [], weather_code: [] } }) }));
  await ctx.addInitScript(() => { if (!localStorage.getItem('wardrobe.sync')) localStorage.setItem('wardrobe.sync', JSON.stringify({ key: 'audit-placeholder', acct: 'SYNC_ACCOUNT_ID', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'Not synced yet' })); });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 200))); const bad = []; p.on('response', r => { if (r.status() >= 400 && /assets\/worn/.test(r.url())) bad.push(r.url()); });
  await p.goto(process.argv[2], { waitUntil: 'load' });
  for (let i = 0; i < 80; i++) { const n = await p.evaluate(() => { try { return (JSON.parse(localStorage.getItem('wardrobe.items') || '[]') || []).length; } catch (e) { return -1; } }); if (n >= 172) break; await p.waitForTimeout(1000); }
  await p.waitForTimeout(2500); const build = await p.evaluate(() => (typeof WARDROBE_BUILD !== 'undefined' ? WARDROBE_BUILD : (document.body.innerText.match(/20\d\d-\d\d-\d\d\.\d+\.\d+/) || [''])[0]));
  await p.tap('#section-ideas'); await p.waitForTimeout(1500);
  // Closet -> Jackets
  await p.evaluate(() => { const b = document.querySelector('#panel-looks [data-lk-go="wardrobe"]'); if (b) b.click(); }); await p.waitForTimeout(3000);
  const closet = await p.evaluate(() => { wardFilter = 'Jackets'; renderWardrobe(); const j = wardrobeItems.filter(i => i.category === 'Jackets'); return { jackets: j.map(i => i.name), total: wardrobeItems.length }; }); await p.waitForTimeout(2500);
  await p.evaluate(() => { const im = [...document.querySelectorAll('img')].find(i => i.offsetParent !== null && /Human Assembly/.test(i.alt || '') ) || [...document.querySelectorAll('*')].filter(e => e.children.length === 0 && /Human Assembly/.test(e.textContent || '') && e.offsetParent !== null)[0]; if (im) im.scrollIntoView({ block: 'center' }); }); await p.waitForTimeout(1500);
  await p.screenshot({ path: S + '/look/out/shot-closet.png' });
  // Go-to's
  const tabs = await p.evaluate(() => [...document.querySelectorAll('#panel-looks [data-lk-go]')].map(b => b.getAttribute('data-lk-go') + ':' + b.textContent.trim()));
  await p.evaluate(() => { const b = [...document.querySelectorAll('#panel-looks [data-lk-go]')].find(b => /go-to/i.test(b.textContent)); if (b) b.click(); }); await p.waitForTimeout(4000);
  const gotos = await p.evaluate(() => { const g = (window.gotoEntries841 ? window.gotoEntries841() : []); const first = g[0] || {}; const img = [...document.querySelectorAll('img[data-worn845]')][0]; return { n: g.length, first: { title: first.title, date: (first.dates || [])[0], fig: String(first.fig || '').slice(0, 70), pieces: (first.items || []).map(i => i.name) }, firstImg: img ? { src: (img.getAttribute('src') || '').slice(0, 70), w: img.naturalWidth, h: img.naturalHeight, back: img.hasAttribute('data-worn845-back') } : null }; });
  await p.evaluate(() => window.scrollTo(0, 0)); await p.waitForTimeout(800); await p.evaluate(() => { const c = document.querySelector('.lk-goto843'); if (c) c.scrollIntoView({ block: 'start' }); window.scrollBy(0, -90); }); await p.waitForTimeout(1200);
  await p.screenshot({ path: S + '/look/out/shot-gotos.png' });
  // Calendar
  await p.tap('#section-calendar'); await p.waitForTimeout(3500); await p.screenshot({ path: S + '/look/out/shot-calendar.png' });
  const cal = await p.evaluate(() => ({ worn: (typeof wornLog !== 'undefined' ? wornLog : []).map(e => e.date + ' ' + e.title) }));
  console.log(JSON.stringify({ build, errs, missingWornPictures: bad, closet, tabs, gotos, cal }, null, 1)); await b.close(); })();
