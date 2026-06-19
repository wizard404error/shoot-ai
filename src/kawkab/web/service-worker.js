/* Kawkab AI - Service Worker for PWA support */

const CACHE_NAME = "kawkab-ai-v1";
const STATIC_ASSETS = [
    "index.html",
    "manifest.json",
    "css/main.css",
    "css/accessibility.css",
    "js/app.js",
    "js/kawkab_polish.js",
    "js/calibration_v2.js",
    "js/tactical_sandbox.js",
    "js/kawkab_animations.js",
    "js/qwebchannel.js",
    "vendor/popmotion.min.js",
    "vendor/matter.min.js",
];

/* Install: cache static assets */
self.addEventListener("install", function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

/* Activate: clean old caches */
self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys
                    .filter(function (k) { return k !== CACHE_NAME; })
                    .map(function (k) { return caches.delete(k); })
            );
        })
    );
    self.clients.claim();
});

/* Fetch: network-first, fall back to cache */
self.addEventListener("fetch", function (event) {
    event.respondWith(
        fetch(event.request)
            .then(function (response) {
                return caches.open(CACHE_NAME).then(function (cache) {
                    cache.put(event.request, response.clone());
                    return response;
                });
            })
            .catch(function () {
                return caches.match(event.request);
            })
    );
});
