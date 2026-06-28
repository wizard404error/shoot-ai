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
        "Space": { key: "Space", label: "Video: Play/Pause" },
        "J": { key: "J", label: "Video: Rewind 10s" },
        "L": { key: "L", label: "Video: Forward 10s" },
        "K": { key: "K", label: "Video: Pause" },
        "ArrowLeft": { key: "←", label: "Video: Rewind 5s" },
        "ArrowRight": { key: "→", label: "Video: Forward 5s" },
        "F": { key: "F", label: "Video: Fullscreen" },
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

    var _kawkabLocaleCache = {};

    function loadLocale(lang) {
        if (_kawkabLocaleCache[lang]) return Promise.resolve(_kawkabLocaleCache[lang]);
        var url = "locales/" + lang + ".json";
        return fetch(url)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                _kawkabLocaleCache[lang] = data;
                return data;
            })
            .catch(function () {
                return null;
            });
    }

    function setLang(lang) {
        if (lang !== "en" && lang !== "ar") return;
        var html = document.documentElement;
        html.setAttribute("lang", lang);
        html.setAttribute("dir", lang === "ar" ? "rtl" : "ltr");
        try {
            localStorage.setItem(STORAGE_KEY, lang);
        } catch (e) {}
        loadLocale(lang).then(function (dict) {
            if (!dict) {
                dict = _kawkabFallbackDict(lang);
            }
            document.querySelectorAll("[data-i18n]").forEach(function (el) {
                var key = el.getAttribute("data-i18n");
                if (dict[key] !== undefined) {
                    el.textContent = dict[key];
                }
            });
            // Update placeholders
            document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
                var key = el.getAttribute("data-i18n-placeholder");
                if (dict[key] !== undefined) {
                    el.setAttribute("placeholder", dict[key]);
                }
            });
            // Update option labels
            document.querySelectorAll("option[data-i18n]").forEach(function (el) {
                var key = el.getAttribute("data-i18n");
                if (dict[key] !== undefined) {
                    el.textContent = dict[key];
                }
            });
            // Update document title
            if (dict["appTitle"]) {
                document.title = dict["appTitle"];
            }
            // Update theme toggle button tooltip
            var themeBtn = document.getElementById("theme-toggle");
            if (themeBtn) {
                var isLight = html.getAttribute("data-theme") === "light";
                themeBtn.title = isLight ? "Switch to dark mode" : "Switch to light mode";
            }
        });
        announce(lang === "ar" ? "تم التبديل إلى العربية" : "Switched to English");
    }

    function _kawkabFallbackDict(lang) {
        if (lang === "ar") {
            return {
                "app_subtitle": "مدرب كرة القدم",
                "tab_analyze": "تحليل",
                "tab_players": "اللاعبون",
                "tab_compare": "مقارنة",
                "tab_export": "تصدير",
                "btn_analyze": "تحليل الفيديو",
                "btn_calibrate": "معايرة الملعب",
                "btn_settings": "الإعدادات",
                "btn_help": "المساعدة",
                "btn_cancel": "إلغاء",
                "btn_confirm": "تأكيد",
                "btn_save": "حفظ",
                "btn_load": "تحميل",
                "status_ready": "جاهز",
                "status_processing": "جارٍ المعالجة",
                "status_complete": "اكتمل التحليل",
                "status_error": "حدث خطأ",
                "status_idle": "خامل",
                "metric_distance": "المسافة",
                "metric_sprints": "الركضات السريعة",
                "metric_passes": "التمريرات",
                "metric_shots": "التسديدات",
                "metric_possession": "الاستحواذ",
                "metric_xg": "الأهداف المتوقعة",
                "metric_goals": "الأهداف",
                "metric_hir": "الجري عالي الشدة",
                "section_pro": "التحليل الاحترافي",
                "section_realtime": "الوضع المباشر",
                "section_psychology": "علم النفس الرياضي",
                "section_weather": "الطقس",
                "section_rules": "قوانين اللعبة",
                "section_cards": "الكروت",
                "section_pose": "تحليل الوضعية",
                "section_mujoco": "محاكاة الكرة",
                "section_fluidx3d": "محاكاة الموائع",
                "section_setpiece": "الكرات الثابتة",
                "section_goalkeeper": "حارس المرمى",
                "section_substitution": "التبديلات",
                "section_possession": "الاستحواذ",
                "alert_shot": "تسديدة",
                "alert_goal": "هدف",
                "alert_offside": "تسلل",
                "alert_card": "كرت",
                "alert_tackle": "تدخل",
                "msg_processing_video": "جارٍ معالجة الفيديو",
                "msg_no_video": "الرجاء اختيار ملف فيديو",
                "msg_calibration_required": "يجب إجراء المعايرة أولاً",
            "msg_saved": "تم الحفظ",
            "msg_loaded": "تم التحميل",
            "btn_compare": "مقارنة",
            "kbLoading": "قاعدة المعرفة: جاري التحميل...",
            "appTitle": "Kawkab AI - تحليلات مدرب كرة القدم",
            "dashboardTitle": "📊 لوحة التحكم",
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
            "btn_settings": "Settings",
            "btn_help": "Help",
            "btn_cancel": "Cancel",
            "btn_confirm": "Confirm",
            "btn_save": "Save",
            "btn_load": "Load",
            "status_ready": "Ready",
            "status_processing": "Processing",
            "status_complete": "Analysis complete",
            "status_error": "An error occurred",
            "status_idle": "Idle",
            "metric_distance": "Distance",
            "metric_sprints": "Sprints",
            "metric_passes": "Passes",
            "metric_shots": "Shots",
            "metric_possession": "Possession",
            "metric_xg": "xG",
            "metric_goals": "Goals",
            "metric_hir": "HIR",
            "section_pro": "Pro Analytics",
            "section_realtime": "Real-Time Mode",
            "section_psychology": "Sports Psychology",
            "section_weather": "Weather",
            "section_rules": "Game Rules",
            "section_cards": "Cards",
            "section_pose": "Pose Analysis",
            "section_mujoco": "Ball Simulation",
            "section_fluidx3d": "Fluid Simulation",
            "section_setpiece": "Set Pieces",
            "section_goalkeeper": "Goalkeeper",
            "section_substitution": "Substitutions",
            "section_possession": "Possession",
            "alert_shot": "Shot",
            "alert_goal": "Goal",
            "alert_offside": "Offside",
            "alert_card": "Card",
            "alert_tackle": "Tackle",
            "msg_processing_video": "Processing video",
            "msg_no_video": "Please select a video file",
            "msg_calibration_required": "Calibration required first",
            "msg_saved": "Saved",
            "msg_loaded": "Loaded",
            "btn_compare": "Compare",
            "kbLoading": "Knowledge Base: Loading...",
            "appTitle": "Kawkab AI - Football Coach Analytics",
            "dashboardTitle": "📊 Dashboard",
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
        const lang = detectInitialLang();
        setLang(lang);
        const selector = document.getElementById("language-selector");
        if (selector && selector.value !== lang) {
            selector.value = lang;
        }
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
