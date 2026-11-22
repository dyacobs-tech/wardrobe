const { chromium } = require('playwright'); const fs = require('fs');
const S = '/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad'; const DL = fs.readFileSync(S + '/sync/latest-dl.json');
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 2, serviceWorkers: 'block', hasTouch: true, isMobile: true });
  await ctx.route(/workers\.dev|fashn|cloudflare/, async (route) => { const r = route.request();
    if (/\/sync$/.test(r.url()) && r.method() === 'POST') { let body = {}; try { body = JSON.parse(r.postData() || '{}'); } catch (e) {} return route.fulfill({ status: 200, contentType: 'application/json', body: !body.since ? DL : JSON.stringify({ recs: [], meta: null, now: 99999 }) }); }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }); });
  await ctx.route(/open-meteo/, r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ current: { temperature_2m: 80, apparent_temperature: 83, weather_code: 1, is_day: 1 }, daily: { time: [], temperature_2m_max: [], temperature_2m_min: [], weather_code: [] } }) }));
  await ctx.addInitScript(() => { if (!localStorage.getItem('wardrobe.sync')) localStorage.setItem('wardrobe.sync', JSON.stringify({ key: 'audit-placeholder', acct: 'SYNC_ACCOUNT_ID', last: 0, snap: {}, st: {}, tomb: {}, dirty: {}, status: 'Not synced yet' })); });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 160))); await p.goto(process.argv[2], { waitUntil: 'load' });
  for (let i = 0; i < 80; i++) { const n = await p.evaluate(() => { try { return (JSON.parse(localStorage.getItem('wardrobe.items') || '[]') || []).length; } catch (e) { return -1; } }); if (n >= 165) break; await p.waitForTimeout(1000); }
  await p.waitForTimeout(3000); await p.tap('#section-ideas'); await p.waitForTimeout(4000);
  const LV = process.argv[3] || '2';
  const picked = await p.evaluate((LV) => { const vis = e => !!(e && e.offsetParent !== null);
    const menus = [...document.querySelectorAll('.cdd-menu, [role=menu]')].filter(m => m.querySelector('[data-studio-type]'));
    const info = menus.map(m => ({ id: m.id, btnVisible: vis(m.parentElement && m.parentElement.querySelector('button')), pressed: [...m.querySelectorAll('[data-studio-type][aria-pressed=true]')].map(b => b.getAttribute('data-studio-type')) }));
    const m = document.getElementById('ideas-type-menu'); if (!m) return { info };
    const want = m.querySelector('[data-studio-type="' + LV + '"]'); if (want.getAttribute('aria-pressed') !== 'true') want.click();
    [...m.querySelectorAll('[data-studio-type][aria-pressed=true]')].filter(b => b.getAttribute('data-studio-type') !== LV).forEach(b => b.click());
    return { info, used: m.id, label: want.textContent.trim(), now: [...m.querySelectorAll('[data-studio-type][aria-pressed=true]')].map(b => b.getAttribute('data-studio-type')) }; }, LV); console.log('level', JSON.stringify(picked)); await p.waitForTimeout(5000);
  const NEW = new Set(JSON.parse(fs.readFileSync(S + '/r2/list1.json')).concat(JSON.parse(fs.readFileSync(S + '/r2/list2.json'))).map(j => j.f));
  const st = await p.evaluate((nf) => { const looks = window.__cfLooks81 ? __cfLooks81() : []; const srcs = [...document.querySelectorAll('#cf-grid article img')].map(i => (i.getAttribute('src') || '').split('/').pop()); return { build: window.WARDROBE_BUILD, renders: Object.keys(ONBODY.map).length, looks: looks.length, cards: document.querySelectorAll('#cf-grid article').length, newOnScreen: srcs.filter(s => nf.includes(s)).length, label: (document.querySelector('#panel-looks .cdd-btn, #panel-looks [data-cdd]') || {}).textContent }; }, [...NEW]);
  console.log(JSON.stringify(st), 'errors', errs.length);
  for (let i = 0; i < 3; i++) { await p.screenshot({ path: S + '/r2/outfits-' + i + '.png' }); await p.evaluate(() => { document.scrollingElement.scrollTop += 780; }); await p.waitForTimeout(2500); }
  await b.close(); })();
