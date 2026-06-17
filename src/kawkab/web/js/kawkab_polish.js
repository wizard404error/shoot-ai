/* Kawkab AI — UX polish and accessibility utilities
 *
 * Loaded after app.js. Provides:
 *  - ARIA live-region announcer for screen readers
 *  - Keyboard shortcuts (g=gallery, /=search, ?=help, Esc=close)
 *  - RTL language toggle
 *  - Focus management helpers
 *  - prefers-reduced-motion detection
 *
 * Public API: window.KawkabPolish.{announce, setLang, on}
 */

(function () {
    "use strict";

    const STORAGE_KEY = "kawkab_lang";
    const SHORTCUTS = {
        "g": { key: "g", label: "Gallery" },
        "/": { key: "/", label: "Focus search" },
        "?": { key: "?", label: "Show keyboard shortcuts", shift: true },
        "Escape": { key: "Escape", label: "Close dialog" },
    };

    function createLiveRegion() {
        let region = document.getElementById("kawkab-live-region");
        if (region) return region;
        region = document.createElement("div");
        region.id = "kawkab-live-region";
        region.className = "sr-only";
        region.setAttribute("aria-live", "polite");
        region.setAttribute("aria-atomic", "true");
        document.body.appendChild(region);
        return region;
    }

    function announce(message, priority) {
        const region = createLiveRegion();
        region.setAttribute("aria-live", priority === "assertive" ? "assertive" : "polite");
        region.textContent = "";
        setTimeout(function () { region.textContent = message; }, 50);
    }

    function setLang(lang) {
        if (lang !== "en" && lang !== "ar") return;
        const html = document.documentElement;
        html.setAttribute("lang", lang);
        html.setAttribute("dir", lang === "ar" ? "rtl" : "ltr");
        try {
            localStorage.setItem(STORAGE_KEY, lang);
        } catch (e) {}
        const dict = getDict(lang);
        document.querySelectorAll("[data-i18n]").forEach(function (el) {
            const key = el.getAttribute("data-i18n");
            if (dict[key] !== undefined) {
                el.textContent = dict[key];
            }
        });
        announce(lang === "ar" ? "تم التبديل إلى العربية" : "Switched to English");
    }

    function getDict(lang) {
        if (lang === "ar") {
            return {
                "app_subtitle": "مدرب كرة القدم",
                "tab_analyze": "تحليل",
                "tab_players": "اللاعبون",
                "tab_compare": "مقارنة",
                "tab_export": "تصدير",
                "btn_analyze": "تحليل الفيديو",
                "btn_calibrate": "معايرة الملعب",
                "status_ready": "جاهز",
                "status_processing": "جارٍ المعالجة",
                "status_complete": "اكتمل التحليل",
            };
        }
        return {
            "app_subtitle": "Football Coach",
            "tab_analyze": "Analyze",
            "tab_players": "Players",
            "tab_compare": "Compare",
            "tab_export": "Export",
            "btn_analyze": "Analyze Video",
            "btn_calibrate": "Calibrate Pitch",
            "status_ready": "Ready",
            "status_processing": "Processing",
            "status_complete": "Analysis complete",
        };
    }

    function detectInitialLang() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored === "ar" || stored === "en") return stored;
        } catch (e) {}
        const params = new URLSearchParams(window.location.search);
        if (params.get("lang") === "ar" || params.get("lang") === "en") {
            return params.get("lang");
        }
        const browser = (navigator.language || "en").toLowerCase();
        return browser.startsWith("ar") ? "ar" : "en";
    }

    function showShortcutHelp() {
        const lines = Object.values(SHORTCUTS).map(function (s) {
            return s.shift ? "Shift + " + s.key : s.key;
        });
        const msg = "Shortcuts: " + lines.join(", ");
        announce(msg, "assertive");
        alert(msg);
    }

    function onKeydown(e) {
        if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) {
            return;
        }
        if (e.ctrlKey || e.metaKey || e.altKey) return;
        if (e.key === "?") {
            e.preventDefault();
            showShortcutHelp();
            return;
        }
        if (e.key === "/") {
            e.preventDefault();
            const search = document.querySelector("[data-search-input]");
            if (search) search.focus();
            return;
        }
        if (e.key === "g") {
            const gallery = document.querySelector("[data-tab='gallery']");
            if (gallery) gallery.click();
            announce("Opening gallery");
            return;
        }
        if (e.key === "Escape") {
            const open = document.querySelector("[data-open='true']");
            if (open) {
                open.setAttribute("data-open", "false");
                announce("Closed");
            }
            return;
        }
    }

    function prefersReducedMotion() {
        return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    function init() {
        createLiveRegion();
        setLang(detectInitialLang());
        document.addEventListener("keydown", onKeydown);
        window.__kawkabPrefersReducedMotion = prefersReducedMotion();
        if (window.matchMedia) {
            window.matchMedia("(prefers-reduced-motion: reduce)").addEventListener("change", function (e) {
                window.__kawkabPrefersReducedMotion = e.matches;
            });
        }
    }

    window.KawkabPolish = {
        announce: announce,
        setLang: setLang,
        prefersReducedMotion: prefersReducedMotion,
        showShortcutHelp: showShortcutHelp,
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
