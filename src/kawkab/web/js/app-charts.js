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

    // Register on window for external access
    window.KawkabCharts = {
        init: initChartEnhancements,
        renderMomentum: renderMomentumIndexChart,
        renderWinProb: renderWinProbabilityChart,
        renderXGTimeline: renderXGTimelineChart,
        renderRadar: renderRadarChart,
        renderDualRadar: renderDualRadar,
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
