// Kawkab AI - Keyboard Shortcut HUD
(function() {
    'use strict';

    const shortcuts = [];

    function register(key, description, callback) {
        shortcuts.push({ key, description, callback });
    }

    function showHUD() {
        const existing = document.getElementById('kawkab-hud');
        if (existing) {
            existing.remove();
            return;
        }

        const overlay = document.createElement('div');
        overlay.id = 'kawkab-hud';
        overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:10000;display:flex;align-items:center;justify-content:center;';

        const panel = document.createElement('div');
        panel.style.cssText = 'background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:24px;max-width:600px;width:90%;max-height:80vh;overflow-y:auto;color:#e0e0e0;font-family:monospace;';

        panel.innerHTML = '<h2 style="margin-top:0;font-size:18px;color:#4ecdc4;">Keyboard Shortcuts</h2><table style="width:100%;border-collapse:collapse;">' +
            '<tr><th style="text-align:left;padding:6px 12px;border-bottom:1px solid #333;color:#888;">Key</th><th style="text-align:left;padding:6px 12px;border-bottom:1px solid #333;color:#888;">Action</th></tr>' +
            shortcuts.map(s => '<tr><td style="padding:6px 12px;border-bottom:1px solid #222;font-weight:bold;color:#45b7d1;">' + s.key + '</td><td style="padding:6px 12px;border-bottom:1px solid #222;">' + s.description + '</td></tr>').join('') +
            '</table><p style="margin-top:16px;font-size:12px;color:#666;text-align:center;">Press <kbd>?</kbd> again to close</p>';

        overlay.appendChild(panel);
        document.body.appendChild(overlay);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) overlay.remove();
        });
    }

    // Register built-in shortcuts
    register('?', 'Show this help');
    register('Ctrl+Z', 'Undo');
    register('Ctrl+Shift+Z', 'Redo');
    register('Space', 'Video: Play/Pause');
    register('J', 'Video: -10s');
    register('L', 'Video: +10s');
    register('\u2190', 'Video: -5s');
    register('\u2192', 'Video: +5s');
    register('F', 'Video: Fullscreen');
    register('/', 'Global Search');

    document.addEventListener('keydown', function(e) {
        if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            e.preventDefault();
            showHUD();
        }
    });

    window.KawkabShortcuts = { register, showHUD };
})();
