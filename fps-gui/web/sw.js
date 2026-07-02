/**
 * Face Prompt Studio — Service Worker v3.0
 * PWA オフラインキャッシュ + バックグラウンド同期
 */
const CACHE_NAME = "fps-v3.0.0";
const STATIC_ASSETS = ["/", "/index.html", "/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // API リクエストはキャッシュしない
  if (url.pathname.startsWith("/api") || url.pathname.startsWith("/compile")
      || url.pathname.startsWith("/wildcards") || url.pathname.startsWith("/sessions")
      || url.pathname.startsWith("/marketplace") || url.pathname.startsWith("/translate")) {
    return;
  }
  // 静的アセットはキャッシュファースト
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (!response || response.status !== 200) return response;
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      });
    })
  );
});
