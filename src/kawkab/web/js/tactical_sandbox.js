// Kawkab AI - Tactical sandbox with matter.js physics
// Enhanced with 3-4-3, diamond, triangle overlay, pressing arrows, line spacing
// Drag-and-drop player tokens. Click "Press Ball" to simulate pressing.

(function() {
    'use strict';

    if (typeof Matter === 'undefined') {
        console.warn('matter-js not loaded; tactical sandbox disabled');
        if (typeof showToast === 'function') showToast('Tactical sandbox disabled: matter-js not loaded.', 'info');
        return;
    }

    const { Engine, World, Bodies, Body, Events, Mouse, MouseConstraint } = Matter;

    const FORMATIONS = {
        '4-4-2': [
            { x: 30, y: 200, color: '#fbbf24', label: 'GK' },
            { x: 130, y: 80, color: '#3b82f6', label: 'LB' },
            { x: 130, y: 160, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 240, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 320, color: '#3b82f6', label: 'RB' },
            { x: 250, y: 80, color: '#22c55e', label: 'LM' },
            { x: 250, y: 160, color: '#22c55e', label: 'CM' },
            { x: 250, y: 240, color: '#22c55e', label: 'CM' },
            { x: 250, y: 320, color: '#22c55e', label: 'RM' },
            { x: 380, y: 150, color: '#ef4444', label: 'ST' },
            { x: 380, y: 250, color: '#ef4444', label: 'ST' },
        ],
        '4-3-3': [
            { x: 30, y: 200, color: '#fbbf24', label: 'GK' },
            { x: 130, y: 80, color: '#3b82f6', label: 'LB' },
            { x: 130, y: 160, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 240, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 320, color: '#3b82f6', label: 'RB' },
            { x: 260, y: 130, color: '#22c55e', label: 'CM' },
            { x: 260, y: 200, color: '#22c55e', label: 'CDM' },
            { x: 260, y: 270, color: '#22c55e', label: 'CM' },
            { x: 400, y: 100, color: '#ef4444', label: 'LW' },
            { x: 400, y: 200, color: '#ef4444', label: 'ST' },
            { x: 400, y: 300, color: '#ef4444', label: 'RW' },
        ],
        '3-5-2': [
            { x: 30, y: 200, color: '#fbbf24', label: 'GK' },
            { x: 130, y: 120, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 200, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 280, color: '#3b82f6', label: 'CB' },
            { x: 280, y: 50, color: '#22c55e', label: 'LWB' },
            { x: 280, y: 140, color: '#22c55e', label: 'CM' },
            { x: 280, y: 200, color: '#22c55e', label: 'CDM' },
            { x: 280, y: 260, color: '#22c55e', label: 'CM' },
            { x: 280, y: 350, color: '#22c55e', label: 'RWB' },
            { x: 410, y: 160, color: '#ef4444', label: 'ST' },
            { x: 410, y: 240, color: '#ef4444', label: 'ST' },
        ],
        '4-2-3-1': [
            { x: 30, y: 200, color: '#fbbf24', label: 'GK' },
            { x: 130, y: 80, color: '#3b82f6', label: 'LB' },
            { x: 130, y: 160, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 240, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 320, color: '#3b82f6', label: 'RB' },
            { x: 240, y: 160, color: '#22c55e', label: 'CDM' },
            { x: 240, y: 240, color: '#22c55e', label: 'CDM' },
            { x: 340, y: 100, color: '#ef4444', label: 'LW' },
            { x: 340, y: 200, color: '#ef4444', label: 'CAM' },
            { x: 340, y: 300, color: '#ef4444', label: 'RW' },
            { x: 460, y: 200, color: '#ef4444', label: 'ST' },
        ],
        '3-4-3': [
            { x: 30, y: 200, color: '#fbbf24', label: 'GK' },
            { x: 130, y: 120, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 200, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 280, color: '#3b82f6', label: 'CB' },
            { x: 260, y: 70, color: '#22c55e', label: 'LM' },
            { x: 260, y: 170, color: '#22c55e', label: 'CM' },
            { x: 260, y: 230, color: '#22c55e', label: 'CM' },
            { x: 260, y: 330, color: '#22c55e', label: 'RM' },
            { x: 400, y: 100, color: '#ef4444', label: 'LW' },
            { x: 410, y: 200, color: '#ef4444', label: 'ST' },
            { x: 400, y: 300, color: '#ef4444', label: 'RW' },
        ],
        '4-1-2-1-2 Diamond': [
            { x: 30, y: 200, color: '#fbbf24', label: 'GK' },
            { x: 130, y: 80, color: '#3b82f6', label: 'LB' },
            { x: 130, y: 160, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 240, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 320, color: '#3b82f6', label: 'RB' },
            { x: 240, y: 200, color: '#22c55e', label: 'CDM' },
            { x: 320, y: 130, color: '#22c55e', label: 'LM' },
            { x: 320, y: 270, color: '#22c55e', label: 'RM' },
            { x: 360, y: 200, color: '#22c55e', label: 'CAM' },
            { x: 450, y: 160, color: '#ef4444', label: 'ST' },
            { x: 450, y: 240, color: '#ef4444', label: 'ST' },
        ],
        '3-2-4-1': [
            { x: 30, y: 200, color: '#fbbf24', label: 'GK' },
            { x: 130, y: 120, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 200, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 280, color: '#3b82f6', label: 'CB' },
            { x: 240, y: 160, color: '#22c55e', label: 'CDM' },
            { x: 240, y: 240, color: '#22c55e', label: 'CDM' },
            { x: 350, y: 70, color: '#ef4444', label: 'LW' },
            { x: 350, y: 150, color: '#ef4444', label: 'AM' },
            { x: 350, y: 250, color: '#ef4444', label: 'AM' },
            { x: 350, y: 330, color: '#ef4444', label: 'RW' },
            { x: 480, y: 200, color: '#ef4444', label: 'ST' },
        ],
    };

    let engine = null;
    let world = null;
    let canvas = null;
    let ctx = null;
    let playerBodies = [];
    let ballBody = null;
    let runner = null;
    let triangleMode = false;
    let triangleClicks = [];
    let showTriangles = false;
    let showPressingArrows = false;
    let showLineSpacing = false;
    let pressedSinceLastClick = false;

    function init() {
        canvas = document.getElementById('sandbox-canvas');
        if (!canvas) return;
        ctx = canvas.getContext('2d');
        engine = Engine.create({ gravity: { x: 0, y: 0 } });
        world = engine.world;
        createPitchBoundaries();
        createBall();
        loadFormation('4-4-2');
        setupMouseConstraint();
        setupListeners();
        startRenderLoop();
        setupSandboxToolbar();
    }

    function createPitchBoundaries() {
        const w = canvas.width;
        const h = canvas.height;
        const thickness = 30;
        const walls = [
            Bodies.rectangle(w / 2, -thickness / 2, w, thickness, { isStatic: true, label: 'wall' }),
            Bodies.rectangle(w / 2, h + thickness / 2, w, thickness, { isStatic: true, label: 'wall' }),
            Bodies.rectangle(-thickness / 2, h / 2, thickness, h, { isStatic: true, label: 'wall' }),
            Bodies.rectangle(w + thickness / 2, h / 2, thickness, h, { isStatic: true, label: 'wall' }),
        ];
        World.add(world, walls);
    }

    function createBall() {
        ballBody = Bodies.circle(550, 200, 10, {
            label: 'ball',
            restitution: 0.8,
            frictionAir: 0.02,
            render: { fillStyle: '#ffffff' },
        });
        World.add(world, ballBody);
    }

    function loadFormation(formationName) {
        playerBodies.forEach((b) => World.remove(world, b));
        playerBodies = [];
        triangleClicks = [];
        const formation = FORMATIONS[formationName] || FORMATIONS['4-4-2'];
        formation.forEach((p) => {
            const body = Bodies.circle(p.x, p.y, 14, {
                label: 'player',
                restitution: 0.5,
                frictionAir: 0.05,
                plugin: { color: p.color, label: p.label },
            });
            playerBodies.push(body);
            World.add(world, body);
        });
    }

    function setupMouseConstraint() {
        const mouse = Mouse.create(canvas);
        const mouseConstraint = MouseConstraint.create(engine, {
            mouse: mouse,
            constraint: { stiffness: 0.2, render: { visible: false } },
        });
        World.add(world, mouseConstraint);
        Events.on(mouseConstraint, 'mousedown', function(event) {
            if (triangleMode) {
                const mousePos = event.mouse.position;
                const clicked = playerBodies.find(function(b) {
                    return Math.hypot(b.position.x - mousePos.x, b.position.y - mousePos.y) < 18;
                });
                if (clicked && !pressedSinceLastClick) {
                    triangleClicks.push(clicked);
                    if (triangleClicks.length > 3) triangleClicks = [clicked];
                    pressedSinceLastClick = true;
                }
            }
        });
        Events.on(mouseConstraint, 'mouseup', function() {
            pressedSinceLastClick = false;
        });
    }

    function setupListeners() {
        const loadBtn = document.getElementById('sandbox-load-btn');
        if (loadBtn) {
            loadBtn.addEventListener('click', function() {
                const sel = document.getElementById('sandbox-formation');
                loadFormation(sel.value);
            });
        }
        const pressBtn = document.getElementById('sandbox-press-btn');
        if (pressBtn) {
            pressBtn.addEventListener('click', function() {
                simulatePress();
            });
        }
    }

    function simulatePress() {
        if (!ballBody || playerBodies.length === 0) return;
        const sorted = playerBodies
            .map(function(b) { return { body: b, dist: Math.hypot(b.position.x - ballBody.position.x, b.position.y - ballBody.position.y) }; })
            .sort(function(a, b) { return a.dist - b.dist; })
            .slice(0, 4);
        sorted.forEach(function(entry) {
            const dx = ballBody.position.x - entry.body.position.x;
            const dy = ballBody.position.y - entry.body.position.y;
            const dist = Math.hypot(dx, dy) || 1;
            const force = 0.0008;
            Body.applyForce(entry.body, entry.body.position, {
                x: (dx / dist) * force,
                y: (dy / dist) * force,
            });
        });
        const bdx = (Math.random() - 0.5) * 0.001;
        Body.applyForce(ballBody, ballBody.position, { x: bdx, y: -0.0002 });
    }

    function setupSandboxToolbar() {
        const toolbar = document.getElementById('sandbox-toolbar');
        if (!toolbar) return;
        const triBtn = document.getElementById('sandbox-triangle-btn');
        if (triBtn) {
            triBtn.addEventListener('click', function() {
                triangleMode = !triangleMode;
                triBtn.classList.toggle('active', triangleMode);
                triBtn.textContent = triangleMode ? '🔺 Drawing...' : '🔺 Triangle';
                if (!triangleMode) triangleClicks = [];
            });
        }
        const showTriBtn = document.getElementById('sandbox-show-tri-btn');
        if (showTriBtn) {
            showTriBtn.addEventListener('click', function() {
                showTriangles = !showTriangles;
                showTriBtn.classList.toggle('active', showTriangles);
            });
        }
        const arrowBtn = document.getElementById('sandbox-arrow-btn');
        if (arrowBtn) {
            arrowBtn.addEventListener('click', function() {
                showPressingArrows = !showPressingArrows;
                arrowBtn.classList.toggle('active', showPressingArrows);
            });
        }
        const spacingBtn = document.getElementById('sandbox-spacing-btn');
        if (spacingBtn) {
            spacingBtn.addEventListener('click', function() {
                showLineSpacing = !showLineSpacing;
                spacingBtn.classList.toggle('active', showLineSpacing);
            });
        }
        const clearBtn = document.getElementById('sandbox-clear-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                resetBall();
            });
        }
    }

    function resetBall() {
        if (ballBody) {
            Body.setPosition(ballBody, { x: 550, y: 200 });
            Body.setVelocity(ballBody, { x: 0, y: 0 });
        }
    }

    function startRenderLoop() {
        function loop() {
            if (!canvas || !document.body.contains(canvas)) {
                if (runner) {
                    cancelAnimationFrame(runner);
                    runner = null;
                }
                return;
            }
            Engine.update(engine, 1000 / 60);
            draw();
            runner = requestAnimationFrame(loop);
        }
        loop();
    }

    function stopRenderLoop() {
        if (runner) {
            cancelAnimationFrame(runner);
            runner = null;
        }
    }

    function draw() {
        ctx.fillStyle = '#16a34a22';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = '#ffffff80';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(canvas.width / 2, 0);
        ctx.lineTo(canvas.width / 2, canvas.height);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(canvas.width / 2, canvas.height / 2, 50, 0, 2 * Math.PI);
        ctx.stroke();

        // Ball
        if (ballBody) {
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(ballBody.position.x, ballBody.position.y, 8, 0, 2 * Math.PI);
            ctx.fill();
            ctx.strokeStyle = '#000000';
            ctx.lineWidth = 1;
            ctx.stroke();
        }

        // Line spacing indicators
        if (showLineSpacing && playerBodies.length > 1) {
            const byX = playerBodies.slice().sort(function(a, b) { return a.position.x - b.position.x; });
            if (byX.length >= 4) {
                const lines = [];
                let currentLine = [byX[0]];
                for (let i = 1; i < byX.length; i++) {
                    if (byX[i].position.x - byX[i-1].position.x > 30) {
                        lines.push(currentLine);
                        currentLine = [byX[i]];
                    } else {
                        currentLine.push(byX[i]);
                    }
                }
                if (currentLine.length) lines.push(currentLine);
                if (lines.length >= 2) {
                    ctx.strokeStyle = '#fbbf2460';
                    ctx.lineWidth = 2;
                    ctx.setLineDash([4, 4]);
                    for (let i = 0; i < lines.length - 1; i++) {
                        const l1 = lines[i];
                        const l2 = lines[i+1];
                        const x1 = l1.reduce(function(s, b) { return s + b.position.x; }, 0) / l1.length;
                        const x2 = l2.reduce(function(s, b) { return s + b.position.x; }, 0) / l2.length;
                        const y1 = l1.reduce(function(s, b) { return s + b.position.y; }, 0) / l1.length;
                        const y2 = l2.reduce(function(s, b) { return s + b.position.y; }, 0) / l2.length;
                        ctx.beginPath();
                        ctx.moveTo(x1, 5);
                        ctx.lineTo(x2, 5);
                        ctx.stroke();
                        ctx.fillStyle = '#fbbf24';
                        ctx.font = '10px sans-serif';
                        ctx.textAlign = 'center';
                        ctx.fillText(Math.round(Math.abs(x2 - x1)) + 'px', (x1 + x2) / 2, 18);
                    }
                    ctx.setLineDash([]);
                }
            }
        }

        // Pressing arrows
        if (showPressingArrows && ballBody && playerBodies.length > 0) {
            const sorted = playerBodies
                .map(function(b) { return { body: b, dist: Math.hypot(b.position.x - ballBody.position.x, b.position.y - ballBody.position.y) }; })
                .sort(function(a, b) { return a.dist - b.dist; })
                .slice(0, 4);
            sorted.forEach(function(entry) {
                const dx = ballBody.position.x - entry.body.position.x;
                const dy = ballBody.position.y - entry.body.position.y;
                const dist = Math.hypot(dx, dy) || 1;
                const len = Math.min(dist * 0.4, 60);
                const nx = dx / dist;
                const ny = dy / dist;
                const sx = entry.body.position.x;
                const sy = entry.body.position.y;
                const ex = sx + nx * len;
                const ey = sy + ny * len;
                ctx.strokeStyle = '#ef444480';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(sx, sy);
                ctx.lineTo(ex, ey);
                ctx.stroke();
                // Arrowhead
                const angle = Math.atan2(ny, nx);
                ctx.fillStyle = '#ef444480';
                ctx.beginPath();
                ctx.moveTo(ex, ey);
                ctx.lineTo(ex - 8 * Math.cos(angle - 0.4), ey - 8 * Math.sin(angle - 0.4));
                ctx.lineTo(ex - 8 * Math.cos(angle + 0.4), ey - 8 * Math.sin(angle + 0.4));
                ctx.closePath();
                ctx.fill();
            });
        }

        // Triangles
        if (triangleClicks.length === 3) {
            ctx.strokeStyle = '#fbbf24';
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.moveTo(triangleClicks[0].position.x, triangleClicks[0].position.y);
            ctx.lineTo(triangleClicks[1].position.x, triangleClicks[1].position.y);
            ctx.lineTo(triangleClicks[2].position.x, triangleClicks[2].position.y);
            ctx.closePath();
            ctx.stroke();
            ctx.fillStyle = '#fbbf2420';
            ctx.fill();
            ctx.fillStyle = '#fbbf24';
            ctx.font = 'bold 10px sans-serif';
            ctx.textAlign = 'center';
            const cx = (triangleClicks[0].position.x + triangleClicks[1].position.x + triangleClicks[2].position.x) / 3;
            const cy = (triangleClicks[0].position.y + triangleClicks[1].position.y + triangleClicks[2].position.y) / 3;
            ctx.fillText('🔺', cx, cy - 12);
        }

        // Show all triangles
        if (showTriangles && playerBodies.length >= 3) {
            ctx.strokeStyle = '#22c55e60';
            ctx.lineWidth = 1.5;
            for (let i = 0; i < playerBodies.length; i++) {
                for (let j = i + 1; j < playerBodies.length; j++) {
                    for (let k = j + 1; k < playerBodies.length; k++) {
                        const d1 = Math.hypot(playerBodies[i].position.x - playerBodies[j].position.x, playerBodies[i].position.y - playerBodies[j].position.y);
                        const d2 = Math.hypot(playerBodies[j].position.x - playerBodies[k].position.x, playerBodies[j].position.y - playerBodies[k].position.y);
                        const d3 = Math.hypot(playerBodies[k].position.x - playerBodies[i].position.x, playerBodies[k].position.y - playerBodies[i].position.y);
                        if (d1 < 120 && d2 < 120 && d3 < 120) {
                            ctx.beginPath();
                            ctx.moveTo(playerBodies[i].position.x, playerBodies[i].position.y);
                            ctx.lineTo(playerBodies[j].position.x, playerBodies[j].position.y);
                            ctx.lineTo(playerBodies[k].position.x, playerBodies[k].position.y);
                            ctx.closePath();
                            ctx.stroke();
                        }
                    }
                }
            }
        }

        // Players
        playerBodies.forEach(function(b) {
            const color = b.plugin.color || '#3b82f6';
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(b.position.x, b.position.y, 14, 0, 2 * Math.PI);
            ctx.fill();
            ctx.strokeStyle = '#000000';
            ctx.lineWidth = 1.5;
            ctx.stroke();
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 9px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(b.plugin.label || '', b.position.x, b.position.y);
        });

        // Triangle mode indicator on clicked players
        if (triangleMode && triangleClicks.length > 0) {
            triangleClicks.forEach(function(b) {
                ctx.strokeStyle = '#fbbf24';
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.arc(b.position.x, b.position.y, 18, 0, 2 * Math.PI);
                ctx.stroke();
            });
        }
    }

    window.stopSandboxRenderLoop = stopRenderLoop;
    window.loadSandboxFormation = loadFormation;
    window.resetSandboxBall = resetBall;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        setTimeout(init, 100);
    }
})();
