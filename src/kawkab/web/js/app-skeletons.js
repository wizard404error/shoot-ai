/* Kawkab AI — Loading skeleton helpers for initial page load
 * 
 * Shows skeleton placeholders while data is being fetched.
 * https://opencode.ai
 */

(function () {
    'use strict';

    var _skeletonConfigs = [];

    function _createSkeletonHTML(width, height, count) {
        var html = '';
        for (var i = 0; i < count; i++) {
            html += '<div class="skeleton-item" style="width:' + width + ';height:' + height + 'px;margin-bottom:8px;border-radius:6px;background:linear-gradient(90deg,var(--bg-secondary) 25%,var(--bg-hover) 50%,var(--bg-secondary) 75%);background-size:200% 100%;animation:skeleton-shimmer 1.5s infinite;"></div>';
        }
        return html;
    }

    function _injectSkeletonStyles() {
        if (document.getElementById('kawkab-skeleton-styles')) return;
        var style = document.createElement('style');
        style.id = 'kawkab-skeleton-styles';
        style.textContent = '@keyframes skeleton-shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}.skeleton-item{opacity:0.6}.skeleton-container{pointer-events:none}';
        document.head.appendChild(style);
    }

    function KawkabSkeletons() {
        if (window.__kawkabSkeletons) return window.__kawkabSkeletons;
        window.__kawkabSkeletons = this;
        _injectSkeletonStyles();
    }

    KawkabSkeletons.prototype.register = function (containerId, width, height, count) {
        _skeletonConfigs.push({ id: containerId, w: width || '100%', h: height || 20, c: count || 3 });
    };

    KawkabSkeletons.prototype.showAll = function () {
        _skeletonConfigs.forEach(function (cfg) {
            var el = document.getElementById(cfg.id);
            if (!el || el.dataset.skeletonActive === 'true') return;
            el.dataset.skeletonActive = 'true';
            el.dataset.skeletonOriginal = el.innerHTML;
            el.classList.add('skeleton-container');
            el.innerHTML = _createSkeletonHTML(cfg.w, cfg.h, cfg.c);
        });
    };

    KawkabSkeletons.prototype.hideAll = function () {
        _skeletonConfigs.forEach(function (cfg) {
            var el = document.getElementById(cfg.id);
            if (!el || el.dataset.skeletonActive !== 'true') return;
            el.classList.remove('skeleton-container');
            el.innerHTML = el.dataset.skeletonOriginal || '';
            delete el.dataset.skeletonActive;
            delete el.dataset.skeletonOriginal;
        });
    };

    window.KawkabSkeletons = KawkabSkeletons;
})();
