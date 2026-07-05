(function() {
    'use strict';

    window.KawkabErrorBoundary = {
        _sections: {},

        wrap: function(sectionId, renderFn, fallbackHtml) {
            var self = this;
            this._sections[sectionId] = { renderFn: renderFn, fallbackHtml: fallbackHtml || '<p class="error-message">Something went wrong loading this section.</p>' };
            return function() {
                try {
                    return renderFn.apply(this, arguments);
                } catch(e) {
                    console.error('Error in section ' + sectionId + ':', e);
                    var el = document.getElementById(sectionId);
                    if (el) {
                        el.innerHTML = self._sections[sectionId].fallbackHtml;
                        self.showRetry(sectionId);
                    }
                }
            };
        },

        showRetry: function(sectionId) {
            var el = document.getElementById(sectionId);
            if (!el) return;
            var btn = document.createElement('button');
            btn.className = 'retry-btn';
            btn.textContent = String.fromCharCode(8635) + ' Retry';
            btn.onclick = function() {
                var section = window.KawkabErrorBoundary._sections[sectionId];
                if (section) section.renderFn();
            };
            el.appendChild(btn);
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        var sections = ['dashboard-kpis', 'results-section', 'report-section',
                       'coding-section', 'review-section', 'squad-section',
                       'tactics-section', 'ai-section', 'scout-section'];
        sections.forEach(function(id) {
            var el = document.getElementById(id);
        });
    });
})();
