// Kawkab AI - UI animation wrappers around Popmotion
// Used for: score counters, timeline progress, smooth transitions
// Requires: popmotion.min.js loaded before app.js

(function() {
    'use strict';

    if (typeof popmotion === 'undefined') {
        console.warn('Popmotion not loaded; UI animations disabled');
        return;
    }

    const { animate, spring, keyframes } = popmotion;

    window.kawkabAnimations = {
        // Animate a score/percentage value from `from` to `to`
        animateNumber(elementId, from, to, duration) {
            const el = document.getElementById(elementId);
            if (!el) return;
            duration = duration || 800;
            animate({
                from: Number(from),
                to: Number(to),
                duration: duration,
                ease: popmotion.easeInOut,
                onUpdate: (v) => {
                    el.textContent = Math.round(v);
                },
            });
        },

        // Animate possession bar fill
        animateBarFill(elementId, percentage, duration) {
            const el = document.getElementById(elementId);
            if (!el) return;
            duration = duration || 1000;
            animate({
                from: parseFloat(el.style.width) || 0,
                to: Math.max(0, Math.min(100, percentage)),
                duration: duration,
                ease: popmotion.easeInOut,
                onUpdate: (v) => {
                    el.style.width = v + '%';
                },
            });
        },

        // Spring-based animation for hover effects
        springHover(element) {
            if (!element) return;
            spring({
                from: { scale: 1 },
                to: { scale: 1.05 },
                stiffness: 300,
                damping: 20,
                onUpdate: (v) => {
                    element.style.transform = `scale(${v.scale})`;
                },
            });
        },

        // Fade in + slide up
        fadeInSlideUp(element, delay) {
            if (!element) return;
            delay = delay || 0;
            setTimeout(() => {
                element.style.opacity = '0';
                element.style.transform = 'translateY(10px)';
                animate({
                    from: 0,
                    to: 1,
                    duration: 400,
                    ease: popmotion.easeOut,
                    onUpdate: (v) => {
                        element.style.opacity = v;
                        element.style.transform = `translateY(${10 * (1 - v)}px)`;
                    },
                    onComplete: () => {
                        element.style.transform = '';
                    },
                });
            }, delay);
        },

        // Stagger animation for list items
        staggerIn(items, stagger) {
            if (!items || !items.length) return;
            stagger = stagger || 50;
            items.forEach((item, idx) => {
                this.fadeInSlideUp(item, idx * stagger);
            });
        },

        // Pulse animation for live indicator
        pulse(element) {
            if (!element) return;
            animate({
                from: { scale: 1, opacity: 1 },
                to: { scale: 1.1, opacity: 0.7 },
                duration: 1000,
                repeat: Infinity,
                repeatType: 'reverse',
                ease: popmotion.easeInOut,
                onUpdate: (v) => {
                    element.style.transform = `scale(${v.scale})`;
                    element.style.opacity = v.opacity;
                },
            });
        },
    };

    console.log('Kawkab animations module loaded');
})();
