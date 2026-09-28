const CACHE_NAME = "billing-manager-v1";
const ASSETS = [
  "/",
  "/dashboard",
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)).catch(() => undefined));
});

self.addEventListener("fetch", event => {
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
