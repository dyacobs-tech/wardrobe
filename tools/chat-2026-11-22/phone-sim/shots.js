const { chromium } = require('playwright'); const fs = require('fs');
const S = '/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'; const DL = fs.readFileSync(S + '/sync/latest-dl.json');
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 2, serviceWorkers: 'block', hasTouch: true, isMobile: true });
  await ctx.route(/workers\.dev|fashn|cloudflare/, async (route) => { const r = route.request();
    if (/\/sync$/.test(r.url()) && r.method() === 'POST') { let body = {}; try { body = JSON.parse(r.postData() || '{}'); } catch (e) {} return route.fulfill({ status: 200, contentType: 'application/json', body: !body.since ? DL : JSON.stringify({ recs: [], meta: null, now: 99999 }) }); }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }); });
  await ctx.route(/open-meteo/, r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ current: { temperature_2m: 80, apparent_temperature: 83, weather_code: 1, is_day: 1 }, daily: { time: [], temperature_2m_max: [], temperature_2m_min: [], weather_code: [] } }) }));
  await ctx.addInitScript(() => { if (!localStorage.getItem('wardrobe.sync')) localStorage.setItem('wardrobe.sync', JSON.stringify({ key: 'audit-placeholder', acct: 'SYNC_ACCOUNT_ID', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'Not synced yet' })); });
  const p = await ctx.newPage(); await p.goto(process.argv[2], { waitUntil: 'load' });
  for (let i = 0; i < 80; i++) { const n = await p.evaluate(() => { try { return (JSON.parse(localStorage.getItem('wardrobe.items') || '[]') || []).length; } catch (e) { return -1; } }); if (n >= 171) break; await p.waitForTimeout(1000); }
  await p.waitForTimeout(2500); await p.tap('#section-ideas'); await p.waitForTimeout(1500); await p.evaluate(() => { const b = document.querySelector('#panel-looks [data-lk-go="wardrobe"]'); if (b) b.click(); }); await p.waitForTimeout(3000);
  for (const c of process.argv.slice(3)) {
    const n = await p.evaluate((c) => { wardFilter = c; renderWardrobe(); document.scrollingElement.scrollTop = 0; return wardrobeItems.filter(i => i.category === c).length; }, c);
    await p.waitForTimeout(2500); console.log(c, n); await p.screenshot({ path: S + '/phonesim/closet-' + c + '.png', fullPage: false }); if (n > 6) { await p.evaluate(() => { document.scrollingElement.scrollTop += 700; }); await p.waitForTimeout(1500); await p.screenshot({ path: S + '/phonesim/closet-' + c + '-2.png', fullPage: false }); } if (n > 12) { await p.evaluate(() => { document.scrollingElement.scrollTop += 700; }); await p.waitForTimeout(1500); await p.screenshot({ path: S + '/phonesim/closet-' + c + '-3.png', fullPage: false }); } }
  await b.close(); })();
