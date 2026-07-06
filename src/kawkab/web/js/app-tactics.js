// Kawkab AI - Tactical Periods + Formation + Shape + Pressing + Tactical Report
// Phase 2.3-2.4 + Tactical Engine enhancements

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
        showSkeleton('tactics-phases-content');
        showSkeleton('tactics-formation-content');
        showSkeleton('tactics-shape-content');
        showSkeleton('tactics-pressing-content');
        showSkeleton('tactics-profile-content');

        bridge.get_tactical_periods(matchId, function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                renderTacticalPhases(data);
            } catch(e) { status.textContent = 'Error loading phases.'; showToast('Error loading tactical phases.', 'error'); console.warn(e); }
            hideSkeleton('tactics-phases-content');
        });

        bridge.analyze_formation(matchId, function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                renderFormation(data);
            } catch(e) { showToast('Error loading formation data.', 'error'); console.warn(e); }
            hideSkeleton('tactics-formation-content');
        });

        // New: shape analysis
        if (bridge.analyze_tactical_shapes) {
            bridge.analyze_tactical_shapes(matchId, function(result) {
                try {
                    var data = typeof result === 'string' ? JSON.parse(result) : result;
                    renderShapeAnalysis(data);
                } catch(e) { console.warn('Shape analysis error:', e); }
                hideSkeleton('tactics-shape-content');
            });
        } else {
            document.getElementById('tactics-shape-content').innerHTML = '<p class="hint">Shape analysis not available in this build.</p>';
            hideSkeleton('tactics-shape-content');
        }

        // New: pressing classification
        if (bridge.classify_pressing) {
            bridge.classify_pressing(matchId, function(result) {
                try {
                    var data = typeof result === 'string' ? JSON.parse(result) : result;
                    renderPressingAnalysis(data);
                } catch(e) { console.warn('Pressing analysis error:', e); }
                hideSkeleton('tactics-pressing-content');
            });
        } else {
            document.getElementById('tactics-pressing-content').innerHTML = '<p class="hint">Pressing classification not available in this build.</p>';
            hideSkeleton('tactics-pressing-content');
        }

        // New: tactical profile comparison
        if (bridge.get_tactical_report) {
            bridge.get_tactical_report(matchId, function(result) {
                try {
                    var data = typeof result === 'string' ? JSON.parse(result) : result;
                    renderTacticalProfile(data);
                } catch(e) { console.warn('Tactical report error:', e); }
                hideSkeleton('tactics-profile-content');
            });
        } else {
            document.getElementById('tactics-profile-content').innerHTML = '<p class="hint">Tactical report not available in this build.</p>';
            hideSkeleton('tactics-profile-content');
        }

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
                (f.out_possession_formation && f.out_possession_formation !== f.in_possession_formation ? ' \u2192 ' + escapeHtml(f.out_possession_formation) : '') +
                '</div>' +
                '<div style="display:flex;gap:12px;margin-top:4px;font-size:0.72rem;color:var(--text-muted)">' +
                '<span>Width: ' + (f.avg_width_in || 0).toFixed(1) + 'm</span>' +
                '<span>Depth: ' + (f.avg_depth_in || 0).toFixed(1) + 'm</span>' +
                '<span>Compact: ' + (f.avg_compactness_in || 0).toFixed(2) + '</span>' +
                '</div></div>';
        });
        container.innerHTML = html;
    }

    function renderShapeAnalysis(data) {
        var container = document.getElementById('tactics-shape-content');
        if (!container) return;
        if (data.error || (!data.home && !data.away)) {
            container.innerHTML = '<p class="hint">Shape analysis not available.</p>';
            return;
        }
        var html = '<div class="shape-grid">';
        ['home', 'away'].forEach(function(side) {
            var s = data[side];
            if (!s) {
                html += '<div class="shape-card"><div class="label">' + side.charAt(0).toUpperCase() + side.slice(1) + '</div><div class="value">No data</div></div>';
                return;
            }
            var attShape = s.primary_attacking_shape || 'unknown';
            var defShape = s.primary_defensive_shape || 'unknown';
            var diamond = s.diamond_midfield_pct || 0;
            var triangles = s.avg_triangles_per_frame || 0;
            var changes = s.shape_changes || 0;
            var shapeIcon = '📐';
            if (attShape.indexOf('3-2-5') >= 0) shapeIcon = '🧩';
            else if (attShape.indexOf('Diamond') >= 0 || attShape.indexOf('4-1-2-1-2') >= 0) shapeIcon = '🔷';
            html += '<div class="shape-card">' +
                '<div class="label">' + side.charAt(0).toUpperCase() + side.slice(1) + '</div>' +
                '<div class="value" style="font-size:1.2rem">' + shapeIcon + ' ' + escapeHtml(attShape) + '</div>' +
                '<div style="display:flex;gap:8px;margin-top:4px;font-size:0.72rem;color:var(--text-muted);flex-wrap:wrap">' +
                '<span>Def: ' + escapeHtml(defShape) + '</span>' +
                '<span>Diamond: ' + diamond.toFixed(0) + '%</span>' +
                '<span>Tri/frame: ' + triangles.toFixed(1) + '</span>' +
                '<span>Changes: ' + changes + '</span>' +
                '</div></div>';
        });
        html += '</div>';
        container.innerHTML = html;
    }

    function renderPressingAnalysis(data) {
        var container = document.getElementById('tactics-pressing-content');
        if (!container) return;
        if (data.error || (!data.home && !data.away)) {
            container.innerHTML = '<p class="hint">Pressing analysis not available.</p>';
            return;
        }
        var html = '<div class="pressing-grid">';
        ['home', 'away'].forEach(function(side) {
            var p = data[side];
            if (!p) {
                html += '<div class="pressing-card"><div class="label">' + side.charAt(0).toUpperCase() + side.slice(1) + '</div><div class="value">No data</div></div>';
                return;
            }
            var blockTypes = { high_block: '🔥 High Block', mid_block: '⚖️ Mid Block', low_block: '🛡 Low Block' };
            var styleTypes = { man_oriented: '🧑 Man-Oriented', zonal: '🧱 Zonal', unknown: '—' };
            var blockLabel = blockTypes[p.primary_block_type] || p.primary_block_type || 'unknown';
            var styleLabel = styleTypes[p.pressing_style] || p.pressing_style || '—';
            html += '<div class="pressing-card">' +
                '<div class="label">' + side.charAt(0).toUpperCase() + side.slice(1) + '</div>' +
                '<div class="value" style="font-size:1.1rem">' + escapeHtml(blockLabel) + '</div>' +
                '<div style="display:flex;gap:8px;margin-top:4px;font-size:0.72rem;color:var(--text-muted);flex-wrap:wrap">' +
                '<span>Style: ' + escapeHtml(styleLabel) + '</span>' +
                '<span>PPDA: ' + (p.ppda || 0).toFixed(1) + '</span>' +
                '<span>Triggers: ' + (p.trigger_count || 0) + '</span>' +
                '<span>Success: ' + ((p.trigger_success_rate || 0) * 100).toFixed(0) + '%</span>' +
                '<span>Intensity: ' + (p.avg_press_intensity || 0).toFixed(1) + '/min</span>' +
                '</div></div>';
        });
        html += '</div>';
        container.innerHTML = html;
    }

    function renderTacticalProfile(data) {
        var container = document.getElementById('tactics-profile-content');
        if (!container) return;
        if (data.error) {
            container.innerHTML = '<p class="hint">Tactical report not available.</p>';
            return;
        }

        var html = '<div class="tactical-profile-table-wrapper"><table class="tactical-profile-table"><thead><tr>' +
            '<th>Metric</th><th>' + escapeHtml((data.home && data.home.team) || 'Home') + '</th><th>' + escapeHtml((data.away && data.away.team) || 'Away') + '</th></tr></thead><tbody>';

        function addRow(label, homeVal, awayVal, highlightBetter) {
            var h = homeVal !== undefined && homeVal !== null ? homeVal : '—';
            var a = awayVal !== undefined && awayVal !== null ? awayVal : '—';
            var hClass = '', aClass = '';
            if (highlightBetter && typeof h === 'number' && typeof a === 'number') {
                if (h > a) hClass = ' class="better"';
                else if (a > h) aClass = ' class="better"';
            }
            html += '<tr><td>' + label + '</td><td' + hClass + '>' + h + '</td><td' + aClass + '>' + a + '</td></tr>';
        }

        var h = data.home || {}, a = data.away || {};
        addRow('Attacking Shape', h.primary_shape || '—', a.primary_shape || '—');
        addRow('Formation', h.primary_formation || '—', a.primary_formation || '—');
        addRow('Pressing System', h.pressing_system || '—', a.pressing_system || '—');
        addRow('Pressing Style', h.pressing_style || '—', a.pressing_style || '—');
        addRow('Triangles', h.triangle_count || 0, a.triangle_count || 0, true);
        addRow('Triangles/90', h.triangles_per_90 || 0, a.triangles_per_90 || 0, true);
        addRow('Transitions', h.transition_count || 0, a.transition_count || 0, true);

        html += '</tbody></table></div>';

        // Key observations
        if (data.key_tactical_observations && data.key_tactical_observations.length > 0) {
            html += '<div style="margin-top:10px"><strong>Tactical Observations:</strong><ul style="margin:4px 0 0 16px;font-size:0.8rem">';
            data.key_tactical_observations.forEach(function(obs) {
                html += '<li>' + escapeHtml(obs) + '</li>';
            });
            html += '</ul></div>';
        }

        container.innerHTML = html;
    }

    function initTacticsKnowledge() {
        var tabs = document.querySelectorAll('[data-knowledge-tab]');
        tabs.forEach(function(tab) {
            tab.addEventListener('click', function() {
                tabs.forEach(function(t) { t.classList.remove('active'); });
                tab.classList.add('active');
                var panels = document.querySelectorAll('.knowledge-panel');
                panels.forEach(function(p) { p.classList.add('hidden'); });
                var target = document.getElementById(tab.getAttribute('data-knowledge-tab') + '-knowledge');
                if (target) target.classList.remove('hidden');
            });
        });
    }

    function escapeHtml(str) {
        if (typeof str !== 'string') return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function showSkeleton(id) {
        var el = document.getElementById(id);
        if (el) el.style.opacity = '0.5';
    }

    function hideSkeleton(id) {
        var el = document.getElementById(id);
        if (el) el.style.opacity = '1';
    }

    window.initTacticsWorkspace = initTacticsWorkspace;
    window.loadTacticsAnalysis = loadTacticsAnalysis;
    window.renderTacticalPhases = renderTacticalPhases;
    window.renderFormation = renderFormation;
    window.renderShapeAnalysis = renderShapeAnalysis;
    window.renderPressingAnalysis = renderPressingAnalysis;
    window.renderTacticalProfile = renderTacticalProfile;
    window.initTacticsKnowledge = initTacticsKnowledge;

    window.KawkabTactics = {
        initTacticsWorkspace: initTacticsWorkspace,
        loadTacticsAnalysis: loadTacticsAnalysis,
        renderTacticalPhases: renderTacticalPhases,
        renderFormation: renderFormation,
        renderShapeAnalysis: renderShapeAnalysis,
        renderPressingAnalysis: renderPressingAnalysis,
        renderTacticalProfile: renderTacticalProfile,
        initTacticsKnowledge: initTacticsKnowledge,
    };

})();
