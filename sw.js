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
const WARDROBE_BUILD = '2026-11-19.76';
const SHELL_CACHE = 'wardrobe-shell-' + WARDROBE_BUILD;
const PHOTO_CACHE = 'wardrobe-photos-' + WARDROBE_BUILD;
const ASSET_CACHE = 'wardrobe-assets-' + WARDROBE_BUILD;
// On-body renders (assets/onbody/<content-hash>.webp) are immutable, so
// their cache is versioned on its own and survives build updates; bump
// ONBODY_CACHE only if the render format changes.
const ONBODY_CACHE = 'wardrobe-onbody-v1';
const SHELL_KEY = './index.html';
const SHELL_FILES = ['./index.html', './manifest.webmanifest',
  './assets/icon-180.png', './assets/icon-192.png', './assets/icon-512.png',
  './assets/fonts/Inter.var.woff2', './assets/fonts/Inter-Italic.var.woff2',
  './assets/fonts/Fraunces.var.woff2', './assets/fonts/Fraunces-Italic.var.woff2'];
const SHELL_DEADLINE_MS = 30000;
const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    // Build .75: precache with cache:'reload' so the HTTP cache can never
    // hand a new worker the previous build's shell, and always skipWaiting —
    // even when a precache file fails — so an installed iOS PWA is never
    // left with the new worker stuck in "waiting" behind the old one.
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_FILES.map((u) => new Request(u, { cache: 'reload' }))))
      .catch(() => {})
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  const keep = [SHELL_CACHE, PHOTO_CACHE, ASSET_CACHE, ONBODY_CACHE];
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => keep.indexOf(k) === -1).map((k) => caches.delete(k))
    )).then(() => caches.open(ASSET_CACHE)).then((cache) =>
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

  // On-body renders: content-hashed, cache-first in their own cache.
  // The manifest beside them stays network-first (below).
  if (url.pathname.includes('/assets/onbody/') && url.pathname.endsWith('.webp')) {
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
        const deadline = new Promise((resolve) => setTimeout(resolve, SHELL_DEADLINE_MS, null));
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
