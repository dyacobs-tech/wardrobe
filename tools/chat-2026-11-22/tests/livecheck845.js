const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  await ctx.route(/workers\.dev|fashn/, r => r.abort());
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 200)));
  await p.goto('https://dyacobs-tech.github.io/wardrobe/?t=' + Date.now(), { waitUntil: 'load', timeout: 90000 }); await p.waitForTimeout(4000);
  const r = await p.evaluate(() => ({ build: window.WARDROBE_BUILD, stamp: (document.getElementById('build-stamp') || {}).textContent, nav: [...document.querySelectorAll('.nav-pill button span')].map(s => s.textContent.trim()).filter(Boolean),
    auto: !!(window.__enAuto845 && typeof window.__enAuto845.start === 'function') }));
  r.errs = errs; console.log(JSON.stringify(r)); await b.close(); })();
