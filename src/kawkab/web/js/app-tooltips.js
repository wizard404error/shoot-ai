(function () {
    "use strict";

    var tooltipEl = null;
    var showTimer = null;
    var hideTimer = null;
    var currentTarget = null;

    function getTooltip() {
        if (!tooltipEl) {
            tooltipEl = document.createElement("div");
            tooltipEl.className = "kawkab-tooltip";
            tooltipEl.style.cssText = "position:fixed;z-index:10001;max-width:280px;padding:8px 12px;border-radius:6px;background:#1e293b;color:#f1f5f9;font-size:0.8rem;line-height:1.4;pointer-events:none;opacity:0;transition:opacity 0.2s ease;box-shadow:0 4px 16px rgba(0,0,0,0.4);border:1px solid #334155;";
            document.body.appendChild(tooltipEl);
        }
        return tooltipEl;
    }

    function positionTooltip(el, tip) {
        var rect = el.getBoundingClientRect();
        var tipW = tip.offsetWidth || 200;
        var tipH = tip.offsetHeight || 40;
        var gap = 6;

        var positions = [
            { side: "bottom", x: rect.left + rect.width / 2 - tipW / 2, y: rect.bottom + gap },
            { side: "top", x: rect.left + rect.width / 2 - tipW / 2, y: rect.top - tipH - gap },
            { side: "right", x: rect.right + gap, y: rect.top + rect.height / 2 - tipH / 2 },
            { side: "left", x: rect.left - tipW - gap, y: rect.top + rect.height / 2 - tipH / 2 },
        ];

        var vw = window.innerWidth;
        var vh = window.innerHeight;
        var best = positions[0];
        for (var i = 0; i < positions.length; i++) {
            var p = positions[i];
            if (p.x >= 4 && p.x + tipW <= vw - 4 && p.y >= 4 && p.y + tipH <= vh - 4) {
                best = p;
                break;
            }
        }

        tip.style.left = Math.max(4, Math.min(best.x, vw - tipW - 4)) + "px";
        tip.style.top = Math.max(4, Math.min(best.y, vh - tipH - 4)) + "px";
    }

    function showTooltip(el) {
        if (hideTimer) {
            clearTimeout(hideTimer);
            hideTimer = null;
        }
        if (showTimer) {
            clearTimeout(showTimer);
        }
        showTimer = setTimeout(function () {
            var content = el.getAttribute("data-tooltip");
            if (!content) return;
            currentTarget = el;
            var tip = getTooltip();
            tip.innerHTML = content;
            tip.style.opacity = "1";
            positionTooltip(el, tip);
        }, 300);
    }

    function hideTooltip() {
        if (showTimer) {
            clearTimeout(showTimer);
            showTimer = null;
        }
        if (hideTimer) {
            clearTimeout(hideTimer);
        }
        hideTimer = setTimeout(function () {
            var tip = getTooltip();
            tip.style.opacity = "0";
            currentTarget = null;
        }, 100);
    }

    function initTooltips() {
        document.querySelectorAll("[data-tooltip]").forEach(function (el) {
            el.addEventListener("mouseenter", function () { showTooltip(el); });
            el.addEventListener("mouseleave", hideTooltip);
            el.addEventListener("focus", function () { showTooltip(el); });
            el.addEventListener("blur", hideTooltip);
        });
    }

    window.initTooltips = initTooltips;
    window.reinitTooltips = function () {
        // Remove old listeners by re-initializing
        // (simple approach: just scan and attach)
        document.querySelectorAll("[data-tooltip]").forEach(function (el) {
            // Remove existing listeners by cloning approach not practical;
            // we just attach new ones — duplicates are harmless for mouseenter/mouseleave
            // but we guard with a data attribute to avoid double-binding
            if (el.getAttribute("data-tooltip-bound")) return;
            el.setAttribute("data-tooltip-bound", "1");
            el.addEventListener("mouseenter", function () { showTooltip(el); });
            el.addEventListener("mouseleave", hideTooltip);
            el.addEventListener("focus", function () { showTooltip(el); });
            el.addEventListener("blur", hideTooltip);
        });
    };
    // Also run reinit after a short delay to catch dynamically added elements
    setTimeout(window.reinitTooltips, 500);
})();
