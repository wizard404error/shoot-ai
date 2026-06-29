/* Kawkab AI - Service Worker v2 with offline-first strategy */

var CACHE_NAME = "kawkab-ai-v2";
var STATIC_ASSETS = [
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
    "js/utils.js",
    "js/app-perf.js",
    "js/app-ux.js",
    "js/app-router.js",
    "js/app-skeletons.js",
    "vendor/popmotion.min.js",
    "vendor/matter.min.js",
    "icons/icon-192.svg",
    "icons/icon-512.svg",
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

/* Activate: clean old caches + take control */
self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys
                    .filter(function (k) { return k !== CACHE_NAME; })
                    .map(function (k) { return caches.delete(k); })
            );
        }).then(function () {
            return self.clients.claim();
        })
    );
});

/* Fetch: cache-first for static, network-first for API calls */
self.addEventListener("fetch", function (event) {
    var url = new URL(event.request.url);

    // Bridge API calls — network-only (no cache)
    if (url.pathname.indexOf("qwc") >= 0 || event.request.method === "POST") {
        return;
    }

    // Static assets — cache-first
    if (STATIC_ASSETS.indexOf(url.pathname.split("/").pop()) >= 0) {
        event.respondWith(
            caches.match(event.request).then(function (cached) {
                return cached || fetch(event.request).then(function (response) {
                    return caches.open(CACHE_NAME).then(function (cache) {
                        cache.put(event.request, response.clone());
                        return response;
                    });
                });
            })
        );
        return;
    }

    // Everything else — network-first, fallback to cache
    event.respondWith(
        fetch(event.request).then(function (response) {
            return caches.open(CACHE_NAME).then(function (cache) {
                cache.put(event.request, response.clone());
                return response;
            });
        }).catch(function () {
            return caches.match(event.request);
        })
    );
});

/* Listen for messages (e.g., skip waiting) */
self.addEventListener("message", function (event) {
    if (event.data && event.data.action === "skipWaiting") {
        self.skipWaiting();
    }
});
