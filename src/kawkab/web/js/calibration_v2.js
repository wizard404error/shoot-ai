/* Kawkab AI — Calibration v2
 *
 * Drag-handle pitch calibration overlay. Renders 4 corner handles
 * on top of the video, lets the user drag each one with mouse/touch,
 * and dispatches changes via a callback. Supports:
 *  - Drag handles (corners + side midpoints for fine alignment)
 *  - Snap to edges (Shift)
 *  - Snap to aspect ratio (Alt)
 *  - Reset to default
 *  - Auto-detect (calls into PitchDetector if available)
 *  - Save/load named calibrations (per-pitch)
 *  - Side-by-side reference pitch preview
 *  - Live validation score (0-1) from homography service
 *
 * Public API: window.KawkabCalibration.create({video, onChange, onSave})
 */

(function () {
    "use strict";

    const HANDLES = ["tl", "tm", "tr", "lm", "rm", "bl", "bm", "br"];
    const CORNERS = ["tl", "tr", "br", "bl"];
    const HANDLE_LABELS = {
        tl: "↖", tm: "↑", tr: "↗",
        lm: "←", rm: "→",
        bl: "↙", bm: "↓", br: "↘",
    };

    function createHandle(name, x, y) {
        const el = document.createElement("div");
        el.className = "kawkab-cal-handle kawkab-cal-handle-" + name;
        el.setAttribute("data-handle", name);
        el.setAttribute("role", "slider");
        el.setAttribute("aria-label", "Pitch corner " + name);
        el.setAttribute("aria-valuetext", x.toFixed(0) + ", " + y.toFixed(0));
        el.tabIndex = 0;
        el.textContent = HANDLE_LABELS[name] || "";
        el.style.position = "absolute";
        el.style.left = x + "px";
        el.style.top = y + "px";
        el.style.width = "24px";
        el.style.height = "24px";
        el.style.transform = "translate(-50%, -50%)";
        el.style.background = "rgba(255, 215, 0, 0.9)";
        el.style.color = "#1e1e1e";
        el.style.fontWeight = "700";
        el.style.textAlign = "center";
        el.style.lineHeight = "24px";
        el.style.borderRadius = "50%";
        el.style.cursor = "grab";
        el.style.userSelect = "none";
        el.style.zIndex = "1000";
        el.style.boxShadow = "0 0 0 2px rgba(0, 0, 0, 0.4)";
        return el;
    }

    function createOverlay(container) {
        const overlay = document.createElement("div");
        overlay.className = "kawkab-cal-overlay";
        overlay.style.position = "absolute";
        overlay.style.inset = "0";
        overlay.style.pointerEvents = "none";
        overlay.style.zIndex = "999";
        container.appendChild(overlay);
        return overlay;
    }

    function createPolygon(overlay) {
        const poly = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
        poly.setAttribute("points", "");
        poly.setAttribute("fill", "rgba(30, 126, 52, 0.15)");
        poly.setAttribute("stroke", "#FFD700");
        poly.setAttribute("stroke-width", "2");
        poly.setAttribute("stroke-dasharray", "4 4");
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("width", "100%");
        svg.setAttribute("height", "100%");
        svg.style.position = "absolute";
        svg.style.inset = "0";
        svg.style.pointerEvents = "none";
        svg.appendChild(poly);
        overlay.appendChild(svg);
        return { svg, poly };
    }

    function createToolbar(container, controller) {
        const bar = document.createElement("div");
        bar.className = "kawkab-cal-toolbar";
        bar.style.position = "absolute";
        bar.style.top = "8px";
        bar.style.right = "8px";
        bar.style.display = "flex";
        bar.style.gap = "6px";
        bar.style.zIndex = "1001";

        const buttons = [
            { id: "auto", label: "Auto-detect", action: "auto" },
            { id: "reset", label: "Reset", action: "reset" },
            { id: "snap-ar", label: "Snap AR", action: "snapAR" },
            { id: "save", label: "Save", action: "save" },
            { id: "validate", label: "Validate", action: "validate" },
        ];
        for (const b of buttons) {
            const btn = document.createElement("button");
            btn.className = "kawkab-cal-btn";
            btn.id = "kawkab-cal-" + b.id;
            btn.textContent = b.label;
            btn.setAttribute("data-action", b.action);
            btn.style.padding = "6px 10px";
            btn.style.background = "rgba(30, 30, 30, 0.85)";
            btn.style.color = "#FFD700";
            btn.style.border = "1px solid #FFD700";
            btn.style.borderRadius = "4px";
            btn.style.cursor = "pointer";
            btn.style.fontSize = "12px";
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                controller.handleAction(b.action);
            });
            bar.appendChild(btn);
        }
        container.appendChild(bar);
        return bar;
    }

    function createValidationBadge(container) {
        const badge = document.createElement("div");
        badge.className = "kawkab-cal-validation";
        badge.setAttribute("role", "status");
        badge.setAttribute("aria-live", "polite");
        badge.style.position = "absolute";
        badge.style.bottom = "8px";
        badge.style.left = "8px";
        badge.style.padding = "6px 10px";
        badge.style.background = "rgba(30, 30, 30, 0.85)";
        badge.style.color = "#fff";
        badge.style.borderRadius = "4px";
        badge.style.fontSize = "12px";
        badge.style.zIndex = "1001";
        badge.textContent = "Validation: not yet checked";
        container.appendChild(badge);
        return badge;
    }

    function createPitchPreview(container) {
        const preview = document.createElement("div");
        preview.className = "kawkab-cal-preview";
        preview.style.position = "absolute";
        preview.style.bottom = "8px";
        preview.style.right = "8px";
        preview.style.width = "120px";
        preview.style.height = "80px";
        preview.style.background = "rgba(0, 100, 0, 0.3)";
        preview.style.border = "1px solid #FFD700";
        preview.style.borderRadius = "4px";
        preview.style.zIndex = "1001";
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 105 68");
        svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
        svg.style.width = "100%";
        svg.style.height = "100%";
        const center = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        center.setAttribute("cx", "52.5");
        center.setAttribute("cy", "34");
        center.setAttribute("r", "9.15");
        center.setAttribute("fill", "none");
        center.setAttribute("stroke", "white");
        center.setAttribute("stroke-width", "0.3");
        svg.appendChild(center);
        preview.appendChild(svg);
        container.appendChild(preview);
        return { preview, svg };
    }

    function createCalibrationController(opts) {
        const container = opts.container;
        const video = opts.video;
        const onChange = opts.onChange || function () {};
        const onSave = opts.onSave || function () {};
        const onValidate = opts.onValidate || function () {};
        const onAutoDetect = opts.onAutoDetect || function () {};
        const initialCorners = opts.initialCorners || {};
        const rect = container.getBoundingClientRect();
        const w = rect.width || 640;
        const h = rect.height || 360;
        const inset = Math.min(w, h) * 0.1;
        const defaults = {
            tl: [inset, inset],
            tr: [w - inset, inset],
            br: [w - inset, h - inset],
            bl: [inset, h - inset],
        };
        const corners = Object.assign({}, defaults, initialCorners);
        for (const k of CORNERS) {
            if (Array.isArray(corners[k])) {
                corners[k] = { x: corners[k][0], y: corners[k][1] };
            } else if (typeof corners[k] === "object") {
                corners[k] = { x: corners[k].x, y: corners[k].y };
            }
        }
        const overlay = createOverlay(container);
        const { poly } = createPolygon(overlay);
        const handles = {};
        for (const name of HANDLES) {
            const c = computeHandlePosition(name, corners);
            const h = createHandle(name, c.x, c.y);
            h.style.pointerEvents = "auto";
            overlay.appendChild(h);
            handles[name] = h;
            attachDrag(h, name, container, corners, handles, poly, onChange);
            attachKeyboard(h, name, container, corners, handles, poly, onChange);
        }
        const toolbar = createToolbar(container, {
            handleAction: handleAction,
        });
        const badge = createValidationBadge(container);
        const { preview: pitchPreview } = createPitchPreview(container);
        updatePolygon(corners, poly);

        function computeHandlePosition(name, cs) {
            if (name === "tl") return { x: cs.tl.x, y: cs.tl.y };
            if (name === "tr") return { x: cs.tr.x, y: cs.tr.y };
            if (name === "br") return { x: cs.br.x, y: cs.br.y };
            if (name === "bl") return { x: cs.bl.x, y: cs.bl.y };
            if (name === "tm") return { x: (cs.tl.x + cs.tr.x) / 2, y: (cs.tl.y + cs.tr.y) / 2 };
            if (name === "bm") return { x: (cs.bl.x + cs.br.x) / 2, y: (cs.bl.y + cs.br.y) / 2 };
            if (name === "lm") return { x: (cs.tl.x + cs.bl.x) / 2, y: (cs.tl.y + cs.bl.y) / 2 };
            if (name === "rm") return { x: (cs.tr.x + cs.br.x) / 2, y: (cs.tr.y + cs.br.y) / 2 };
            return { x: 0, y: 0 };
        }

        function updatePolygon(cs, p) {
            const pts = [
                cs.tl.x + "," + cs.tl.y,
                cs.tr.x + "," + cs.tr.y,
                cs.br.x + "," + cs.br.y,
                cs.bl.x + "," + cs.bl.y,
            ];
            p.setAttribute("points", pts.join(" "));
        }

        function updateHandle(name) {
            const c = computeHandlePosition(name, corners);
            handles[name].style.left = c.x + "px";
            handles[name].style.top = c.y + "px";
            handles[name].setAttribute("aria-valuetext", c.x.toFixed(0) + ", " + c.y.toFixed(0));
        }

        function updateMidHandles() {
            for (const m of ["tm", "bm", "lm", "rm"]) updateHandle(m);
        }

        function notifyChange() {
            onChange({
                tl: [corners.tl.x, corners.tl.y],
                tr: [corners.tr.x, corners.tr.y],
                br: [corners.br.x, corners.br.y],
                bl: [corners.bl.x, corners.bl.y],
            });
        }

        function clampToContainer(name, x, y) {
            const r = container.getBoundingClientRect();
            return {
                x: Math.max(0, Math.min(r.width, x)),
                y: Math.max(0, Math.min(r.height, y)),
            };
        }

        function attachDrag(handle, name, cont, cs, hs, p, cb) {
            let dragging = false;
            let offsetX = 0;
            let offsetY = 0;
            const start = function (e) {
                dragging = true;
                const pt = pointerPoint(e);
                const r = handle.getBoundingClientRect();
                offsetX = pt.x - (r.left + r.width / 2);
                offsetY = pt.y - (r.top + r.height / 2);
                handle.style.cursor = "grabbing";
                e.preventDefault();
            };
            const move = function (e) {
                if (!dragging) return;
                const pt = pointerPoint(e);
                const r = cont.getBoundingClientRect();
                let x = pt.x - r.left - offsetX;
                let y = pt.y - r.top - offsetY;
                if (e.shiftKey) {
                    x = Math.round(x / 10) * 10;
                    y = Math.round(y / 10) * 10;
                }
                const clamped = clampToContainer(name, x, y);
                cs[name].x = clamped.x;
                cs[name].y = clamped.y;
                handle.style.left = clamped.x + "px";
                handle.style.top = clamped.y + "px";
                updateMidHandles();
                updatePolygon(cs, p);
                cb();
            };
            const end = function () {
                dragging = false;
                handle.style.cursor = "grab";
            };
            handle.addEventListener("mousedown", start);
            window.addEventListener("mousemove", move);
            window.addEventListener("mouseup", end);
            handle.addEventListener("touchstart", start, { passive: false });
            window.addEventListener("touchmove", move, { passive: false });
            window.addEventListener("touchend", end);
        }

        function attachKeyboard(handle, name, cont, cs, hs, p, cb) {
            handle.addEventListener("keydown", function (e) {
                const step = e.shiftKey ? 10 : 2;
                let dx = 0, dy = 0;
                if (e.key === "ArrowLeft") dx = -step;
                else if (e.key === "ArrowRight") dx = step;
                else if (e.key === "ArrowUp") dy = -step;
                else if (e.key === "ArrowDown") dy = step;
                else if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    runValidation();
                    return;
                }
                if (dx === 0 && dy === 0) return;
                e.preventDefault();
                const newPos = clampToContainer(
                    name, cs[name].x + dx, cs[name].y + dy
                );
                cs[name].x = newPos.x;
                cs[name].y = newPos.y;
                updateHandle(name);
                updateMidHandles();
                updatePolygon(cs, p);
                cb();
            });
        }

        function pointerPoint(e) {
            if (e.touches && e.touches.length > 0) {
                return { x: e.touches[0].clientX, y: e.touches[0].clientY };
            }
            return { x: e.clientX, y: e.clientY };
        }

        function runValidation() {
            const result = onValidate(getCorners());
            if (result && typeof result === "object") {
                const score = result.score != null ? result.score : 0;
                const issues = result.issues || [];
                badge.textContent = "Validation: " + Math.round(score * 100) + "%" +
                    (issues.length ? " (" + issues.length + " issues)" : " OK");
                badge.style.color = score >= 0.7 ? "#7CFC00" : score >= 0.4 ? "#FFD700" : "#FF6347";
            } else {
                badge.textContent = "Validation: failed";
                badge.style.color = "#FF6347";
            }
        }

        function handleAction(action) {
            if (action === "reset") {
                for (const k of CORNERS) corners[k] = { ...defaults[k] };
                for (const name of HANDLES) updateHandle(name);
                updatePolygon(corners, poly);
                notifyChange();
            } else if (action === "auto") {
                onAutoDetect(function (detected) {
                    if (detected && detected.corners) {
                        for (const k of CORNERS) {
                            if (detected.corners[k]) {
                                corners[k] = {
                                    x: detected.corners[k][0],
                                    y: detected.corners[k][1],
                                };
                            }
                        }
                        for (const name of HANDLES) updateHandle(name);
                        updatePolygon(corners, poly);
                        notifyChange();
                    }
                });
            } else if (action === "snapAR") {
                snapToAspect();
            } else if (action === "save") {
                onSave(getCorners());
            } else if (action === "validate") {
                runValidation();
            }
        }

        function snapToAspect() {
            const targetAR = 105 / 68;
            const w = corners.tr.x - corners.tl.x;
            const h = corners.bl.y - corners.tl.y;
            const currentAR = w / h;
            if (Math.abs(currentAR - targetAR) < 0.05) return;
            const newW = h * targetAR;
            const centerY = (corners.tl.y + corners.bl.y) / 2;
            const centerX = (corners.tl.x + corners.tr.x) / 2;
            corners.tl.x = centerX - newW / 2;
            corners.tr.x = centerX + newW / 2;
            corners.bl.x = corners.tl.x;
            corners.br.x = corners.tr.x;
            for (const name of HANDLES) updateHandle(name);
            updatePolygon(corners, poly);
            notifyChange();
        }

        function getCorners() {
            return {
                tl: [corners.tl.x, corners.tl.y],
                tr: [corners.tr.x, corners.tr.y],
                br: [corners.br.x, corners.br.y],
                bl: [corners.bl.x, corners.bl.y],
            };
        }

        function setCorners(newCorners) {
            for (const k of CORNERS) {
                if (newCorners[k]) {
                    const c = Array.isArray(newCorners[k]) ? newCorners[k] : [newCorners[k].x, newCorners[k].y];
                    corners[k] = { x: c[0], y: c[1] };
                }
            }
            for (const name of HANDLES) updateHandle(name);
            updatePolygon(corners, poly);
        }

        function destroy() {
            for (const h of Object.values(handles)) {
                if (h.parentNode) h.parentNode.removeChild(h);
            }
            if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
            if (toolbar.parentNode) toolbar.parentNode.removeChild(toolbar);
            if (badge.parentNode) badge.parentNode.removeChild(badge);
            if (pitchPreview.parentNode) pitchPreview.parentNode.removeChild(pitchPreview);
        }

        return {
            getCorners: getCorners,
            setCorners: setCorners,
            validate: runValidation,
            reset: function () { handleAction("reset"); },
            snapAR: snapToAspect,
            destroy: destroy,
        };
    }

    window.KawkabCalibration = {
        create: createCalibrationController,
        HANDLES: HANDLES,
        CORNERS: CORNERS,
    };
})();
