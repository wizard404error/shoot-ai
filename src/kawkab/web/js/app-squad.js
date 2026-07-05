// Kawkab AI - Squad Management (Phase 4)
// Extracted from app-ai.js for modularity

(function() { 'use strict';

    function initSquadWorkspace() {
        var loadBtn = document.getElementById('squad-load-btn');
        var matchSelect = document.getElementById('squad-match-select');
        if (!loadBtn) return;

        window.loadSquadMatchSelect = function() {
            if (typeof bridge === 'undefined' || !bridge) return;
            bridge.get_all_matches(function(result) {
                try {
                    var data = typeof result === 'string' ? JSON.parse(result) : result;
                    if (data.error) data = [];
                    var sel = document.getElementById('squad-match-select');
                    sel.innerHTML = '<option value="">-- Select Match --</option>';
                    (data || []).forEach(function(m) {
                        var name = m.name || (m.home_team + ' vs ' + m.away_team) || 'Match #' + m.id;
                        sel.innerHTML += '<option value="' + m.id + '">' + escapeHtml(name) + '</option>';
                    });
                } catch(e) { showToast('Failed to load squad matches.', 'error'); console.warn(e); }
            });
        };

        loadBtn.addEventListener('click', function() {
            var matchId = parseInt(matchSelect.value, 10);
            if (!matchId) { showToast('Select a match first.', 'warning'); return; }
            loadSquadData(matchId);
        });

        loadSquadMatchSelect();
    }

    function loadSquadData(matchId) {
        var status = document.getElementById('squad-status');
        status.textContent = 'Loading...';

        document.getElementById('squad-workspace').classList.remove('hidden');

        bridge.get_squad_summary(matchId, function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                renderSquadRoster(data);
                if (data.squad) {
                    loadPlayerRatings(matchId, data.squad);
                }
            } catch(e) { status.textContent = 'Error loading squad.'; showToast('Error loading squad data.', 'error'); console.warn(e); return; }
            status.textContent = 'Done';
        });
    }

    function renderSquadRoster(data) {
        var container = document.getElementById('squad-roster-content');
        if (!container) return;
        if (!data.squad || Object.keys(data.squad).length === 0) {
            container.innerHTML = '<p class="hint">No squad data available.</p>';
            return;
        }

        var html = '';
        Object.keys(data.squad).forEach(function(team) {
            var players = data.squad[team] || [];
            html += '<div class="squad-team-header">' + escapeHtml(team.charAt(0).toUpperCase() + team.slice(1)) + ' (' + players.length + ')</div>';
            players.forEach(function(p) {
                html += '<div class="squad-player-row" data-track-id="' + p.track_id + '">' +
                    '<span class="jersey">' + escapeHtml(String(p.jersey || '')) + '</span>' +
                    '<span class="name">' + escapeHtml(p.name || 'Player #' + p.track_id) + '</span>' +
                    '<span class="pos">' + escapeHtml(p.position || '') + '</span>' +
                    '<span class="stat">P' + (p.passes || 0) + '</span>' +
                    '<span class="stat">S' + (p.shots || 0) + '</span>' +
                    '<span class="stat">T' + (p.tackles || 0) + '</span>' +
                    '<span class="rating-badge" id="rating-' + p.track_id + '">--</span>' +
                    '</div>';
            });
        });
        container.innerHTML = html;
    }

    function initSquadHealthTab() {
        var loadBtn = document.getElementById('squad-health-load-btn');
        if (!loadBtn) return;
        loadBtn.addEventListener('click', function() {
            var matchId = parseInt(document.getElementById('squad-match-select').value, 10);
            if (!matchId) { showToast('Select a match first.', 'warning'); return; }
            loadSquadHealthData(matchId);
        });
    }

    function loadSquadHealthData(matchId) {
        var status = document.getElementById('squad-status');
        status.textContent = 'Loading health...';
        document.getElementById('squad-health-content').innerHTML = '<p class="hint">Loading injury risk data...</p>';

        bridge.get_squad_injury_report(matchId, function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                if (data.error) { showToast(data.error, 'error'); status.textContent = 'Error'; return; }
                renderSquadHealthSummary(data);
                renderSquadHealthPlayers(data);
            } catch(e) { status.textContent = 'Error'; showToast('Failed to load health data.', 'error'); console.warn(e); return; }
            status.textContent = 'Done';
        });
    }

    function renderSquadHealthSummary(data) {
        var container = document.getElementById('squad-health-summary');
        if (!container) return;
        container.innerHTML =
            '<div class="risk-health-stat"><div class="value">' + (data.avg_risk_home || 0).toFixed(2) + '</div><div class="label">Avg Risk (Home)</div></div>' +
            '<div class="risk-health-stat"><div class="value">' + (data.avg_risk_away || 0).toFixed(2) + '</div><div class="label">Avg Risk (Away)</div></div>' +
            '<div class="risk-health-stat"><div class="value">' + (data.high_risk_count || 0) + '</div><div class="label">High/Critical Risk</div></div>' +
            '<div class="risk-health-stat"><div class="value">' + (data.total_players || 0) + '</div><div class="label">Total Players</div></div>';
    }

    function renderSquadHealthPlayers(data) {
        var container = document.getElementById('squad-health-content');
        if (!container) return;
        var html = '';
        function renderTeam(players, label) {
            if (!players || players.length === 0) return;
            html += '<div class="squad-team-header">' + escapeHtml(label) + ' (' + players.length + ')</div>';
            players.forEach(function(p) {
                var riskClass = 'risk-' + (p.risk_category || 'low');
                var acwrPct = Math.min((p.acwr || 0) / 2.0 * 100, 100);
                var factors = p.key_factors && p.key_factors.length > 0 ? p.key_factors.join('; ') : '';
                html += '<div class="squad-player-row" data-track-id="' + p.track_id + '">' +
                    '<span class="jersey">' + escapeHtml(String(p.jersey || '')) + '</span>' +
                    '<span class="name">' + escapeHtml(p.name || 'Player #' + p.track_id) + '</span>' +
                    '<span class="pos">' + escapeHtml(p.position || '') + '</span>' +
                    '<span class="stat"><span class="risk-acwr-bar"><span class="risk-acwr-bar-fill" style="width:' + acwrPct.toFixed(0) + '%"></span></span>' + (p.acwr || 0).toFixed(2) + '</span>' +
                    '<span class="risk-badge ' + riskClass + '">' + escapeHtml(p.risk_category || 'low') + '</span>' +
                    '<span class="risk-rec" title="' + escapeHtml(p.recovery_recommendation || '') + '">' + escapeHtml((p.recovery_recommendation || '').substring(0, 20)) + '</span>' +
                    '<span class="risk-factors" title="' + escapeHtml(factors) + '">' + escapeHtml(factors.substring(0, 25)) + '</span>' +
                    '</div>';
            });
        }
        renderTeam(data.home_players, 'Home');
        renderTeam(data.away_players, 'Away');
        if (!html) html = '<p class="hint">No player health data available.</p>';
        container.innerHTML = html;
    }

    function loadPlayerRatings(matchId, squad) {
        Object.keys(squad).forEach(function(team) {
            (squad[team] || []).forEach(function(p) {
                bridge.get_player_rating(matchId, p.track_id, function(result) {
                    try {
                        var data = typeof result === 'string' ? JSON.parse(result) : result;
                        var badge = document.getElementById('rating-' + p.track_id);
                        if (badge) {
                            var r = data.rating || 0;
                            var cls = r >= 70 ? 'rating-high' : (r >= 40 ? 'rating-mid' : 'rating-low');
                            badge.textContent = r.toFixed(0);
                            badge.className = 'rating-badge ' + cls;
                        }
                    } catch(e) { /* ignore */ }
                });
            });
        });
    }

    function escapeHtml(text) {
        if (typeof text !== 'string') return '';
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                   .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    window.initSquadWorkspace = initSquadWorkspace;
    window.loadSquadData = loadSquadData;
    window.renderSquadRoster = renderSquadRoster;
    window.loadPlayerRatings = loadPlayerRatings;
    window.initSquadHealthTab = initSquadHealthTab;
    window.loadSquadHealthData = loadSquadHealthData;
    window.renderSquadHealthSummary = renderSquadHealthSummary;
    window.renderSquadHealthPlayers = renderSquadHealthPlayers;

    window.KawkabSquad = {
        initSquadWorkspace: initSquadWorkspace,
        loadSquadData: loadSquadData,
        renderSquadRoster: renderSquadRoster,
        initSquadHealthTab: initSquadHealthTab,
    };

})();
