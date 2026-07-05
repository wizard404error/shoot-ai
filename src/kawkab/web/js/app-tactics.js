// Kawkab AI - Tactical Periods + Formation Analysis (Phase 2.3-2.4)
// Extracted from app.js for modularity

(function() { 'use strict';

    function initTacticsWorkspace() {
        var loadBtn = document.getElementById('tactics-load-btn');
        var matchSelect = document.getElementById('tactics-match-select');
        if (!loadBtn) return;

        window.loadTacticsMatchSelect = function() {
            if (typeof bridge === 'undefined' || !bridge) return;
            bridge.get_all_matches(function(result) {
                try {
                    var data = typeof result === 'string' ? JSON.parse(result) : result;
                    if (data.error) data = [];
                    var sel = document.getElementById('tactics-match-select');
                    sel.innerHTML = '<option value="">-- Select Match --</option>';
                    (data || []).forEach(function(m) {
                        var name = m.name || (m.home_team + ' vs ' + m.away_team) || 'Match #' + m.id;
                        sel.innerHTML += '<option value="' + m.id + '">' + escapeHtml(name) + '</option>';
                    });
                } catch(e) { showToast('Failed to load matches for tactics.', 'error'); console.warn(e); }
            });
        };

        loadBtn.addEventListener('click', function() {
            var matchId = parseInt(matchSelect.value, 10);
            if (!matchId) { showToast('Select a match first.', 'warning'); return; }
            loadTacticsAnalysis(matchId);
        });

        loadTacticsMatchSelect();
    }

    function loadTacticsAnalysis(matchId) {
        var status = document.getElementById('tactics-status');
        status.textContent = 'Analyzing...';

        bridge.get_tactical_periods(matchId, function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                renderTacticalPhases(data);
            } catch(e) { status.textContent = 'Error loading phases.'; showToast('Error loading tactical phases.', 'error'); console.warn(e); }
        });

        bridge.analyze_formation(matchId, function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                renderFormation(data);
            } catch(e) { showToast('Error loading formation data.', 'error'); console.warn(e); }
        });

        document.getElementById('tactics-workspace').classList.remove('hidden');
        status.textContent = 'Done';
    }

    function renderTacticalPhases(data) {
        var container = document.getElementById('tactics-phases-content');
        if (!container) return;
        if (data.error || !data.phases || data.phases.length === 0) {
            container.innerHTML = '<p class="hint">No phase data available.</p>';
            return;
        }

        var colors = {
            settled_possession: '#2563eb', transition: '#d97706',
            counter: '#dc2626', set_piece: '#16a34a', direct: '#8b5cf6',
        };
        var totalDur = 0;
        data.phases.forEach(function(p) { totalDur += p.duration_s; });
        totalDur = Math.max(1, totalDur);

        var phaseHtml = '';
        data.phases.forEach(function(p) {
            var pct = (p.duration_s / totalDur * 100).toFixed(1);
            var color = colors[p.label] || '#64748b';
            phaseHtml += '<div class="phase-bar">' +
                '<span class="phase-label">' + escapeHtml(p.label.replace(/_/g, ' ')) + '</span>' +
                '<span class="phase-fill" style="width:' + pct + '%;background:' + color + '"></span>' +
                '<span class="phase-dur">' + p.duration_s.toFixed(0) + 's</span>' +
                '<span class="phase-pct">' + pct + '%</span>' +
                '</div>';
        });

        container.innerHTML = '<div style="margin-bottom:8px">' +
            '<span style="font-size:0.78rem;color:var(--text-muted)">' + data.phases.length + ' phases detected</span>' +
            '</div>' + phaseHtml;
    }

    function renderFormation(data) {
        var container = document.getElementById('tactics-formation-content');
        if (!container) return;
        if (data.error) {
            container.innerHTML = '<p class="hint">Formation analysis not available.</p>';
            return;
        }

        var html = '';
        ['home', 'away'].forEach(function(side) {
            var f = data[side];
            if (!f || !f.in_possession_formation) {
                html += '<div class="formation-card"><div class="label">' + side.charAt(0).toUpperCase() + side.slice(1) + '</div>' +
                    '<div class="value">Unknown</div></div>';
                return;
            }
            html += '<div class="formation-card">' +
                '<div class="label">' + side.charAt(0).toUpperCase() + side.slice(1) + '</div>' +
                '<div class="value" style="font-size:1.3rem">' + escapeHtml(f.in_possession_formation) +
                (f.out_possession_formation && f.out_possession_formation !== f.in_possession_formation ? ' → ' + escapeHtml(f.out_possession_formation) : '') +
                '</div>' +
                '<div style="display:flex;gap:12px;margin-top:4px;font-size:0.72rem;color:var(--text-muted)">' +
                '<span>Width: ' + (f.avg_width_in || 0).toFixed(1) + 'm</span>' +
                '<span>Depth: ' + (f.avg_depth_in || 0).toFixed(1) + 'm</span>' +
                '<span>Compact: ' + (f.avg_compactness_in || 0).toFixed(2) + '</span>' +
                '</div></div>';
        });
        container.innerHTML = html;
    }

    function escapeHtml(str) {
        if (typeof str !== 'string') return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    window.initTacticsWorkspace = initTacticsWorkspace;
    window.loadTacticsAnalysis = loadTacticsAnalysis;
    window.renderTacticalPhases = renderTacticalPhases;
    window.renderFormation = renderFormation;

    window.KawkabTactics = {
        initTacticsWorkspace: initTacticsWorkspace,
        loadTacticsAnalysis: loadTacticsAnalysis,
        renderTacticalPhases: renderTacticalPhases,
        renderFormation: renderFormation,
    };

})();
