// Kawkab AI - Tactical sandbox with matter.js physics
// Drag-and-drop player tokens on a 2D pitch with simple collision physics.
// Click "Press Ball" to simulate a pressing motion toward the ball.

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
            // Goalkeeper
            { x: 30, y: 200, color: '#fbbf24', label: 'GK' },
            // Defenders (4)
            { x: 130, y: 80, color: '#3b82f6', label: 'LB' },
            { x: 130, y: 160, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 240, color: '#3b82f6', label: 'CB' },
            { x: 130, y: 320, color: '#3b82f6', label: 'RB' },
            // Midfielders (4)
            { x: 250, y: 80, color: '#22c55e', label: 'LM' },
            { x: 250, y: 160, color: '#22c55e', label: 'CM' },
            { x: 250, y: 240, color: '#22c55e', label: 'CM' },
            { x: 250, y: 320, color: '#22c55e', label: 'RM' },
            // Forwards (2)
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
    };

    let engine = null;
    let world = null;
    let canvas = null;
    let ctx = null;
    let playerBodies = [];
    let ballBody = null;
    let runner = null;

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
        // Remove old players
        playerBodies.forEach((b) => World.remove(world, b));
        playerBodies = [];
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
    }

    function setupListeners() {
        const loadBtn = document.getElementById('sandbox-load-btn');
        if (loadBtn) {
            loadBtn.addEventListener('click', () => {
                const sel = document.getElementById('sandbox-formation');
                loadFormation(sel.value);
            });
        }
        const pressBtn = document.getElementById('sandbox-press-btn');
        if (pressBtn) {
            pressBtn.addEventListener('click', () => {
                simulatePress();
            });
        }
    }

    function simulatePress() {
        if (!ballBody || playerBodies.length === 0) return;
        // Sort players by distance to ball, take closest 4
        const sorted = playerBodies
            .map((b) => ({ body: b, dist: Math.hypot(b.position.x - ballBody.position.x, b.position.y - ballBody.position.y) }))
            .sort((a, b) => a.dist - b.dist)
            .slice(0, 4);
        sorted.forEach((entry) => {
            const dx = ballBody.position.x - entry.body.position.x;
            const dy = ballBody.position.y - entry.body.position.y;
            const dist = Math.hypot(dx, dy) || 1;
            const force = 0.0008;
            Body.applyForce(entry.body, entry.body.position, {
                x: (dx / dist) * force,
                y: (dy / dist) * force,
            });
        });
        // Slight ball kick
        const bdx = (Math.random() - 0.5) * 0.001;
        Body.applyForce(ballBody, ballBody.position, { x: bdx, y: -0.0002 });
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
        // Clear
        ctx.fillStyle = '#16a34a22';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        // Pitch lines
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
        // Players
        playerBodies.forEach((b) => {
            const color = b.plugin.color || '#3b82f6';
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(b.position.x, b.position.y, 14, 0, 2 * Math.PI);
            ctx.fill();
            ctx.strokeStyle = '#000000';
            ctx.lineWidth = 1.5;
            ctx.stroke();
            // Label
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 9px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(b.plugin.label || '', b.position.x, b.position.y);
        });
    }

    window.stopSandboxRenderLoop = stopRenderLoop;

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        setTimeout(init, 100);
    }
})();
