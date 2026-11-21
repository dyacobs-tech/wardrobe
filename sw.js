// Wardrobe — offline cache
// Strategy
//  · App shell (the page): network-first with a 30s deadline (build .58),
//    so a 2.7MB index.html can finish on a typical phone link before any
//    cached shell is used. Only a failed or over-deadline fetch falls back. Only a good (200) response ever replaces the
//    cached shell, and it is always stored under one key.
//  · Photos under assets/photos/ are cache-first, kept once seen.
//    Cache names include WARDROBE_BUILD, so a new release re-fetches
//    photos that were edited in place under the same filename.
//  · Everything else on this origin (icons, the wardrobe-look renders, the
//    manifest): network-first. These files keep their names when they
//    change, so a cached copy must never win over a fresh one — the
//    network copy is served (and re-cached) whenever it answers, and
//    the cache is only the offline fallback. Web fonts keep
//    stale-while-revalidate: their URLs are versioned by the provider.
//
// Build .55 (handover 3.9): only the app shell itself (a navigation, the
// directory root, or index.html) maps to the shell key — any other .html
// file is an ordinary asset, so a future terms.html can never overwrite
// the cached app. Cache-buster URLs (?r=…) are stored and matched under
// their clean URL, and activate prunes buster entries cached by older
// builds, so ASSET_CACHE no longer grows one entry per buster.
// Cross-origin requests (the sync worker included) are never cached:
// the fetch handler returns early for any origin but this one.
// Build .58/.59/.62: cache names include the app build, so a new release
// drops the previous photo/shell/asset caches on activate. That is
// what lets returning clients pick up in-place photo edits (Breguet
// 3050, Breton) that kept the same hashed filenames. The shell
// deadline is 30s — long enough for a 2.7MB index.html on a typical
// phone connection — so a slow fetch is not replaced by a stale
// cached shell after 4 seconds.
// Preview flow (Nov 19): the same file also runs as the PREVIEW worker at
// <site>/preview/ (scope .../preview/). Its caches are namespaced
// 'preview-…' so neither worker ever prunes the other's caches; the preview
// page's assets/ requests are served from the live site's assets/ (the
// preview deploy does not duplicate the 600 MB of photos); and the live
// worker leaves everything under preview/ to the network / preview worker.
const SCOPE_PATH = new URL(self.registration.scope).pathname;
const PREVIEW = /\/preview\/$/.test(SCOPE_PATH);
const NS = PREVIEW ? 'preview-' : '';
const WARDROBE_BUILD = '2026-11-21.86.41';
const SHELL_CACHE = NS + 'wardrobe-shell-' + WARDROBE_BUILD;
const PHOTO_CACHE = NS + 'wardrobe-photos-' + WARDROBE_BUILD;
const ASSET_CACHE = NS + 'wardrobe-assets-' + WARDROBE_BUILD;
// Cut-outs keep their filenames when the matte is repaired, so bump
// ONBODY_CACHE to drop the v2 copies whose left shoe faded out.
const ONBODY_CACHE = NS + 'wardrobe-onbody-v3';
// Build .79.3: the JSON manifests (renders, cut-outs, inspo, the Edit
// catalogue, the cut-out placeholders) are stale-while-revalidate in a
// cache that survives builds, so a reopen never waits on them; a change
// lands on the next open.
const DATA_CACHE = NS + 'wardrobe-data-v2';
const DATA_RE = /\/assets\/(onbody\/manifest\.json|onbody-cut\/(manifest|lq|feet)\.json|inspo\/manifest\.json|edit-catalog(-lite)?\.json)$/;
// Cut-outs (assets/onbody-cut/, and the full-resolution zoom copies in
// assets/onbody-cut-hq/) are immutable: cache-first in ONBODY_CACHE.
const CUT_RE = /\/assets\/onbody-cut(-hq)?\/[^\/]+\.(webp|png)$/;
// Build .80: the shell (index.html) is small; the app's code lives in
// app/<name>.<content-hash>.(js|css), written by scripts/build_shell.py.
// Those files are immutable: cache-first in CODE_CACHE, which survives
// builds (activate drops files no longer listed), precached on install.
const CODE_CACHE = NS + 'wardrobe-code-v1';
const CODE_RE = /\/app\/[^\/]+\.[0-9a-f]{10}\.(js|css|json)$/;
const CODE_FILES = ['./app/app.d6b3ae9438.css', './app/00-brand-list.27a288fac9.js', './app/01.25d1ca2c3c.js', './app/02.224ece68bd.js', './app/25.318a5abe99.js', './app/26.44c6f329b2.js', './app/27.a6437f4596.js', './app/bundle.c6e7098ac5.js', './app/style-icons.e167dc7786.json', './app/extra-renders.ab99cb82a0.json', './app/sale-items.0fae754db8.json', './app/icon-directory.fe780b77f4.json', './app/shop-catalogue.6133045db3.json', './app/icon-specs.766c27918a.json', './app/endless.a9560722a4.js', './app/endless-worker.b78472a424.js'];
const SHELL_KEY = './index.html';
const SHELL_FILES = ['./index.html', './manifest.webmanifest',
  './assets/icon-180.png', './assets/icon-192.png', './assets/icon-512.png',
  './assets/icon-512-maskable.png', './assets/favicon-32.png',
  './assets/fonts/Inter.var.woff2', './assets/fonts/Inter-Italic.var.woff2',
  './assets/fonts/Fraunces.v803.woff2', './assets/fonts/Fraunces-Italic.v803.woff2'];
// Build .80: the shell is small now — a reopen waits at most 0.4s (was 0.8s) for the
// network (a 304 on a good link answers inside that); a slower link gets the
// cached shell at once and the fresh one lands in the cache for the
// next open ("A newer build is ready" covers the rest). With no cached
// shell it still waits for the network.
const SHELL_DEADLINE_MS = 400;
const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com'];

// Safety (Nov 19): the precache is ATOMIC. The new shell (index.html for
// this exact build) and every CODE_FILES entry must be in the caches before
// this worker may skipWaiting/claim; if any of them failed, install rejects,
// the new worker is discarded, and the old one keeps serving a complete,
// working offline app (the browser retries on the next update check). A
// failed install never leaves a worker stuck in "waiting", so the iOS PWA
// concern from build .75 does not apply. Icons and fonts stay best-effort.
const CODE_MANIFEST_KEY = 'https://wardrobe.invalid/__code-manifest__';
self.addEventListener('install', (event) => {
  const scopeUrl = (u) => new URL(u, self.registration.scope).toString();
  const shellHasBuild = (res) => res ? res.clone().text().then((t) => t.indexOf('content="' + WARDROBE_BUILD + '"') !== -1) : Promise.resolve(false);
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => caches.keys().then((keys) => Promise.all(keys.filter((k) => k.indexOf(NS + 'wardrobe-shell-') === 0 && k !== SHELL_CACHE).map((k) =>
        caches.open(k).then((c) => c.match(SHELL_KEY)).then((hit) => shellHasBuild(hit).then((ok) => ok ? hit : null))
      ))).then((hits) => {
        const own = hits.filter(Boolean)[0];
        // Required: this build's shell.
        const shell = own ? cache.put(SHELL_KEY, own) : fetch(new Request('./index.html', { cache: 'reload' })).then((res) => {
          if (!res || res.status !== 200) throw new Error('shell download failed');
          return shellHasBuild(res).then((ok) => { if (!ok) throw new Error('shell is not build ' + WARDROBE_BUILD); return cache.put(SHELL_KEY, res); });
        });
        // Best-effort: manifest, icons, fonts (copied from an older cache when present).
        const extras = SHELL_FILES.filter((u) => u !== './index.html').map((u) =>
          caches.match(u).then((m) => m ? cache.put(u, m) : cache.add(new Request(u, { cache: 'reload', priority: 'low' }))).catch(() => {})
        );
        return Promise.all([shell].concat(extras));
      }))
      // Required: every code file of this build.
      .then(() => caches.open(CODE_CACHE).then((cc) => Promise.all(CODE_FILES.map((u) => {
        const key = scopeUrl(u);
        // .80.3: low priority, so Home's next cut-outs go first on a slow link
        return cc.match(key).then((hit) => hit || fetch(key, { priority: 'low' }).then((res) => {
          if (!res || res.status !== 200) throw new Error('code file failed: ' + u);
          return cc.put(key, res);
        }));
      }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  const keep = [SHELL_CACHE, PHOTO_CACHE, ASSET_CACHE, ONBODY_CACHE, DATA_CACHE, CODE_CACHE];
  const live = CODE_FILES.map((u) => new URL(u, self.registration.scope).toString());
  // Safety (Nov 19): the previous build's code files are kept for one more
  // release, so a page still running the old build (an update held while a
  // sheet is open, a second tab) never hits a missing file. The cache keeps a
  // small manifest of which files belong to which build; with no manifest yet
  // (first activate after this change) nothing is pruned this time.
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      // only this worker's own namespace is ever pruned
      keys.filter((k) => keep.indexOf(k) === -1 && (PREVIEW ? k.indexOf('preview-') === 0 : k.indexOf('preview-') !== 0)).map((k) => caches.delete(k))
    )).then(() => caches.open(CODE_CACHE)).then((cc) => cc.match(CODE_MANIFEST_KEY)
      .then((m) => m ? m.json().catch(() => null) : null)
      .then((old) => {
        let prev = null;
        if (old && old.build && old.build !== WARDROBE_BUILD) prev = { build: old.build, files: old.files || [] };
        else if (old && old.prev) prev = old.prev;
        const manifest = { build: WARDROBE_BUILD, files: live, prev: prev };
        const put = cc.put(CODE_MANIFEST_KEY, new Response(JSON.stringify(manifest), { headers: { 'content-type': 'application/json' } }));
        if (!old) return put; // unknown history: prune nothing this release
        const keepUrls = live.concat(prev ? prev.files : []).concat([CODE_MANIFEST_KEY]);
        return put.then(() => cc.keys()).then((reqs) => Promise.all(
          reqs.filter((r) => keepUrls.indexOf(r.url) === -1).map((r) => cc.delete(r))
        ));
      })
    ).then(() => caches.open(ASSET_CACHE)).then((cache) =>
      // Prune ?r= cache-buster entries an older build may have stored.
      cache.keys().then((reqs) => Promise.all(
        reqs.filter((r) => new URL(r.url).searchParams.has('r'))
          .map((r) => cache.delete(r))
      ))
    ).then(() => trimImageCaches().catch(() => {})).then(() => self.clients.claim())
  );
});

// Safety/perf (Nov 19): the image caches (cut-outs + on-body renders in
// ONBODY_CACHE, photos in PHOTO_CACHE) are capped at IMAGE_CACHE_MAX bytes,
// least-recently-used first, so iOS never evicts the whole origin's storage
// (localStorage/IndexedDB included) under pressure. Every stored image carries
// x-sw-size and x-sw-at; a hit older than a day is re-stamped (moved to the
// recent end); a trim runs a few seconds after writes settle.
const IMAGE_CACHE_MAX = 150 * 1024 * 1024;
const LRU_TOUCH_MS = 24 * 60 * 60 * 1000;
let _trimT = null;
function putLRU(cache, key, res) {
  return res.clone().blob().then((body) => {
    const h = new Headers(res.headers);
    h.set('x-sw-size', String(body.size)); h.set('x-sw-at', String(Date.now()));
    return cache.put(key, new Response(body, { status: 200, statusText: 'OK', headers: h }));
  }).then(scheduleTrim, () => {});
}
function touchLRU(cache, key, hit) {
  const at = +(hit.headers.get('x-sw-at') || 0);
  if (Date.now() - at < LRU_TOUCH_MS) return Promise.resolve();
  return putLRU(cache, key, hit);
}
function scheduleTrim() {
  clearTimeout(_trimT);
  _trimT = setTimeout(() => { trimImageCaches().catch(() => {}); }, 4000);
}
function trimImageCaches(max) {
  const limit = max || IMAGE_CACHE_MAX;
  return Promise.all([ONBODY_CACHE, PHOTO_CACHE].map((n) => caches.open(n).then((c) => c.keys().then((ks) =>
    Promise.all(ks.map((k) => c.match(k).then((r) => ({ c, k, at: +((r && r.headers.get('x-sw-at')) || 0), size: +((r && (r.headers.get('x-sw-size') || r.headers.get('content-length'))) || 60000) }))))
  )))).then((lists) => {
    const all = [].concat.apply([], lists);
    let total = all.reduce((t, e) => t + e.size, 0);
    if (total <= limit) return { total, removed: 0 };
    all.sort((a, b) => a.at - b.at);
    const dels = [];
    for (const e of all) { if (total <= limit * 0.9) break; total -= e.size; dels.push(e.c.delete(e.k)); }
    return Promise.all(dels).then(() => ({ total, removed: dels.length }));
  });
}

// The cache identity of an asset request: its URL without the ?r=
// cache-buster, so a busted request reads and refreshes the one
// canonical entry instead of adding a new one every time.
function assetKey(req) {
  const url = new URL(req.url);
  if (!url.searchParams.has('r')) return req;
  url.searchParams.delete('r');
  return url.toString();
}

function networkFirst(event, cacheName) {
  const req = event.request;
  const key = assetKey(req);
  event.respondWith(
    fetch(req, { cache: 'no-cache' }).then((res) => {
      // Opaque (cross-origin) responses report status 0; keep those too.
      if (res && (res.status === 200 || res.type === 'opaque')) {
        const copy = res.clone();
        event.waitUntil(caches.open(cacheName).then((cache) => cache.put(key, copy)));
      }
      return res;
    }).catch(() =>
      caches.open(cacheName).then((cache) => cache.match(key)).then((hit) => {
        if (hit) return hit;
        throw new Error('offline and not cached: ' + req.url);
      })
    )
  );
}

function staleWhileRevalidate(event, cacheName) {
  const req = event.request;
  event.respondWith(
    caches.open(cacheName).then((cache) =>
      cache.match(req).then((hit) => {
        const network = fetch(req).then((res) => {
          // Opaque (cross-origin font) responses report status 0; keep those too.
          if (res && (res.status === 200 || res.type === 'opaque')) cache.put(req, res.clone());
          return res;
        }).catch(() => hit);
        if (hit) { event.waitUntil(network); return hit; }
        return network;
      })
    )
  );
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (FONT_HOSTS.indexOf(url.hostname) !== -1) { staleWhileRevalidate(event, ASSET_CACHE); return; }
  if (url.origin !== self.location.origin) return;
  // The preview build reads the live site's assets (both workers map
  // preview/assets/* onto assets/*, so even a first preview visit still
  // controlled by the live worker resolves them).
  const ROOT_PATH = PREVIEW ? SCOPE_PATH.replace(/preview\/$/, '') : SCOPE_PATH;
  if (url.pathname.indexOf(ROOT_PATH + 'preview/assets/') === 0 && !req.headers.has('range')) {
    const target = url.origin + ROOT_PATH + url.pathname.slice((ROOT_PATH + 'preview/').length);
    const cacheName = CUT_RE.test(url.pathname) || url.pathname.includes('/assets/onbody/') ? ONBODY_CACHE : (url.pathname.includes('/assets/photos/') ? PHOTO_CACHE : ASSET_CACHE);
    event.respondWith(caches.open(cacheName).then((cache) => cache.match(target).then((hit) => {
      const net = fetch(target + url.search).then((res) => { if (res && res.status === 200) { if (cacheName === ASSET_CACHE) cache.put(target, res.clone()); else event.waitUntil(putLRU(cache, target, res)); } return res; });
      if (hit && cacheName !== ASSET_CACHE) { event.waitUntil(touchLRU(cache, target, hit)); return hit; }
      return net.catch(() => hit || Promise.reject(new Error('offline')));
    })));
    return;
  }
  // The live worker never answers for the rest of the preview build.
  if (!PREVIEW && url.pathname.indexOf(ROOT_PATH + 'preview/') === 0) return;
  // Partial requests (the page's "is there a newer build?" probe) go straight
  // to the network and are never cached.
  if (req.headers.has('range')) return;

  // App code: content-hashed, cache-first.
  if (CODE_RE.test(url.pathname)) {
    event.respondWith(
      caches.open(CODE_CACHE).then((cache) =>
        cache.match(req, { ignoreSearch: true }).then((hit) => {
          if (hit) return hit;
          return fetch(req).then((res) => {
            if (res && res.status === 200) cache.put(url.origin + url.pathname, res.clone());
            return res;
          });
        })
      )
    );
    return;
  }
  // Cut-outs: immutable, cache-first (a ?r= retry reads the same entry).
  if (CUT_RE.test(url.pathname)) {
    event.respondWith(
      caches.open(ONBODY_CACHE).then((cache) =>
        cache.match(req, { ignoreSearch: true }).then((hit) => {
          const key = url.origin + url.pathname;
          if (hit) { event.waitUntil(touchLRU(cache, key, hit)); return hit; }
          return fetch(req).then((res) => {
            if (res && res.status === 200) event.waitUntil(putLRU(cache, key, res));
            return res;
          });
        })
      )
    );
    return;
  }
  if (DATA_RE.test(url.pathname)) {
    event.respondWith(
      caches.open(DATA_CACHE).then((cache) =>
        cache.match(req, { ignoreSearch: true }).then((hit) => {
          const key = url.origin + url.pathname;
          const refresh = () => fetch(req, { cache: 'no-cache' }).then((res) => {
            if (res && res.status === 200) {
              // remember when this copy was fetched, so reopens soon after skip the refresh
              return res.clone().blob().then((body) => {
                const h = new Headers(res.headers); h.set('x-sw-at', String(Date.now()));
                return cache.put(key, new Response(body, { status: 200, headers: h }));
              }).then(() => res);
            }
            return res;
          });
          if (hit) {
            const at = +(hit.headers.get('x-sw-at') || 0);
            // a fresh copy (under 15 min) is not refetched; an older one is
            // refreshed in the background, after the first paint and first swipes
            if (Date.now() - at > 15 * 60 * 1000) event.waitUntil(new Promise((r) => setTimeout(r, 6000)).then(refresh).catch(() => {}));
            return hit;
          }
          return refresh();
        })
      )
    );
    return;
  }

  // On-body renders: content-hashed, cache-first in their own cache.
  // The manifest beside them stays network-first (below).
  if ((url.pathname.includes('/assets/onbody/') || url.pathname.includes('/assets/inspo/')) && url.pathname.endsWith('.webp')) {
    event.respondWith(
      caches.open(ONBODY_CACHE).then((cache) =>
        cache.match(req, { ignoreSearch: true }).then((hit) => {
          if (hit) { event.waitUntil(touchLRU(cache, req, hit)); return hit; }
          return fetch(req).then((res) => {
            if (res && res.status === 200) event.waitUntil(putLRU(cache, req, res));
            return res;
          });
        })
      )
    );
    return;
  }

  // Photos: immutable, cache-first.
  if (url.pathname.includes('/assets/photos/')) {
    event.respondWith(
      caches.open(PHOTO_CACHE).then((cache) =>
        cache.match(req).then((hit) => {
          if (hit) { event.waitUntil(touchLRU(cache, req, hit)); return hit; }
          return fetch(req).then((res) => {
            if (res && res.status === 200) event.waitUntil(putLRU(cache, req, res));
            return res;
          });
        })
      )
    );
    return;
  }

  // The page: network-first with a deadline; cache as the fallback.
  // Only the shell itself maps to the shell key (build .55 / 3.9).
  const isShell = req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('/index.html');
  if (isShell) {
    event.respondWith(
      caches.open(SHELL_CACHE).then((cache) => {
        const cached = cache.match(SHELL_KEY);
        const network = fetch(req, { cache: 'no-cache' }).then((res) => {
          if (res && res.status === 200) cache.put(SHELL_KEY, res.clone());
          return res;
        });
        const deadline = cached.then((hit) => hit ? new Promise((resolve) => setTimeout(resolve, SHELL_DEADLINE_MS, null)) : network.catch(() => null));
        return Promise.race([network.catch(() => null), deadline]).then((res) => {
          if (res && res.status === 200) return res;
          // Slow, offline, or an error page: use the cached shell if there is
          // one; otherwise wait for whatever the network finally says.
          event.waitUntil(network.catch(() => {}));
          return cached.then((hit) => hit || network);
        });
      })
    );
    return;
  }

  // Speed: this origin's web fonts are cache-first from the shell cache
  // (precached with the shell; a changed font ships under a new name) —
  // network-first re-downloaded 134KB on every open, alongside the hero.
  if (url.origin === self.location.origin && url.pathname.indexOf('/assets/fonts/') !== -1) {
    event.respondWith(caches.open(SHELL_CACHE).then((cache) => cache.match(req, { ignoreSearch: true }).then((hit) => hit || fetch(req).then((res) => {
      if (res && res.status === 200) cache.put(req, res.clone());
      return res;
    }))));
    return;
  }

  // Same-name assets (the wardrobe-look renders, lazy renders, icons,
  // the manifest): network-first, so a corrected file under an
  // unchanged name is what the next view actually shows.
  networkFirst(event, ASSET_CACHE);
});

// Build .79.3: the page names the cut-outs it will show next (the outfit
// of the day and the queued looks); fetch any not yet cached so the next
// open or Next paints from Cache Storage.
self.addEventListener('message', (event) => {
  const d = event.data || {};
  if (d.type === 'trim-images') { event.waitUntil(trimImageCaches(d.max).then((r) => { if (event.source && event.source.postMessage) event.source.postMessage({ type: 'trimmed', r }); })); return; }
  if (d.type !== 'warm-cuts' || !Array.isArray(d.urls)) return;
  event.waitUntil(caches.open(ONBODY_CACHE).then((cache) => Promise.all(d.urls.slice(0, 8).map((u) => {
    let url; try { url = new URL(u, self.registration.scope); } catch (e) { return null; }
    if (url.origin !== self.location.origin || !CUT_RE.test(url.pathname)) return null;
    const key = url.origin + url.pathname;
    return cache.match(key).then((hit) => hit || fetch(key).then((res) => { if (res && res.status === 200) return putLRU(cache, key, res); }).catch(() => {}));
  }))));
});
