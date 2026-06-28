/* Kawkab AI — UI performance utilities
 * 
 * Passive event listeners, memoized DOM queries, and throttled handlers.
 */

(function () {
    'use strict';

    // --- Memoized DOM queries ---
    var _domCache = {};
    
    function $(id) {
        if (!_domCache[id]) {
            _domCache[id] = document.getElementById(id);
        }
        return _domCache[id];
    }

    // --- Throttle ---
    function throttle(fn, delay) {
        var last = 0;
        var timer = null;
        return function () {
            var now = Date.now();
            var args = arguments;
            var context = this;
            if (now - last >= delay) {
                last = now;
                fn.apply(context, args);
            } else {
                if (timer) clearTimeout(timer);
                timer = setTimeout(function () {
                    last = Date.now();
                    fn.apply(context, args);
                }, delay - (now - last));
            }
        };
    }

    // --- Debounce ---
    function debounce(fn, delay) {
        var timer = null;
        return function () {
            var args = arguments;
            var context = this;
            if (timer) clearTimeout(timer);
            timer = setTimeout(function () {
                fn.apply(context, args);
            }, delay);
        };
    }

    // --- Passive event listener helper ---
    function addPassiveListener(el, event, handler, options) {
        if (!el) return;
        var opts = options || {};
        opts.passive = true;
        el.addEventListener(event, handler, opts);
    }

    // --- Apply passive listeners to common events ---
    function initPassiveListeners() {
        // Touch events
        addPassiveListener(document, 'touchstart', function () {}, { passive: true });
        addPassiveListener(document, 'touchmove', function () {}, { passive: true });
        addPassiveListener(document, 'wheel', function () {}, { passive: true });
        
        // Scroll events on canvases
        document.querySelectorAll('canvas').forEach(function (c) {
            addPassiveListener(c, 'wheel', function () {}, { passive: true });
        });
    }

    // --- Apply throttled scroll handler ---
    function initThrottledScroll() {
        var throttledScroll = throttle(function () {
            // Any scroll-dependent updates can go here
        }, 100);
        window.addEventListener('scroll', throttledScroll, { passive: true });
    }

    // --- Apply throttled resize handler ---
    function initThrottledResize(callback) {
        var throttledResize = throttle(function () {
            // Clear DOM cache on resize (elements may be repositioned)
            _domCache = {};
            if (typeof callback === 'function') callback();
        }, 200);
        window.addEventListener('resize', throttledResize, { passive: true });
    }

    // Export
    window.$K = $;
    window.throttle = throttle;
    window.debounce = debounce;
    window.initPassiveListeners = initPassiveListeners;
    window.initThrottledScroll = initThrottledScroll;
    window.initThrottledResize = initThrottledResize;

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initPassiveListeners();
            initThrottledScroll();
            initThrottledResize();
        });
    } else {
        initPassiveListeners();
        initThrottledScroll();
        initThrottledResize();
    }
})();
