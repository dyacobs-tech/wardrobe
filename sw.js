// Wardrobe — offline cache
// Strategy: app shell network-first (new builds arrive when online, cache
// serves offline); photos under assets/ are content-hashed and immutable,
// so they are cache-first and kept permanently once seen.
const SHELL_CACHE = 'wardrobe-shell-1';
const PHOTO_CACHE = 'wardrobe-photos-1';
const SHELL_FILES = ['./', './index.html', './manifest.webmanifest',
  './assets/icon-180.png', './assets/icon-192.png', './assets/icon-512.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_FILES))
      .then(() => self.skipWaiting())
      .catch(() => {})
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k !== SHELL_CACHE && k !== PHOTO_CACHE)
        .map((k) => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Photos: immutable, cache-first forever.
  if (url.pathname.includes('/assets/')) {
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

  // Pages / shell: network-first so updates land, cache as offline fallback.
  if (req.mode === 'navigate' || url.pathname.endsWith('.html') ||
      url.pathname.endsWith('.webmanifest')) {
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(SHELL_CACHE).then((cache) => cache.put(req, copy));
        return res;
      }).catch(() => caches.match(req).then((hit) => hit || caches.match('./index.html')))
    );
    return;
  }

  // Everything else same-origin: stale-while-revalidate.
  event.respondWith(
    caches.match(req).then((hit) => {
      const network = fetch(req).then((res) => {
        if (res && res.status === 200) {
          const copy = res.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(req, copy));
        }
        return res;
      }).catch(() => hit);
      return hit || network;
    })
  );
});
