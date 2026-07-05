// Kawkab AI - Scout Portal (Wave E)
// Extracted from app.js for modularity

(function() { 'use strict';

    var _scoutState = {
        searchResults: [],
        shortlist: [],
        compareA: null,
        compareB: null,
    };

    function initScoutPortal() {
        var tabs = document.querySelectorAll('.scout-tabs .tab-btn');
        tabs.forEach(function(tab) {
            tab.addEventListener('click', function() {
                tabs.forEach(function(t) { t.classList.remove('active'); });
                this.classList.add('active');
                document.querySelectorAll('.scout-tab-content').forEach(function(c) { c.classList.remove('active'); });
                var target = document.getElementById('scout-' + this.dataset.stab);
                if (target) target.classList.add('active');
            });
        });

        var searchBtn = document.getElementById('scout-search-btn');
        var searchInput = document.getElementById('scout-search-input');
        var compareBtn = document.getElementById('scout-compare-btn');
        var reportBtn = document.getElementById('scout-report-btn');
        var refreshBtn = document.getElementById('scout-shortlist-refresh');

        if (!searchBtn) return;

        searchBtn.addEventListener('click', function() {
            var query = searchInput.value.trim();
            var pos = document.getElementById('scout-position-input').value.trim();
            if (!query) { showToast('Enter a player name.', 'warning'); return; }
            scoutSearch(query, pos);
        });

        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') searchBtn.click();
        });

        compareBtn.addEventListener('click', function() {
            var a = document.getElementById('scout-compare-a').value;
            var b = document.getElementById('scout-compare-b').value;
            if (!a || !b) { showToast('Select two players to compare.', 'warning'); return; }
            if (a === b) { showToast('Select two different players.', 'warning'); return; }
            scoutCompare(a, b);
        });

        reportBtn.addEventListener('click', function() {
            generateScoutReport();
        });

        refreshBtn.addEventListener('click', loadShortlist);

        loadShortlist();
        populateCompareSelects();
    }

    function scoutSearch(query, position) {
        if (typeof bridge === 'undefined' || !bridge) {
            var mockPlayers = [
                { track_id: 1, name: 'Erling Haaland', position: 'FW', team: 'Manchester City', age: 22, matches: 28, goals: 32, assists: 5, xg: 28.5, passes: 412, tackles: 12 },
                { track_id: 2, name: 'Kevin De Bruyne', position: 'MF', team: 'Manchester City', age: 30, matches: 25, goals: 8, assists: 16, xg: 7.2, passes: 1250, tackles: 34 },
                { track_id: 3, name: 'Virgil van Dijk', position: 'DF', team: 'Liverpool', age: 31, matches: 30, goals: 3, assists: 2, xg: 2.8, passes: 1800, tackles: 45 },
                { track_id: 4, name: 'Kylian Mbappé', position: 'FW', team: 'PSG', age: 24, matches: 26, goals: 28, assists: 8, xg: 24.1, passes: 380, tackles: 8 },
                { track_id: 5, name: 'Jude Bellingham', position: 'MF', team: 'Real Madrid', age: 20, matches: 27, goals: 15, assists: 7, xg: 12.8, passes: 890, tackles: 42 },
            ];
            var q = query.toLowerCase();
            _scoutState.searchResults = mockPlayers.filter(function(p) {
                return (p.name || '').toLowerCase().indexOf(q) >= 0;
            });
            renderScoutResults();
            return;
        }
        bridge.scout_search_players(query, position, function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                _scoutState.searchResults = data.results || [];
                renderScoutResults();
            } catch(e) { showToast('Scout search failed.', 'error'); console.warn('Scout search error:', e); }
        });
    }

    function renderScoutResults() {
        var container = document.getElementById('scout-search-results');
        if (!container) return;
        var results = _scoutState.searchResults;

        if (!results || results.length === 0) {
            container.innerHTML = '<p class="hint">No players found. Try a different search.</p>';
            return;
        }

        var html = '';
        results.forEach(function(p) {
            var initial = (p.name || '?').charAt(0).toUpperCase();
            var onShortlist = _scoutState.shortlist.some(function(s) { return s.track_id === p.track_id; });
            html += '<div class="scout-player-card">' +
                '<div class="scout-player-avatar">' + initial + '</div>' +
                '<div class="scout-player-info">' +
                '<div class="scout-player-name">' + escapeHtml(p.name || 'Unknown') + '</div>' +
                '<div class="scout-player-meta">' +
                '<span>' + escapeHtml(p.position || '--') + '</span>' +
                '<span>' + escapeHtml(p.team || '--') + '</span>' +
                '<span>Age: ' + (p.age || '--') + '</span>' +
                '</div></div>' +
                '<div class="scout-player-stats">' +
                '<div class="stat"><div class="stat-val">' + (p.goals != null ? p.goals : '--') + '</div><div class="stat-label">G</div></div>' +
                '<div class="stat"><div class="stat-val">' + (p.assists != null ? p.assists : '--') + '</div><div class="stat-label">A</div></div>' +
                '<div class="stat"><div class="stat-val">' + (p.matches || '--') + '</div><div class="stat-label">M</div></div>' +
                '</div>' +
                '<div class="scout-icons">' +
                '<button class="scout-icon ' + (onShortlist ? 'added' : '') + '" data-action="shortlist" data-track-id="' + p.track_id + '" data-name="' + escapeHtml(p.name) + '" data-pos="' + escapeHtml(p.position || '') + '">' + (onShortlist ? '★' : '☆') + '</button>' +
                '<button class="scout-icon" data-action="compare" data-track-id="' + p.track_id + '" data-name="' + escapeHtml(p.name) + '">⇄</button>' +
                '</div></div>';
        });
        container.innerHTML = html;

        container.querySelectorAll('[data-action="shortlist"]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var trackId = parseInt(this.dataset.trackId, 10);
                var name = this.dataset.name;
                var pos = this.dataset.pos;
                toggleShortlist(trackId, name, pos, this);
            });
        });

        container.querySelectorAll('[data-action="compare"]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var trackId = this.dataset.trackId;
                var name = this.dataset.name;
                addToCompare(trackId, name);
                document.querySelector('.scout-tabs [data-stab="compare"]').click();
            });
        });
    }

    function toggleShortlist(trackId, name, position, btn) {
        var idx = _scoutState.shortlist.findIndex(function(s) { return s.track_id === trackId; });
        if (idx >= 0) {
            _scoutState.shortlist.splice(idx, 1);
            btn.textContent = '☆';
            btn.classList.remove('added');
            showToast('Removed from shortlist.', 'info');
        } else {
            _scoutState.shortlist.push({ track_id: trackId, name: name, position: position });
            btn.textContent = '★';
            btn.classList.add('added');
            showToast('Added to shortlist!', 'success');
        }
        renderShortlist();
    }

    function renderShortlist() {
        var container = document.getElementById('scout-shortlist-content');
        if (!container) return;
        var players = _scoutState.shortlist;

        if (!players || players.length === 0) {
            container.innerHTML = '<p class="hint">No shortlisted players yet.</p>';
            return;
        }

        var html = '';
        players.forEach(function(p) {
            var initial = (p.name || '?').charAt(0).toUpperCase();
            html += '<div class="scout-player-card">' +
                '<div class="scout-player-avatar">' + initial + '</div>' +
                '<div class="scout-player-info">' +
                '<div class="scout-player-name">' + escapeHtml(p.name || 'Unknown') + '</div>' +
                '<div class="scout-player-meta">' +
                '<span>' + escapeHtml(p.position || '--') + '</span>' +
                '</div></div>' +
                '<div class="scout-icons">' +
                '<button class="scout-icon" data-action="remove-shortlist" data-track-id="' + p.track_id + '">✕</button>' +
                '</div></div>';
        });
        container.innerHTML = html;

        container.querySelectorAll('[data-action="remove-shortlist"]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var trackId = parseInt(this.dataset.trackId, 10);
                var idx = _scoutState.shortlist.findIndex(function(s) { return s.track_id === trackId; });
                if (idx >= 0) {
                    _scoutState.shortlist.splice(idx, 1);
                    renderShortlist();
                    renderScoutResults();
                    showToast('Removed from shortlist.', 'info');
                }
            });
        });
    }

    function loadShortlist() {
        if (typeof bridge === 'undefined' || !bridge) {
            renderShortlist();
            return;
        }
        bridge.get_shortlist(function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                _scoutState.shortlist = data.players || [];
                renderShortlist();
            } catch(e) { showToast('Failed to load shortlist.', 'error'); console.warn('Shortlist load error:', e); }
        });
    }

    function generateScoutReport() {
        if (_scoutState.shortlist.length === 0) {
            showToast('Add players to your shortlist first.', 'warning');
            return;
        }

        var report = '# Scout Report\n\n## Shortlisted Players\n\n';
        _scoutState.shortlist.forEach(function(p) {
            report += '- **' + p.name + '** (' + (p.position || 'N/A') + ')\n';
        });
        report += '\n_Generated by Kawkab AI Scout Portal_\n';

        var blob = new Blob([report], { type: 'text/markdown' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'scout-report-' + Date.now() + '.md';
        document.body.appendChild(a);
        a.click();
        setTimeout(function() { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
        showToast('Scout report downloaded!', 'success');
    }

    function populateCompareSelects() {
        // Will be populated from search results
    }

    function addToCompare(trackId, name) {
        var selA = document.getElementById('scout-compare-a');
        var selB = document.getElementById('scout-compare-b');
        var opt = document.createElement('option');
        opt.value = trackId;
        opt.textContent = name;

        var exists = false;
        [selA, selB].forEach(function(sel) {
            for (var i = 0; i < sel.options.length; i++) {
                if (sel.options[i].value === trackId) exists = true;
            }
        });

        if (!exists) {
            selA.appendChild(opt.cloneNode(true));
            selB.appendChild(opt.cloneNode(true));
        }

        if (!selA.value) selA.value = trackId;
        else if (!selB.value) selB.value = trackId;
    }

    function scoutCompare(trackIdA, trackIdB) {
        var a = _scoutState.searchResults.find(function(p) { return p.track_id == trackIdA; });
        var b = _scoutState.searchResults.find(function(p) { return p.track_id == trackIdB; });

        var container = document.getElementById('scout-compare-results');
        if (!container) return;
        container.classList.remove('hidden');

        if (!a || !b) {
            container.innerHTML = '<p class="hint">Player data not found. Search for players first.</p>';
            return;
        }

        var html = '<div class="pro-card"><h4>Comparison: ' + escapeHtml(a.name) + ' vs ' + escapeHtml(b.name) + '</h4>';
        html += '<table class="data-table"><thead><tr><th>Stat</th><th>' + escapeHtml(a.name) + '</th><th>' + escapeHtml(b.name) + '</th></tr></thead><tbody>';

        var stats = [
            { key: 'goals', label: 'Goals' },
            { key: 'assists', label: 'Assists' },
            { key: 'matches', label: 'Matches' },
            { key: 'xg', label: 'xG' },
            { key: 'passes', label: 'Passes' },
            { key: 'tackles', label: 'Tackles' },
        ];

        stats.forEach(function(s) {
            var va = a[s.key] != null ? a[s.key] : '--';
            var vb = b[s.key] != null ? b[s.key] : '--';
            html += '<tr><td>' + s.label + '</td><td>' + va + '</td><td>' + vb + '</td></tr>';
        });

        html += '</tbody></table></div>';
        container.innerHTML = html;
    }

    function escapeHtml(str) {
        if (typeof str !== 'string') return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    window.initScoutPortal = initScoutPortal;
    window.scoutSearch = scoutSearch;
    window.renderScoutResults = renderScoutResults;
    window.renderShortlist = renderShortlist;
    window.loadShortlist = loadShortlist;
    window.generateScoutReport = generateScoutReport;
    window.scoutCompare = scoutCompare;
    window.toggleShortlist = toggleShortlist;
    window.addToCompare = addToCompare;
    window.populateCompareSelects = populateCompareSelects;

    window.KawkabScout = {
        initScoutPortal: initScoutPortal,
        scoutSearch: scoutSearch,
        renderScoutResults: renderScoutResults,
        renderShortlist: renderShortlist,
        generateScoutReport: generateScoutReport,
        scoutCompare: scoutCompare,
    };

})();
