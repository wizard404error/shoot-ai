/* Kawkab AI — Core initialization, theme, i18n setup (ES module) */

import { showToast } from './ui.js';

let bridge = null;
let currentLanguage = 'en';
let currentMatchId = null;
window.__kawkab = window.__kawkab || {};
Object.defineProperty(window.__kawkab, 'currentMatchId', { get: function() { return currentMatchId; } });

export function setCurrentMatchId(id) { currentMatchId = id; }
export function getCurrentMatchId() { return currentMatchId; }
export function getBridge() { return bridge; }
export function setBridge(b) { bridge = b; }
export function getCurrentLanguage() { return currentLanguage; }

export function getStoredTheme() {
    try { return localStorage.getItem('kawkab_theme'); } catch(e) { return null; }
}
export function setStoredTheme(t) {
    try { localStorage.setItem('kawkab_theme', t); } catch(e) {}
}

export function applyTheme(theme) {
    var html = document.documentElement;
    if (theme === 'light') {
        html.setAttribute('data-theme', 'light');
    } else {
        html.setAttribute('data-theme', 'dark');
    }
    var btn = document.getElementById('theme-toggle');
    if (btn) {
        btn.textContent = theme === 'light' ? '☀️' : '🌙';
        btn.title = theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode';
    }
}

export function toggleTheme() {
    var current = getStoredTheme();
    var next = current === 'light' ? 'dark' : 'light';
    setStoredTheme(next);
    applyTheme(next);
}

export function initTheme() {
    var stored = getStoredTheme();
    if (stored) applyTheme(stored);
    var btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', toggleTheme);
}

export function initLanguageSelector() {
    var sel = document.getElementById('language-selector');
    if (!sel) return;
    sel.addEventListener('change', function() {
        currentLanguage = sel.value;
        if (window.KawkabPolish && window.KawkabPolish.setLang) {
            window.KawkabPolish.setLang(currentLanguage);
        }
        if (window.setLanguage && typeof window.setLanguage === 'function') {
            window.setLanguage(currentLanguage);
        }
    });
}

export function startup() {
    initTheme();
    initLanguageSelector();
    var loading = document.getElementById('startup-loading');
    if (loading) loading.style.display = 'none';
}
