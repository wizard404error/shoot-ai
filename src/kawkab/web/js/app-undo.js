// Kawkab AI - Undo/Redo Manager
(function() {
    'use strict';

    class UndoManager {
        constructor(maxStack = 50) {
            this.undoStack = [];
            this.redoStack = [];
            this.maxStack = maxStack;
            this.isUndoing = false;
        }

        push(action) {
            if (this.isUndoing) return;
            this.undoStack.push(action);
            this.redoStack = [];
            if (this.undoStack.length > this.maxStack) {
                this.undoStack.shift();
            }
        }

        undo() {
            if (this.undoStack.length === 0) return null;
            this.isUndoing = true;
            const action = this.undoStack.pop();
            try {
                if (typeof action.undo === 'function') action.undo();
                this.redoStack.push(action);
            } catch (e) {
                console.error('Undo failed:', e);
            }
            this.isUndoing = false;
            return action;
        }

        redo() {
            if (this.redoStack.length === 0) return null;
            const action = this.redoStack.pop();
            try {
                if (typeof action.redo === 'function') action.redo();
                this.undoStack.push(action);
            } catch (e) {
                console.error('Redo failed:', e);
            }
            return action;
        }

        clear() {
            this.undoStack = [];
            this.redoStack = [];
        }
    }

    window.KawkabUndo = new UndoManager();

    // Register keyboard shortcut
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
            e.preventDefault();
            window.KawkabUndo.undo();
            if (window.showToast) window.showToast('Undo', 'info');
        }
        if ((e.ctrlKey || e.metaKey) && e.key === 'z' && e.shiftKey) {
            e.preventDefault();
            window.KawkabUndo.redo();
            if (window.showToast) window.showToast('Redo', 'info');
        }
        if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
            e.preventDefault();
            window.KawkabUndo.redo();
            if (window.showToast) window.showToast('Redo', 'info');
        }
    });
})();
