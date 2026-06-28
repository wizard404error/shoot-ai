/* Kawkab AI — UX enhancements
 * 
 * Confirmation dialogs, keyboard navigation, empty state messages.
 */

(function () {
    'use strict';

    // --- Confirmation Dialog ---
    function showConfirmDialog(message, onConfirm, onCancel) {
        // Check if modal container exists, create one if not
        var overlay = document.getElementById('kawkab-confirm-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'kawkab-confirm-overlay';
            overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;';
            overlay.innerHTML = '<div id="kawkab-confirm-dialog" style="background:var(--bg-primary,#1e293b);border:1px solid var(--border-color,#334155);border-radius:12px;padding:24px;max-width:400px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.5);">' +
                '<p id="kawkab-confirm-message" style="color:var(--text-primary,#f1f5f9);font-size:15px;line-height:1.5;margin:0 0 20px 0;"></p>' +
                '<div style="display:flex;gap:10px;justify-content:flex-end;">' +
                '<button id="kawkab-confirm-cancel" style="padding:8px 20px;border:1px solid var(--border-color,#334155);border-radius:8px;background:transparent;color:var(--text-primary,#f1f5f9);cursor:pointer;">Cancel</button>' +
                '<button id="kawkab-confirm-ok" style="padding:8px 20px;border:none;border-radius:8px;background:#ef4444;color:white;cursor:pointer;font-weight:600;">Confirm</button>' +
                '</div></div>';
            document.body.appendChild(overlay);
        }
        document.getElementById('kawkab-confirm-message').textContent = message;
        overlay.classList.remove('hidden');
        
        var okBtn = document.getElementById('kawkab-confirm-ok');
        var cancelBtn = document.getElementById('kawkab-confirm-cancel');
        
        var cleanup = function () {
            overlay.classList.add('hidden');
            okBtn.removeEventListener('click', onOk);
            cancelBtn.removeEventListener('click', onCancelClick);
            document.removeEventListener('keydown', onKey);
        };
        
        var onOk = function () {
            cleanup();
            if (typeof onConfirm === 'function') onConfirm();
        };
        
        var onCancelClick = function () {
            cleanup();
            if (typeof onCancel === 'function') onCancel();
        };
        
        var onKey = function (e) {
            if (e.key === 'Escape') {
                onCancelClick();
            } else if (e.key === 'Enter') {
                onOk();
            }
        };
        
        okBtn.addEventListener('click', onOk);
        cancelBtn.addEventListener('click', onCancelClick);
        document.addEventListener('keydown', onKey);
        
        // Focus trap
        setTimeout(function () { okBtn.focus(); }, 50);
    }

    // --- Empty State Helper ---
    function showEmptyState(containerId, message, icon) {
        var el = document.getElementById(containerId);
        if (!el) return;
        icon = icon || '\u26BD';  // football emoji
        el.innerHTML = '<div style="text-align:center;padding:40px 20px;color:var(--text-muted,#7e8ea8);">' +
            '<div style="font-size:48px;margin-bottom:12px;opacity:0.5;">' + icon + '</div>' +
            '<p style="margin:0;font-size:14px;">' + (message || 'No data available') + '</p></div>';
    }

    // --- Keyboard Navigation Init ---
    function initKeyboardNav() {
        // Collapsible cards: Enter/Space to toggle
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                var target = e.target;
                if (target && target.classList.contains('collapsible-header')) {
                    e.preventDefault();
                    target.click();
                }
            }
            
            // Escape to close modals
            if (e.key === 'Escape') {
                var modals = document.querySelectorAll('.modal-overlay:not(.hidden)');
                modals.forEach(function (m) {
                    var closeBtn = m.querySelector('.modal-close');
                    if (closeBtn) closeBtn.click();
                });
            }
        });
        
        // Focus trap in modals
        document.addEventListener('keydown', function (e) {
            if (e.key !== 'Tab') return;
            var modal = e.target.closest('.modal-overlay, .modal');
            if (!modal || modal.classList.contains('hidden')) return;
            var focusable = modal.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])');
            if (focusable.length === 0) return;
            var first = focusable[0];
            var last = focusable[focusable.length - 1];
            if (e.shiftKey) {
                if (e.target === first) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (e.target === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        });
    }

    // Export
    window.showConfirmDialog = showConfirmDialog;
    window.showEmptyState = showEmptyState;
    window.initKeyboardNav = initKeyboardNav;

    // Init on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initKeyboardNav();
        });
    } else {
        initKeyboardNav();
    }
})();
