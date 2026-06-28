var CACHE = 'KAWKAB_CACHE_V1';
var STATIC_ASSETS = [
  'css/main.css',
  'js/kawkab_polish.js',
  'js/app.js',
  'offline.html'
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE && k.startsWith('KAWKAB_CACHE_'); })
          .map(function (k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function (event) {
  var url = new URL(event.request.url);
  var isStatic = /\.(css|js|png|jpg|jpeg|gif|svg|woff2?|ttf|eot|ico)$/i.test(url.pathname);
  var isApi = url.pathname.indexOf('/bridge/') !== -1 || url.pathname.indexOf('/api/') !== -1 || url.pathname.indexOf('/data/') !== -1;
  var isNavigation = event.request.mode === 'navigate';

  if (isStatic) {
    event.respondWith(
      caches.match(event.request).then(function (cached) {
        return cached || fetch(event.request).then(function (response) {
          return caches.open(CACHE).then(function (cache) {
            cache.put(event.request, response.clone());
            return response;
          });
        });
      })
    );
    return;
  }

  if (isApi) {
    event.respondWith(
      fetch(event.request).then(function (response) {
        return caches.open(CACHE).then(function (cache) {
          cache.put(event.request, response.clone());
          return response;
        });
      }).catch(function () {
        return caches.match(event.request);
      })
    );
    return;
  }

  if (isNavigation) {
    event.respondWith(
      fetch(event.request).catch(function () {
        return caches.match('offline.html');
      })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(function (cached) {
      return cached || fetch(event.request);
    })
  );
});
