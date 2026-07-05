(function () {
  'use strict';

  const DB_NAME = 'KawkabOfflineDB';
  const DB_VERSION = 1;
  const STORES = ['events', 'tags', 'matches', 'pending_sync'];

  function openDB() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        STORES.forEach(function (store) {
          if (!db.objectStoreNames.contains(store)) {
            db.createObjectStore(store, { keyPath: 'id', autoIncrement: true });
          }
        });
      };
      req.onsuccess = function (e) { resolve(e.target.result); };
      req.onerror = function (e) { reject(e.target.error); };
    });
  }

  function getStore(db, storeName, mode) {
    var tx = db.transaction(storeName, mode);
    return tx.objectStore(storeName);
  }

  window.KawkabOffline = {
    // --- Matches ---
    saveMatches: function (matches) {
      return openDB().then(function (db) {
        var store = getStore(db, 'matches', 'readwrite');
        return new Promise(function (resolve, reject) {
          matches.forEach(function (m) {
            var data = typeof m.id !== 'undefined' ? m : { id: Date.now() + Math.random(), data: m };
            store.put(data);
          });
          db.close();
          resolve(matches.length);
        });
      });
    },

    getMatches: function () {
      return openDB().then(function (db) {
        var store = getStore(db, 'matches', 'readonly');
        return new Promise(function (resolve, reject) {
          var req = store.getAll();
          req.onsuccess = function () { resolve(req.result || []); };
          req.onerror = function () { reject(req.error); };
          db.close();
        });
      });
    },

    // --- Sync Queue ---
    enqueueSync: function (action) {
      return openDB().then(function (db) {
        var store = getStore(db, 'pending_sync', 'readwrite');
        return new Promise(function (resolve, reject) {
          var record = {
            id: Date.now() + '_' + Math.random().toString(36).slice(2, 9),
            action: action,
            created: Date.now()
          };
          var req = store.put(record);
          req.onsuccess = function () { resolve(record.id); };
          req.onerror = function () { reject(req.error); };
          db.close();
        });
      });
    },

    getPendingSync: function () {
      return openDB().then(function (db) {
        var store = getStore(db, 'pending_sync', 'readonly');
        return new Promise(function (resolve, reject) {
          var req = store.getAll();
          req.onsuccess = function () { resolve(req.result || []); };
          req.onerror = function () { reject(req.error); };
          db.close();
        });
      });
    },

    processSyncQueue: function () {
      var self = this;
      return self.getPendingSync().then(function (pending) {
        if (pending.length === 0) { return 0; }
        var processed = 0;
        return openDB().then(function (db) {
          var store = getStore(db, 'pending_sync', 'readwrite');
          return new Promise(function (resolve, reject) {
            pending.forEach(function (record) {
              store.delete(record.id);
              processed++;
            });
            db.close();
            resolve(processed);
          });
        });
      });
    },

    initSyncOnReconnect: function () {
      var self = this;
      window.addEventListener('online', function () {
        self.processSyncQueue().then(function (count) {
          if (count > 0) {
            console.log('[KawkabOffline] Synced ' + count + ' pending actions');
          }
        });
      });
    }
  };
})();
