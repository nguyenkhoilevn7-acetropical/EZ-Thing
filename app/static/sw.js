/* EZ Thing offline shell: cache key and asset list generated from file contents.
   Only public HTML shells and static assets; NEVER authenticated API, payment,
   mutation or business-specific responses. Network-first avoids stale UI. */
const SHELL = 'ezthing-shell-__EZ_CONTENT_HASH__';
const PRECACHE = __EZ_PRECACHE_ASSETS__;
const SHELL_PAGES = new Set(['/', '/app', '/menu/cafe', '/store/mart',
  '/store/online', '/booking/wellness', '/reserve/cafe']);

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL).then(cache => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key.startsWith('ezthing-shell-') && key !== SHELL)
        .map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin ||
      url.pathname === '/api' || url.pathname.startsWith('/api/') ||
      url.pathname === '/sw.js' || url.pathname === '/manifest.webmanifest') return;
  if (!SHELL_PAGES.has(url.pathname) && !url.pathname.startsWith('/assets/')) return;

  event.respondWith(
    fetch(request).then(response => {
      if (response.ok && (response.type === 'basic' || response.type === 'default')) {
        const copy = response.clone();
        event.waitUntil(
          caches.open(SHELL).then(cache => cache.put(request, copy)).catch(() => {})
        );
      }
      return response;
    }).catch(async () => {
      const cached = await caches.match(request, {
        ignoreSearch: SHELL_PAGES.has(url.pathname)
      });
      return cached || Response.error();
    })
  );
});
