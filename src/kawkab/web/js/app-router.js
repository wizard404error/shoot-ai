/* Kawkab AI — SPA hash-based router
 * 
 * Manages navigation between application sections using URL hash.
 * Supports show/hide of sections, history state, and init hooks.
 */

(function () {
    'use strict';

    var _routes = {};
    var _currentRoute = null;
    var _prevRoute = null;

    function KawkabRouter() {
        // Singleton
        if (window.__kawkabRouter) return window.__kawkabRouter;
        window.__kawkabRouter = this;
    }

    KawkabRouter.prototype.register = function (hash, sectionId, onActivate) {
        _routes[hash] = { sectionId: sectionId, onActivate: onActivate || null };
    };

    KawkabRouter.prototype.navigate = function (hash, pushState) {
        if (pushState !== false) {
            window.location.hash = hash;
        }
        this._activate(hash);
    };

    KawkabRouter.prototype._activate = function (hash) {
        var route = _routes[hash];
        if (!route) return;

        _prevRoute = _currentRoute;
        _currentRoute = hash;

        // Hide all registered sections
        for (var h in _routes) {
            var el = document.getElementById(_routes[h].sectionId);
            if (el) {
                if (h === hash) {
                    el.classList.remove('hidden');
                    if (route.onActivate) route.onActivate();
                } else {
                    el.classList.add('hidden');
                }
            }
        }
    };

    KawkabRouter.prototype.getCurrentRoute = function () {
        return _currentRoute;
    };

    KawkabRouter.prototype.getPreviousRoute = function () {
        return _prevRoute;
    };

    // Listen for hash changes
    window.addEventListener('hashchange', function () {
        var hash = window.location.hash.replace('#', '') || 'dashboard';
        if (window.__kawkabRouter) {
            window.__kawkabRouter._activate(hash);
            _updateNavTabs(hash);
        }
    });

    function _updateNavTabs(hash) {
        var tabs = document.querySelectorAll('.nav-tab');
        tabs.forEach(function (t) {
            t.classList.toggle('active', t.dataset.route === hash);
        });
    }

    // Auto-init on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            var hash = window.location.hash.replace('#', '') || 'dashboard';
            if (window.__kawkabRouter) {
                window.__kawkabRouter._activate(hash);
                _updateNavTabs(hash);
            }
        });
    } else {
        var hash = window.location.hash.replace('#', '') || 'dashboard';
        if (window.__kawkabRouter) {
            window.__kawkabRouter._activate(hash);
            _updateNavTabs(hash);
        }
    }

    window.KawkabRouter = KawkabRouter;
})();
