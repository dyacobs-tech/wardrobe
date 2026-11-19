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
const WARDROBE_BUILD = '2026-11-19.80.12';
const SHELL_CACHE = 'wardrobe-shell-' + WARDROBE_BUILD;
const PHOTO_CACHE = 'wardrobe-photos-' + WARDROBE_BUILD;
const ASSET_CACHE = 'wardrobe-assets-' + WARDROBE_BUILD;
// On-body renders (assets/onbody/<content-hash>.webp) are immutable, so
// their cache is versioned on its own and survives build updates; bump
// ONBODY_CACHE only if the render format changes.
const ONBODY_CACHE = 'wardrobe-onbody-v2';
// Build .79.3: the JSON manifests (renders, cut-outs, inspo, the Edit
// catalogue, the cut-out placeholders) are stale-while-revalidate in a
// cache that survives builds, so a reopen never waits on them; a change
// lands on the next open.
const DATA_CACHE = 'wardrobe-data-v2';
const DATA_RE = /\/assets\/(onbody\/manifest\.json|onbody-cut\/(manifest|lq|feet)\.json|inspo\/manifest\.json|edit-catalog\.json)$/;
// Cut-outs (assets/onbody-cut/, and the full-resolution zoom copies in
// assets/onbody-cut-hq/) are immutable: cache-first in ONBODY_CACHE.
const CUT_RE = /\/assets\/onbody-cut(-hq)?\/[^\/]+\.(webp|png)$/;
// Build .80: the shell (index.html) is small; the app's code lives in
// app/<name>.<content-hash>.(js|css), written by scripts/build_shell.py.
// Those files are immutable: cache-first in CODE_CACHE, which survives
// builds (activate drops files no longer listed), precached on install.
const CODE_CACHE = 'wardrobe-code-v1';
const CODE_RE = /\/app\/[^\/]+\.[0-9a-f]{10}\.(js|css|json)$/;
const CODE_FILES = ['./app/app.f15f590af9.css', './app/00-brand-list.27a288fac9.js', './app/01.8e77662400.js', './app/02.19c51521a4.js', './app/22.318a5abe99.js', './app/23.b8fdd92cdc.js', './app/24.7505b30a4e.js', './app/bundle.73e2b6d85f.js', './app/style-icons.e167dc7786.json', './app/extra-renders.ab99cb82a0.json', './app/sale-items.0fae754db8.json', './app/icon-directory.fe780b77f4.json', './app/shop-catalogue.6133045db3.json', './app/icon-specs.766c27918a.json'];
const SHELL_KEY = './index.html';
const SHELL_FILES = ['./index.html', './manifest.webmanifest',
  './assets/icon-180.png', './assets/icon-192.png', './assets/icon-512.png',
  './assets/fonts/Inter.var.woff2', './assets/fonts/Inter-Italic.var.woff2',
  './assets/fonts/Fraunces.v803.woff2', './assets/fonts/Fraunces-Italic.v803.woff2'];
// Build .80: the shell is small now — a reopen waits at most 0.4s (was 0.8s) for the
// network (a 304 on a good link answers inside that); a slower link gets the
// cached shell at once and the fresh one lands in the cache for the
// next open ("A newer build is ready" covers the rest). With no cached
// shell it still waits for the network.
const SHELL_DEADLINE_MS = 400;
const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    // Build .75: precache with cache:'reload' so the HTTP cache can never
    // hand a new worker the previous build's shell, and always skipWaiting —
    // even when a precache file fails — so an installed iOS PWA is never
    // left with the new worker stuck in "waiting" behind the old one.
    // Build .79.3: the page that found this worker usually has just fetched
    // this very build's shell (into the previous build's cache) — reuse that
    // copy instead of downloading the 3MB shell a second time.
    caches.open(SHELL_CACHE)
      .then((cache) => caches.keys().then((keys) => Promise.all(keys.filter((k) => k.indexOf('wardrobe-shell-') === 0 && k !== SHELL_CACHE).map((k) =>
        caches.open(k).then((c) => c.match(SHELL_KEY)).then((hit) => hit ? hit.clone().text().then((t) => (t.indexOf('content="' + WARDROBE_BUILD + '"') !== -1 ? hit : null)) : null)
      ))).then((hits) => {
        const own = hits.filter(Boolean)[0];
        const files = own ? SHELL_FILES.filter((u) => u !== './index.html') : SHELL_FILES;
        return (own ? cache.put(SHELL_KEY, own) : Promise.resolve()).then(() => Promise.all(files.map((u) =>
          // fonts/icons already cached by an older build are copied, not refetched
          caches.match(u).then((m) => m && u !== './index.html' ? cache.put(u, m) : cache.add(new Request(u, { cache: 'reload', priority: 'low' })))
        )));
      }))
      .catch(() => {})
      .then(() => caches.open(CODE_CACHE).then((cc) => Promise.all(CODE_FILES.map((u) => {
        const key = new URL(u, self.registration.scope).toString();
        // .80.3: low priority, so Home's next cut-outs go first on a slow link
        return cc.match(key).then((hit) => hit || fetch(key, { priority: 'low' }).then((res) => { if (res && res.status === 200) return cc.put(key, res); }));
      }))).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  const keep = [SHELL_CACHE, PHOTO_CACHE, ASSET_CACHE, ONBODY_CACHE, DATA_CACHE, CODE_CACHE];
  const live = CODE_FILES.map((u) => new URL(u, self.registration.scope).toString());
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => keep.indexOf(k) === -1).map((k) => caches.delete(k))
    )).then(() => caches.open(CODE_CACHE)).then((cc) => cc.keys().then((reqs) => Promise.all(
      reqs.filter((r) => live.indexOf(r.url) === -1).map((r) => cc.delete(r))
    ))).then(() => caches.open(ASSET_CACHE)).then((cache) =>
      // Prune ?r= cache-buster entries an older build may have stored.
      cache.keys().then((reqs) => Promise.all(
        reqs.filter((r) => new URL(r.url).searchParams.has('r'))
          .map((r) => cache.delete(r))
      ))
    ).then(() => self.clients.claim())
  );
});

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
          if (hit) return hit;
          return fetch(req).then((res) => {
            if (res && res.status === 200) cache.put(req, res.clone());
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
          if (hit) return hit;
          return fetch(req).then((res) => {
            if (res && res.status === 200) cache.put(req, res.clone());
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
  if (d.type !== 'warm-cuts' || !Array.isArray(d.urls)) return;
  event.waitUntil(caches.open(ONBODY_CACHE).then((cache) => Promise.all(d.urls.slice(0, 8).map((u) => {
    let url; try { url = new URL(u, self.registration.scope); } catch (e) { return null; }
    if (url.origin !== self.location.origin || !CUT_RE.test(url.pathname)) return null;
    const key = url.origin + url.pathname;
    return cache.match(key).then((hit) => hit || fetch(key).then((res) => { if (res && res.status === 200) return cache.put(key, res); }).catch(() => {}));
  }))));
});
