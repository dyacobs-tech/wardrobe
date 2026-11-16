// Wardrobe — offline cache
// Strategy
//  · App shell (the page): network-first with a short deadline, so new
//    builds arrive when online and a weak signal falls back to the cached
//    copy instead of hanging. Only a good (200) response ever replaces the
//    cached shell, and it is always stored under one key.
//  · Photos under assets/photos/ are content-hashed and immutable:
//    cache-first, kept once seen.
//  · Everything else on this origin (icons, the wardrobe-look renders, the
//    manifest): network-first. These files keep their names when they
//    change, so a cached copy must never win over a fresh one — the
//    network copy is served (and re-cached) whenever it answers, and
//    the cache is only the offline fallback. Web fonts keep
//    stale-while-revalidate: their URLs are versioned by the provider.
const SHELL_CACHE = 'wardrobe-shell-3';
const PHOTO_CACHE = 'wardrobe-photos-1';
const ASSET_CACHE = 'wardrobe-assets-1';
const SHELL_KEY = './index.html';
const SHELL_FILES = ['./index.html', './manifest.webmanifest',
  './assets/icon-180.png', './assets/icon-192.png', './assets/icon-512.png'];
const SHELL_DEADLINE_MS = 4000;
const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_FILES))
      .then(() => self.skipWaiting())
      .catch(() => {})
  );
});

self.addEventListener('activate', (event) => {
  const keep = [SHELL_CACHE, PHOTO_CACHE, ASSET_CACHE];
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => keep.indexOf(k) === -1).map((k) => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

function networkFirst(event, cacheName) {
  const req = event.request;
  event.respondWith(
    fetch(req, { cache: 'no-cache' }).then((res) => {
      // Opaque (cross-origin) responses report status 0; keep those too.
      if (res && (res.status === 200 || res.type === 'opaque')) {
        const copy = res.clone();
        event.waitUntil(caches.open(cacheName).then((cache) => cache.put(req, copy)));
      }
      return res;
    }).catch(() =>
      caches.open(cacheName).then((cache) => cache.match(req)).then((hit) => {
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
  const isShell = req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('.html');
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
