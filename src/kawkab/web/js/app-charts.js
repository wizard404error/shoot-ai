/* Kawkab AI — Chart.js enhanced chart renderers
 *
 * Replaces hand-drawn Canvas charts with Chart.js for:
 *  - Momentum Index
 *  - Win Probability
 *  - xG Timeline
 *  - Player Radar
 *
 * Falls back to original renderers if Chart.js is not available.
 */

(function () {
    "use strict";

    var ChartJS = typeof Chart !== "undefined" ? Chart : null;

    var _cachedHome = null;
    var _cachedAway = null;

    function _getColor(side) {
        var root = document.documentElement;
        return getComputedStyle(root).getPropertyValue('--team-' + side).trim() || (side === 'home' ? '#2563eb' : '#dc2626');
    }

    function _getHomeColor() { return _cachedHome || (_cachedHome = _getColor('home')); }
    function _getAwayColor() { return _cachedAway || (_cachedAway = _getColor('away')); }

    function _hexToRgba(hex, alpha) {
        if (hex.startsWith('rgb')) {
            return hex.replace('rgb', 'rgba').replace(')', ', ' + alpha + ')');
        }
        var r = parseInt(hex.slice(1, 3), 16);
        var g = parseInt(hex.slice(3, 5), 16);
        var b = parseInt(hex.slice(5, 7), 16);
        return 'rgba(' + r + ', ' + g + ', ' + b + ', ' + alpha + ')';
    }

    function _invalidateColorCache() {
        _cachedHome = null;
        _cachedAway = null;
    }

    window.__invalidateColorCache = _invalidateColorCache;

    // Store original renderers
    var _origRenderers = {};

    function _register(name, fn) {
        if (typeof fn !== "function") return;
        _origRenderers[name] = fn;
        window.__kawkabCharts = window.__kawkabCharts || {};
        window.__kawkabCharts[name] = fn;
    }

    // ============================================================
    // Helper: destroy existing chart instance on a canvas
    // ============================================================
    var _chartInstances = {};

    function _destroyChart(canvasId) {
        if (_chartInstances[canvasId]) {
            try { _chartInstances[canvasId].destroy(); } catch (e) {}
            delete _chartInstances[canvasId];
        }
    }

    // ============================================================
    // Inline annotation plugin (no external dep needed)
    // Draws vertical lines and horizontal reference lines
    // ============================================================
    var KawkabAnnotationPlugin = {
        id: "kawkabAnnotation",
        afterDraw: function (chart) {
            var opts = chart.options.plugins && chart.options.plugins.kawkabAnnotation;
            if (!opts || !opts.annotations) return;
            var ctx = chart.ctx;
            var chartArea = chart.chartArea;
            opts.annotations.forEach(function (ann) {
                if (ann.type === "line" && ann.xMin != null) {
                    var x = chart.scales.x.getPixelForValue(ann.xMin);
                    ctx.save();
                    ctx.beginPath();
                    ctx.setLineDash(ann.borderDash || []);
                    ctx.strokeStyle = ann.borderColor || "#ffd700";
                    ctx.lineWidth = ann.borderWidth || 1;
                    ctx.moveTo(x, chartArea.top);
                    ctx.lineTo(x, chartArea.bottom);
                    ctx.stroke();
                    ctx.restore();
                }
                if (ann.type === "line" && ann.yMin != null) {
                    var y = chart.scales.y.getPixelForValue(ann.yMin);
                    ctx.save();
                    ctx.beginPath();
                    ctx.setLineDash([5, 5]);
                    ctx.strokeStyle = ann.borderColor || "rgba(255,255,255,0.4)";
                    ctx.lineWidth = ann.borderWidth || 1;
                    ctx.moveTo(chartArea.left, y);
                    ctx.lineTo(chartArea.right, y);
                    ctx.stroke();
                    ctx.restore();
                }
            });
        }
    };
    if (ChartJS) {
        ChartJS.register(KawkabAnnotationPlugin);
    }

    // ============================================================
    // PNG export helper
    // ============================================================
    function downloadPNG(chartInstance, filename) {
        if (!chartInstance) return;
        var url = chartInstance.toBase64Image();
        var a = document.createElement("a");
        a.href = url;
        a.download = (filename || "chart") + ".png";
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { document.body.removeChild(a); }, 100);
    }

    // ============================================================
    // CSV export helper
    // ============================================================
    function downloadCSV(headers, rows, filename) {
        var csv = headers.join(",") + "\n" +
            rows.map(function (r) {
                return r.map(function (c) {
                    var s = String(c);
                    return s.indexOf(",") >= 0 ? '"' + s + '"' : s;
                }).join(",");
            }).join("\n");
        var blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = (filename || "chart-data") + ".csv";
        document.body.appendChild(a);
        a.click();
        setTimeout(function () {
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 100);
    }

    // ============================================================
    // Setup export buttons for a chart container
    // ============================================================
    function setupChartExport(chartInstance, title, csvHeaders, csvRows) {
        var canvas = chartInstance.canvas;
        if (!canvas) return;
        var parent = canvas.parentElement;
        if (!parent) return;
        var existing = parent.querySelector(".chart-export-bar");
        if (existing) return;

        var bar = document.createElement("div");
        bar.className = "chart-export-bar";
        bar.setAttribute("role", "toolbar");
        bar.setAttribute("aria-label", "Chart export options");

        var pngBtn = document.createElement("button");
        pngBtn.className = "chart-export-btn chart-export-png";
        pngBtn.innerHTML = "&#8595;";
        pngBtn.title = "Download PNG";
        pngBtn.setAttribute("aria-label", "Download " + (title || "chart") + " as PNG");
        pngBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            downloadPNG(chartInstance, title || "chart");
        });

        bar.appendChild(pngBtn);

        if (csvHeaders && csvRows) {
            var csvBtn = document.createElement("button");
            csvBtn.className = "chart-export-btn chart-export-csv";
            csvBtn.textContent = "CSV";
            csvBtn.title = "Download CSV";
            csvBtn.setAttribute("aria-label", "Download " + (title || "chart") + " data as CSV");
            csvBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                downloadCSV(csvHeaders, csvRows, title || "chart-data");
            });
            bar.appendChild(csvBtn);
        }

        parent.style.position = "relative";
        parent.appendChild(bar);
    }

    // ============================================================
    // Track all instances for external access
    // ============================================================
    var _exportInstances = [];

    function _saveInstance(chart, title, csvHeaders, csvRows) {
        _exportInstances.push({ chart: chart, title: title, csvHeaders: csvHeaders, csvRows: csvRows });
        setupChartExport(chart, title, csvHeaders, csvRows);
    }

    // ============================================================
    // 1. Momentum Index — line chart
    // ============================================================
    function renderMomentumIndexChart(data) {
        if (!ChartJS || !data || !data.timeline || data.timeline.length < 2) {
            if (_origRenderers.momentum) _origRenderers.momentum(data);
            return;
        }
        var canvas = document.getElementById("momentum-canvas");
        if (!canvas) return;
        _destroyChart("momentum-canvas");

        var labels = data.timeline.map(function (p) { return p.minute; });
        var home = data.timeline.map(function (p) { return p.home_momentum; });
        var away = data.timeline.map(function (p) { return p.away_momentum; });

        var chart = new ChartJS(canvas.getContext("2d"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Home",
                    data: home,
                    borderColor: _getHomeColor(),
                    backgroundColor: _hexToRgba(_getHomeColor(), 0.1),
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                    borderWidth: 2,
                }, {
                    label: "Away",
                    data: away,
                    borderColor: _getAwayColor(),
                    backgroundColor: _hexToRgba(_getAwayColor(), 0.1),
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: function(e, elements) {
                    if (elements && elements.length > 0) {
                        var idx = elements[0].index;
                        var m = data.timeline[idx];
                        if (m && typeof window.__kawkabChartFilter === 'function') {
                            window.__kawkabChartFilter({ match_minute: m.minute, range: 3, canvasId: 'momentum-canvas' });
                        }
                    }
                },
                plugins: {
                    legend: { position: "top", labels: { color: "#ccc" } },
                },
                scales: {
                    x: { title: { display: true, text: "Minute", color: "#999" }, ticks: { color: "#999" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: { title: { display: true, text: "Momentum", color: "#999" }, ticks: { color: "#999" }, grid: { color: "rgba(255,255,255,0.05)" }, min: -1, max: 1 },
                },
            },
        });
        _chartInstances["momentum-canvas"] = chart;
        _saveInstance(chart, "momentum-index",
            ["Minute", "Home Momentum", "Away Momentum"],
            data.timeline.map(function (p) { return [p.minute, p.home_momentum, p.away_momentum]; }));
    }

    // ============================================================
    // 2. Win Probability — stacked area chart
    // ============================================================
    function renderWinProbabilityChart(data) {
        if (!ChartJS || !data || !data.timeline || data.timeline.length < 2) {
            if (_origRenderers.winprob) _origRenderers.winprob(data);
            return;
        }
        var canvas = document.getElementById("winprob-canvas");
        if (!canvas) return;
        _destroyChart("winprob-canvas");

        var labels = data.timeline.map(function (p) { return p.minute; });

        var chart = new ChartJS(canvas.getContext("2d"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Home Win",
                    data: data.timeline.map(function (p) { return p.home_win; }),
                    borderColor: _getHomeColor(),
                    backgroundColor: _hexToRgba(_getHomeColor(), 0.3),
                    fill: "+1",
                    tension: 0.3,
                    pointRadius: 0,
                    borderWidth: 2,
                }, {
                    label: "Draw",
                    data: data.timeline.map(function (p) { return p.draw; }),
                    borderColor: "#f59e0b",
                    backgroundColor: "rgba(245,158,11,0.3)",
                    fill: "+1",
                    tension: 0.3,
                    pointRadius: 0,
                    borderWidth: 2,
                }, {
                    label: "Away Win",
                    data: data.timeline.map(function (p) { return p.away_win; }),
                    borderColor: _getAwayColor(),
                    backgroundColor: _hexToRgba(_getAwayColor(), 0.3),
                    fill: "+1",
                    tension: 0.3,
                    pointRadius: 0,
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: function(e, elements) {
                    if (elements && elements.length > 0) {
                        var idx = elements[0].index;
                        var m = data.timeline[idx];
                        if (m && typeof window.__kawkabChartFilter === 'function') {
                            window.__kawkabChartFilter({ match_minute: m.minute, range: 5, canvasId: 'winprob-canvas' });
                        }
                    }
                },
                plugins: {
                    legend: { position: "top", labels: { color: "#ccc" } },
                    tooltip: {
                        callbacks: {
                            footer: function (items) {
                                var i = items[0].dataIndex;
                                var pt = data.timeline[i];
                                return "Score: " + (pt.home_score || 0) + " - " + (pt.away_score || 0);
                            },
                        },
                    },
                },
                scales: {
                    x: { title: { display: true, text: "Minute", color: "#999" }, ticks: { color: "#999" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: { stacked: true, title: { display: true, text: "Probability", color: "#999" }, ticks: { color: "#999", format: { style: "percent" } }, grid: { color: "rgba(255,255,255,0.05)" }, min: 0, max: 1 },
                },
            },
        });
        _chartInstances["winprob-canvas"] = chart;
        _saveInstance(chart, "win-probability",
            ["Minute", "Home Win", "Draw", "Away Win", "Home Score", "Away Score"],
            data.timeline.map(function (p) {
                return [p.minute, p.home_win, p.draw, p.away_win, p.home_score || 0, p.away_score || 0];
            }));
    }

    // ============================================================
    // 3. xG Timeline — bar chart (home above, away below)
    // ============================================================
    function renderXGTimelineChart(data) {
        if (!ChartJS || !data || !data.timeline || data.timeline.length < 2) {
            if (_origRenderers.xgtimeline) _origRenderers.xgtimeline(data);
            return;
        }
        var canvas = document.getElementById("xg-timeline-canvas");
        if (!canvas) return;
        _destroyChart("xg-timeline-canvas");

        var labels = data.timeline.map(function (p) { return p.minute; });
        var homeXG = data.timeline.map(function (p) { return p.home_xg || 0; });
        var awayXG = data.timeline.map(function (p) { return p.away_xg ? -p.away_xg : 0; });
        var homeGoals = data.timeline.map(function (p) { return p.home_goal ? p.home_xg || 0.5 : 0; });
        var awayGoals = data.timeline.map(function (p) { return p.away_goal ? -(p.away_xg || 0.5) : 0; });

        // Build goal annotations (vertical lines) + xG=0.5 reference line
        var annotations = [
            { type: "line", yMin: 0.5, borderColor: "rgba(255,255,255,0.25)", borderWidth: 1, borderDash: [5, 5] },
            { type: "line", yMin: -0.5, borderColor: "rgba(255,255,255,0.25)", borderWidth: 1, borderDash: [5, 5] },
        ];
        data.timeline.forEach(function (p) {
            if (p.home_goal) {
                annotations.push({ type: "line", xMin: p.minute, borderColor: _getHomeColor(), borderWidth: 1, borderDash: [4, 2] });
            }
            if (p.away_goal) {
                annotations.push({ type: "line", xMin: p.minute, borderColor: _getAwayColor(), borderWidth: 1, borderDash: [4, 2] });
            }
        });

        var chart = new ChartJS(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Home xG",
                    data: homeXG,
                    backgroundColor: _hexToRgba(_getHomeColor(), 0.6),
                    borderColor: _getHomeColor(),
                    borderWidth: 1,
                }, {
                    label: "Home Goal",
                    data: homeGoals,
                    backgroundColor: _hexToRgba(_getHomeColor(), 0.9),
                    borderColor: _getHomeColor(),
                    borderWidth: 2,
                }, {
                    label: "Away xG",
                    data: awayXG,
                    backgroundColor: _hexToRgba(_getAwayColor(), 0.6),
                    borderColor: _getAwayColor(),
                    borderWidth: 1,
                }, {
                    label: "Away Goal",
                    data: awayGoals,
                    backgroundColor: _hexToRgba(_getAwayColor(), 0.9),
                    borderColor: _getAwayColor(),
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: function(e, elements) {
                    if (elements && elements.length > 0) {
                        var idx = elements[0].index;
                        var m = data.timeline[idx];
                        if (m && typeof window.__kawkabChartFilter === 'function') {
                            window.__kawkabChartFilter({ match_minute: m.minute, range: 5, canvasId: 'xg-timeline-canvas' });
                        }
                    }
                },
                plugins: {
                    legend: { position: "top", labels: { color: "#ccc" } },
                    kawkabAnnotation: { annotations: annotations },
                },
                scales: {
                    x: { title: { display: true, text: "Minute", color: "#999" }, ticks: { color: "#999" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: { title: { display: true, text: "xG", color: "#999" }, ticks: { color: "#999" }, grid: { color: "rgba(255,255,255,0.05)" } },
                },
            },
        });
        _chartInstances["xg-timeline-canvas"] = chart;
        _saveInstance(chart, "xg-timeline",
            ["Minute", "Home xG", "Away xG", "Home Goal", "Away Goal"],
            data.timeline.map(function (p) {
                return [p.minute, p.home_xg || 0, p.away_xg || 0, p.home_goal ? 1 : 0, p.away_goal ? 1 : 0];
            }));
    }

    // ============================================================
    // 4. Player Radar Chart
    // ============================================================
    function renderRadarChart(data) {
        if (!ChartJS || !data || !data.labels || data.labels.length < 3) {
            if (_origRenderers.radar) _origRenderers.radar(data);
            return;
        }
        var canvas = document.getElementById("radar-canvas");
        if (!canvas) return;
        _destroyChart("radar-canvas");

        var chart = new ChartJS(canvas.getContext("2d"), {
            type: "radar",
            data: {
                labels: data.labels,
                datasets: [{
                    label: data.playerName || "Player",
                    data: data.values,
                    backgroundColor: _hexToRgba(_getHomeColor(), 0.2),
                    borderColor: _getHomeColor(),
                    pointBackgroundColor: _getHomeColor(),
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top", labels: { color: "#ccc" } },
                },
                scales: {
                    r: {
                        angleLines: { color: "rgba(255,255,255,0.1)" },
                        grid: { color: "rgba(255,255,255,0.1)" },
                        pointLabels: { color: "#ccc", font: { size: 10 } },
                        ticks: { color: "#999", backdropColor: "transparent" },
                        min: 0,
                        max: 1,
                    },
                },
            },
        });
        _chartInstances["radar-canvas"] = chart;
        _saveInstance(chart, data.playerName || "player-radar",
            ["Metric"].concat(data.labels),
            [["Value"].concat(data.values)]);
    }

    // ============================================================
    // 5. Dual Player Radar — two side-by-side radar charts
    // ============================================================
    function renderDualRadar(canvasIdA, dataA, canvasIdB, dataB, maxVal) {
        if (!ChartJS || !dataA || !dataA.labels || dataA.labels.length < 2) return;
        maxVal = maxVal || 1;
        _destroyChart(canvasIdA);
        _destroyChart(canvasIdB);

        var baseOpts = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "top", labels: { color: "#ccc", font: { size: 11 } } },
            },
            scales: {
                r: {
                    angleLines: { color: "rgba(255,255,255,0.1)" },
                    grid: { color: "rgba(255,255,255,0.1)" },
                    pointLabels: { color: "#ccc", font: { size: 10 } },
                    ticks: { color: "#999", backdropColor: "transparent", display: false },
                    min: 0,
                    max: maxVal,
                },
            },
        };

        var canvasA = document.getElementById(canvasIdA);
        if (canvasA) {
            _chartInstances[canvasIdA] = new ChartJS(canvasA.getContext("2d"), {
                type: "radar",
                data: {
                    labels: dataA.labels,
                    datasets: [{
                        label: dataA.playerName || "Player A",
                        data: dataA.values,
                        backgroundColor: _hexToRgba(_getHomeColor(), 0.2),
                        borderColor: _getHomeColor(),
                        pointBackgroundColor: _getHomeColor(),
                        borderWidth: 2,
                    }],
                },
                options: baseOpts,
            });
        }

        var canvasB = document.getElementById(canvasIdB);
        if (canvasB) {
            _chartInstances[canvasIdB] = new ChartJS(canvasB.getContext("2d"), {
                type: "radar",
                data: {
                    labels: dataB.labels,
                    datasets: [{
                        label: dataB.playerName || "Player B",
                        data: dataB.values,
                        backgroundColor: _hexToRgba(_getAwayColor(), 0.2),
                        borderColor: _getAwayColor(),
                        pointBackgroundColor: _getAwayColor(),
                        borderWidth: 2,
                    }],
                },
                options: baseOpts,
            });
        }
    }

    // ============================================================
    // Registration — override existing render functions
    // ============================================================
    function initChartEnhancements() {
        if (!ChartJS) return;

        // Replace momentum render
        if (typeof window.renderMomentumIndex === "function") {
            _register("momentum", window.renderMomentumIndex);
            window.renderMomentumIndex = renderMomentumIndexChart;
        }

        // Replace win probability render
        if (typeof window.renderWinProbability === "function") {
            _register("winprob", window.renderWinProbability);
            window.renderWinProbability = renderWinProbabilityChart;
        }

        // Replace xG timeline render
        if (typeof window.renderXGTimeline === "function") {
            _register("xgtimeline", window.renderXGTimeline);
            window.renderXGTimeline = renderXGTimelineChart;
        }

        // Replace radar render
        if (typeof window.renderRadarCharts === "function") {
            _register("radar", window.renderRadarCharts);
            window.renderRadarCharts = renderRadarChart;
        }

        }

    // ============================================================
    // 6. Pitch Control Overlay — SVG heatmap on pitch
    // ============================================================
    function renderPitchControlOverlay(data) {
        var container = document.getElementById("pitch-control-container");
        if (!container) return;
        container.innerHTML = "";

        if (!data || data.error || !data.home_grid || data.home_grid.length === 0) {
            container.innerHTML = '<div class="empty-state" data-i18n="noPitchControl">No pitch control data available</div>';
            return;
        }

        var svgNS = "http://www.w3.org/2000/svg";
        var pitchW = 525;
        var pitchH = 340;
        var svg = document.createElementNS(svgNS, "svg");
        svg.setAttribute("viewBox", "0 0 " + pitchW + " " + pitchH);
        svg.setAttribute("width", "100%");
        svg.setAttribute("height", "100%");
        svg.setAttribute("class", "pitch-svg");
        svg.style.maxHeight = "340px";

        // Pitch background (green)
        var bg = document.createElementNS(svgNS, "rect");
        bg.setAttribute("x", "0"); bg.setAttribute("y", "0");
        bg.setAttribute("width", String(pitchW)); bg.setAttribute("height", String(pitchH));
        bg.setAttribute("fill", "#2d7d3a");
        svg.appendChild(bg);

        // Heatmap overlay
        var grid = data.home_grid;
        var rows = grid.length;
        var cols = grid[0] ? grid[0].length : 0;
        if (rows > 0 && cols > 0) {
            var cellW = pitchW / cols;
            var cellH = pitchH / rows;
            for (var r = 0; r < rows; r++) {
                for (var c = 0; c < cols; c++) {
                    var val = grid[r][c]; // 0-1 home control
                    if (val == null) continue;
                    var r2 = 255 * (1 - val);
                    var g2 = 255 * val;
                    var fill = "rgba(" + Math.round(g2) + "," + Math.round(r2) + ",0,0.6)";
                    var rect = document.createElementNS(svgNS, "rect");
                    rect.setAttribute("x", String(c * cellW));
                    rect.setAttribute("y", String(r * cellH));
                    rect.setAttribute("width", String(cellW + 1));
                    rect.setAttribute("height", String(cellH + 1));
                    rect.setAttribute("fill", fill);
                    svg.appendChild(rect);
                }
            }
        }

        // Pitch markings
        var markings = [
            { x: 0, y: 0, w: pitchW, h: pitchH, fill: "none", stroke: "rgba(255,255,255,0.4)", sw: 1.5 },
            // Center line
            { x1: pitchW/2, y1: 0, x2: pitchW/2, y2: pitchH, stroke: "rgba(255,255,255,0.4)", sw: 1.5 },
            // Center circle
            { cx: pitchW/2, cy: pitchH/2, r: 30, fill: "none", stroke: "rgba(255,255,255,0.4)", sw: 1.5 },
            // Left penalty area
            { x: 0, y: pitchH*0.2, w: pitchW*0.16, h: pitchH*0.6, fill: "none", stroke: "rgba(255,255,255,0.4)", sw: 1.5 },
            // Right penalty area
            { x: pitchW*0.84, y: pitchH*0.2, w: pitchW*0.16, h: pitchH*0.6, fill: "none", stroke: "rgba(255,255,255,0.4)", sw: 1.5 },
        ];
        markings.forEach(function (m) {
            var el;
            if (m.x != null && m.w != null) {
                el = document.createElementNS(svgNS, "rect");
                el.setAttribute("x", String(m.x));
                el.setAttribute("y", String(m.y));
                el.setAttribute("width", String(m.w));
                el.setAttribute("height", String(m.h));
                el.setAttribute("fill", m.fill || "none");
                el.setAttribute("stroke", m.stroke);
                el.setAttribute("stroke-width", String(m.sw || 1));
            } else if (m.x1 != null) {
                el = document.createElementNS(svgNS, "line");
                el.setAttribute("x1", String(m.x1));
                el.setAttribute("y1", String(m.y1));
                el.setAttribute("x2", String(m.x2));
                el.setAttribute("y2", String(m.y2));
                el.setAttribute("stroke", m.stroke);
                el.setAttribute("stroke-width", String(m.sw || 1));
            } else if (m.cx != null) {
                el = document.createElementNS(svgNS, "circle");
                el.setAttribute("cx", String(m.cx));
                el.setAttribute("cy", String(m.cy));
                el.setAttribute("r", String(m.r));
                el.setAttribute("fill", m.fill || "none");
                el.setAttribute("stroke", m.stroke);
                el.setAttribute("stroke-width", String(m.sw || 1));
            }
            if (el) svg.appendChild(el);
        });

        container.appendChild(svg);

        // KPI bar below pitch
        var kpi = document.createElement("div");
        kpi.className = "pitch-control-kpi";
        kpi.innerHTML = '<span class="kpi-label" data-i18n="possession">Possession: </span>' +
            '<span class="kpi-value">' + (data.ball_control_pct || 50) + '% Home</span>';
        container.appendChild(kpi);
    }

    // ============================================================
    // 7. Pass Sonar — Polar area chart via Chart.js
    // ============================================================
    function renderPassSonar(data, playerName) {
        var canvas = document.getElementById("pass-sonar-canvas");
        if (!canvas) return;
        _destroyChart("pass-sonar-canvas");

        if (!data || data.error || !data.directions || data.directions.length === 0) {
            var parent = canvas.parentElement;
            if (parent) parent.innerHTML = '<div class="empty-state" data-i18n="noPassSonar">No pass sonar data</div>';
            return;
        }

        if (!ChartJS) {
            if (_origRenderers.passsonar) _origRenderers.passsonar(data);
            return;
        }

        var labels = ["N","NE","E","SE","S","SW","W","NW"];
        var values = data.pass_counts || [];
        var acc = data.accuracy_pct || [];

        var bgColors = values.map(function (v, i) {
            var a = acc[i] || 0;
            if (a > 75) return "rgba(34,197,94,0.7)";
            if (a > 50) return "rgba(234,179,8,0.7)";
            return "rgba(239,68,68,0.7)";
        });
        var borderColors = values.map(function (v, i) {
            var a = acc[i] || 0;
            if (a > 75) return "rgb(34,197,94)";
            if (a > 50) return "rgb(234,179,8)";
            return "rgb(239,68,68)";
        });

        var chart = new ChartJS(canvas.getContext("2d"), {
            type: "polarArea",
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: bgColors,
                    borderColor: borderColors,
                    borderWidth: 1,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "right", labels: { color: "#ccc", font: { size: 10 } } },
                    tooltip: {
                        callbacks: {
                            label: function (item) {
                                var idx = item.dataIndex;
                                return labels[idx] + ": " + values[idx] + " passes (" + acc[idx] + "% acc)";
                            },
                        },
                    },
                },
                scales: {
                    r: {
                        angleLines: { color: "rgba(255,255,255,0.15)" },
                        grid: { color: "rgba(255,255,255,0.1)" },
                        pointLabels: { color: "#ccc", font: { size: 10 } },
                        ticks: { color: "#999", backdropColor: "transparent", font: { size: 9 } },
                    },
                },
            },
        });
        _chartInstances["pass-sonar-canvas"] = chart;
        _saveInstance(chart, playerName ? playerName + "-pass-sonar" : "pass-sonar",
            ["Direction", "Count", "Accuracy %"],
            labels.map(function (l, i) { return [l, values[i], acc[i]]; }));
    }

    // ============================================================
    // 8. Space Control Heatmap — SVG Voronoi fill on pitch
    // ============================================================
    function renderSpaceControlHeatmap(data) {
        var container = document.getElementById("space-control-container");
        if (!container) return;
        container.innerHTML = "";

        if (!data || data.error || !data.grid || data.grid.length === 0) {
            container.innerHTML = '<div class="empty-state" data-i18n="noSpaceControl">No space control data available</div>';
            return;
        }

        var svgNS = "http://www.w3.org/2000/svg";
        var pitchW = 525;
        var pitchH = 340;
        var svg = document.createElementNS(svgNS, "svg");
        svg.setAttribute("viewBox", "0 0 " + pitchW + " " + pitchH);
        svg.setAttribute("width", "100%");
        svg.setAttribute("height", "100%");
        svg.style.maxHeight = "340px";

        // background
        var bg = document.createElementNS(svgNS, "rect");
        bg.setAttribute("x", "0"); bg.setAttribute("y", "0");
        bg.setAttribute("width", String(pitchW)); bg.setAttribute("height", String(pitchH));
        bg.setAttribute("fill", "#1a1a2e");
        svg.appendChild(bg);

        var grid = data.grid;
        var rows = grid.length;
        var cols = grid[0] ? grid[0].length : 0;
        if (rows > 0 && cols > 0) {
            var cellW = pitchW / cols;
            var cellH = pitchH / rows;
            for (var r = 0; r < rows; r++) {
                for (var c = 0; c < cols; c++) {
                    var val = grid[r][c];
                    var fill;
                    if (val === 0) fill = "rgba(37,99,235,0.5)";  // home = blue
                    else if (val === 1) fill = "rgba(220,38,38,0.5)"; // away = red
                    else fill = "rgba(255,255,255,0.1)"; // neutral

                    var rect = document.createElementNS(svgNS, "rect");
                    rect.setAttribute("x", String(c * cellW));
                    rect.setAttribute("y", String(r * cellH));
                    rect.setAttribute("width", String(cellW + 1));
                    rect.setAttribute("height", String(cellH + 1));
                    rect.setAttribute("fill", fill);
                    svg.appendChild(rect);
                }
            }
        }

        // Hot zones — highlight top 3
        var hotZones = data.hot_zones || [];
        var topZones = hotZones.slice(0, 3);
        topZones.forEach(function (zone) {
            if (zone.center_x == null) return;
            var cx = (zone.center_x / cols) * pitchW;
            var cy = (zone.center_y / rows) * pitchH;
            var radius = Math.sqrt((zone.area_pct || 5) / 100 * pitchW * pitchH / Math.PI) * 0.8;
            var circle = document.createElementNS(svgNS, "circle");
            circle.setAttribute("cx", String(cx));
            circle.setAttribute("cy", String(cy));
            circle.setAttribute("r", String(radius));
            circle.setAttribute("fill", "rgba(255,215,0,0.2)");
            circle.setAttribute("stroke", "rgba(255,215,0,0.6)");
            circle.setAttribute("stroke-width", "2");
            svg.appendChild(circle);
        });

        // Pitch markings
        var markings = [
            { x: 0, y: 0, w: pitchW, h: pitchH, fill: "none", stroke: "rgba(255,255,255,0.3)", sw: 1.5 },
            { x1: pitchW/2, y1: 0, x2: pitchW/2, y2: pitchH, stroke: "rgba(255,255,255,0.3)", sw: 1.5 },
            { cx: pitchW/2, cy: pitchH/2, r: 30, fill: "none", stroke: "rgba(255,255,255,0.3)", sw: 1.5 },
            { x: 0, y: pitchH*0.2, w: pitchW*0.16, h: pitchH*0.6, fill: "none", stroke: "rgba(255,255,255,0.3)", sw: 1.5 },
            { x: pitchW*0.84, y: pitchH*0.2, w: pitchW*0.16, h: pitchH*0.6, fill: "none", stroke: "rgba(255,255,255,0.3)", sw: 1.5 },
        ];
        markings.forEach(function (m) {
            var el;
            if (m.x != null && m.w != null) {
                el = document.createElementNS(svgNS, "rect");
                el.setAttribute("x", String(m.x)); el.setAttribute("y", String(m.y));
                el.setAttribute("width", String(m.w)); el.setAttribute("height", String(m.h));
                el.setAttribute("fill", m.fill || "none"); el.setAttribute("stroke", m.stroke);
                el.setAttribute("stroke-width", String(m.sw || 1));
            } else if (m.x1 != null) {
                el = document.createElementNS(svgNS, "line");
                el.setAttribute("x1", String(m.x1)); el.setAttribute("y1", String(m.y1));
                el.setAttribute("x2", String(m.x2)); el.setAttribute("y2", String(m.y2));
                el.setAttribute("stroke", m.stroke); el.setAttribute("stroke-width", String(m.sw || 1));
            } else if (m.cx != null) {
                el = document.createElementNS(svgNS, "circle");
                el.setAttribute("cx", String(m.cx)); el.setAttribute("cy", String(m.cy));
                el.setAttribute("r", String(m.r)); el.setAttribute("fill", m.fill || "none");
                el.setAttribute("stroke", m.stroke); el.setAttribute("stroke-width", String(m.sw || 1));
            }
            if (el) svg.appendChild(el);
        });

        container.appendChild(svg);

        var kpi = document.createElement("div");
        kpi.className = "space-control-kpi";
        var pcts = data.team_control_pcts || {};
        var homePct = pcts["0"] != null ? pcts["0"] + "% Home" : "—";
        var awayPct = pcts["1"] != null ? pcts["1"] + "% Away" : "—";
        kpi.innerHTML = '<span class="kpi-label">Control: </span>' +
            '<span class="kpi-value home">' + homePct + '</span> <span class="kpi-sep">|</span> ' +
            '<span class="kpi-value away">' + awayPct + '</span> ' +
            '<span class="kpi-sep">|</span> <span class="kpi-label">Space Gained: </span>' +
            '<span class="kpi-value">' + (data.space_gained || 0) + ' m²</span>';
        container.appendChild(kpi);
    }

    // ============================================================
    // 9. Role Badge — HTML colored badge
    // ============================================================
    function renderRoleBadge(role, confidence, secondary) {
        var colorMap = {
            "goalkeeper": "#f59e0b",
            "centre_back": "#3b82f6",
            "full_back": "#60a5fa",
            "inverted_fullback": "#818cf8",
            "defensive_midfielder": "#22c55e",
            "box_to_box_midfielder": "#10b981",
            "wide_midfielder": "#34d399",
            "attacking_midfielder": "#ef4444",
            "winger": "#f87171",
            "inside_forward": "#f97316",
            "target_forward": "#dc2626",
            "false_nine": "#fb923c",
            "poacher": "#b91c1c",
            "wide_playmaker": "#a78bfa",
            "utility_player": "#9ca3af",
        };
        var color = colorMap[role] || "#9ca3af";
        var badge = document.createElement("span");
        badge.className = "role-badge";
        badge.style.cssText = "display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;color:#fff;background:" + color;
        badge.textContent = role.replace(/_/g, " ");
        var confPct = Math.round((confidence || 0) * 100);
        badge.title = "Confidence: " + confPct + "%" + (secondary ? " | Secondary: " + secondary.replace(/_/g, " ") : "");
        return badge;
    }

    // ============================================================
    // 10. Dominance Index Gauge — SVG circular gauge
    // ============================================================
    function renderDominanceGauge(data) {
        var container = document.getElementById("dominance-gauge-container");
        if (!container) return;
        container.innerHTML = "";

        if (!data || data.error || data.index == null) {
            container.innerHTML = '<div class="empty-state" data-i18n="noDominance">No dominance data available</div>';
            return;
        }

        var svgNS = "http://www.w3.org/2000/svg";
        var size = 200;
        var cx = size / 2;
        var cy = size / 2;
        var radius = 80;
        var strokeW = 16;

        var svg = document.createElementNS(svgNS, "svg");
        svg.setAttribute("viewBox", "0 0 " + size + " " + size);
        svg.setAttribute("width", "100%");
        svg.setAttribute("height", "100%");
        svg.style.maxWidth = "200px";
        svg.style.maxHeight = "200px";

        // Background arc
        var bgArc = document.createElementNS(svgNS, "path");
        var d = describeArc(cx, cy, radius, 180, 360);
        bgArc.setAttribute("d", d);
        bgArc.setAttribute("fill", "none");
        bgArc.setAttribute("stroke", "rgba(255,255,255,0.1)");
        bgArc.setAttribute("stroke-width", String(strokeW));
        svg.appendChild(bgArc);

        // Value arc
        var index = Math.max(0, Math.min(100, data.index || 50));
        var angle = 180 + (index / 100) * 180;
        var color = index > 66 ? "#22c55e" : (index > 33 ? "#eab308" : "#ef4444");
        var valArc = document.createElementNS(svgNS, "path");
        valArc.setAttribute("d", describeArc(cx, cy, radius, 180, angle));
        valArc.setAttribute("fill", "none");
        valArc.setAttribute("stroke", color);
        valArc.setAttribute("stroke-width", String(strokeW));
        valArc.setAttribute("stroke-linecap", "round");
        svg.appendChild(valArc);

        // Center text
        var text = document.createElementNS(svgNS, "text");
        text.setAttribute("x", String(cx));
        text.setAttribute("y", String(cy - 5));
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("fill", "#fff");
        text.setAttribute("font-size", "28");
        text.setAttribute("font-weight", "bold");
        text.textContent = String(Math.round(index));
        svg.appendChild(text);

        var label = document.createElementNS(svgNS, "text");
        label.setAttribute("x", String(cx));
        label.setAttribute("y", String(cy + 15));
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("fill", "#999");
        label.setAttribute("font-size", "11");
        label.textContent = "DOMINANCE";
        svg.appendChild(label);

        container.appendChild(svg);
        container.style.textAlign = "center";

        // Sub-scores as horizontal bars
        var subs = data.sub_scores || {};
        var subContainer = document.createElement("div");
        subContainer.className = "dominance-subs";
        subContainer.style.cssText = "margin-top:12px;";
        var labels = {
            possession: "Possession",
            xg_diff: "xG Diff",
            territory: "Territory",
            pressing: "Pressing",
            pass_completion: "Pass Comp",
        };
        Object.keys(labels).forEach(function (key) {
            var val = subs[key];
            if (val == null) return;
            var row = document.createElement("div");
            row.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:4px;";
            var lbl = document.createElement("span");
            lbl.style.cssText = "width:80px;font-size:11px;color:#999;text-align:right;";
            lbl.textContent = labels[key];
            var barOuter = document.createElement("div");
            barOuter.style.cssText = "flex:1;height:8px;background:rgba(255,255,255,0.1);border-radius:4px;overflow:hidden;";
            var barInner = document.createElement("div");
            barInner.style.cssText = "height:100%;width:" + val + "%;background:" + (val > 66 ? "#22c55e" : val > 33 ? "#eab308" : "#ef4444") + ";border-radius:4px;transition:width 0.3s;";
            barOuter.appendChild(barInner);
            var valLabel = document.createElement("span");
            valLabel.style.cssText = "width:35px;font-size:11px;color:#fff;text-align:left;";
            valLabel.textContent = Math.round(val);
            row.appendChild(lbl);
            row.appendChild(barOuter);
            row.appendChild(valLabel);
            subContainer.appendChild(row);
        });

        container.appendChild(subContainer);

        // Phase breakdown
        var phases = data.phases || {};
        if (Object.keys(phases).length > 0) {
            var phaseTitle = document.createElement("div");
            phaseTitle.style.cssText = "font-size:11px;color:#999;margin-top:8px;font-weight:600;";
            phaseTitle.textContent = "Phase Breakdown";
            container.appendChild(phaseTitle);
            var phaseContainer = document.createElement("div");
            phaseContainer.style.cssText = "display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;";
            Object.keys(phases).forEach(function (phase) {
                var v = phases[phase];
                var chip = document.createElement("span");
                chip.style.cssText = "padding:2px 8px;border-radius:8px;font-size:10px;background:rgba(255,255,255,0.1);color:#ccc;";
                chip.textContent = phase.replace(/_/g, " ") + ": " + Math.round(v) + "%";
                phaseContainer.appendChild(chip);
            });
            container.appendChild(phaseContainer);
        }
    }

    // Arc helper for SVG gauge
    function describeArc(x, y, radius, startAngle, endAngle) {
        var start = polarToCartesian(x, y, radius, endAngle);
        var end = polarToCartesian(x, y, radius, startAngle);
        var largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
        return "M " + start.x + " " + start.y + " A " + radius + " " + radius + " 0 " + largeArcFlag + " 0 " + end.x + " " + end.y;
    }

    function polarToCartesian(cx, cy, r, angleDeg) {
        var rad = (angleDeg - 180) * Math.PI / 180;
        return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
    }

    // ============================================================
    // Register on window for external access
    // ============================================================
    window.KawkabCharts = {
        init: initChartEnhancements,
        renderMomentum: renderMomentumIndexChart,
        renderWinProb: renderWinProbabilityChart,
        renderXGTimeline: renderXGTimelineChart,
        renderRadar: renderRadarChart,
        renderDualRadar: renderDualRadar,
        renderPitchControlOverlay: renderPitchControlOverlay,
        renderPassSonar: renderPassSonar,
        renderSpaceControlHeatmap: renderSpaceControlHeatmap,
        renderRoleBadge: renderRoleBadge,
        renderDominanceGauge: renderDominanceGauge,
        _instances: _chartInstances,
        downloadPNG: downloadPNG,
        downloadCSV: downloadCSV,
        setupChartExport: setupChartExport,
    };

    // Auto-init on DOMContentLoaded
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initChartEnhancements);
    } else {
        initChartEnhancements();
    }
})();
