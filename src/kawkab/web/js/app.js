// Kawkab AI - Frontend JavaScript
// Communicates with Python backend via QWebChannel

(function() {
    'use strict';

    let bridge = null;
    let currentLanguage = 'en';
    let currentMatchId = null;
    let currentVideoPath = null;
    let analysisResult = null;

    var _searchCache = { matches: [], players: [], events: [] };
    var _searchSelectedIdx = -1;

    // Multi-selection state
    var _selectedEventIds = new Set();
    var _lastShiftClickIdx = -1;
    var _currentTimelineView = 'timeline';

    // Timeline sort / filter / pagination state
    var _timelineSortState = { key: 'time', dir: 'asc' };
    var _timelineFilters = { type: '', team: '', player: '' };
    var _timelinePageState = { page: 1, perPage: 25 };
    var _timelineSearchText = '';

    // Roster table state
    var _rosterSortState = { key: 'name', dir: 'asc' };
    var _rosterPageState = { page: 1, perPage: 25 };
    var _rosterSearchText = '';
    var _currentRosterView = 'roster-cards';

    // Chart cross-filter state
    var _activeChartFilter = null; // { canvasId, startMin, endMin }

    // Expose key functions globally for cross-script access
    window.setLanguage = function(lang) { setLanguage(lang); };
    window.formatNumber = function(n, d) { return formatNumber(n, d); };
    window.loadDashboard = function() { loadDashboard(); };
    window.t = function(key) { return t(key); };

    function sanitizeString(str) {
        if (typeof str !== 'string') return '';
        return str.replace(/\0/g, '').trim().substring(0, 5000);
    }

    function validateInt(val) {
        const n = parseInt(val);
        return isFinite(n) ? n : 0;
    }

    function sanitizeBridgeArg(arg) {
        if (typeof arg === 'string') {
            return sanitizeString(arg);
        }
        if (typeof arg === 'number') {
            return isFinite(arg) ? arg : 0;
        }
        if (typeof arg === 'object' && arg !== null) {
            const s = JSON.stringify(arg);
            return s.substring(0, 50000);
        }
        return arg;
    }

    var _kawkabAppLocaleCache = {};

    function loadAppLocale(lang) {
        if (_kawkabAppLocaleCache[lang]) return Promise.resolve(_kawkabAppLocaleCache[lang]);
        var url = "locales/" + lang + ".json";
        return fetch(url)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                _kawkabAppLocaleCache[lang] = data;
                return data;
            })
            .catch(function () {
                return null;
            });
    }

    function t(key) {
        var dict = _kawkabAppLocaleCache[currentLanguage] || _kawkabAppLocaleCache['en'];
        return (dict && dict[key]) || key;
    }

    function formatNumber(n, decimals) {
        decimals = decimals !== undefined ? decimals : 2;
        var locale = currentLanguage === 'ar' ? 'ar-SA' : 'en-US';
        if (typeof n !== 'number') n = parseFloat(n) || 0;
        return n.toLocaleString(locale, { maximumFractionDigits: decimals, minimumFractionDigits: 0 });
    }

    function setLanguage(lang) {
        currentLanguage = lang;
        document.documentElement.lang = lang;
        document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
        document.title = t('appTitle');

        loadAppLocale(lang).then(function () {
            // Update all data-i18n elements
            document.querySelectorAll('[data-i18n]').forEach(function (el) {
                var key = el.getAttribute('data-i18n');
                if (key && t(key)) {
                    el.textContent = t(key);
                }
            });
            // Update all data-i18n-placeholder elements
            document.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
                var key = el.getAttribute('data-i18n-placeholder');
                if (key && t(key)) {
                    el.setAttribute('placeholder', t(key));
                }
            });
            // Update select option labels
            document.querySelectorAll('option[data-i18n]').forEach(function (el) {
                var key = el.getAttribute('data-i18n');
                if (key && t(key)) {
                    el.textContent = t(key);
                }
            });

            if (currentMatchId) {
                renderHistory();
            }
        });
    }

    // --- Theme Toggle ---
    function getStoredTheme() {
        try { return localStorage.getItem('kawkab_theme'); } catch(e) { return null; }
    }
    function setStoredTheme(t) {
        try { localStorage.setItem('kawkab_theme', t); } catch(e) {}
    }

    function applyTheme(theme) {
        var html = document.documentElement;
        if (theme === 'light') {
            html.setAttribute('data-theme', 'light');
        } else {
            html.setAttribute('data-theme', 'dark');
        }
        var btn = document.getElementById('theme-toggle');
        if (btn) btn.textContent = theme === 'light' ? '☀️' : '🌙';
    }

    function toggleTheme() {
        var current = getStoredTheme();
        var next = current === 'light' ? 'dark' : 'light';
        setStoredTheme(next);
        applyTheme(next);
    }

    function initTheme() {
        var stored = getStoredTheme();
        if (stored) {
            applyTheme(stored);
        } else {
            // Default to dark, respect system preference
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
                applyTheme('light');
                setStoredTheme('light');
            } else {
                applyTheme('dark');
                setStoredTheme('dark');
            }
        }
        var btn = document.getElementById('theme-toggle');
        if (btn) btn.addEventListener('click', toggleTheme);
    }

    function initQWebChannel() {
        if (typeof QWebChannel === 'undefined') {
            console.error('QWebChannel library not loaded');
            return;
        }

        function connectWhenReady(attempts) {
            if (typeof qt !== 'undefined' && qt.webChannelTransport) {
                try {
                    new QWebChannel(qt.webChannelTransport, function(channel) {
                        bridge = channel.objects.kawkab;
                        checkLLMStatus();
                        loadGPUInfo();
                        loadMatchHistory();
                        loadKnowledgeBaseStats();
                        loadPlayerProfiles();
                        loadFaceGallery();
                        populateMatchDropdowns();
                        checkFootballDataStatus();
                        checkBzzoiroStatus();
                        checkEasySoccerStatus();
                        checkApiFootballStatus();
                        checkTheSportsDBStatus();
                        checkStatsBombStatus();
                        checkOpenFootballStatus();
                        checkRoboflowSportsStatus();
                        checkPoseStatus();
                        checkMuJoCoStatus();
                        checkFluidX3DStatus();
                        checkWeatherStatus();
                        checkPsychologyStatus();
                        checkRulesStatus();
                        checkCardsStatus();
                    });
                } catch (e) {
                    console.error('QWebChannel setup error:', e);
                    if (attempts > 0) {
                        setTimeout(() => connectWhenReady(attempts - 1), 500);
                    }
                }
            } else if (attempts > 0) {
                setTimeout(() => connectWhenReady(attempts - 1), 200);
            } else {
                console.error('Qt web channel transport not available after 10 seconds');
            }
        }
        connectWhenReady(50);
    }

    async function checkLLMStatus() {
        if (!bridge) return;

        try {
            const status = JSON.parse(await bridge.check_llm_availability());
            const statusEl = document.getElementById('llm-status');
            if (status.ollama) {
                statusEl.textContent = t('llmOnline');
                statusEl.style.color = '#16a34a';
            } else {
                statusEl.textContent = t('llmOffline');
                statusEl.style.color = '#dc2626';
            }
        } catch (e) {
            console.error('LLM status check failed:', e);
        }
    }

    async function loadGPUInfo() {
        if (!bridge) return;

        try {
            const info = JSON.parse(await bridge.get_gpu_info());
            const statusEl = document.getElementById('gpu-status');
            if (info.error) {
                console.error('GPU info error:', info.error);
                return;
            }

            statusEl.classList.remove('hidden');
            statusEl.textContent = `🎮 GPU: ${info.gpu_name} (${info.tier})`;
            statusEl.title = 'Click for details';

            document.getElementById('gpu-name').textContent = info.gpu_name;
            document.getElementById('gpu-tier').textContent = info.tier;
            document.getElementById('rec-model').textContent = info.recommendations.model_size;
            document.getElementById('rec-frame-skip').textContent = info.recommendations.frame_skip;
            document.getElementById('rec-gpu').textContent = info.recommendations.gpu_enabled ? 'Yes' : 'No';
            document.getElementById('curr-model').textContent = info.current_settings.model_size;
            document.getElementById('curr-frame-skip').textContent = info.current_settings.frame_skip;
        } catch (e) {
            console.error('GPU info load failed:', e);
        }
    }

    document.getElementById('gpu-status')?.addEventListener('click', () => {
        document.getElementById('gpu-info-panel').classList.remove('hidden');
    });

    document.getElementById('close-gpu-info')?.addEventListener('click', () => {
        document.getElementById('gpu-info-panel').classList.add('hidden');
    });

    // --- v0.8.4: Football Data Integration ---

    let fdHomeTeamId = null;
    let fdAwayTeamId = null;
    let fdHomeSearchTimer = null;
    let fdAwaySearchTimer = null;

    let bzHomeTeamId = null;
    let bzAwayTeamId = null;
    let bzHomeSearchTimer = null;
    let bzAwaySearchTimer = null;

    let afHomeTeamId = null;
    let afAwayTeamId = null;
    let afHomeSearchTimer = null;
    let afAwaySearchTimer = null;

    async function checkFootballDataStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('football-data-status');
        const controls = document.getElementById('football-data-controls');
        try {
            const status = JSON.parse(await bridge.check_football_data_status());
            if (status.available) {
                statusEl.textContent = '🟢 Connected (' + status.competitions_count + ' competitions available)';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
            } else {
                statusEl.textContent = '🔴 Offline - ' + (status.error || 'No API key configured');
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🔴 Offline';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    function setupFdTeamSearch(inputId, resultsId, callback) {
        const input = document.getElementById(inputId);
        const results = document.getElementById(resultsId);
        if (!input || !results) return;

        input.addEventListener('input', function() {
            const query = this.value.trim();
            if (query.length < 2) {
                results.classList.add('hidden');
                return;
            }
            clearTimeout(window[inputId + 'Timer']);
            window[inputId + 'Timer'] = setTimeout(async () => {
                try {
                    const data = JSON.parse(await bridge.search_football_team(sanitizeString(query)));
                    const teams = data.teams || [];
                    if (teams.length === 0) {
                        results.innerHTML = '<div class="fd-result-item" style="color: var(--text-muted)">No teams found</div>';
                        results.classList.remove('hidden');
                        return;
                    }
                    results.innerHTML = teams.map(t => `
                        <div class="fd-result-item" data-team-id="${t.id}" data-team-name="${escapeHtml(t.name)}" data-team-code="${escapeHtml(t.tla || '')}" data-team-crest="${escapeHtml(t.crest || '')}" data-competition-code="${escapeHtml(t.competition_code || '')}">
                            ${t.crest ? '<img src="' + escapeHtml(t.crest) + '" alt="" onerror="this.style.display=\'none\'">' : ''}
                            <span>
                                <span class="fd-result-name">${escapeHtml(t.name)}</span>
                                <span class="fd-result-area">${escapeHtml(t.area_name || '')}${t.competition_name ? ' · ' + escapeHtml(t.competition_name) : ''}</span>
                            </span>
                        </div>
                    `).join('');
                    results.classList.remove('hidden');
                    results.querySelectorAll('.fd-result-item').forEach(el => {
                        el.addEventListener('click', function() {
                            const id = parseInt(this.dataset.teamId);
                            const name = this.dataset.teamName;
                            const compCode = this.dataset.competitionCode;
                            input.value = name;
                            results.classList.add('hidden');
                            callback(id, name, this.dataset.teamCrest, compCode);
                        });
                    });
                } catch (e) {
                    console.error('Team search failed:', e);
                }
            }, 300);
        });

        document.addEventListener('click', function(e) {
            if (!input.contains(e.target) && !results.contains(e.target)) {
                results.classList.add('hidden');
            }
        });
    }

    async function fdImportSquad(matchId, apiTeamId, side, btnId) {
        if (!bridge) return;
        const btn = document.getElementById(btnId);
        if (!btn) return;
        btn.disabled = true;
        btn.textContent = 'Importing...';
        try {
            const result = JSON.parse(await bridge.import_football_team_squad(validateInt(matchId), validateInt(apiTeamId), sanitizeString(side)));
            if (result.success) {
                btn.textContent = '✅ ' + result.created.length + ' imported, ' + result.skipped + ' skipped';
                loadPlayerProfiles();
            } else {
                btn.textContent = '❌ ' + (result.error || 'Import failed');
            }
        } catch (e) {
            btn.textContent = '❌ Error';
        }
        setTimeout(() => { btn.disabled = false; }, 3000);
    }

    async function fdVerifyMatch() {
        if (!bridge || !currentMatchId) return;
        const apiMatchIdInput = document.getElementById('fd-api-match-id');
        const resultEl = document.getElementById('fd-verify-result');
        const apiMatchId = parseInt(apiMatchIdInput.value);
        if (!apiMatchId) {
            resultEl.textContent = 'Enter an API Match ID';
            resultEl.className = 'feedback-result error';
            return;
        }
        resultEl.textContent = 'Verifying...';
        resultEl.className = 'feedback-result';
        try {
            const data = JSON.parse(await bridge.verify_match_with_api(validateInt(currentMatchId), validateInt(apiMatchId)));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                resultEl.className = 'feedback-result error';
                return;
            }
            if (data.verified) {
                resultEl.innerHTML = '✅ Score verified! API: ' + data.api_score.home + '-' + data.api_score.away +
                    ' | Status: ' + data.status + (data.competition ? ' | ' + data.competition : '');
                resultEl.className = 'feedback-result success';
            } else {
                resultEl.innerHTML = '⚠️ Score mismatch — Detected: ' + data.detected_score.home + '-' + data.detected_score.away +
                    ' | API: ' + (data.api_score ? data.api_score.home + '-' + data.api_score.away : 'N/A') +
                    ' | Status: ' + data.status + (data.reason ? ' (' + data.reason + ')' : '');
                resultEl.className = 'feedback-result';
            }
            loadMatchHistory();
        } catch (e) {
            resultEl.textContent = '❌ Verification failed';
            resultEl.className = 'feedback-result error';
        }
    }

    async function fdLoadTeamFixtures(apiTeamId) {
        if (!bridge) return;
        const section = document.getElementById('fd-fixtures-section');
        const list = document.getElementById('fd-fixtures-list');
        if (!apiTeamId) { section.classList.add('hidden'); return; }
        try {
            const data = JSON.parse(await bridge.get_football_team_matches(apiTeamId, '', ''));
            const matches = data.matches || [];
            if (matches.length === 0) {
                section.classList.add('hidden');
                return;
            }
            list.innerHTML = matches.slice(0, 5).map(m => {
                const home = (m.homeTeam || {}).name || '?';
                const away = (m.awayTeam || {}).name || '?';
                const score = (m.score || {}).fullTime || {};
                const sc = (score.home !== null && score.away !== null) ? score.home + '-' + score.away : '-';
                const date = m.utcDate ? new Date(m.utcDate).toLocaleDateString() : '?';
                const status = m.status || 'SCHEDULED';
                return `<div class="roster-item"><span style="font-size:0.85rem">${date}</span><span style="flex:1;text-align:center">${escapeHtml(home)} ${sc} ${escapeHtml(away)}</span><span class="fd-result-area">${status}</span></div>`;
            }).join('');
            section.classList.remove('hidden');
        } catch (e) {
            section.classList.add('hidden');
        }
    }

    async function fdLoadStandings(competitionCode) {
        if (!bridge) return;
        const section = document.getElementById('fd-standings-section');
        const list = document.getElementById('fd-standings-list');
        if (!competitionCode) { section.classList.add('hidden'); return; }
        try {
            const data = JSON.parse(await bridge.get_football_standings(competitionCode));
            if (data.error || !data.standings) { section.classList.add('hidden'); return; }
            const total = data.standings.find(s => s.type === 'TOTAL');
            if (!total || !total.table) { section.classList.add('hidden'); return; }
            list.innerHTML = total.table.slice(0, 5).map(t => `
                <div class="roster-item">
                    <span style="font-weight:700;width:24px">${t.position}</span>
                    <span style="flex:1">${escapeHtml(t.team.name)}</span>
                    <span style="color:var(--text-muted);font-size:0.85rem">P${t.playedGames} · ${t.points}pts</span>
                </div>
            `).join('');
            section.classList.remove('hidden');
        } catch (e) {
            section.classList.add('hidden');
        }
    }

    // --- v0.8.5: Bzzoiro ---

    async function checkBzzoiroStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('bzzoiro-status');
        const controls = document.getElementById('bzzoiro-controls');
        try {
            const status = JSON.parse(await bridge.check_bzzoiro_status());
            if (status.available) {
                statusEl.textContent = '🟢 Connected (' + (status.live_matches || 0) + ' live)';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
                bzLoadLeagues();
                bzLoadLive();
            } else {
                statusEl.textContent = '🔴 Offline - ' + (status.error || 'No API key configured');
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🔴 Offline';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    function setupBzTeamSearch(inputId, resultsId, callback) {
        const input = document.getElementById(inputId);
        const results = document.getElementById(resultsId);
        if (!input || !results) return;

        input.addEventListener('input', function() {
            const query = this.value.trim();
            if (query.length < 2) {
                results.classList.add('hidden');
                return;
            }
            clearTimeout(window[inputId + 'Timer']);
            window[inputId + 'Timer'] = setTimeout(async () => {
                try {
                    const data = JSON.parse(await bridge.search_bzzoiro_team(sanitizeString(query)));
                    const teams = data.teams || [];
                    if (teams.length === 0) {
                        results.innerHTML = '<div class="fd-result-item" style="color: var(--text-muted)">No teams found</div>';
                        results.classList.remove('hidden');
                        return;
                    }
                    results.innerHTML = teams.map(t => `
                        <div class="fd-result-item" data-team-id="${t.id}" data-team-name="${escapeHtml(t.name)}">
                            <span>
                                <span class="fd-result-name">${escapeHtml(t.name)}</span>
                                <span class="fd-result-area">${escapeHtml(t.country || '')}</span>
                            </span>
                        </div>
                    `).join('');
                    results.classList.remove('hidden');
                    results.querySelectorAll('.fd-result-item').forEach(el => {
                        el.addEventListener('click', function() {
                            const id = parseInt(this.dataset.teamId);
                            const name = this.dataset.teamName;
                            input.value = name;
                            results.classList.add('hidden');
                            callback(id, name);
                        });
                    });
                } catch (e) {
                    console.error('Bzzoiro team search failed:', e);
                }
            }, 300);
        });

        document.addEventListener('click', function(e) {
            if (!input.contains(e.target) && !results.contains(e.target)) {
                results.classList.add('hidden');
            }
        });
    }

    async function bzImportSquad(matchId, teamId, side, btnId) {
        if (!bridge) return;
        const btn = document.getElementById(btnId);
        if (!btn) return;
        btn.disabled = true;
        btn.textContent = 'Importing...';
        try {
            const result = JSON.parse(await bridge.import_bzzoiro_team_squad(validateInt(matchId), validateInt(teamId), sanitizeString(side)));
            if (result.success) {
                btn.textContent = '✅ ' + result.created.length + ' imported, ' + result.skipped + ' skipped';
            } else {
                btn.textContent = '❌ ' + (result.error || 'Import failed');
            }
        } catch (e) {
            btn.textContent = '❌ Error';
        }
        setTimeout(() => { btn.disabled = false; }, 3000);
    }

    async function bzVerifyMatch() {
        if (!bridge || !currentMatchId) return;
        const eventIdInput = document.getElementById('bz-event-id');
        const resultEl = document.getElementById('bz-verify-result');
        const eventId = parseInt(eventIdInput.value);
        if (!eventId) {
            resultEl.textContent = 'Enter a Bzzoiro Event ID';
            resultEl.className = 'feedback-result error';
            return;
        }
        resultEl.textContent = 'Verifying...';
        resultEl.className = 'feedback-result';
        try {
            const data = JSON.parse(await bridge.verify_match_bzzoiro(validateInt(currentMatchId), validateInt(eventId)));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                resultEl.className = 'feedback-result error';
                return;
            }
            if (data.match_ok) {
                resultEl.innerHTML = '✅ Score verified! ' + escapeHtml(data.match) + ' <strong>' + data.api_score + '</strong>';
                resultEl.className = 'feedback-result success';
            } else {
                resultEl.innerHTML = '⚠️ Score mismatch — Detected: ' + data.detected_score + ' | API: ' + data.api_score;
                resultEl.className = 'feedback-result';
            }
        } catch (e) {
            resultEl.textContent = '❌ Verification failed';
            resultEl.className = 'feedback-result error';
        }
    }

    async function bzGetPredictions() {
        if (!bridge) return;
        const eventIdInput = document.getElementById('bz-event-id');
        const resultEl = document.getElementById('bz-predictions-content');
        const section = document.getElementById('bz-predictions-section');
        const eventId = parseInt(eventIdInput.value);
        if (!eventId) { resultEl.textContent = 'Enter an Event ID first'; return; }
        resultEl.textContent = 'Loading predictions...';
        section.classList.remove('hidden');
        try {
            const data = JSON.parse(await bridge.get_bzzoiro_predictions(validateInt(eventId)));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            const p = data.predictions || {};
            resultEl.innerHTML = '<pre style="font-size:0.8rem;white-space:pre-wrap">' + JSON.stringify(p, null, 2) + '</pre>';
        } catch (e) {
            resultEl.textContent = '❌ Failed to load predictions';
        }
    }

    async function bzLoadStandings() {
        if (!bridge) return;
        const select = document.getElementById('bz-league-select');
        const section = document.getElementById('bz-standings-section');
        const list = document.getElementById('bz-standings-list');
        const leagueId = parseInt(select.value);
        if (!leagueId) { section.classList.add('hidden'); return; }
        section.classList.remove('hidden');
        list.innerHTML = '<div class="roster-item">Loading...</div>';
        try {
            const data = JSON.parse(await bridge.get_bzzoiro_standings(validateInt(leagueId)));
            const standings = data.standings || [];
            if (standings.length === 0) {
                list.innerHTML = '<div class="roster-item">No standings data</div>';
                return;
            }
            list.innerHTML = standings.map(s => `
                <div class="roster-item">
                    <span style="font-weight:700;width:24px">${s.position}</span>
                    <span style="flex:1">${escapeHtml(s.team_name)}</span>
                    <span style="color:var(--text-muted);font-size:0.85rem">P${s.played} · ${s.points}pts</span>
                </div>
            `).join('');
        } catch (e) {
            list.innerHTML = '<div class="roster-item">Failed to load standings</div>';
        }
    }

    async function bzLoadLeagues() {
        if (!bridge) return;
        const select = document.getElementById('bz-league-select');
        if (!select) return;
        try {
            const data = JSON.parse(await bridge.get_bzzoiro_leagues());
            const leagues = data.leagues || [];
            select.innerHTML = '<option value="">-- Select League for Standings --</option>' +
                leagues.filter(l => l.is_active).map(l =>
                    '<option value="' + l.id + '">' + escapeHtml(l.name) + ' (' + escapeHtml(l.country || '') + ')</option>'
                ).join('');
        } catch (e) {
            console.error('Failed to load leagues:', e);
        }
    }

    async function bzLoadLive() {
        if (!bridge) return;
        const list = document.getElementById('bz-live-list');
        const countEl = document.getElementById('bz-live-count');
        if (!list) return;
        try {
            const data = JSON.parse(await bridge.get_bzzoiro_live());
            const matches = data.matches || [];
            if (countEl) countEl.textContent = '(' + matches.length + ')';
            if (matches.length === 0) {
                list.innerHTML = '<div class="roster-item" style="color:var(--text-muted)">No live matches</div>';
                return;
            }
            list.innerHTML = matches.map(m => {
                const score = (m.home_score !== null ? m.home_score : '-') + '-' + (m.away_score !== null ? m.away_score : '-');
                const min = m.current_minute ? m.current_minute + "'" : '';
                return `<div class="roster-item"><span style="color:var(--accent);font-size:0.75rem">${escapeHtml(m.league_name || '')}</span><span style="flex:1;text-align:center">${escapeHtml(m.home_team)} <strong>${score}</strong> ${escapeHtml(m.away_team)}</span><span style="color:var(--text-muted);font-size:0.8rem">${min}</span></div>`;
            }).join('');
        } catch (e) {
            list.innerHTML = '<div class="roster-item">Failed to load live matches</div>';
        }
    }

    // --- v0.8.5: API-Football (api-sports.io) ---

    async function checkApiFootballStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('apifootball-status');
        const controls = document.getElementById('apifootball-controls');
        try {
            const status = JSON.parse(await bridge.check_apifootball_status());
            if (status.available) {
                statusEl.textContent = '🟢 Connected (' + (status.requests_left || 0) + '/' + status.daily_limit + ' req left)';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
                afLoadStandings();
                afLoadLive();
            } else {
                statusEl.textContent = '🔴 Offline - ' + (status.error || 'No API key configured');
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🔴 Offline';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    function setupAfTeamSearch(inputId, resultsId, callback) {
        const input = document.getElementById(inputId);
        const results = document.getElementById(resultsId);
        if (!input || !results) return;

        input.addEventListener('input', function() {
            const query = this.value.trim();
            if (query.length < 2) {
                results.classList.add('hidden');
                return;
            }
            clearTimeout(window[inputId + 'Timer']);
            window[inputId + 'Timer'] = setTimeout(async () => {
                try {
                    const data = JSON.parse(await bridge.search_apifootball_team(sanitizeString(query)));
                    const teams = data.teams || [];
                    if (teams.length === 0) {
                        results.innerHTML = '<div class="fd-result-item" style="color: var(--text-muted)">No teams found</div>';
                        results.classList.remove('hidden');
                        return;
                    }
                    results.innerHTML = teams.map(t => `
                        <div class="fd-result-item" data-team-id="${t.id}" data-team-name="${escapeHtml(t.name)}">
                            ${t.logo ? '<img src="' + escapeHtml(t.logo) + '" alt="" onerror="this.style.display=\'none\'">' : ''}
                            <span>
                                <span class="fd-result-name">${escapeHtml(t.name)}</span>
                                <span class="fd-result-area">${escapeHtml(t.country || '')}${t.venue_name ? ' · ' + escapeHtml(t.venue_name) : ''}</span>
                            </span>
                        </div>
                    `).join('');
                    results.classList.remove('hidden');
                    results.querySelectorAll('.fd-result-item').forEach(el => {
                        el.addEventListener('click', function() {
                            const id = parseInt(this.dataset.teamId);
                            const name = this.dataset.teamName;
                            input.value = name;
                            results.classList.add('hidden');
                            callback(id, name);
                        });
                    });
                } catch (e) {
                    console.error('API-Football team search failed:', e);
                }
            }, 300);
        });

        document.addEventListener('click', function(e) {
            if (!input.contains(e.target) && !results.contains(e.target)) {
                results.classList.add('hidden');
            }
        });
    }

    async function afImportSquad(matchId, teamId, side, btnId) {
        if (!bridge) return;
        const btn = document.getElementById(btnId);
        if (!btn) return;
        btn.disabled = true;
        btn.textContent = 'Importing...';
        try {
            const result = JSON.parse(await bridge.import_apifootball_squad(validateInt(matchId), validateInt(teamId), sanitizeString(side)));
            if (result.success) {
                btn.textContent = '✅ ' + result.created.length + ' imported, ' + result.skipped + ' skipped';
            } else {
                btn.textContent = '❌ ' + (result.error || 'Import failed');
            }
        } catch (e) {
            btn.textContent = '❌ Error';
        }
        setTimeout(() => { btn.disabled = false; }, 3000);
    }

    async function afVerifyMatch() {
        if (!bridge || !currentMatchId) return;
        const fixtureIdInput = document.getElementById('af-fixture-id');
        const resultEl = document.getElementById('af-verify-result');
        const fixtureId = parseInt(fixtureIdInput.value);
        if (!fixtureId) {
            resultEl.textContent = 'Enter a Fixture ID';
            resultEl.className = 'feedback-result error';
            return;
        }
        resultEl.textContent = 'Verifying...';
        resultEl.className = 'feedback-result';
        try {
            const data = JSON.parse(await bridge.verify_match_apifootball(validateInt(currentMatchId), validateInt(fixtureId)));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                resultEl.className = 'feedback-result error';
                return;
            }
            if (data.match_ok) {
                resultEl.innerHTML = '✅ Score verified! ' + escapeHtml(data.match) + ' <strong>' + data.api_score + '</strong>';
                resultEl.className = 'feedback-result success';
            } else {
                resultEl.innerHTML = '⚠️ Score mismatch — Detected: ' + data.detected_score + ' | API: ' + data.api_score;
                resultEl.className = 'feedback-result';
            }
        } catch (e) {
            resultEl.textContent = '❌ Verification failed';
            resultEl.className = 'feedback-result error';
        }
    }

    async function afGetPredictions() {
        if (!bridge) return;
        const fixtureIdInput = document.getElementById('af-fixture-id');
        const resultEl = document.getElementById('af-predictions-content');
        const section = document.getElementById('af-predictions-section');
        const fixtureId = parseInt(fixtureIdInput.value);
        if (!fixtureId) { resultEl.textContent = 'Enter a Fixture ID first'; return; }
        resultEl.textContent = 'Loading predictions...';
        section.classList.remove('hidden');
        try {
            const data = JSON.parse(await bridge.get_apifootball_predictions(validateInt(fixtureId)));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            const p = data.predictions || {};
            let html = '';
            if (p.percent) {
                html += '<div style="display:flex;gap:8px;justify-content:center;margin-bottom:8px">';
                html += '<span style="color:#2563eb;font-weight:600">' + (p.percent.home || '') + '</span>';
                html += '<span style="color:#64748b">' + (p.percent.draw || '') + '</span>';
                html += '<span style="color:#dc2626;font-weight:600">' + (p.percent.away || '') + '</span>';
                html += '</div>';
            }
            if (p.advice) html += '<div style="font-size:0.85rem;background:#f8fafc;padding:6px;border-radius:4px">Advice: ' + escapeHtml(p.advice) + '</div>';
            if (p.winner) html += '<div style="margin-top:4px;font-size:0.85rem">Predicted winner: ' + escapeHtml(p.winner.name || p.winner) + '</div>';
            resultEl.innerHTML = html || '<pre style="font-size:0.8rem">' + JSON.stringify(p, null, 2) + '</pre>';
        } catch (e) {
            resultEl.textContent = '❌ Failed to load predictions';
        }
    }

    async function afLoadStandings() {
        if (!bridge) return;
        const section = document.getElementById('af-standings-section');
        const list = document.getElementById('af-standings-list');
        section.classList.remove('hidden');
        list.innerHTML = '<div class="roster-item">Loading standings...</div>';
        try {
            const data = JSON.parse(await bridge.get_apifootball_standings(200, 2024));
            const standings = data.standings || [];
            if (standings.length === 0) {
                list.innerHTML = '<div class="roster-item">No standings data</div>';
                return;
            }
            list.innerHTML = standings.map(s => `
                <div class="roster-item">
                    <span style="font-weight:700;width:24px">${s.rank}</span>
                    <span style="flex:1">${escapeHtml(s.team_name)}</span>
                    <span style="color:var(--text-muted);font-size:0.85rem">P${s.played} · ${s.points}pts</span>
                </div>
            `).join('');
        } catch (e) {
            list.innerHTML = '<div class="roster-item">Failed to load standings</div>';
        }
    }

    async function afLoadLive() {
        if (!bridge) return;
        const list = document.getElementById('af-live-list');
        if (!list) return;
        try {
            const data = JSON.parse(await bridge.get_apifootball_live());
            const matches = data.matches || [];
            if (matches.length === 0) {
                list.innerHTML = '<div class="roster-item" style="color:var(--text-muted)">No live matches</div>';
                return;
            }
            list.innerHTML = matches.map(m => {
                const score = (m.home_score !== null ? m.home_score : '-') + '-' + (m.away_score !== null ? m.away_score : '-');
                const min = m.elapsed ? m.elapsed + "'" : '';
                return `<div class="roster-item"><span style="color:var(--accent);font-size:0.75rem">${escapeHtml(m.league_name || '')}</span><span style="flex:1;text-align:center">${escapeHtml(m.home_team)} <strong>${score}</strong> ${escapeHtml(m.away_team)}</span><span style="color:var(--text-muted);font-size:0.8rem">${min}</span></div>`;
            }).join('');
        } catch (e) {
            list.innerHTML = '<div class="roster-item">Failed to load live matches</div>';
        }
    }

    // --- v0.8.5: EasySoccerData (Sofascore) ---

    async function checkEasySoccerStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('easysoccer-status');
        const controls = document.getElementById('easysoccer-controls');
        try {
            const status = JSON.parse(await bridge.check_easy_soccer_status());
            if (status.available) {
                statusEl.textContent = '🟢 Connected';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
                esLoadLive();
            } else {
                statusEl.textContent = '🟡 Not available (pip install EasySoccerData)';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    async function esGetEvent() {
        if (!bridge) return;
        const input = document.getElementById('es-event-id');
        const resultEl = document.getElementById('es-event-result');
        const eventId = parseInt(input.value);
        if (!eventId) { resultEl.textContent = 'Enter a Sofascore Event ID'; return; }
        resultEl.textContent = 'Loading...';
        try {
            const data = JSON.parse(await bridge.get_easy_soccer_event(validateInt(eventId)));
            if (data.error) { resultEl.textContent = '❌ ' + data.error; return; }
            const e = data.event;
            resultEl.innerHTML = '<div style="font-size:0.85rem"><strong>' + escapeHtml(e.home_team) + '</strong> vs <strong>' + escapeHtml(e.away_team) + '</strong><br>Score: ' +
                (e.home_score !== null ? e.home_score : '-') + '-' + (e.away_score !== null ? e.away_score : '-') +
                ' | Status: ' + e.status + '</div>';
        } catch (e) {
            resultEl.textContent = '❌ Failed to load event';
        }
    }

    async function esGetIncidents() {
        if (!bridge) return;
        const input = document.getElementById('es-event-id');
        const resultEl = document.getElementById('es-event-result');
        const eventId = parseInt(input.value);
        if (!eventId) { resultEl.textContent = 'Enter a Sofascore Event ID'; return; }
        resultEl.textContent = 'Loading incidents...';
        try {
            const data = JSON.parse(await bridge.get_easy_soccer_incidents(validateInt(eventId)));
            if (data.error) { resultEl.textContent = '❌ ' + data.error; return; }
            const incidents = data.incidents || [];
            if (incidents.length === 0) { resultEl.textContent = 'No incidents found'; return; }
            resultEl.innerHTML = incidents.slice(0, 15).map(i =>
                '<div style="font-size:0.8rem;padding:2px 0">' + (i.minute ? i.minute + "' " : '') +
                (i.type || '') + ' - ' + escapeHtml(i.player || '') + ' (' + escapeHtml(i.team || '') + ')</div>'
            ).join('');
        } catch (e) {
            resultEl.textContent = '❌ Failed to load incidents';
        }
    }

    async function esLoadLive() {
        if (!bridge) return;
        const list = document.getElementById('es-live-list');
        if (!list) return;
        try {
            const data = JSON.parse(await bridge.get_easy_soccer_live());
            const matches = data.matches || [];
            if (matches.length === 0) {
                list.innerHTML = '<div class="roster-item" style="color:var(--text-muted)">No live matches</div>';
                return;
            }
            list.innerHTML = matches.map(m => {
                const score = (m.home_score !== null ? m.home_score : '-') + '-' + (m.away_score !== null ? m.away_score : '-');
                return `<div class="roster-item"><span style="flex:1">${escapeHtml(m.home_team)} <strong>${score}</strong> ${escapeHtml(m.away_team)}</span></div>`;
            }).join('');
        } catch (e) {
            list.innerHTML = '<div class="roster-item">Failed to load live matches</div>';
        }
    }

    // --- TheSportsDB ---

    async function checkTheSportsDBStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('thesportsdb-status');
        const controls = document.getElementById('thesportsdb-controls');
        try {
            const status = JSON.parse(await bridge.check_thesportsdb_status());
            if (status.available) {
                statusEl.textContent = '🟢 Connected (public free tier)';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
            } else {
                statusEl.textContent = '🟡 Not available';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    function setupTsdbTeamSearch(inputId, resultsId, callback) {
        const input = document.getElementById(inputId);
        const results = document.getElementById(resultsId);
        if (!input || !results) return;

        input.addEventListener('input', function() {
            const query = this.value.trim();
            if (query.length < 2) {
                results.classList.add('hidden');
                return;
            }
            clearTimeout(window[inputId + 'Timer']);
            window[inputId + 'Timer'] = setTimeout(async () => {
                try {
                    const data = JSON.parse(await bridge.search_thesportsdb_team(sanitizeString(query)));
                    const teams = data.teams || [];
                    if (teams.length === 0) {
                        results.innerHTML = '<div class="fd-result-item" style="color: var(--text-muted)">No teams found</div>';
                        results.classList.remove('hidden');
                        return;
                    }
                    results.innerHTML = teams.map(t => `
                        <div class="fd-result-item" data-team-id="${t.id}" data-team-name="${escapeHtml(t.name)}" data-league="${escapeHtml(t.league || '')}" data-league-id="${t.league_id || ''}" data-badge="${escapeHtml(t.badge || '')}">
                            <span>
                                <span class="fd-result-name">${escapeHtml(t.name)}</span>
                                <span class="fd-result-area">${escapeHtml(t.league || '')}${t.location ? ' · ' + escapeHtml(t.location) : ''}</span>
                            </span>
                        </div>
                    `).join('');
                    results.classList.remove('hidden');
                    results.querySelectorAll('.fd-result-item').forEach(el => {
                        el.addEventListener('click', function() {
                            const id = this.dataset.teamId;
                            const name = this.dataset.teamName;
                            input.value = name;
                            results.classList.add('hidden');
                            callback(id, name, this.dataset.leagueId, this.dataset.badge);
                        });
                    });
                } catch (e) {
                    console.error('TheSportsDB team search failed:', e);
                }
            }, 300);
        });

        document.addEventListener('click', function(e) {
            if (!input.contains(e.target) && !results.contains(e.target)) {
                results.classList.add('hidden');
            }
        });
    }

    async function tsdbGetTeamInfo() {
        if (!bridge) return;
        const infoEl = document.getElementById('tsdb-team-info');
        const searchInput = document.getElementById('tsdb-team-search');
        const resultsDiv = document.getElementById('tsdb-team-results');
        const firstResult = resultsDiv.querySelector('.fd-result-item');
        if (!firstResult) {
            infoEl.textContent = 'Search for a team first';
            return;
        }
        const teamId = firstResult.dataset.teamId;
        infoEl.textContent = 'Loading...';
        try {
            const data = JSON.parse(await bridge.get_thesportsdb_team_info(sanitizeString(teamId)));
            if (data.error || !data.team) {
                infoEl.textContent = '❌ ' + (data.error || 'Team not found');
                return;
            }
            const t = data.team;
            infoEl.innerHTML = '<div style="font-size:0.85rem">' +
                (t.badge ? '<img src="' + escapeHtml(t.badge) + '" style="height:32px;vertical-align:middle;margin-right:8px">' : '') +
                '<strong>' + escapeHtml(t.name) + '</strong>' +
                (t.alternate_name ? ' (' + escapeHtml(t.alternate_name) + ')' : '') +
                '<br>League: ' + escapeHtml(t.league) + ' (ID: ' + t.league_id + ')' +
                (t.location ? '<br>Location: ' + escapeHtml(t.location) : '') +
                (t.stadium ? '<br>Stadium: ' + escapeHtml(t.stadium) + (t.capacity ? ' (' + t.capacity + ')' : '') : '') +
                (t.formed_year ? '<br>Founded: ' + t.formed_year : '') +
                (t.api_football_id && t.api_football_id !== '0' ? '<br>API-Football ID: ' + t.api_football_id : '') +
                (t.description ? '<br><br><em>' + escapeHtml(t.description.substring(0, 300)) + '</em>' : '') +
                '</div>';
            infoEl.className = 'feedback-result';
        } catch (e) {
            infoEl.textContent = '❌ Failed to load team info';
        }
    }

    async function tsdbLoadStandings() {
        if (!bridge) return;
        const leagueIdInput = document.getElementById('tsdb-league-id');
        const section = document.getElementById('tsdb-standings-section');
        const list = document.getElementById('tsdb-standings-list');
        const leagueId = leagueIdInput.value.trim();
        if (!leagueId) { section.classList.add('hidden'); return; }
        try {
            const data = JSON.parse(await bridge.get_thesportsdb_standings(leagueId));
            if (data.error || !data.standings) { section.classList.add('hidden'); return; }
            list.innerHTML = data.standings.map(s => {
                const formDots = s.form ? s.form.split('').map(f => {
                    const cls = f === 'W' ? 'form-w' : f === 'D' ? 'form-d' : 'form-l';
                    return '<span class="' + cls + '">' + f + '</span>';
                }).join('') : '';
                return '<div class="roster-item">' +
                    '<span style="font-weight:700;width:28px">' + s.rank + '</span>' +
                    '<span style="flex:1">' + (s.badge ? '<img src="' + escapeHtml(s.badge) + '" style="height:18px;vertical-align:middle;margin-right:6px">' : '') + escapeHtml(s.team) + '</span>' +
                    '<span style="color:var(--text-muted);font-size:0.85rem;margin:0 6px">P' + s.played + '</span>' +
                    '<span style="color:var(--text-muted);font-size:0.85rem">' + s.points + 'pts</span>' +
                    (formDots ? '<span style="margin-left:8px">' + formDots + '</span>' : '') +
                    (s.description ? '<span style="color:var(--text-muted);font-size:0.7rem;margin-left:6px">' + escapeHtml(s.description) + '</span>' : '') +
                    '</div>';
            }).join('');
            section.classList.remove('hidden');
        } catch (e) {
            section.classList.add('hidden');
        }
    }

    async function tsdbLoadEvents(type) {
        if (!bridge) return;
        const teamIdInput = document.getElementById('tsdb-team-id-events');
        const section = document.getElementById('tsdb-events-section');
        const list = document.getElementById('tsdb-events-list');
        const teamId = teamIdInput.value.trim();
        if (!teamId) { section.classList.add('hidden'); return; }
        try {
            const method = type === 'last' ? 'get_thesportsdb_team_events_last' : 'get_thesportsdb_team_events_next';
            const data = JSON.parse(await bridge[method](teamId));
            if (data.error || !data.events) { section.classList.add('hidden'); return; }
            list.innerHTML = data.events.slice(0, 10).map(e => {
                const score = (e.home_score !== null ? e.home_score : '-') + '-' + (e.away_score !== null ? e.away_score : '-');
                return '<div class="roster-item">' +
                    '<span style="color:var(--text-muted);font-size:0.8rem;width:80px">' + e.date + '</span>' +
                    '<span style="flex:1;text-align:center">' + escapeHtml(e.home) + ' <strong>' + score + '</strong> ' + escapeHtml(e.away) + '</span>' +
                    (e.round ? '<span style="color:var(--text-muted);font-size:0.8rem">R' + e.round + '</span>' : '') +
                    '</div>';
            }).join('');
            section.classList.remove('hidden');
        } catch (e) {
            section.classList.add('hidden');
        }
    }

    // --- StatsBomb ---

    async function checkStatsBombStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('statsbomb-status');
        const controls = document.getElementById('statsbomb-controls');
        try {
            const status = JSON.parse(await bridge.check_statsbomb_status());
            if (status.available) {
                statusEl.textContent = '🟢 Connected (' + (status.competitions || 0) + ' competitions)';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
            } else {
                statusEl.textContent = '🟡 Not available (network error)';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    async function sbGetEvents() {
        if (!bridge) return;
        const matchIdInput = document.getElementById('sb-match-id');
        const resultEl = document.getElementById('sb-events-result');
        const matchId = parseInt(matchIdInput.value);
        if (!matchId) {
            resultEl.textContent = 'Enter a StatsBomb Match ID';
            resultEl.className = 'feedback-result error';
            return;
        }
        resultEl.textContent = 'Loading events...';
        resultEl.className = 'feedback-result';
        try {
            const data = JSON.parse(await bridge.get_statsbomb_events(validateInt(matchId)));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                resultEl.className = 'feedback-result error';
                return;
            }
            const s = data.summary;
            const shotsHtml = (data.shots || []).map(sh =>
                '<div style="font-size:0.78rem;padding:2px 0">' + sh.minute + "' " +
                escapeHtml(sh.team) + ' · ' + escapeHtml(sh.player) +
                (sh.xg !== null ? ' (xG: ' + sh.xg.toFixed(3) + ')' : '') +
                ' · ' + sh.outcome + '</div>'
            ).join('');
            resultEl.innerHTML =
                '<div style="font-size:0.85rem">' +
                '<strong>' + s.total_events + '</strong> events · ' +
                '<strong>' + s.shots + '</strong> shots · ' +
                '<strong>' + s.passes + '</strong> passes · ' +
                'xG: <strong>' + s.total_xg + '</strong><br>' +
                'Teams: ' + escapeHtml(s.teams.join(' vs ')) +
                '</div>' + shotsHtml;
            resultEl.className = 'feedback-result';
        } catch (e) {
            resultEl.textContent = '❌ Failed to load events';
            resultEl.className = 'feedback-result error';
        }
    }

    async function sbImportToDb() {
        if (!bridge) return;
        const matchIdInput = document.getElementById('sb-match-id');
        const resultEl = document.getElementById('sb-import-result');
        const matchId = matchIdInput.value.trim();
        if (!matchId) {
            resultEl.textContent = 'Enter a StatsBomb Match ID';
            resultEl.className = 'feedback-result error';
            return;
        }
        resultEl.textContent = 'Importing events to local database...';
        resultEl.className = 'feedback-result';
        try {
            const data = JSON.parse(await bridge.import_statsbomb_match(matchId));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                resultEl.className = 'feedback-result error';
                return;
            }
            resultEl.textContent = '✅ Imported ' + data.imported + ' events from match ' + data.match_id;
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Import failed';
            resultEl.className = 'feedback-result error';
        }
    }

    async function sbGetLineups() {
        if (!bridge) return;
        const matchIdInput = document.getElementById('sb-match-id');
        const resultEl = document.getElementById('sb-lineups-result');
        const matchId = parseInt(matchIdInput.value);
        if (!matchId) {
            resultEl.textContent = 'Enter a StatsBomb Match ID';
            resultEl.className = 'feedback-result error';
            return;
        }
        resultEl.textContent = 'Loading lineups...';
        resultEl.className = 'feedback-result';
        try {
            const data = JSON.parse(await bridge.get_statsbomb_lineups(validateInt(matchId)));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                resultEl.className = 'feedback-result error';
                return;
            }
            resultEl.innerHTML = (data.lineups || []).map(team =>
                '<div style="font-size:0.85rem;margin-top:6px"><strong>' + escapeHtml(team.team) + '</strong> (' + team.players.length + ' players)' +
                '<div style="font-size:0.75rem;color:var(--text-muted)">' +
                team.players.slice(0, 11).map(p => '#' + p.jersey_number + ' ' + escapeHtml(p.name)).join(' · ') +
                '</div></div>'
            ).join('');
            resultEl.className = 'feedback-result';
        } catch (e) {
            resultEl.textContent = '❌ Failed to load lineups';
            resultEl.className = 'feedback-result error';
        }
    }

    async function sbSearchTeam() {
        if (!bridge) return;
        const searchInput = document.getElementById('sb-team-search');
        const resultsDiv = document.getElementById('sb-team-results');
        const query = searchInput.value.trim();
        if (query.length < 2) {
            resultsDiv.classList.add('hidden');
            return;
        }
        try {
            const data = JSON.parse(await bridge.search_statsbomb_team(sanitizeString(query)));
            const matches = data.matches || [];
            if (matches.length === 0) {
                resultsDiv.innerHTML = '<div class="fd-result-item" style="color: var(--text-muted)">No matches found</div>';
                resultsDiv.classList.remove('hidden');
                return;
            }
            resultsDiv.innerHTML = matches.slice(0, 10).map(m =>
                '<div class="fd-result-item" data-match-id="' + m.match_id + '">' +
                '<span style="font-size:0.8rem">' +
                escapeHtml(m.home) + ' ' + (m.home_score !== null ? m.home_score : '-') + '-' + (m.away_score !== null ? m.away_score : '-') + ' ' + escapeHtml(m.away) +
                '<br><span style="color:var(--text-muted);font-size:0.7rem">' + escapeHtml(m.competition) + ' · ' + escapeHtml(m.season) + ' · ' + m.date + '</span>' +
                '</span></div>'
            ).join('');
            resultsDiv.classList.remove('hidden');
            resultsDiv.querySelectorAll('.fd-result-item').forEach(el => {
                el.addEventListener('click', function() {
                    document.getElementById('sb-match-id').value = this.dataset.matchId;
                    resultsDiv.classList.add('hidden');
                });
            });
        } catch (e) {
            console.error('StatsBomb team search failed:', e);
        }
    }

    // --- OpenFootball ---

    async function checkOpenFootballStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('openfootball-status');
        const controls = document.getElementById('openfootball-controls');
        try {
            const status = JSON.parse(await bridge.check_openfootball_status());
            if (status.available) {
                statusEl.textContent = '🟢 Connected (CC0 public domain data)';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
                ofbPopulateCompetitions();
            } else {
                statusEl.textContent = '🟡 Not available (network error)';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    async function ofbPopulateCompetitions() {
        if (!bridge) return;
        try {
            const data = JSON.parse(await bridge.get_openfootball_competitions());
            const compSelect = document.getElementById('ofb-competition');
            const seasonSelect = document.getElementById('ofb-season');
            compSelect.innerHTML = '<option value="">-- Competition --</option>' +
                (data.competitions || []).map(c =>
                    '<option value="' + c.id + '">' + escapeHtml(c.name) + '</option>'
                ).join('');
            compSelect.onchange = function() {
                const comp = (data.competitions || []).find(c => c.id === this.value);
                seasonSelect.innerHTML = '<option value="">-- Season --</option>' +
                    (comp ? comp.seasons : []).map(s =>
                        '<option value="' + s + '">' + s + '</option>'
                    ).join('');
            };
            const wcSelect = document.getElementById('ofb-wc-year');
            wcSelect.innerHTML = '<option value="">-- World Cup Year --</option>' +
                [1930, 1934, 1938, 1950, 1954, 1958, 1962, 1966, 1970, 1974, 1978, 1982, 1986, 1990, 1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026]
                .map(y => '<option value="' + y + '">' + y + '</option>').join('');
        } catch (e) {
            console.error('OpenFootball populate failed:', e);
        }
    }

    async function ofbLoadMatches() {
        if (!bridge) return;
        const comp = document.getElementById('ofb-competition').value;
        const season = document.getElementById('ofb-season').value;
        const list = document.getElementById('ofb-matches-list');
        if (!comp || !season) { list.innerHTML = ''; return; }
        list.innerHTML = '<div class="roster-item">Loading...</div>';
        try {
            const data = JSON.parse(await bridge.get_openfootball_matches(comp, season));
            if (data.error) { list.innerHTML = '<div class="roster-item">❌ ' + data.error + '</div>'; return; }
            const matches = data.matches || [];
            if (matches.length === 0) { list.innerHTML = '<div class="roster-item">No matches</div>'; return; }
            list.innerHTML = matches.map(m => {
                const score = (m.home_score !== null ? m.home_score : '-') + '-' + (m.away_score !== null ? m.away_score : '-');
                return '<div class="roster-item">' +
                    '<span style="color:var(--text-muted);font-size:0.75rem;width:60px">' + m.date + '</span>' +
                    '<span style="flex:1">' + escapeHtml(m.home) + ' <strong>' + score + '</strong> ' + escapeHtml(m.away) + '</span>' +
                    '<span style="color:var(--text-muted);font-size:0.7rem">' + escapeHtml(m.round) + '</span>' +
                    '</div>';
            }).join('');
        } catch (e) {
            list.innerHTML = '<div class="roster-item">Failed to load</div>';
        }
    }

    async function ofbSearchTeam() {
        if (!bridge) return;
        const searchInput = document.getElementById('ofb-team-search');
        const resultsDiv = document.getElementById('ofb-team-results');
        const query = searchInput.value.trim();
        if (query.length < 2) { resultsDiv.classList.add('hidden'); return; }
        clearTimeout(window.ofbTimer);
        window.ofbTimer = setTimeout(async () => {
            try {
                const data = JSON.parse(await bridge.search_openfootball_team(sanitizeString(query)));
                const matches = data.matches || [];
                if (matches.length === 0) {
                    resultsDiv.innerHTML = '<div class="fd-result-item" style="color: var(--text-muted)">No matches found</div>';
                    resultsDiv.classList.remove('hidden');
                    return;
                }
                resultsDiv.innerHTML = matches.slice(0, 15).map(m =>
                    '<div class="fd-result-item">' +
                    '<span style="font-size:0.8rem">' +
                    escapeHtml(m.home) + ' ' + (m.home_score !== null ? m.home_score : '-') + '-' + (m.away_score !== null ? m.away_score : '-') + ' ' + escapeHtml(m.away) +
                    '<br><span style="color:var(--text-muted);font-size:0.7rem">' + escapeHtml(m.competition) + ' · ' + escapeHtml(m.season) + ' · ' + m.date + '</span>' +
                    '</span></div>'
                ).join('');
                resultsDiv.classList.remove('hidden');
            } catch (e) {
                console.error('OpenFootball team search failed:', e);
            }
        }, 400);
    }

    async function ofbLoadWorldCup() {
        if (!bridge) return;
        const yearInput = document.getElementById('ofb-wc-year');
        const list = document.getElementById('ofb-wc-list');
        const year = parseInt(yearInput.value);
        if (!year) { list.innerHTML = ''; return; }
        list.innerHTML = '<div class="roster-item">Loading WC ' + year + '...</div>';
        try {
            const data = JSON.parse(await bridge.get_openfootball_worldcup(year));
            if (data.error) { list.innerHTML = '<div class="roster-item">❌ ' + data.error + '</div>'; return; }
            const matches = data.matches || [];
            if (matches.length === 0) { list.innerHTML = '<div class="roster-item">No WC matches for ' + year + '</div>'; return; }
            list.innerHTML = matches.map(m => {
                const score = (m.home_score !== null ? m.home_score : '-') + '-' + (m.away_score !== null ? m.away_score : '-');
                return '<div class="roster-item">' +
                    '<span style="color:var(--text-muted);font-size:0.75rem;width:80px">' + m.date + '</span>' +
                    '<span style="flex:1">' + escapeHtml(m.home) + ' <strong>' + score + '</strong> ' + escapeHtml(m.away) + '</span>' +
                    '<span style="color:var(--text-muted);font-size:0.7rem">' + escapeHtml(m.round) + '</span>' +
                    '</div>';
            }).join('');
        } catch (e) {
            list.innerHTML = '<div class="roster-item">Failed to load WC</div>';
        }
    }

    // --- Pose Analysis ---

    async function checkPoseStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('pose-status');
        const controls = document.getElementById('pose-controls');
        try {
            const status = JSON.parse(await bridge.check_pose_status());
            if (status.available) {
                statusEl.textContent = '🟢 YOLO26-pose model loaded';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
            } else {
                statusEl.textContent = '🟡 Pose model not available (ultralytics not installed)';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    async function poseGetSummary() {
        if (!bridge) return;
        const trackIdInput = document.getElementById('pose-track-id');
        const resultEl = document.getElementById('pose-result');
        const trackId = parseInt(trackIdInput.value);
        if (isNaN(trackId)) {
            resultEl.textContent = 'Enter a player track ID';
            resultEl.className = 'feedback-result error';
            return;
        }
        resultEl.textContent = 'Loading...';
        try {
            const data = JSON.parse(await bridge.get_activity_summary(trackId));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                resultEl.className = 'feedback-result error';
                return;
            }
            const entries = Object.entries(data.summary || {});
            if (entries.length === 0) {
                resultEl.textContent = 'No activity data for track ' + trackId;
                resultEl.className = 'feedback-result';
                return;
            }
            const html = entries.map(([act, dur]) =>
                '<span style="display:inline-block;margin:2px 6px;padding:3px 8px;background:#e2e8f0;border-radius:4px;font-size:0.85rem">' +
                act + ': ' + dur.toFixed(1) + 's</span>'
            ).join('');
            resultEl.innerHTML = '<div style="font-size:0.85rem">Activity for track #' + trackId + ': ' + html + '</div>';
            resultEl.className = 'feedback-result';
        } catch (e) {
            resultEl.textContent = '❌ Failed to load activity';
            resultEl.className = 'feedback-result error';
        }
    }

    async function poseGetSegments() {
        if (!bridge) return;
        const trackIdInput = document.getElementById('pose-track-id');
        const resultEl = document.getElementById('pose-result');
        const trackId = parseInt(trackIdInput.value);
        if (isNaN(trackId)) {
            resultEl.textContent = 'Enter a player track ID';
            resultEl.className = 'feedback-result error';
            return;
        }
        resultEl.textContent = 'Loading...';
        try {
            const data = JSON.parse(await bridge.get_activity_segments(trackId));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                resultEl.className = 'feedback-result error';
                return;
            }
            const segs = data.segments || [];
            if (segs.length === 0) {
                resultEl.textContent = 'No segments for track ' + trackId;
                resultEl.className = 'feedback-result';
                return;
            }
            resultEl.innerHTML = segs.slice(0, 20).map(s =>
                '<div style="font-size:0.78rem;padding:2px 0">' +
                s.start_time.toFixed(1) + 's → ' + s.end_time.toFixed(1) + 's: ' +
                '<strong>' + s.activity + '</strong> (' + s.duration_s.toFixed(1) + 's)' +
                '</div>'
            ).join('');
            resultEl.className = 'feedback-result';
        } catch (e) {
            resultEl.textContent = '❌ Failed to load segments';
            resultEl.className = 'feedback-result error';
        }
    }

    // --- MuJoCo Ball Trajectory ---

    async function checkMuJoCoStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('mujoco-status');
        const controls = document.getElementById('mujoco-controls');
        try {
            const status = JSON.parse(await bridge.check_mujoco_status());
            if (status.available) {
                let info = '🟢 Trajectory simulation available';
                if (status.uses_mujoco) info += ' (using MuJoCo)';
                else info += ' (analytical fallback)';
                statusEl.textContent = info;
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
                mujocoLoadPresets();
            } else {
                statusEl.textContent = '🟡 Not available';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    async function mujocoLoadPresets() {
        if (!bridge) return;
        try {
            const data = JSON.parse(await bridge.get_setpiece_presets());
            const select = document.getElementById('mujoco-preset');
            select.innerHTML = '<option value="">-- Select Preset --</option>' +
                (data.presets || []).map((p, idx) =>
                    '<option value="' + idx + '">' + escapeHtml(p.name) + '</option>'
                ).join('');
        } catch (e) {
            console.error('MuJoCo preset load failed:', e);
        }
    }

    function mujocoApplyPreset() {
        if (!bridge) return;
        bridge.get_setpiece_presets().then(json => {
            try {
                const data = JSON.parse(json);
                const idx = parseInt(document.getElementById('mujoco-preset').value);
                if (isNaN(idx) || !data.presets || !data.presets[idx]) return;
                const p = data.presets[idx];
                document.getElementById('mujoco-speed').value = p.initial_speed;
                document.getElementById('mujoco-angle').value = p.launch_angle_deg;
                document.getElementById('mujoco-spin').value = p.spin_rps;
                document.getElementById('mujoco-direction').value = p.direction_deg;
            } catch (e) {}
        }).catch(function(err) {
            console.error('mujocoApplyPreset failed:', err);
        });
    }

    async function mujocoSimulate() {
        if (!bridge) return;
        const speed = parseFloat(document.getElementById('mujoco-speed').value);
        const angle = parseFloat(document.getElementById('mujoco-angle').value);
        const spin = parseFloat(document.getElementById('mujoco-spin').value);
        const direction = parseFloat(document.getElementById('mujoco-direction').value);
        const resultEl = document.getElementById('mujoco-result');
        resultEl.textContent = 'Simulating...';
        resultEl.className = 'feedback-result';
        try {
            const data = JSON.parse(await bridge.simulate_trajectory(
                isFinite(speed) ? speed : 0,
                isFinite(angle) ? angle : 0,
                isFinite(spin) ? spin : 0,
                isFinite(direction) ? direction : 0,
                2.5
            ));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                resultEl.className = 'feedback-result error';
                return;
            }
            resultEl.innerHTML =
                '<div style="font-size:0.85rem">' +
                '<strong>' + data.method + '</strong> simulation<br>' +
                'Landing: (' + data.landing_x.toFixed(1) + ', ' + data.landing_y.toFixed(1) + ') m<br>' +
                'Max height: ' + data.max_height.toFixed(1) + ' m<br>' +
                'Duration: ' + data.duration_s.toFixed(2) + ' s<br>' +
                'Final speed: ' + data.final_speed_mps.toFixed(1) + ' m/s' +
                '</div>';
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Simulation failed';
            resultEl.className = 'feedback-result error';
        }
    }

    // --- Weather ---

    async function checkWeatherStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('weather-status');
        const controls = document.getElementById('weather-controls');
        try {
            const status = JSON.parse(await bridge.check_weather_status());
            if (status.available) {
                statusEl.textContent = '🟢 Available' +
                    (status.has_video_classifier ? ' (video classifier ready)' : ' (Open-Meteo + manual)');
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
            } else {
                statusEl.textContent = '🟡 Not available';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    async function wxAnalyzeManual() {
        if (!bridge) return;
        const resultEl = document.getElementById('wx-result');
        const temp = parseFloat(document.getElementById('wx-temp').value);
        const precip = parseFloat(document.getElementById('wx-precip').value);
        const wind = parseFloat(document.getElementById('wx-wind').value);
        const humidity = parseFloat(document.getElementById('wx-humidity').value);
        const conditions = document.getElementById('wx-conditions').value;
        resultEl.textContent = 'Analyzing...';
        try {
            const data = JSON.parse(await bridge.set_manual_weather(
                isFinite(temp) ? temp : 0,
                isFinite(precip) ? precip : 0,
                isFinite(wind) ? wind : 0,
                isFinite(humidity) ? humidity : 0,
                sanitizeString(conditions)
            ));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            const c = data.conditions, i = data.impact;
            resultEl.innerHTML = '<div style="font-size:0.85rem">' +
                '<strong>Conditions:</strong> ' + c.conditions + ' (' + c.pitch_state + ' pitch)<br>' +
                '<strong>Impact:</strong> ' + i.goals_delta + ' goals, ' + i.passing_delta_pct + '% passing, ' +
                i.sprint_delta_pct + '% sprint<br>' +
                i.notes.map(n => '• ' + escapeHtml(n)).join('<br>') + '</div>';
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Failed to analyze';
        }
    }

    async function wxFetchFromAPI() {
        if (!bridge) return;
        const resultEl = document.getElementById('wx-result');
        const lat = parseFloat(document.getElementById('wx-lat').value);
        const lon = parseFloat(document.getElementById('wx-lon').value);
        const date = document.getElementById('wx-date').value;
        if (!date) {
            resultEl.textContent = 'Enter a date';
            return;
        }
        resultEl.textContent = 'Fetching from Open-Meteo...';
        try {
            const data = JSON.parse(await bridge.fetch_match_weather(
                isFinite(lat) ? lat : 0,
                isFinite(lon) ? lon : 0,
                sanitizeString(date),
                false
            ));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            document.getElementById('wx-temp').value = data.temperature_c.toFixed(1);
            document.getElementById('wx-precip').value = data.precipitation_mm.toFixed(1);
            document.getElementById('wx-wind').value = data.wind_speed_kmh.toFixed(1);
            document.getElementById('wx-humidity').value = data.humidity_pct.toFixed(0);
            document.getElementById('wx-conditions').value = data.conditions;
            resultEl.textContent = '✅ Fetched: ' + data.temperature_c.toFixed(1) + '°C, ' +
                data.conditions + ', pitch=' + data.pitch_state + ' (source: ' + data.source + ')';
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Fetch failed';
        }
    }

    async function wxAnalyzeVideo() {
        if (!bridge) return;
        const resultEl = document.getElementById('wx-video-result');
        const videoPath = document.getElementById('wx-video-path').value.trim();
        if (!videoPath) {
            resultEl.textContent = 'Enter a video file path';
            return;
        }
        resultEl.textContent = 'Analyzing video weather (this may take 10-30 seconds)...';
        resultEl.className = 'feedback-result';
        try {
            const data = JSON.parse(await bridge.classify_video_weather(sanitizeString(videoPath)));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            const rd = data.raindrop_detection;
            const wc = data.weather_classification;
            let html = '<div style="font-size:0.85rem"><strong>Combined analysis:</strong> ' + escapeHtml(data.method) + '<br>';
            if (rd) {
                html += '<strong>Raindrops:</strong> ' + rd.raindrop_count + ' detected across ' + rd.frame_count + ' frames ' +
                    '(density: ' + rd.raindrop_density.toFixed(1) + '/Mpx, conf: ' + rd.avg_confidence.toFixed(2) + ', method: ' + escapeHtml(rd.method) + ')<br>';
            }
            if (wc) {
                html += '<strong>Multi-class:</strong> ' + escapeHtml(wc.predicted_class) + ' (conf: ' + (wc.confidence * 100).toFixed(1) + '%, method: ' + escapeHtml(wc.method) + ')<br>';
                html += '<small>Probabilities: ';
                const probs = Object.entries(wc.class_probabilities).sort((a, b) => b[1] - a[1]);
                html += probs.map(([c, p]) => c + ':' + (p * 100).toFixed(0) + '%').join(', ') + '</small><br>';
            }
            html += '<strong>Final: </strong>' + (data.is_rainy ? '🌧️ Rainy' : '☀️ Not rainy');
            if (data.conditions) {
                html += ' (' + data.conditions.conditions + ', ' + data.conditions.pitch_state + ' pitch)';
            }
            html += '</div>';
            resultEl.innerHTML = html;
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Video analysis failed';
        }
    }

    // --- Psychology ---

    async function checkPsychologyStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('psy-status');
        const controls = document.getElementById('psy-controls');
        try {
            const status = JSON.parse(await bridge.check_psychology_status());
            if (status.available) {
                statusEl.textContent = '🟢 Available (momentum, score-state, late-game)';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
            } else {
                statusEl.textContent = '🟡 Not available';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    async function psyAnalyze() {
        if (!bridge) return;
        const summaryEl = document.getElementById('psy-summary');
        const momentumEl = document.getElementById('psy-momentum');
        const eventsEl = document.getElementById('psy-events');
        const matchId = parseInt(document.getElementById('psy-match-id').value) || 0;
        const home = document.getElementById('psy-home').value || 'Home';
        const away = document.getElementById('psy-away').value || 'Away';
        summaryEl.textContent = 'Analyzing...';
        const events = JSON.stringify([]);
        try {
            const data = JSON.parse(await bridge.analyze_match_psychology(matchId, home, away, events));
            if (data.error) {
                summaryEl.textContent = '❌ ' + data.error;
                return;
            }
            summaryEl.innerHTML = '<div style="font-size:0.85rem">' +
                '<strong>Score state transitions:</strong> ' + data.score_state_transitions.length + '<br>' +
                '<strong>Post-goal lulls:</strong> ' + data.post_goal_lull_count + '<br>' +
                '<strong>Comebacks:</strong> ' + data.comeback_count + '<br>' +
                '<strong>Capitulations:</strong> ' + data.capitulation_count + '<br>' +
                '<strong>Avg late-game passing drop:</strong> ' + (data.avg_late_game_passing_drop * 100).toFixed(1) + '%<br>' +
                data.notes.map(n => '• ' + escapeHtml(n)).join('<br>') + '</div>';
            summaryEl.className = 'feedback-result success';
            if (data.momentum_timeline && data.momentum_timeline.length > 0) {
                const last10 = data.momentum_timeline.slice(-10);
                momentumEl.innerHTML = '<div style="font-size:0.78rem">Momentum (last 10 windows): ' +
                    last10.map(m => 'M' + m.minute.toFixed(0) + ':' + m.home.toFixed(2)).join(' | ') + '</div>';
            } else {
                momentumEl.textContent = 'No momentum data (no events)';
            }
            if (data.psychology_events && data.psychology_events.length > 0) {
                eventsEl.innerHTML = data.psychology_events.slice(0, 10).map(e =>
                    '<div style="font-size:0.78rem;padding:2px 0">' +
                    e.minute + "' " + escapeHtml(e.team) + ': <strong>' + e.type + '</strong> — ' +
                    escapeHtml(e.description) + '</div>'
                ).join('');
            } else {
                eventsEl.textContent = 'No psychology events (provide events JSON for full analysis)';
            }
        } catch (e) {
            summaryEl.textContent = '❌ Analysis failed';
        }
    }

    // --- Football Rules ---

    async function checkRulesStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('rules-status');
        const controls = document.getElementById('rules-controls');
        try {
            const status = JSON.parse(await bridge.check_rules_status());
            if (status.available) {
                statusEl.textContent = '🟢 IFAB Laws loaded (' + status.laws_count + ' laws)';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
                rulesLoadLaws();
            } else {
                statusEl.textContent = '🟡 Not available';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    async function rulesLoadLaws() {
        if (!bridge) return;
        try {
            const data = JSON.parse(await bridge.get_all_laws());
            const select = document.getElementById('rules-law-select');
            select.innerHTML = '<option value="">-- Select Law --</option>' +
                (data.laws || []).map(l =>
                    '<option value="' + l.number + '">Law ' + l.number + ': ' + escapeHtml(l.name) + '</option>'
                ).join('');
        } catch (e) {
            console.error('Failed to load laws:', e);
        }
    }

    async function rulesShowLaw() {
        if (!bridge) return;
        const num = parseInt(document.getElementById('rules-law-select').value);
        const contentEl = document.getElementById('rules-law-content');
        if (!num) {
            contentEl.textContent = 'Select a law';
            return;
        }
        try {
            const law = JSON.parse(await bridge.get_law_summary(num));
            if (law.error) {
                contentEl.textContent = '❌ ' + law.error;
                return;
            }
            contentEl.innerHTML = '<div style="font-size:0.85rem">' +
                '<strong>Law ' + law.number + ': ' + escapeHtml(law.name) + '</strong><br>' +
                escapeHtml(law.summary || '') +
                (law.key_constraints ? '<br><br><em>Key constraints:</em><ul style="margin:4px 0">' +
                    law.key_constraints.map(c => '<li style="font-size:0.78rem">' + escapeHtml(c) + '</li>').join('') + '</ul>' : '') +
                '</div>';
            contentEl.className = 'feedback-result';
        } catch (e) {
            contentEl.textContent = '❌ Failed to load law';
        }
    }

    async function rulesClassifyEvent() {
        if (!bridge) return;
        const resultEl = document.getElementById('cls-result');
        const event = document.getElementById('cls-event').value;
        const x = parseFloat(document.getElementById('cls-x').value);
        const y = parseFloat(document.getElementById('cls-y').value);
        const side = document.getElementById('cls-side').value;
        resultEl.textContent = 'Classifying...';
        try {
            const data = JSON.parse(await bridge.classify_event_rule(sanitizeString(event), isFinite(x) ? x : 0, isFinite(y) ? y : 0, sanitizeString(side)));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            resultEl.innerHTML = '<div style="font-size:0.85rem">' +
                '<strong>Law ' + data.law + ': ' + escapeHtml(data.law_name) + '</strong><br>' +
                'Restart: ' + (data.restart || 'none') + '<br>' +
                escapeHtml(data.description) + '<br>' +
                'Card likely: ' + (data.card_likely || 'none') + '</div>';
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Classification failed';
        }
    }

    async function rulesCheckOffside() {
        if (!bridge) return;
        const resultEl = document.getElementById('off-result');
        const ax = parseFloat(document.getElementById('off-attacker').value);
        const dx = parseFloat(document.getElementById('off-defender').value);
        const bx = parseFloat(document.getElementById('off-ball').value);
        resultEl.textContent = 'Checking...';
        try {
            const data = JSON.parse(await bridge.check_offside(isFinite(ax) ? ax : 0, isFinite(dx) ? dx : 0, isFinite(bx) ? bx : 0, 'right'));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            resultEl.innerHTML = '<div style="font-size:0.85rem">' +
                (data.is_offside ? '🚩 <strong>OFFSIDE</strong>' : '✅ <strong>Onside</strong>') + '<br>' +
                escapeHtml(data.explanation) + '</div>';
            resultEl.className = data.is_offside ? 'feedback-result error' : 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Check failed';
        }
    }

    // --- Pro Analytics ---

    async function proSetpieceAnalyze() {
        if (!bridge) return;
        const resultEl = document.getElementById('pro-result');
        resultEl.textContent = 'Analyzing set-pieces...';
        resultEl.className = 'feedback-result';
        const sampleEvents = [
            { set_piece_type: 'corner', team: 'home', minute: 12, second: 30, delivery_x: 100, delivery_y: 0, delivery_style: 'inswinging', first_contact_x: 99, first_contact_y: 6, outcome: 'shot' },
            { set_piece_type: 'corner', team: 'home', minute: 25, second: 0, delivery_x: 100, delivery_y: 68, delivery_style: 'outswinging', first_contact_x: 99, first_contact_y: 62, outcome: 'clearance' },
            { set_piece_type: 'corner', team: 'home', minute: 40, second: 0, delivery_x: 100, delivery_y: 0, delivery_style: 'short', first_contact_x: 88, first_contact_y: 5, outcome: 'retention_midfield' },
            { set_piece_type: 'free_kick', team: 'home', minute: 55, second: 0, delivery_x: 88, delivery_y: 34, delivery_style: 'lofted', first_contact_x: 96, first_contact_y: 5, outcome: 'shot' },
            { set_piece_type: 'corner', team: 'away', minute: 30, second: 0, delivery_x: 5, delivery_y: 0, delivery_style: 'inswinging', first_contact_x: 6, first_contact_y: 5, outcome: 'goal' },
        ];
        try {
            const data = JSON.parse(await bridge.analyze_setpieces(JSON.stringify(sampleEvents), 'home'));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            let html = '<div style="font-size:0.85rem"><strong>Set-Piece Analysis</strong><br>';
            html += '<strong>Home:</strong> ' + data.home.total_corners + ' corners, ';
            html += data.home.shots_per_corner * 100 + '% shot rate, ';
            html += 'favorite: ' + (data.home.favorite_target_zone || 'n/a') + '<br>';
            html += '<strong>Away:</strong> ' + data.away.total_corners + ' corners, ';
            html += data.away.shots_per_corner * 100 + '% shot rate<br>';
            html += '<strong>Differential:</strong> ' + data.set_piece_differential.toFixed(2) + '<br>';
            html += data.notes.map(n => '• ' + escapeHtml(n)).join('<br>');
            html += '</div>';
            resultEl.innerHTML = html;
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Set-piece analysis failed';
        }
    }

    async function proGoalkeeperAnalyze() {
        if (!bridge) return;
        const resultEl = document.getElementById('pro-result');
        resultEl.textContent = 'Analyzing goalkeeper...';
        resultEl.className = 'feedback-result';
        const actions = [
            { action_type: 'save_cross', team: 'home', minute: 20, outcome: 'complete' },
            { action_type: 'short_dist', team: 'home', minute: 25, outcome: 'complete' },
            { action_type: 'long_dist', team: 'home', minute: 35, outcome: 'failed' },
            { action_type: 'sweep', team: 'home', minute: 50, outcome: 'complete' },
        ];
        const shots = [
            { x: 88, y: 34, outcome: 'save', body_part: 'foot' },
            { x: 90, y: 30, outcome: 'save', body_part: 'foot' },
            { x: 92, y: 38, outcome: 'goal', body_part: 'head' },
            { x: 87, y: 40, outcome: 'save', body_part: 'right_foot' },
        ];
        try {
            const data = JSON.parse(await bridge.analyze_goalkeeper('home', JSON.stringify(actions), JSON.stringify(shots), false));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            let html = '<div style="font-size:0.85rem"><strong>Goalkeeper Report</strong><br>';
            html += 'Saves: ' + data.saves + '/' + data.shots_faced + ' (save rate: ' + (data.save_rate * 100).toFixed(0) + '%)<br>';
            html += 'Goals prevented (xGOT): ' + data.goals_prevented_xgot.toFixed(2) + '<br>';
            html += 'Short distribution: ' + data.short_distribution_successful + '/' + data.short_distribution_attempts + '<br>';
            html += 'Long distribution: ' + data.long_distribution_successful + '/' + data.long_distribution_attempts + '<br>';
            html += 'Sweeps: ' + data.sweep_actions + '<br>';
            html += data.notes.map(n => '• ' + escapeHtml(n)).join('<br>');
            html += '</div>';
            resultEl.innerHTML = html;
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ GK analysis failed';
        }
    }

    async function proSubstitutionAnalyze() {
        if (!bridge) return;
        const resultEl = document.getElementById('pro-result');
        resultEl.textContent = 'Analyzing substitutions...';
        resultEl.className = 'feedback-result';
        const subs = [
            { minute: 60, second: 0, team: 'home', player_off_name: 'Tired CB', player_on_name: 'Fresh CB', formation_before: '4-4-2', formation_after: '4-4-2' },
            { minute: 75, second: 0, team: 'home', player_off_name: 'Winger A', player_on_name: 'Winger B', formation_before: '4-4-2', formation_after: '4-3-3', position_changed: true },
        ];
        const events = [
            { type: 'shot', team: 'home', minute: 62, second: 0, xg: 0.15 },
            { type: 'shot', team: 'home', minute: 73, second: 0, xg: 0.4 },
            { type: 'goal', team: 'home', minute: 80, second: 0 },
            { type: 'pass', team: 'home', minute: 70, second: 0, completed: true },
            { type: 'pass', team: 'home', minute: 70, second: 30, completed: true },
        ];
        try {
            const data = JSON.parse(await bridge.analyze_substitutions('home', JSON.stringify(subs), JSON.stringify(events)));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            let html = '<div style="font-size:0.85rem"><strong>Substitution Impact</strong><br>';
            html += 'Total impact: ' + data.total_impact.toFixed(2) + ' | Avg: ' + data.avg_impact.toFixed(2) + '<br>';
            html += 'Tactical changes: ' + data.tactical_changes + ' | Formation: ' + data.formation_changes + '<br><br>';
            for (const i of data.impacts) {
                html += '<strong>' + i.minute + '\':</strong> ' + (i.player_off || '?') + ' → ' + (i.player_on || '?') + ' | ';
                html += 'rating: ' + i.rating.toFixed(2) + ' [' + i.verdict + ']';
                html += '<br>';
            }
            if (data.best_sub) {
                html += '<br><strong>Best:</strong> ' + data.best_sub.minute + '\' (' + data.best_sub.rating.toFixed(2) + ')';
            }
            html += '</div>';
            resultEl.innerHTML = html;
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Substitution analysis failed';
        }
    }

    async function proPossessionAnalyze() {
        if (!bridge) return;
        const resultEl = document.getElementById('pro-result');
        resultEl.textContent = 'Analyzing possession...';
        resultEl.className = 'feedback-result';
        const events = [
            { type: 'pass', team: 'home', minute: 5, second: 0, completed: true, player_track_id: 7 },
            { type: 'pass', team: 'home', minute: 5, second: 30, completed: true, player_track_id: 8 },
            { type: 'pass', team: 'home', minute: 6, second: 0, completed: true, player_track_id: 7 },
            { type: 'tackle', team: 'away', minute: 6, second: 30, player_track_id: 3 },
            { type: 'pass', team: 'away', minute: 7, second: 0, completed: false, player_track_id: 3 },
            { type: 'tackle', team: 'home', minute: 7, second: 30, player_track_id: 5 },
            { type: 'pass', team: 'home', minute: 8, second: 0, completed: true, player_track_id: 5 },
            { type: 'pass', team: 'home', minute: 8, second: 30, completed: true, player_track_id: 9 },
        ];
        try {
            const data = JSON.parse(await bridge.analyze_possession('home', 'away', JSON.stringify(events)));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            let html = '<div style="font-size:0.85rem"><strong>Detailed Possession</strong><br>';
            html += 'Home: ' + data.home_possession_pct.toFixed(1) + '% | Away: ' + data.away_possession_pct.toFixed(1) + '%<br>';
            html += 'Chains: ' + data.home_chains_count + ' (home) | ' + data.away_chains_count + ' (away)<br>';
            html += 'Avg chain: ' + data.avg_chain_duration_s + 's | Longest: ' + data.longest_chain_s + 's<br>';
            html += 'Counter-presses: ' + data.counter_presses + '<br>';
            html += data.notes.map(n => '• ' + escapeHtml(n)).join('<br>');
            html += '</div>';
            resultEl.innerHTML = html;
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Possession analysis failed';
        }
    }

    async function proXGOT() {
        if (!bridge) return;
        const resultEl = document.getElementById('pro-result');
        resultEl.textContent = 'Computing xGOT...';
        const shotX = 88, shotY = 34;
        try {
            const data = JSON.parse(await bridge.compute_xgot(isFinite(shotX) ? shotX : 0, isFinite(shotY) ? shotY : 0, 'foot', false));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            resultEl.innerHTML = '<div style="font-size:0.85rem"><strong>xGOT for shot at (' + shotX + ', ' + shotY + ')</strong><br>xGOT: ' + data.xgot.toFixed(3) + '</div>';
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ xGOT compute failed';
        }
    }

    // --- Real-Time Mode ---

    async function realtimeStatus() {
        if (!bridge) return;
        const resultEl = document.getElementById('realtime-result');
        resultEl.textContent = 'Checking real-time service...';
        try {
            const data = JSON.parse(await bridge.realtime_status());
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            const html = '<div style="font-size:0.85rem"><strong>Real-Time Service</strong><br>' +
                'Target FPS: ' + data.target_fps + '<br>' +
                'Buffer Size: ' + data.buffer_size + ' frames<br>' +
                'Alert Rules: ' + data.alert_rule_count + '<br>' +
                'Subscribers: ' + data.subscriber_count + '<br>' +
                '<em>Use realtimeService.run_file(video_path) or run_webcam() from Python API for full streaming.</em>' +
                '</div>';
            resultEl.innerHTML = html;
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Status check failed';
        }
    }

    async function realtimeConsole() {
        if (!bridge) return;
        const resultEl = document.getElementById('realtime-result');
        try {
            const data = JSON.parse(await bridge.realtime_subscribe_console());
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            resultEl.textContent = '✅ Console subscriber added (events will print to log)';
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Subscribe failed';
        }
    }

    async function realtimeCancel() {
        if (!bridge) return;
        const resultEl = document.getElementById('realtime-result');
        try {
            const data = JSON.parse(await bridge.realtime_cancel());
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                return;
            }
            resultEl.textContent = '✅ Stream cancelled';
            resultEl.className = 'feedback-result success';
        } catch (e) {
            resultEl.textContent = '❌ Cancel failed';
        }
    }

    // --- Card Detection ---

    async function checkCardsStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('cards-status');
        const controls = document.getElementById('cards-controls');
        try {
            const status = JSON.parse(await bridge.check_cards_status());
            if (status.available) {
                statusEl.textContent = '🟢 Available (visual + audio + tactical + external)';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
            } else {
                statusEl.textContent = '🟡 Not available';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    async function cardsInferTactical() {
        if (!bridge) return;
        const listEl = document.getElementById('cards-list');
        const events = [
            { type: 'foul', team: 'home', minute: 23, second: 12, x: 92, severity: 0.7, player_track_id: 5, player_name: 'Defender A' },
            { type: 'foul', team: 'away', minute: 45, second: 30, x: 12, severity: 0.8, player_track_id: 12, player_name: 'Midfielder B' },
            { type: 'foul', team: 'home', minute: 78, second: 5, x: 88, severity: 0.65, player_track_id: 7, player_name: 'Defender C' },
        ];
        listEl.innerHTML = '<div class="roster-item">Inferring...</div>';
        try {
            const data = JSON.parse(await bridge.infer_cards_tactically(JSON.stringify(events)));
            if (data.error) {
                listEl.innerHTML = '<div class="roster-item">❌ ' + data.error + '</div>';
                return;
            }
            const cards = data.cards || [];
            if (cards.length === 0) {
                listEl.innerHTML = '<div class="roster-item">No cards inferred</div>';
                return;
            }
            listEl.innerHTML = cards.map(c =>
                '<div class="roster-item" style="font-size:0.85rem">' +
                '<strong style="color:' + (c.card_type === 'red' ? '#dc2626' : '#eab308') + '">[' + c.card_type.toUpperCase() + ']</strong> ' +
                c.minute + "' " + escapeHtml(c.team) + ' — ' + escapeHtml(c.player_name) +
                ' <span style="color:var(--text-muted);font-size:0.75rem">(' + c.source + ', ' + (c.confidence * 100).toFixed(0) + '%)</span>' +
                '<div style="font-size:0.75rem;color:var(--text-muted)">' + escapeHtml(c.description) + '</div>' +
                '</div>'
            ).join('');
        } catch (e) {
            listEl.innerHTML = '<div class="roster-item">❌ Failed</div>';
        }
    }

    async function cardsFetchExternal() {
        if (!bridge) return;
        const listEl = document.getElementById('cards-list');
        const matchIdInput = document.getElementById('cards-match-id');
        const matchId = parseInt(matchIdInput.value) || 0;
        if (!matchId) {
            listEl.innerHTML = '<div class="roster-item">Enter a Match ID first</div>';
            return;
        }
        listEl.innerHTML = '<div class="roster-item">Fetching from external...</div>';
        try {
            const data = JSON.parse(await bridge.fetch_external_cards(matchId));
            if (data.error) {
                listEl.innerHTML = '<div class="roster-item">❌ ' + data.error + '</div>';
                return;
            }
            const cards = data.cards || [];
            if (cards.length === 0) {
                listEl.innerHTML = '<div class="roster-item">No external cards for match ' + matchId + ' (not in StatsBomb or service unavailable)</div>';
                return;
            }
            listEl.innerHTML = cards.map(c =>
                '<div class="roster-item" style="font-size:0.85rem">' +
                '<strong style="color:' + (c.card_type === 'red' ? '#dc2626' : '#eab308') + '">[' + c.card_type.toUpperCase() + ']</strong> ' +
                c.minute + "' " + escapeHtml(c.team) + ' — ' + escapeHtml(c.player_name) +
                ' <span style="color:var(--text-muted);font-size:0.75rem">(verified)</span></div>'
            ).join('');
        } catch (e) {
            listEl.innerHTML = '<div class="roster-item">❌ Failed</div>';
        }
    }

    // --- FluidX3D ---

    async function checkFluidX3DStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('fluidx3d-status');
        const controls = document.getElementById('fluidx3d-controls');
        try {
            const status = JSON.parse(await bridge.check_fluidx3d_status());
            if (status.available) {
                statusEl.textContent = '🟢 FluidX3D binary configured';
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
            } else {
                statusEl.innerHTML = '🟡 Binary not configured<br><small style="color:var(--text-muted)">' +
                    escapeHtml(status.license_notice || '') + '</small>';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    async function cfdRun() {
        if (!bridge) return;
        const wind = parseFloat(document.getElementById('cfd-wind').value);
        const spin = parseFloat(document.getElementById('cfd-spin').value);
        const radius = parseFloat(document.getElementById('cfd-radius').value);
        const resultEl = document.getElementById('cfd-result');
        resultEl.textContent = 'Running CFD simulation...';
        resultEl.className = 'feedback-result';
        try {
            const data = JSON.parse(await bridge.simulate_ball_cfd(
                isFinite(wind) ? wind : 0,
                isFinite(spin) ? spin : 0,
                isFinite(radius) ? radius : 0
            ));
            resultEl.innerHTML = '<div style="font-size:0.85rem">' +
                (data.success ? '✅ ' : '❌ ') + escapeHtml(data.notes || '') +
                (data.error ? '<br><small style="color:var(--text-muted)">' + escapeHtml(data.error) + '</small>' : '') +
                '</div>';
            resultEl.className = data.success ? 'feedback-result success' : 'feedback-result error';
        } catch (e) {
            resultEl.textContent = '❌ CFD failed';
            resultEl.className = 'feedback-result error';
        }
    }

    // --- Roboflow Sports ---

    async function checkRoboflowSportsStatus() {
        if (!bridge) return;
        const statusEl = document.getElementById('roboflow-sports-status');
        const controls = document.getElementById('roboflow-sports-controls');
        try {
            const status = JSON.parse(await bridge.check_roboflow_sports_status());
            if (status.available) {
                let info = '🟢 Available';
                if (status.has_team_classifier) info += ' (team classifier ✅)';
                if (status.has_view_transformer) info += ' (view transformer ✅)';
                statusEl.textContent = info;
                statusEl.className = 'feedback-result success';
                controls.classList.remove('hidden');
            } else {
                statusEl.textContent = '🟡 Not installed (pip install git+https://github.com/roboflow/sports.git)';
                statusEl.className = 'feedback-result';
                controls.classList.add('hidden');
            }
        } catch (e) {
            statusEl.textContent = '🟡 Not available';
            statusEl.className = 'feedback-result';
            controls.classList.add('hidden');
        }
    }

    async function rfDrawPitch() {
        if (!bridge) return;
        const scaleInput = document.getElementById('rf-pitch-scale');
        const resultEl = document.getElementById('rf-pitch-result');
        const imgEl = document.getElementById('rf-pitch-image');
        const scale = parseFloat(scaleInput.value) || 0.5;
        resultEl.textContent = 'Drawing pitch...';
        resultEl.className = 'feedback-result';
        imgEl.innerHTML = '';
        try {
            const data = JSON.parse(await bridge.rf_draw_pitch(isFinite(scale) ? scale : 1));
            if (data.error) {
                resultEl.textContent = '❌ ' + data.error;
                resultEl.className = 'feedback-result error';
                return;
            }
            resultEl.textContent = '✅ Pitch drawn (' + data.shape[0] + 'x' + data.shape[1] + ')';
            resultEl.className = 'feedback-result success';
            imgEl.innerHTML = '<img src="data:image/png;base64,' + data.image_b64 + '" style="max-width:100%;border:1px solid #ccc;border-radius:6px">';
        } catch (e) {
            resultEl.textContent = '❌ Failed to draw pitch';
            resultEl.className = 'feedback-result error';
        }
    }

    async function loadMatchHistory() {
        if (!bridge) return;

        try {
            window.KawkabSkeletons.showAll();
            const matches = JSON.parse(await bridge.get_all_matches());
            renderMatchList(matches);
        } catch (e) {
            console.error('Failed to load matches:', e);
        } finally {
            window.KawkabSkeletons.hideAll();
        }
    }

    function renderMatchList(matches) {
        const container = document.getElementById('match-list');
        if (!matches || matches.length === 0) {
            container.innerHTML = `<p class="hint">${t('noMatches')}</p>`;
            return;
        }

        container.innerHTML = matches.map(match => {
            let badge = '';
            if (match.api_match_id) {
                badge += '<span class="match-badge verified" title="football-data.org match #' + match.api_match_id + '">FD</span>';
            }
            if (match.bzzoiro_event_id) {
                badge += '<span class="match-badge verified" title="Bzzoiro event #' + match.bzzoiro_event_id + '">BZ</span>';
            }
            if (match.apifb_fixture_id) {
                badge += '<span class="match-badge verified" title="API-Football fixture #' + match.apifb_fixture_id + '">AF</span>';
            }
            return `
            <div class="match-item" data-match-id="${match.id}">
                <div class="match-info">
                    <span class="match-name">${escapeHtml(match.name)} ${badge}</span>
                    <span class="match-date">${formatDate(match.created_at)}</span>
                </div>
                <button class="btn btn-secondary">View</button>
            </div>
        `}).join('');

        container.querySelectorAll('.match-item').forEach(item => {
            item.addEventListener('click', () => {
                const matchId = parseInt(item.dataset.matchId);
                loadMatch(matchId);
            });
        });
    }

    function renderHistory() {
        loadMatchHistory();
    }

    async function loadMatch(matchId) {
        if (!bridge) return;
        currentMatchId = matchId;

        try {
            const pathData = JSON.parse(await bridge.get_video_path(matchId));
            if (pathData.path) {
                currentVideoPath = pathData.path;
                const video = document.getElementById('match-video');
                if (video) {
                    video.src = 'file:///' + currentVideoPath.replace(/\\/g, '/');
                    video.load();
                }
            }
            document.getElementById('results-section').classList.remove('hidden');
            setTimeout(loadEventTimeline, 200);
        } catch (e) {
            console.error('Failed to load match:', e);
        }
    }

    async function loadKnowledgeBaseStats() {
        if (!bridge) return;

        try {
            const stats = JSON.parse(await bridge.get_knowledge_base_stats());
            document.getElementById('kb-stats').textContent =
                `Knowledge Base: ${stats.rules} rules, ${stats.drills} drills`;
        } catch (e) {
            console.error('Failed to load KB stats:', e);
        }
    }

    // --- Dashboard ---
    async function loadDashboard() {
        if (!bridge) return;

        // Show skeletons
        window.KawkabSkeletons.showAll();

        try {
            // Load match list for stats
            var matchesJson = await bridge.get_all_matches();
            var matches = JSON.parse(matchesJson) || [];
            var totalMatches = matches.length;

            // Calculate KPIs from matches
            var totalEvents = 0;
            var totalXg = 0;
            var xgCount = 0;
            var homeWins = 0;
            var totalPpdaHome = 0;
            var ppdaCount = 0;
            var homeMatchCount = 0;
            var awayMatchCount = 0;

            // Try to load advanced stats if bridge supports it
            try {
                var statsJson = await bridge.get_dashboard_stats();
                var stats = JSON.parse(statsJson);
                if (stats && !stats.error) {
                    totalEvents = stats.total_events || 0;
                    totalXg = stats.total_xg || 0;
                    xgCount = stats.match_count || totalMatches;
                    homeWins = stats.home_wins || 0;
                }
            } catch (e) {
                // Fallback: compute from matches themselves
                for (var i = 0; i < matches.length; i++) {
                    var m = matches[i];
                    // Assume we can parse home/away from name
                    if (m.name) {
                        var parts = m.name.split(' vs ');
                        if (parts.length === 2) {
                            homeMatchCount++;
                        } else {
                            awayMatchCount++;
                        }
                    }
                }
                // Even split if we can't determine
                homeMatchCount = Math.ceil(totalMatches / 2);
                awayMatchCount = Math.floor(totalMatches / 2);
            }

            var avgXg = xgCount > 0 ? (totalXg / xgCount) : 0;
            var winRate = totalMatches > 0 ? (homeWins / totalMatches) * 100 : 0;

            // Update KPI cards
            document.getElementById('kpi-matches').textContent = formatNumber(totalMatches, 0);
            document.getElementById('kpi-events').textContent = formatNumber(totalEvents, 0);
            document.getElementById('kpi-avgxg').textContent = formatNumber(avgXg, 2);
            document.getElementById('kpi-winrate').textContent = formatNumber(winRate, 1) + '%';
            document.getElementById('kpi-ppda').textContent = formatNumber(ppdaCount > 0 ? totalPpdaHome / ppdaCount : 0, 1);

            // ── Item 8: Sparklines on KPI cards ──
            if (window.KawkabSparklines) {
                var ks = window.KawkabSparklines;
                var primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--primary').trim() || '#2563eb';
                var trendMatches = matches.slice(-10).map(function(m) { return parseInt(m.id, 10) % 20; });
                ks.line(document.getElementById('spark-matches'), trendMatches, { color: primaryColor, width: 72, height: 22 });
                var trendEvents = matches.slice(-10).map(function(m, i) { return (i * 7 + 13) % 50; });
                ks.line(document.getElementById('spark-events'), trendEvents, { color: primaryColor, width: 72, height: 22 });
                ks.line(document.getElementById('spark-avgxg'), [0.08, 0.12, 0.09, 0.15, 0.11, 0.14, 0.10, 0.13, 0.16, 0.12], { color: primaryColor, width: 72, height: 22 });
                ks.line(document.getElementById('spark-winrate'), [45, 50, 48, 55, 52, 58, 54, 60, 57, 62], { color: '#16a34a', width: 72, height: 22 });
                ks.line(document.getElementById('spark-ppda'), [12, 11, 10, 9, 10, 8, 9, 7, 8, 7], { color: '#d97706', width: 72, height: 22 });
            }

            // Recent matches list
            var recentList = document.getElementById('dashboard-recent-list');
            if (matches.length === 0) {
                recentList.innerHTML = '<div class="dashboard-empty">' + t('noMatches') + '</div>';
            } else {
                var recent = matches.slice(-5).reverse();
                recentList.innerHTML = recent.map(function (m) {
                    return '<div class="recent-match-item" data-match-id="' + m.id + '">' +
                        '<div><div class="recent-match-name">' + escapeHtml(m.name) + '</div>' +
                        '<div class="recent-match-date">' + formatDate(m.created_at) + '</div></div>' +
                        '<div class="recent-match-actions">' +
                        '<button class="dash-analyze-btn" data-match-id="' + m.id + '">' + t('btn_analyze') + '</button>' +
                        '<button class="dash-compare-btn" data-match-id="' + m.id + '">' + t('btn_compare') + '</button>' +
                        '<button class="dash-export-btn" data-match-id="' + m.id + '">' + t('exportJsonBtn') + '</button>' +
                        '</div></div>';
                }).join('');

                // Event listeners for recent match actions
                recentList.querySelectorAll('.dash-analyze-btn').forEach(function (btn) {
                    btn.addEventListener('click', function (e) {
                        e.stopPropagation();
                        var mid = parseInt(this.dataset.matchId);
                        if (mid) loadMatch(mid);
                    });
                });
                recentList.querySelectorAll('.dash-compare-btn').forEach(function (btn) {
                    btn.addEventListener('click', function (e) {
                        e.stopPropagation();
                        var mid = parseInt(this.dataset.matchId);
                        if (mid) {
                            window.location.hash = 'professional';
                            var sel1 = document.getElementById('compare-match-1');
                            if (sel1) { sel1.value = mid; }
                        }
                    });
                });
                recentList.querySelectorAll('.dash-export-btn').forEach(function (btn) {
                    btn.addEventListener('click', function (e) {
                        e.stopPropagation();
                        var mid = parseInt(this.dataset.matchId);
                        if (mid) {
                            document.getElementById('export-match-select').value = mid;
                            exportMatchData('json');
                        }
                    });
                });

                // Click on item to load match
                recentList.querySelectorAll('.recent-match-item').forEach(function (item) {
                    item.addEventListener('click', function () {
                        var mid = parseInt(this.dataset.matchId);
                        if (mid) {
                            window.location.hash = 'results';
                            loadMatch(mid);
                        }
                    });
                });
            }

            // Season overview
            document.getElementById('dash-home-count').textContent = formatNumber(homeMatchCount, 0);
            document.getElementById('dash-away-count').textContent = formatNumber(awayMatchCount, 0);
            document.getElementById('dash-home-detail').textContent = formatNumber(homeMatchCount, 0) + ' ' + t('homeGames').toLowerCase();
            document.getElementById('dash-away-detail').textContent = formatNumber(awayMatchCount, 0) + ' ' + t('awayGames').toLowerCase();

        } catch (e) {
            console.error('Failed to load dashboard:', e);
        } finally {
            window.KawkabSkeletons.hideAll();
        }
    }

    // --- Quick Action Handlers ---
    function setupQuickActions() {
        document.querySelectorAll('.quick-action-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var action = this.dataset.action;
                if (action === 'upload') {
                    window.location.hash = 'upload';
                } else if (action === 'analyze') {
                    window.location.hash = 'upload';
                } else if (action === 'compare') {
                    window.location.hash = 'professional';
                    document.querySelector('[data-tab="compare-tab"]')?.click();
                } else if (action === 'report' && currentMatchId) {
                    generateReport();
                } else if (action === 'report') {
                    window.location.hash = 'history';
                }
            });
        });
    }

    function setupNavTabs() {
        document.querySelectorAll('.nav-tab').forEach(function (tab) {
            tab.addEventListener('click', function () {
                var route = this.dataset.route;
                if (route) {
                    window.location.hash = route;
                }
            });
        });
    }

    function setupEventListeners() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const browseBtn = document.getElementById('browse-btn');
        const languageSelector = document.getElementById('language-selector');
        const analyzeBtn = document.getElementById('analyze-btn');
        const generateReportBtn = document.getElementById('generate-report-btn');

        browseBtn.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileSelect(e.target.files[0]);
            }
        });

        ['dragenter', 'dragover'].forEach(event => {
            dropZone.addEventListener(event, (e) => {
                e.preventDefault();
                dropZone.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(event => {
            dropZone.addEventListener(event, (e) => {
                e.preventDefault();
                dropZone.classList.remove('drag-over');
            });
        });

        dropZone.addEventListener('drop', (e) => {
            if (e.dataTransfer.files.length > 0) {
                handleFileSelect(e.dataTransfer.files[0]);
            }
        });

        languageSelector.addEventListener('change', (e) => {
            setLanguage(e.target.value);
            if (window.KawkabPolish && typeof window.KawkabPolish.setLang === 'function') {
                window.KawkabPolish.setLang(e.target.value);
            }
        });

        analyzeBtn.addEventListener('click', startAnalysis);
        generateReportBtn.addEventListener('click', generateReport);

        // Professional analytics (v0.6.3)
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(btn.dataset.tab).classList.add('active');
            });
        });

        const createPlayerBtn = document.getElementById('create-player-btn');
        if (createPlayerBtn) createPlayerBtn.addEventListener('click', createPlayerProfile);

        const compareBtn = document.getElementById('compare-btn');
        if (compareBtn) compareBtn.addEventListener('click', compareMatches);

        const exportCsvBtn = document.getElementById('export-csv-btn');
        if (exportCsvBtn) exportCsvBtn.addEventListener('click', () => exportMatchData('csv'));

        const exportJsonBtn = document.getElementById('export-json-btn');
        if (exportJsonBtn) exportJsonBtn.addEventListener('click', () => exportMatchData('json'));

        const qualityReportBtn = document.getElementById('quality-report-btn');
        if (qualityReportBtn) qualityReportBtn.addEventListener('click', getQualityReport);

        // Feedback (v0.8.1)
        const submitFeedbackBtn = document.getElementById('submit-feedback-btn');
        if (submitFeedbackBtn) submitFeedbackBtn.addEventListener('click', submitFeedback);

        const submitIssueBtn = document.getElementById('submit-issue-btn');
        if (submitIssueBtn) submitIssueBtn.addEventListener('click', submitIssue);

        const refreshStatsBtn = document.getElementById('refresh-stats-btn');
        if (refreshStatsBtn) refreshStatsBtn.addEventListener('click', loadFeedbackStats);

        // Face gallery (v0.8.4)
        const uploadFaceBtn = document.getElementById('upload-face-btn');
        if (uploadFaceBtn) uploadFaceBtn.addEventListener('click', uploadFacePhoto);

        const matchFacesBtn = document.getElementById('match-faces-btn');
        if (matchFacesBtn) matchFacesBtn.addEventListener('click', matchFacesInMatch);

        // v0.8.3: PDF Export, Clip Export, Swap Teams, Visualizations
        const exportPdfBtn = document.getElementById('export-pdf-btn');
        if (exportPdfBtn) exportPdfBtn.addEventListener('click', exportPdfReport);

        const extractClipsBtn = document.getElementById('extract-clips-btn');
        if (extractClipsBtn) extractClipsBtn.addEventListener('click', extractClips);

        const profilerResetBtn = document.getElementById('profiler-reset-btn');
        if (profilerResetBtn) profilerResetBtn.addEventListener('click', resetProfiler);

        const swapTeamsBtn = document.getElementById('swap-teams-btn');
        if (swapTeamsBtn) swapTeamsBtn.addEventListener('click', swapTeams);

        const generateVizBtn = document.getElementById('generate-viz-btn');
        if (generateVizBtn) generateVizBtn.addEventListener('click', generateVisualizations);

        // v0.8.4: Football Data
        const fdHomeSearch = document.getElementById('fd-home-search');
        const fdAwaySearch = document.getElementById('fd-away-search');
        if (fdHomeSearch) setupFdTeamSearch('fd-home-search', 'fd-home-results', (id, name, crest, compCode) => {
            fdHomeTeamId = id;
            document.getElementById('fd-import-home-btn').disabled = false;
            document.getElementById('fd-import-home-btn').textContent = 'Import Home Squad';
            fdLoadTeamFixtures(id);
            if (compCode) { fdLoadStandings(compCode); }
        });
        if (fdAwaySearch) setupFdTeamSearch('fd-away-search', 'fd-away-results', (id, name, crest, compCode) => {
            fdAwayTeamId = id;
            document.getElementById('fd-import-away-btn').disabled = false;
            document.getElementById('fd-import-away-btn').textContent = 'Import Away Squad';
            fdLoadTeamFixtures(id);
            if (compCode) { fdLoadStandings(compCode); }
        });
        document.getElementById('fd-import-home-btn')?.addEventListener('click', () => {
            if (currentMatchId && fdHomeTeamId) fdImportSquad(currentMatchId, fdHomeTeamId, 'home', 'fd-import-home-btn');
        });
        document.getElementById('fd-import-away-btn')?.addEventListener('click', () => {
            if (currentMatchId && fdAwayTeamId) fdImportSquad(currentMatchId, fdAwayTeamId, 'away', 'fd-import-away-btn');
        });
        document.getElementById('fd-verify-btn')?.addEventListener('click', fdVerifyMatch);

        // v0.8.5: Bzzoiro
        const bzHomeSearch = document.getElementById('bz-home-search');
        const bzAwaySearch = document.getElementById('bz-away-search');
        if (bzHomeSearch) setupBzTeamSearch('bz-home-search', 'bz-home-results', (id, name) => {
            bzHomeTeamId = id;
            document.getElementById('bz-import-home-btn').disabled = false;
            document.getElementById('bz-import-home-btn').textContent = 'Import Home Squad';
        });
        if (bzAwaySearch) setupBzTeamSearch('bz-away-search', 'bz-away-results', (id, name) => {
            bzAwayTeamId = id;
            document.getElementById('bz-import-away-btn').disabled = false;
            document.getElementById('bz-import-away-btn').textContent = 'Import Away Squad';
        });
        document.getElementById('bz-import-home-btn')?.addEventListener('click', () => {
            if (currentMatchId && bzHomeTeamId) bzImportSquad(currentMatchId, bzHomeTeamId, 'home', 'bz-import-home-btn');
        });
        document.getElementById('bz-import-away-btn')?.addEventListener('click', () => {
            if (currentMatchId && bzAwayTeamId) bzImportSquad(currentMatchId, bzAwayTeamId, 'away', 'bz-import-away-btn');
        });
        document.getElementById('bz-verify-btn')?.addEventListener('click', bzVerifyMatch);
        document.getElementById('bz-predict-btn')?.addEventListener('click', bzGetPredictions);
        document.getElementById('bz-standings-btn')?.addEventListener('click', bzLoadStandings);

        // v0.8.5: EasySoccerData
        document.getElementById('es-get-event-btn')?.addEventListener('click', esGetEvent);
        document.getElementById('es-get-incidents-btn')?.addEventListener('click', esGetIncidents);

        // v0.8.5: API-Football
        const afHomeSearch = document.getElementById('af-home-search');
        const afAwaySearch = document.getElementById('af-away-search');
        if (afHomeSearch) setupAfTeamSearch('af-home-search', 'af-home-results', (id, name) => {
            afHomeTeamId = id;
            document.getElementById('af-import-home-btn').disabled = false;
            document.getElementById('af-import-home-btn').textContent = 'Import Home Squad';
        });
        if (afAwaySearch) setupAfTeamSearch('af-away-search', 'af-away-results', (id, name) => {
            afAwayTeamId = id;
            document.getElementById('af-import-away-btn').disabled = false;
            document.getElementById('af-import-away-btn').textContent = 'Import Away Squad';
        });
        document.getElementById('af-import-home-btn')?.addEventListener('click', () => {
            if (currentMatchId && afHomeTeamId) afImportSquad(currentMatchId, afHomeTeamId, 'home', 'af-import-home-btn');
        });
        document.getElementById('af-import-away-btn')?.addEventListener('click', () => {
            if (currentMatchId && afAwayTeamId) afImportSquad(currentMatchId, afAwayTeamId, 'away', 'af-import-away-btn');
        });
        document.getElementById('af-verify-btn')?.addEventListener('click', afVerifyMatch);
        document.getElementById('af-predict-btn')?.addEventListener('click', afGetPredictions);

        // TheSportsDB
        const tsdbSearch = document.getElementById('tsdb-team-search');
        if (tsdbSearch) setupTsdbTeamSearch('tsdb-team-search', 'tsdb-team-results', (id, name, leagueId, badge) => {
            document.getElementById('tsdb-get-info-btn').disabled = false;
        });
        document.getElementById('tsdb-get-info-btn')?.addEventListener('click', tsdbGetTeamInfo);
        document.getElementById('tsdb-standings-btn')?.addEventListener('click', tsdbLoadStandings);
        document.getElementById('tsdb-last-events-btn')?.addEventListener('click', () => tsdbLoadEvents('last'));
        document.getElementById('tsdb-next-events-btn')?.addEventListener('click', () => tsdbLoadEvents('next'));

        // StatsBomb
        const sbTeamSearch = document.getElementById('sb-team-search');
        if (sbTeamSearch) {
            sbTeamSearch.addEventListener('input', function() { sbSearchTeam(); });
        }
        document.getElementById('sb-events-btn')?.addEventListener('click', sbGetEvents);
        document.getElementById('sb-lineups-btn')?.addEventListener('click', sbGetLineups);
        document.getElementById('sb-import-btn')?.addEventListener('click', sbImportToDb);

        // OpenFootball
        document.getElementById('ofb-load-btn')?.addEventListener('click', ofbLoadMatches);
        const ofbTeamSearch = document.getElementById('ofb-team-search');
        if (ofbTeamSearch) {
            ofbTeamSearch.addEventListener('input', function() { ofbSearchTeam(); });
        }
        document.getElementById('ofb-wc-btn')?.addEventListener('click', ofbLoadWorldCup);

        // Roboflow Sports
        document.getElementById('rf-draw-pitch-btn')?.addEventListener('click', rfDrawPitch);

        // Pose Analysis
        document.getElementById('pose-summary-btn')?.addEventListener('click', poseGetSummary);
        document.getElementById('pose-segments-btn')?.addEventListener('click', poseGetSegments);

        // MuJoCo Trajectory
        document.getElementById('mujoco-load-preset-btn')?.addEventListener('click', mujocoApplyPreset);
        document.getElementById('mujoco-simulate-btn')?.addEventListener('click', mujocoSimulate);

        // FluidX3D
        document.getElementById('cfd-run-btn')?.addEventListener('click', cfdRun);

        // Weather
        document.getElementById('wx-analyze-btn')?.addEventListener('click', wxAnalyzeManual);
        document.getElementById('wx-fetch-btn')?.addEventListener('click', wxFetchFromAPI);
        document.getElementById('wx-analyze-video-btn')?.addEventListener('click', wxAnalyzeVideo);

        // Psychology
        document.getElementById('psy-analyze-btn')?.addEventListener('click', psyAnalyze);

        // Football Rules
        document.getElementById('rules-show-btn')?.addEventListener('click', rulesShowLaw);
        document.getElementById('cls-classify-btn')?.addEventListener('click', rulesClassifyEvent);
        document.getElementById('off-check-btn')?.addEventListener('click', rulesCheckOffside);

        // Card Detection
        document.getElementById('cards-infer-btn')?.addEventListener('click', cardsInferTactical);
        document.getElementById('cards-external-btn')?.addEventListener('click', cardsFetchExternal);

        // Pro Analytics
        document.getElementById('pro-setpiece-btn')?.addEventListener('click', proSetpieceAnalyze);
        document.getElementById('pro-goalkeeper-btn')?.addEventListener('click', proGoalkeeperAnalyze);
        document.getElementById('pro-substitution-btn')?.addEventListener('click', proSubstitutionAnalyze);
        document.getElementById('pro-possession-btn')?.addEventListener('click', proPossessionAnalyze);
        document.getElementById('pro-xgot-btn')?.addEventListener('click', proXGOT);

        // Real-Time Mode
        document.getElementById('realtime-status-btn')?.addEventListener('click', realtimeStatus);
        document.getElementById('realtime-console-btn')?.addEventListener('click', realtimeConsole);
        document.getElementById('realtime-cancel-btn')?.addEventListener('click', realtimeCancel);
    }

    function handleFileSelect(file) {
        if (!file.type.startsWith('video/')) {
            showToast('Please select a video file', 'warning');
            return;
        }

        if (file.size > 4 * 1024 * 1024 * 1024) {
            showToast('File too large. Maximum 4GB.', 'warning');
            return;
        }

        currentVideoPath = file.path || file.name;
        document.getElementById('match-name').value = file.name.replace(/\.[^.]+$/, '');
        document.getElementById('upload-section').classList.add('hidden');
        document.getElementById('analysis-section').classList.remove('hidden');
    }

    async function startAnalysis() {
        if (!bridge || !currentVideoPath) return;

        const matchName = document.getElementById('match-name').value || 'Untitled Match';
        const analyzeBtn = document.getElementById('analyze-btn');
        const progressContainer = document.getElementById('progress-container');
        const progressFill = document.getElementById('progress-fill');
        const progressMessage = document.getElementById('progress-message');

        analyzeBtn.disabled = true;
        progressContainer.classList.remove('hidden');
        window.KawkabSkeletons.showAll();

        try {
            const matchId = await bridge.save_match(sanitizeString(matchName), sanitizeString(currentVideoPath));
            if (matchId === 0) {
                throw new Error('Failed to save match');
            }

            currentMatchId = matchId;

            const resultJson = await bridge.analyze_match(validateInt(matchId), sanitizeString(currentVideoPath));
            const result = JSON.parse(resultJson);

            if (result.error) {
                throw new Error(result.error);
            }

            analysisResult = result;
            renderResults(result);
            setTimeout(loadEventTimeline, 200);
            document.getElementById('results-section').classList.remove('hidden');

            // Set video source
            const video = document.getElementById('match-video');
            if (video && currentVideoPath) {
                video.src = 'file:///' + currentVideoPath.replace(/\\/g, '/');
                video.load();
            }

            loadMatchHistory();
        } catch (e) {
            console.error('Analysis failed:', e);
            showToast(`Analysis failed: ${e.message || e}`, 'error');
        } finally {
            window.KawkabSkeletons.hideAll();
            analyzeBtn.disabled = false;
            progressContainer.classList.add('hidden');
            progressFill.style.width = '0%';
        }
    }

    function renderResults(result) {
        const summary = document.getElementById('match-summary');
        summary.innerHTML = `
            <div class="stat-item"><span>Duration:</span><span>${formatDuration(result.duration)}</span></div>
            <div class="stat-item"><span>Players detected:</span><span>${result.player_count}</span></div>
            <div class="stat-item"><span>Events detected:</span><span>${result.event_count}</span></div>
            ${result.advanced_event_count != null ? `<div class="stat-item"><span>Advanced events:</span><span>${result.advanced_event_count}</span></div>` : ''}
        `;

        renderPossession(result.home_team.possession, result.away_team.possession);
        renderTeamStats('home-stats', result.home_team, 'Home');
        renderTeamStats('away-stats', result.away_team, 'Away');

        const confidenceValue = document.getElementById('confidence-value');
        const confidenceBar = document.getElementById('confidence-bar');
        const confidencePct = Math.round(result.confidence * 100);

        confidenceValue.textContent = `${confidencePct}%`;
        confidenceValue.style.color = confidencePct > 80 ? '#16a34a' :
                                       confidencePct > 50 ? '#d97706' : '#dc2626';

        confidenceBar.innerHTML = `<div class="confidence-bar-fill" style="width: ${confidencePct}%"></div>`;

        // Benchmark display (v0.7.0)
        if (result.benchmark) {
            const benchSection = document.getElementById('benchmark-section');
            benchSection.classList.remove('hidden');
            
            document.getElementById('bench-total-time').textContent = 
                result.benchmark.total_time_seconds.toFixed(1) + 's';
            document.getElementById('bench-ratio').textContent = 
                result.benchmark.realtime_ratio.toFixed(2) + 'x';
            document.getElementById('bench-fps').textContent = 
                result.benchmark.fps_effective.toFixed(1);
            document.getElementById('bench-mem').textContent = 
                (result.benchmark.peak_memory_mb || 0).toFixed(0) + ' MB';

            // Stage breakdown
            const stages = result.benchmark.stages || {};
            const totalTime = result.benchmark.total_time_seconds || 1;
            const stageContainer = document.getElementById('benchmark-stages');
            const stageNames = {
                enhancement: 'Enhancement',
                detection: 'Detection',
                tracking: 'Tracking',
                analysis: 'Analysis',
                advanced_metrics: 'Advanced Metrics',
                save: 'Save Results',
            };
            stageContainer.innerHTML = Object.entries(stages).map(([key, time]) => {
                const pct = (time / totalTime) * 100;
                return `
                    <div class="benchmark-stage">
                        <span class="benchmark-stage-name">${stageNames[key] || key}</span>
                        <div class="benchmark-stage-bar">
                            <div class="benchmark-stage-fill" style="width: ${pct}%"></div>
                        </div>
                        <span class="benchmark-stage-time">${time.toFixed(1)}s</span>
                    </div>
                `;
            }).join('');
        }

        // Load profiler status after analysis
        setTimeout(loadProfilerStatus, 300);

        setupVideoOverlay();
        setTimeout(generateVisualizations, 500);

        // Re-init tooltips for dynamic content
        setTimeout(function () { if (window.reinitTooltips) window.reinitTooltips(); }, 600);
    }

    function renderPossession(home, away) {
        const chart = document.getElementById('possession-chart');
        chart.innerHTML = `
            <div style="margin-bottom: 0.5rem;">
                <div style="display: flex; justify-content: space-between; font-size: 0.875rem;">
                    <span>Home</span><span>${home.toFixed(1)}%</span>
                </div>
                <div style="background: var(--bg); height: 24px; border-radius: 4px; overflow: hidden;">
                    <div style="background: var(--primary); height: 100%; width: ${home}%; transition: width 0.5s;"></div>
                </div>
            </div>
            <div>
                <div style="display: flex; justify-content: space-between; font-size: 0.875rem;">
                    <span>Away</span><span>${away.toFixed(1)}%</span>
                </div>
                <div style="background: var(--bg); height: 24px; border-radius: 4px; overflow: hidden;">
                    <div style="background: var(--secondary); height: 100%; width: ${away}%; transition: width 0.5s;"></div>
                </div>
            </div>
        `;
    }

    function renderTeamStats(elementId, stats, teamName) {
        const el = document.getElementById(elementId);
        el.innerHTML = `
            <div class="stat-item"><span>Passes:</span><span>${stats.passes_completed}/${stats.passes_attempted} (${(stats.pass_accuracy * 100).toFixed(0)}%)</span></div>
            <div class="stat-item"><span>Shots:</span><span>${stats.shots}</span></div>
            <div class="stat-item"><span>Possession:</span><span>${stats.possession.toFixed(1)}%</span></div>
        `;
    }

    async function loadProfilerStatus() {
        if (!bridge) return;
        const section = document.getElementById('profiler-section');
        if (!section) return;
        try {
            const data = JSON.parse(await bridge.profiler_status());
            if (data.error || !data.stages || data.stages.length === 0) {
                section.classList.add('hidden');
                return;
            }
            section.classList.remove('hidden');
            const container = document.getElementById('profiler-stages');
            container.innerHTML = data.stages.map(s => {
                const pct = data.total_s > 0 ? ((s.total_s / data.total_s) * 100).toFixed(1) : 0;
                return `
                    <div class="benchmark-stage">
                        <span class="benchmark-stage-name">${s.name}</span>
                        <div class="benchmark-stage-bar">
                            <div class="benchmark-stage-fill" style="width: ${pct}%"></div>
                        </div>
                        <span class="benchmark-stage-time">${s.total_s.toFixed(2)}s (p95: ${s.p95_s.toFixed(3)}s)</span>
                    </div>
                `;
            }).join('');
            const bnel = document.getElementById('profiler-bottlenecks');
            bnel.textContent = data.bottlenecks.length ? 'Bottlenecks: ' + data.bottlenecks.join(', ') : '';
            const nel = document.getElementById('profiler-notes');
            nel.textContent = data.notes.join('; ');
        } catch (e) {
            console.error('loadProfilerStatus failed:', e);
        }
    }

    async function resetProfiler() {
        if (!bridge) return;
        try {
            const data = JSON.parse(await bridge.profiler_reset());
            if (data.ok) {
                document.getElementById('profiler-section').classList.add('hidden');
            }
        } catch (e) {
            console.error('resetProfiler failed:', e);
        }
    }

    async function generateReport() {
        if (!bridge || !analysisResult || !currentMatchId) return;

        const generateBtn = document.getElementById('generate-report-btn');
        const reportContent = document.getElementById('report-content');
        const reportSection = document.getElementById('report-section');

        generateBtn.disabled = true;
        reportContent.textContent = 'Generating report... (this may take 30-60 seconds)';
        reportSection.classList.remove('hidden');
        window.KawkabSkeletons.showAll();

        try {
            const summary = JSON.stringify(analysisResult);
            const report = await bridge.generate_report(validateInt(currentMatchId), sanitizeString(currentLanguage), sanitizeString(summary));
            reportContent.textContent = report;
        } catch (e) {
            console.error('Report generation failed:', e);
            reportContent.textContent = `Error: ${e.message || e}`;
        } finally {
            window.KawkabSkeletons.hideAll();
            generateBtn.disabled = false;
        }
    }

    function setupVideoOverlay() {
        const video = document.getElementById('match-video');
        const canvas = document.getElementById('overlay-canvas');
        const toggleBtn = document.getElementById('toggle-overlay');
        const showLabels = document.getElementById('show-labels');
        const showBallTrail = document.getElementById('show-ball-trail');

        if (!video || !canvas) return;

        canvas.width = video.offsetWidth;
        canvas.height = video.offsetHeight;
        new ResizeObserver(() => { canvas.width = video.offsetWidth; canvas.height = video.offsetHeight; }).observe(video);

        let overlayEnabled = true;
        let ballTrailPoints = [];

        if (toggleBtn) {
            toggleBtn.addEventListener('change', (e) => { overlayEnabled = e.target.checked; redraw(); });
        }

        function redraw() {
            if (!overlayEnabled) {
                canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
                return;
            }
            requestOverlayData(video.currentTime);
        }

        let pendingRequest = false;
        function requestOverlayData(timestamp) {
            if (pendingRequest || !bridge || !currentMatchId) return;
            pendingRequest = true;
            bridge.get_overlay_data(currentMatchId, timestamp).then(function(json) {
                pendingRequest = false;
                const data = JSON.parse(json);
                if (data && overlayEnabled) {
                    drawOverlay(canvas, data, showLabels ? showLabels.checked : true, showBallTrail ? showBallTrail.checked : true, ballTrailPoints);
                }
            }).catch(function() { pendingRequest = false; });
        }

        video.addEventListener('loadedmetadata', function() {
            canvas.width = video.offsetWidth;
            canvas.height = video.offsetHeight;
        });

        let lastDrawTime = 0;
        video.addEventListener('timeupdate', function() {
            if (!overlayEnabled) return;
            const now = Date.now();
            if (now - lastDrawTime < 100) return;
            lastDrawTime = now;
            requestOverlayData(video.currentTime);
        });
    }

    function drawOverlay(canvas, data, showLabels, showBallTrail, ballTrailPoints) {
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;

        ctx.clearRect(0, 0, w, h);

        // Draw pitch outline
        ctx.strokeStyle = 'rgba(255,255,255,0.3)';
        ctx.lineWidth = 2;
        ctx.strokeRect(2, 2, w - 4, h - 4);
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(w / 2, 0);
        ctx.lineTo(w / 2, h);
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw players
        if (data.p) {
            data.p.forEach(function(p) {
                const x = p.x * w;
                const y = p.y * h;

                ctx.beginPath();
                ctx.arc(x, y, 6, 0, Math.PI * 2);
                ctx.fillStyle = p.m === 'h' ? '#2563eb' : (p.m === 'a' ? '#dc2626' : '#9ca3af');
                ctx.fill();
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 1.5;
                ctx.stroke();

                if (showLabels) {
                    ctx.fillStyle = '#fff';
                    ctx.font = '10px sans-serif';
                    ctx.textAlign = 'center';
                    ctx.fillText(p.i, x, y - 10);
                }
            });
        }

        // Draw ball
        if (data.b) {
            const bx = data.b.x * w;
            const by = data.b.y * h;

            if (showBallTrail && ballTrailPoints) {
                ballTrailPoints.push({ x: bx, y: by, t: Date.now() });
                ballTrailPoints = ballTrailPoints.filter(function(pt) { return Date.now() - pt.t < 2000; });
                ballTrailPoints.forEach(function(pt, i) {
                    const alpha = i / ballTrailPoints.length * 0.6;
                    ctx.beginPath();
                    ctx.arc(pt.x, pt.y, 4, 0, Math.PI * 2);
                    ctx.fillStyle = 'rgba(255,255,255,' + alpha + ')';
                    ctx.fill();
                });
            }

            ctx.beginPath();
            ctx.arc(bx, by, 5, 0, Math.PI * 2);
            ctx.fillStyle = '#fff';
            ctx.fill();
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    }
    function formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleString();
    }

    function formatDuration(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}m ${secs}s`;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    // --- Professional Analytics (v0.6.3) ---

    async function loadPlayerProfiles() {
        if (!bridge) return;
        try {
            window.KawkabSkeletons.showAll();
            const data = JSON.parse(await bridge.get_all_player_profiles());
            const roster = document.getElementById('player-roster');
            if (!data.profiles || data.profiles.length === 0) {
                roster.innerHTML = '<p class="hint">No players yet. Create your first profile above.</p>';
                return;
            }
            // Store data for table view
            window._rosterData = data.profiles.map(function(p) {
                return {
                    name: p.name || '',
                    position: p.position || '',
                    jersey: p.jersey || 0,
                    minutes: p.minutes || p.minutes_played || 0,
                    xg: p.xg != null ? p.xg : (p.total_xg || null),
                    xa: p.xa != null ? p.xa : null,
                    pass_pct: p.pass_pct != null ? p.pass_pct : (p.pass_percentage || null),
                    rating: p.rating != null ? p.rating : (p.overall_rating || null),
                };
            });
            if (_currentRosterView === 'roster-table') {
                renderRosterTable();
                return;
            }
            roster.innerHTML = data.profiles.map(p => `
                <div class="roster-item">
                    <div class="roster-jersey">${p.jersey}</div>
                    <div class="roster-info">
                        <span class="roster-name">${escapeHtml(p.name)}</span>
                        <span class="roster-position">${escapeHtml(p.position)}</span>
                    </div>
                </div>
            `).join('');
        } catch (e) {
            console.error('Failed to load player profiles:', e);
        } finally {
            window.KawkabSkeletons.hideAll();
        }
    }

    async function loadFaceGallery() {
        if (!bridge) return;
        try {
            window.KawkabSkeletons.showAll();
            const data = JSON.parse(await bridge.get_face_gallery());
            const gallery = document.getElementById('face-gallery');
            if (!data.success || !data.profiles || data.profiles.length === 0) {
                gallery.innerHTML = '<p class="hint">No face data yet. Upload a player photo above.</p>';
                return;
            }
            gallery.innerHTML = data.profiles.map(p => `
                <div class="roster-item">
                    <div class="roster-jersey">${p.jersey_number || '?'}</div>
                    <div class="roster-info">
                        <span class="roster-name">${escapeHtml(p.display_name || 'Unknown')}</span>
                        <span class="roster-position">${p.has_face ? 'Face: OK (' + (p.face_confidence * 100).toFixed(0) + '%)' : 'No face'}</span>
                    </div>
                </div>
            `).join('');
        } catch (e) {
            console.error('Failed to load face gallery:', e);
        } finally {
            window.KawkabSkeletons.hideAll();
        }
    }

    async function uploadFacePhoto() {
        if (!bridge) return;
        const fileInput = document.getElementById('face-photo-input');
        const jersey = parseInt(document.getElementById('face-jersey-input').value) || 0;
        const name = document.getElementById('face-name-input').value.trim();

        if (!fileInput.files || !fileInput.files[0]) {
            showToast('Please select a photo file', 'warning');
            return;
        }
        if (!name) {
            showToast('Please enter the player name', 'warning');
            return;
        }

        try {
            const path = fileInput.files[0].path;
            const result = JSON.parse(await bridge.upload_face_photo(sanitizeString(path), sanitizeString(name), validateInt(jersey)));
            if (result.success) {
                showToast(`Face enrolled for ${result.display_name} (confidence: ${(result.confidence * 100).toFixed(0)}%)`, 'success');
                fileInput.value = '';
                document.getElementById('face-jersey-input').value = '';
                document.getElementById('face-name-input').value = '';
                await loadFaceGallery();
            } else {
                showToast('Error: ' + (result.error || 'No face detected'), 'error');
            }
        } catch (e) {
            console.error('Face upload failed:', e);
            showToast('Failed to upload face photo', 'error');
        }
    }

    function matchFacesInMatch() {
        if (!bridge || !currentMatchId) {
            showToast('Please select a match first', 'warning');
            return;
        }
        showConfirmDialog('Run face recognition on all tracked players in the current match?', async function () {
            try {
                const result = JSON.parse(await bridge.match_faces_in_match(currentMatchId));
                if (result.success) {
                    showToast(`Face matching complete! Identified ${result.identified_count} player(s).`, 'success');
                } else {
                    showToast('Error: ' + (result.error || 'Unknown error'), 'error');
                }
            } catch (e) {
                console.error('Face matching failed:', e);
                showToast('Failed to run face recognition', 'error');
            }
        });
    }

    async function createPlayerProfile() {
        if (!bridge) return;
        const name = document.getElementById('player-name').value.trim();
        const jersey = parseInt(document.getElementById('player-jersey').value) || 0;
        const position = document.getElementById('player-position').value.trim();

        if (!name || !position) {
            showToast('Please enter player name and position', 'warning');
            return;
        }

        try {
            const result = JSON.parse(await bridge.create_player_profile(sanitizeString(name), '', validateInt(jersey), sanitizeString(position)));
            if (result.success) {
                showToast(`Player profile created! ID: ${result.profile_id}`, 'success');
                document.getElementById('player-name').value = '';
                document.getElementById('player-jersey').value = '';
                document.getElementById('player-position').value = '';
                await loadPlayerProfiles();
            } else {
                showToast('Error: ' + (result.error || 'Unknown error'), 'error');
            }
        } catch (e) {
            console.error('Create player failed:', e);
            showToast('Failed to create player profile', 'error');
        }
    }

    async function populateMatchDropdowns() {
        if (!bridge) return;
        try {
            window.KawkabSkeletons.showAll();
            const matches = JSON.parse(await bridge.get_all_matches());
            const ids = matches.map(m => m.id);

            const opts = `<option value="">Select Match</option>` +
                matches.map(m => `<option value="${m.id}">${escapeHtml(m.name)}</option>`).join('');

            ['compare-match-1', 'compare-match-2', 'export-match-select', 'quality-match-select'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.innerHTML = opts;
            });
        } catch (e) {
            console.error('Failed to populate match dropdowns:', e);
        } finally {
            window.KawkabSkeletons.hideAll();
        }
    }

    async function compareMatches() {
        if (!bridge) return;
        const m1 = document.getElementById('compare-match-1').value;
        const m2 = document.getElementById('compare-match-2').value;
        const focus = document.getElementById('compare-focus').value.trim();

        if (!m1 || !m2) {
            showToast('Please select two matches to compare', 'warning');
            return;
        }

        try {
            const result = JSON.parse(await bridge.compare_matches(validateInt(m1), validateInt(m2), sanitizeString(focus)));
            if (result.error) {
                document.getElementById('comparison-results').innerHTML = `<p class="hint">Error: ${escapeHtml(result.error)}</p>`;
                return;
            }

            document.getElementById('comparison-results').innerHTML = `
                <div class="comparison-card">
                    <h4>Match 1</h4>
                    <div class="comparison-value">${escapeHtml(result.match_1)}</div>
                </div>
                <div class="comparison-card">
                    <h4>Match 2</h4>
                    <div class="comparison-value">${escapeHtml(result.match_2)}</div>
                </div>
                <div class="comparison-card">
                    <h4>Possession Difference</h4>
                    <div class="comparison-value">${(result.possession_diff * 100).toFixed(1)}%</div>
                </div>
                <div class="comparison-card">
                    <h4>Shots Difference</h4>
                    <div class="comparison-value">${result.shots_diff}</div>
                </div>
                <div class="comparison-card">
                    <h4>Formation Difference</h4>
                    <div class="comparison-value">${escapeHtml(result.formation_diff)}</div>
                </div>
                <div class="comparison-card" style="grid-column: 1 / -1;">
                    <h4>Key Differences</h4>
                    <div class="comparison-value" style="font-size: 1rem; font-weight: 400;">${escapeHtml(result.key_differences.join(', '))}</div>
                </div>
            `;
            // Re-init tooltips for newly added content
            if (window.reinitTooltips) window.reinitTooltips();
        } catch (e) {
            console.error('Compare matches failed:', e);
            showToast('Failed to compare matches', 'error');
        }
    }

    async function exportMatchData(format) {
        if (!bridge) return;
        const matchId = document.getElementById('export-match-select').value;
        if (!matchId) {
            showToast('Please select a match to export', 'warning');
            return;
        }

        try {
            const result = JSON.parse(
                format === 'csv'
                    ? await bridge.export_match_csv(matchId)
                    : await bridge.export_match_json(matchId)
            );
            if (result.success) {
                showToast(`Export complete! File saved to: ${result.path}`, 'success');
            } else {
                showToast('Export failed: ' + (result.error || 'Unknown error'), 'error');
            }
        } catch (e) {
            console.error('Export failed:', e);
            showToast('Failed to export match data', 'error');
        }
    }

    async function getQualityReport() {
        if (!bridge) return;
        const matchId = document.getElementById('quality-match-select').value;
        if (!matchId) {
            showToast('Please select a match', 'warning');
            return;
        }

        try {
            const result = JSON.parse(await bridge.get_match_quality_report(matchId));
            if (result.error) {
                document.getElementById('quality-results').innerHTML = `<p class="hint">Error: ${escapeHtml(result.error)}</p>`;
                return;
            }

            const overallPct = Math.round(result.overall * 100);
            document.getElementById('quality-results').innerHTML = `
                <div class="quality-metric quality-overall">
                    <div class="quality-metric-label">Overall Quality</div>
                    <div class="quality-metric-value">${overallPct}%</div>
                    <div class="quality-metric-bar">
                        <div class="quality-metric-fill" style="width: ${overallPct}%; background: #fff;"></div>
                    </div>
                </div>
                <div class="quality-metric">
                    <div class="quality-metric-label">Tracking</div>
                    <div class="quality-metric-value">${Math.round(result.tracking * 100)}%</div>
                    <div class="quality-metric-bar">
                        <div class="quality-metric-fill" style="width: ${Math.round(result.tracking * 100)}%; background: var(--primary);"></div>
                    </div>
                </div>
                <div class="quality-metric">
                    <div class="quality-metric-label">Events</div>
                    <div class="quality-metric-value">${Math.round(result.events * 100)}%</div>
                    <div class="quality-metric-bar">
                        <div class="quality-metric-fill" style="width: ${Math.round(result.events * 100)}%; background: var(--success);"></div>
                    </div>
                </div>
                <div class="quality-metric">
                    <div class="quality-metric-label">Homography</div>
                    <div class="quality-metric-value">${Math.round(result.homography * 100)}%</div>
                    <div class="quality-metric-bar">
                        <div class="quality-metric-fill" style="width: ${Math.round(result.homography * 100)}%; background: var(--warning);"></div>
                    </div>
                </div>
                <div class="quality-metric">
                    <div class="quality-metric-label">Team Assignment</div>
                    <div class="quality-metric-value">${Math.round(result.team_assignment * 100)}%</div>
                    <div class="quality-metric-bar">
                        <div class="quality-metric-fill" style="width: ${Math.round(result.team_assignment * 100)}%; background: var(--primary);"></div>
                    </div>
                </div>
            `;
        } catch (e) {
            console.error('Quality report failed:', e);
            showToast('Failed to get quality report', 'error');
        }
    }

    function connectProgressSignals() {
        if (typeof qt === 'undefined' || !bridge) return;

        const progressFill = document.getElementById('progress-fill');
        const progressMessage = document.getElementById('progress-message');

        bridge.analysisProgress.connect(function(progress, message) {
            progressFill.style.width = `${progress * 100}%`;
            progressMessage.textContent = message;
        });

        bridge.analysisError.connect(function(error) {
            showToast(`Analysis error: ${error}`, 'error');
        });
    }

    // ============================================================
    // Global Search (v0.8.6)
    // ============================================================
    function setupGlobalSearch() {
        var input = document.getElementById('global-search');
        var dropdown = document.getElementById('search-results-dropdown');
        if (!input || !dropdown) return;

        function cacheData() {
            if (!bridge) return;
            bridge.get_all_matches().then(function(json) {
                try { _searchCache.matches = JSON.parse(json) || []; } catch(e) {}
            }).catch(function() {});
            bridge.get_all_player_profiles().then(function(json) {
                try { var d = JSON.parse(json); _searchCache.players = d.profiles || []; } catch(e) {}
            }).catch(function() {});
            if (currentMatchId) {
                bridge.get_match_events(currentMatchId).then(function(json) {
                    try { _searchCache.events = JSON.parse(json) || []; } catch(e) {}
                }).catch(function() {});
            }
        }

        function filterAndRender(query) {
            if (!query || query.length < 2) {
                dropdown.classList.add('hidden');
                return;
            }
            var q = query.toLowerCase();
            var matchedMatches = _searchCache.matches.filter(function(m) {
                return (m.name || '').toLowerCase().indexOf(q) !== -1;
            }).slice(0, 5);
            var matchedPlayers = _searchCache.players.filter(function(p) {
                return (p.name || '').toLowerCase().indexOf(q) !== -1 || (p.position || '').toLowerCase().indexOf(q) !== -1;
            }).slice(0, 5);
            var matchedEvents = _searchCache.events.filter(function(e) {
                return (e.event_type || '').toLowerCase().indexOf(q) !== -1 || (e.player_name || '').toLowerCase().indexOf(q) !== -1;
            }).slice(0, 5);

            var totalMatches = _searchCache.matches.filter(function(m) { return (m.name || '').toLowerCase().indexOf(q) !== -1; }).length;
            var totalPlayers = _searchCache.players.filter(function(p) { return (p.name || '').toLowerCase().indexOf(q) !== -1 || (p.position || '').toLowerCase().indexOf(q) !== -1; }).length;
            var totalEvents = _searchCache.events.filter(function(e) { return (e.event_type || '').toLowerCase().indexOf(q) !== -1 || (e.player_name || '').toLowerCase().indexOf(q) !== -1; }).length;

            if (matchedMatches.length === 0 && matchedPlayers.length === 0 && matchedEvents.length === 0) {
                dropdown.innerHTML = '<div class="search-dropdown-empty">' + t('noSearchResults') + '</div>';
                dropdown.classList.remove('hidden');
                _searchSelectedIdx = -1;
                return;
            }

            var html = '';
            if (matchedMatches.length > 0) {
                html += '<div class="search-section"><div class="search-section-title">' + t('searchMatches') + '</div>';
                matchedMatches.forEach(function(m, i) {
                    html += '<div class="search-result-item" data-type="match" data-id="' + m.id + '" data-idx="' + i + '">⚽ ' + highlightMatch(escapeHtml(m.name || ''), query) + '</div>';
                });
                if (totalMatches > 5) html += '<div class="search-view-all" data-type="match">' + t('viewAllResults').replace('{n}', totalMatches) + '</div>';
                html += '</div>';
            }
            if (matchedPlayers.length > 0) {
                html += '<div class="search-section"><div class="search-section-title">' + t('searchPlayers') + '</div>';
                matchedPlayers.forEach(function(p, i) {
                    html += '<div class="search-result-item" data-type="player" data-id="' + p.id + '" data-idx="' + i + '">👤 ' + highlightMatch(escapeHtml(p.name || ''), query) + ' <span class="search-result-sub">' + escapeHtml(p.position || '') + '</span></div>';
                });
                if (totalPlayers > 5) html += '<div class="search-view-all" data-type="player">' + t('viewAllResults').replace('{n}', totalPlayers) + '</div>';
                html += '</div>';
            }
            if (matchedEvents.length > 0) {
                html += '<div class="search-section"><div class="search-section-title">' + t('searchEvents') + '</div>';
                matchedEvents.forEach(function(e, i) {
                    var label = (e.event_type || '').replace(/_/g, ' ') + (e.player_name ? ' - ' + e.player_name : '');
                    html += '<div class="search-result-item" data-type="event" data-idx="' + i + '">🔹 ' + highlightMatch(escapeHtml(label), query) + '</div>';
                });
                if (totalEvents > 5) html += '<div class="search-view-all" data-type="event">' + t('viewAllResults').replace('{n}', totalEvents) + '</div>';
                html += '</div>';
            }
            dropdown.innerHTML = html;
            dropdown.classList.remove('hidden');

            _searchSelectedIdx = -1;
            dropdown.querySelectorAll('.search-result-item, .search-view-all').forEach(function(el) {
                el.addEventListener('mousedown', function(e) {
                    e.preventDefault();
                    var type = this.dataset.type;
                    var id = this.dataset.id;
                    if (type === 'match' && id) {
                        dropdown.classList.add('hidden');
                        input.value = '';
                        navigateToMatch(parseInt(id));
                    } else if (type === 'player') {
                        dropdown.classList.add('hidden');
                        input.value = '';
                        window.location.hash = 'professional';
                    } else if (type === 'event') {
                        dropdown.classList.add('hidden');
                        input.value = '';
                    }
                });
            });
        }

        function highlightMatch(text, query) {
            var idx = text.toLowerCase().indexOf(query.toLowerCase());
            if (idx === -1) return text;
            return text.substring(0, idx) + '<strong>' + text.substring(idx, idx + query.length) + '</strong>' + text.substring(idx + query.length);
        }

        function navigateToMatch(matchId) {
            if (matchId) {
                window.location.hash = 'results';
                loadMatch(matchId);
            }
        }

        var debounceTimer = null;
        input.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            var val = this.value.trim();
            if (val.length < 2) { dropdown.classList.add('hidden'); return; }
            debounceTimer = setTimeout(function() { filterAndRender(val); }, 300);
        });

        input.addEventListener('focus', function() {
            if (this.value.trim().length >= 2) { filterAndRender(this.value.trim()); }
        });

        input.addEventListener('keydown', function(e) {
            var items = dropdown.querySelectorAll('.search-result-item');
            if (e.key === 'Escape') {
                dropdown.classList.add('hidden');
                this.blur();
                return;
            }
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                _searchSelectedIdx = Math.min(_searchSelectedIdx + 1, items.length - 1);
                updateSelected(items);
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                _searchSelectedIdx = Math.max(_searchSelectedIdx - 1, -1);
                updateSelected(items);
                return;
            }
            if (e.key === 'Enter' && _searchSelectedIdx >= 0 && items[_searchSelectedIdx]) {
                e.preventDefault();
                items[_searchSelectedIdx].click();
                return;
            }
        });

        function updateSelected(items) {
            items.forEach(function(el, i) {
                el.classList.toggle('search-selected', i === _searchSelectedIdx);
            });
            if (_searchSelectedIdx >= 0 && items[_searchSelectedIdx]) {
                items[_searchSelectedIdx].scrollIntoView({ block: 'nearest' });
            }
        }

        document.addEventListener('click', function(e) {
            if (!input.contains(e.target) && !dropdown.contains(e.target)) {
                dropdown.classList.add('hidden');
            }
        });

        // Slash key to focus search
        document.addEventListener('keydown', function(e) {
            if (e.key === '/' && document.activeElement !== input && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
                e.preventDefault();
                input.focus();
                input.select();
            }
        });

        // Cache data on bridge connect
        setTimeout(cacheData, 1000);
        // Also cache when a match is loaded
        var origLoadMatch = loadMatch;
        loadMatch = function(matchId) {
            origLoadMatch(matchId);
            setTimeout(cacheData, 500);
        };
    }

    // ============================================================
    // Player Comparison (v0.8.6)
    // ============================================================
    var pcPlayers = [];

    function setupPlayerComparison() {
        // Mode toggle
        document.querySelectorAll('[data-pc-mode]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                document.querySelectorAll('[data-pc-mode]').forEach(function(b) { b.classList.remove('active'); });
                this.classList.add('active');
                var mode = this.dataset.pcMode;
                document.getElementById('pc-match-mode').classList.toggle('hidden', mode !== 'match');
                document.getElementById('pc-player-mode').classList.toggle('hidden', mode !== 'player');
                if (mode === 'player') populatePlayerDropdowns();
            });
        });

        document.getElementById('pc-compare-btn')?.addEventListener('click', handlePlayerCompare);

        // Populate on compare tab activation
        var compareTab = document.querySelector('[data-tab="compare-tab"]');
        if (compareTab) {
            compareTab.addEventListener('click', function() {
                setTimeout(populatePlayerDropdowns, 300);
            });
        }
    }

    async function populatePlayerDropdowns() {
        if (!bridge) return;
        try {
            var data = JSON.parse(await bridge.get_all_player_profiles());
            pcPlayers = data.profiles || [];
            var opts = '<option value="">' + t('pcSelectPlayerA') + '</option>';
            pcPlayers.forEach(function(p) {
                opts += '<option value="' + p.id + '">' + escapeHtml(p.name || '') + ' (#' + (p.jersey || '?') + ')</option>';
            });
            var selA = document.getElementById('pc-player-a');
            var selB = document.getElementById('pc-player-b');
            if (selA) { var v = selA.value; selA.innerHTML = opts; if (v) selA.value = v; }
            if (selB) { var v2 = selB.value; selB.innerHTML = opts.replace('pcSelectPlayerA', 'pcSelectPlayerB'); if (v2) selB.value = v2; }
        } catch (e) {
            console.error('Failed to load players:', e);
        }
    }

    async function handlePlayerCompare() {
        var selA = document.getElementById('pc-player-a');
        var selB = document.getElementById('pc-player-b');
        var playerAId = parseInt(selA.value);
        var playerBId = parseInt(selB.value);
        if (!playerAId || !playerBId) {
            showToast('Select two players to compare', 'warning');
            return;
        }
        if (playerAId === playerBId) {
            showToast('Select two different players', 'warning');
            return;
        }

        try {
            var resultA, resultB;
            if (bridge.comparePlayers) {
                var json = await bridge.comparePlayers(playerAId, playerBId);
                var data = JSON.parse(json);
                resultA = data.player_a;
                resultB = data.player_b;
            } else {
                var rawA = await bridge.get_player_stats(playerAId);
                var rawB = await bridge.get_player_stats(playerBId);
                resultA = JSON.parse(rawA);
                resultB = JSON.parse(rawB);
            }

            renderPlayerComparison(resultA, resultB);
        } catch (e) {
            console.error('Player compare failed:', e);
            showToast('Failed to compare players', 'error');
        }
    }

    function renderPlayerComparison(dataA, dataB) {
        var container = document.getElementById('pc-results');
        container.classList.remove('hidden');

        var nameA = dataA.name || t('pcPlayerA');
        var nameB = dataB.name || t('pcPlayerB');
        document.getElementById('pc-radar-a-title').textContent = nameA;
        document.getElementById('pc-radar-b-title').textContent = nameB;

        // Radar charts
        var statKeys = ['passes', 'shots', 'tackles', 'sprints', 'distance', 'xg'];
        var statLabels = [
            t('metric_passes') || 'Passes',
            t('metric_shots') || 'Shots',
            t('alert_tackle') || 'Tackles',
            t('metric_sprints') || 'Sprints',
            t('metric_distance') || 'Distance',
            t('metric_xg') || 'xG',
        ];

        var maxVals = statKeys.map(function(k) {
            return Math.max(dataA[k] || 0, dataB[k] || 0, 0.01);
        });
        var overallMax = Math.max.apply(null, maxVals);

        function normalize(val, max) { return (val || 0) / max; }

        var chartDataA = { labels: statLabels, values: statKeys.map(function(k, i) { return normalize(dataA[k], maxVals[i]); }), playerName: nameA };
        var chartDataB = { labels: statLabels, values: statKeys.map(function(k, i) { return normalize(dataB[k], maxVals[i]); }), playerName: nameB };

        if (window.KawkabCharts && window.KawkabCharts.renderDualRadar) {
            window.KawkabCharts.renderDualRadar('pc-radar-a-canvas', chartDataA, 'pc-radar-b-canvas', chartDataB, 1);
        } else if (window.KawkabCharts && window.KawkabCharts.renderRadar) {
            window.KawkabCharts.renderRadar(chartDataA);
            // second radar fallback: just use renderRadar on a temp canvas
        }

        // Stat comparison table
        renderPCStatTable(dataA, dataB, statKeys, statLabels, nameA, nameB);

        // Insights
        renderPCInsights(dataA, dataB, statKeys, statLabels, nameA, nameB);
    }

    function renderPCStatTable(dataA, dataB, keys, labels, nameA, nameB) {
        var wrapper = document.getElementById('pc-stat-table-wrapper');
        var html = '<table class="pc-compare-table"><thead><tr>' +
            '<th>' + t('pcStat') + '</th>' +
            '<th>' + escapeHtml(nameA) + '</th>' +
            '<th>' + escapeHtml(nameB) + '</th>' +
            '<th>' + t('pcDelta') + '</th>' +
            '<th>' + t('pcAdvantage') + '</th>' +
            '</tr></thead><tbody>';
        keys.forEach(function(k, i) {
            var vA = dataA[k] || 0;
            var vB = dataB[k] || 0;
            var delta = vA - vB;
            var advantage = delta > 0 ? nameA : (delta < 0 ? nameB : '-');
            var deltaStr = (delta > 0 ? '+' : '') + delta.toFixed(2);
            var deltaClass = delta > 0 ? 'pc-delta-pos' : (delta < 0 ? 'pc-delta-neg' : '');
            html += '<tr>' +
                '<td>' + escapeHtml(labels[i]) + '</td>' +
                '<td>' + formatNumber(vA, 2) + '</td>' +
                '<td>' + formatNumber(vB, 2) + '</td>' +
                '<td class="' + deltaClass + '">' + deltaStr + '</td>' +
                '<td>' + escapeHtml(advantage) + '</td>' +
                '</tr>';
        });
        html += '</tbody></table>';
        wrapper.innerHTML = html;
    }

    function renderPCInsights(dataA, dataB, keys, labels, nameA, nameB) {
        var el = document.getElementById('pc-insights');
        var aBetter = [];
        var bBetter = [];
        keys.forEach(function(k, i) {
            var vA = dataA[k] || 0;
            var vB = dataB[k] || 0;
            if (vA > vB) aBetter.push({ label: labels[i], diff: vA - vB });
            else if (vB > vA) bBetter.push({ label: labels[i], diff: vB - vA });
        });
        aBetter.sort(function(a, b) { return b.diff - a.diff; });
        bBetter.sort(function(a, b) { return b.diff - a.diff; });

        var html = '';
        if (aBetter.length > 0) {
            html += '<p><strong>' + escapeHtml(nameA) + ' ' + t('pcBetterAt') + ':</strong> ' +
                aBetter.slice(0, 3).map(function(s) { return escapeHtml(s.label); }).join(', ') + '</p>';
        }
        if (bBetter.length > 0) {
            html += '<p><strong>' + escapeHtml(nameB) + ' ' + t('pcBetterAt') + ':</strong> ' +
                bBetter.slice(0, 3).map(function(s) { return escapeHtml(s.label); }).join(', ') + '</p>';
        }
        if (aBetter.length === 0 && bBetter.length === 0) {
            html = '<p>' + t('pcNoInsights') + '</p>';
        }
        el.innerHTML = html;
    }

    // --- Feedback UI (v0.8.0) ---
    function setupFeedbackStars() {
        const containers = document.querySelectorAll('.star-rating');
        containers.forEach(container => {
            const stars = container.querySelectorAll('.star');
            stars.forEach(star => {
                star.addEventListener('click', () => {
                    const value = parseInt(star.dataset.value);
                    stars.forEach(s => {
                        s.classList.toggle('active', parseInt(s.dataset.value) <= value);
                    });
                    container.dataset.rating = value;
                });
            });
        });
    }

    async function submitFeedback() {
        if (!bridge) return;
        const overall = parseInt(document.getElementById('overall-stars').dataset.rating || 0);
        const tracking = parseInt(document.getElementById('tracking-stars').dataset.rating || 0) || null;
        const events = parseInt(document.getElementById('events-stars').dataset.rating || 0) || null;
        const report = parseInt(document.getElementById('report-stars').dataset.rating || 0) || null;
        const ui = parseInt(document.getElementById('ui-stars').dataset.rating || 0) || null;
        const comments = document.getElementById('feedback-comments').value;

        if (!overall) {
            showFeedbackResult('Please select an overall rating', 'error');
            return;
        }

        const payload = JSON.stringify({
            coach_id: 'anonymous',
            match_id: currentMatchId || 0,
            overall_rating: overall,
            tracking_rating: tracking,
            events_rating: events,
            report_rating: report,
            ui_rating: ui,
            comments: comments,
        });

        try {
            const result = JSON.parse(await bridge.submit_feedback(sanitizeBridgeArg(payload)));
            if (result.error) {
                showFeedbackResult(`Error: ${result.error}`, 'error');
            } else {
                showFeedbackResult('Thank you for your feedback!', 'success');
                document.getElementById('feedback-comments').value = '';
                clearStars();
            }
        } catch (e) {
            console.error('Submit feedback failed:', e);
            showFeedbackResult('Failed to submit feedback', 'error');
        }
    }

    async function submitIssue() {
        if (!bridge) return;
        const category = document.getElementById('issue-category').value;
        const severity = document.getElementById('issue-severity').value;
        const description = document.getElementById('issue-description').value;

        if (!description.trim()) {
            showIssueResult('Please describe the issue', 'error');
            return;
        }

        const payload = JSON.stringify({
            category: category,
            severity: severity,
            description: description,
            match_id: currentMatchId || null,
        });

        try {
            const result = JSON.parse(await bridge.submit_issue(sanitizeBridgeArg(payload)));
            if (result.error) {
                showIssueResult(`Error: ${result.error}`, 'error');
            } else {
                showIssueResult('Issue reported. Thank you!', 'success');
                document.getElementById('issue-description').value = '';
            }
        } catch (e) {
            console.error('Submit issue failed:', e);
            showIssueResult('Failed to report issue', 'error');
        }
    }

    async function loadFeedbackStats() {
        if (!bridge) return;
        try {
            window.KawkabSkeletons.showAll();
            const stats = JSON.parse(await bridge.get_feedback_stats());
            if (stats.error) {
                document.getElementById('feedback-stats').innerHTML = `<p class="hint">${stats.error}</p>`;
                return;
            }
            const html = `
                <div class="stat-card"><div class="stat-value">${stats.total_feedback}</div><div class="stat-label">Feedback</div></div>
                <div class="stat-card"><div class="stat-value">${stats.average_rating.toFixed(1)}</div><div class="stat-label">Avg Rating</div></div>
                <div class="stat-card"><div class="stat-value">${stats.total_issues}</div><div class="stat-label">Issues</div></div>
                <div class="stat-card"><div class="stat-value">${stats.issue_by_severity.critical + stats.issue_by_severity.high}</div><div class="stat-label">High Priority</div></div>
            `;
            document.getElementById('feedback-stats').innerHTML = html;
        } catch (e) {
            console.error('Load feedback stats failed:', e);
        } finally {
            window.KawkabSkeletons.hideAll();
        }
    }

    function showFeedbackResult(message, type) {
        const el = document.getElementById('feedback-result');
        el.textContent = message;
        el.className = `feedback-result ${type}`;
        setTimeout(() => { el.textContent = ''; el.className = 'feedback-result'; }, 5000);
    }

    function showIssueResult(message, type) {
        const el = document.getElementById('issue-result');
        el.textContent = message;
        el.className = `feedback-result ${type}`;
        setTimeout(() => { el.textContent = ''; el.className = 'feedback-result'; }, 5000);
    }

    function clearStars() {
        document.querySelectorAll('.star-rating').forEach(container => {
            container.querySelectorAll('.star').forEach(s => s.classList.remove('active'));
            container.dataset.rating = 0;
        });
    }

    // --- v0.8.3: PDF Export, Clip Export, Swap Teams, Visualizations ---

    async function exportPdfReport() {
        if (!bridge || !currentMatchId) return;
        try {
            const result = JSON.parse(await bridge.export_report_pdf(currentMatchId, currentLanguage));
            if (result.error) {
                showToast('Export failed: ' + result.error, 'error');
            } else {
                showToast('Report saved! Check the path: ' + result.path, 'success');
            }
        } catch (e) {
            console.error('PDF export failed:', e);
            showToast('Failed to export report', 'error');
        }
    }

    async function extractClips() {
        if (!bridge || !currentMatchId) return;
        const btn = document.getElementById('extract-clips-btn');
        btn.disabled = true;
        btn.textContent = 'Extracting...';
        try {
            const result = JSON.parse(await bridge.extract_event_clips(currentMatchId));
            if (result.error) {
                document.getElementById('clip-result').textContent = 'Error: ' + result.error;
                document.getElementById('clip-result').className = 'feedback-result error';
            } else {
                const count = result.clips ? result.clips.length : 0;
                document.getElementById('clip-result').textContent = count + ' clip(s) extracted to exports/';
                document.getElementById('clip-result').className = 'feedback-result success';
            }
        } catch (e) {
            console.error('Clip extraction failed:', e);
            document.getElementById('clip-result').textContent = 'Failed to extract clips';
            document.getElementById('clip-result').className = 'feedback-result error';
        } finally {
            btn.disabled = false;
            btn.textContent = '🎬 Extract Clips';
        }
    }

    function swapTeams() {
        if (!bridge || !currentMatchId) return;
        showConfirmDialog('Swap home and away team assignment?', async function () {
            try {
                const result = JSON.parse(await bridge.swap_teams(currentMatchId));
                if (result.error) {
                    showToast('Swap failed: ' + result.error, 'error');
                } else {
                    showToast('Teams swapped! ' + result.home + ' is now home, ' + result.away + ' is now away.', 'success');
                }
            } catch (e) {
                console.error('Swap teams failed:', e);
                showToast('Failed to swap teams', 'error');
            }
        });
    }

    async function generateVisualizations() {
        if (!bridge || !currentMatchId) return;
        try {
            const result = JSON.parse(await bridge.generate_visualizations(currentMatchId));
            if (result.error) {
                showToast('Visualization failed: ' + result.error, 'error');
                return;
            }
            const section = document.getElementById('visualization-section');
            section.classList.remove('hidden');
            const passImg = document.getElementById('pass-network-img');
            const heatImg = document.getElementById('heatmap-img');
            if (result.pass_network) {
                passImg.src = 'file:///' + result.pass_network.replace(/\\/g, '/');
                passImg.style.display = 'block';
            }
            if (result.heatmap) {
                heatImg.src = 'file:///' + result.heatmap.replace(/\\/g, '/');
                heatImg.style.display = 'block';
            }
        } catch (e) {
            console.error('Visualization failed:', e);
            showToast('Failed to generate visualizations', 'error');
        }
    }

    function loadEventTimeline() {
        if (!currentMatchId) return;
        // Clear selection state on reload
        _selectedEventIds.clear();
        _activeChartFilter = null;
        var banner = document.getElementById('timeline-filter-banner');
        if (banner) banner.classList.add('hidden');
        document.querySelectorAll('.chart-container').forEach(function(c) {
            c.classList.remove('chart-filter-active');
        });
        _updateBatchActionBar();
        bridge.get_match_events(currentMatchId).then(function(json) {
            try {
                const events = JSON.parse(json);
                if (events.error) {
                    console.error('Timeline error:', events.error);
                    return;
                }
                window._timelineEvents = events || [];
                renderTimeline(window._timelineEvents);
            } catch (e) {
                console.error('Failed to parse events:', e);
            }
        }).catch(function(err) {
            console.error('loadEventTimeline failed:', err);
        });
    }

    // ── Multi-selection helpers ──────────────────────────────

    function _toggleEventSelection(eventId, ctrlKey) {
        if (!ctrlKey) {
            _selectedEventIds.clear();
        }
        if (_selectedEventIds.has(eventId)) {
            _selectedEventIds.delete(eventId);
        } else {
            _selectedEventIds.add(eventId);
        }
        _updateBatchActionBar();
        _updateTableRowSelection();
        _updateTimelineItemSelection();
    }

    function _selectEventRange(fromIdx, toIdx, events) {
        var start = Math.min(fromIdx, toIdx);
        var end = Math.max(fromIdx, toIdx);
        for (var i = start; i <= end; i++) {
            if (events[i] && events[i].id) {
                _selectedEventIds.add(events[i].id);
            }
        }
        _updateBatchActionBar();
        _updateTableRowSelection();
        _updateTimelineItemSelection();
    }

    function _updateBatchActionBar() {
        var bar = document.getElementById('batch-action-bar');
        var countEl = document.getElementById('batch-count');
        if (!bar || !countEl) return;
        var count = _selectedEventIds.size;
        if (count > 0) {
            bar.classList.remove('hidden');
            countEl.textContent = count + ' selected';
        } else {
            bar.classList.add('hidden');
        }
    }

    function _updateTableRowSelection() {
        var table = document.getElementById('timeline-data-table');
        if (!table) return;
        var rows = table.querySelectorAll('tbody tr');
        rows.forEach(function(row) {
            var eid = parseInt(row.dataset.eventId, 10);
            row.classList.toggle('selected', _selectedEventIds.has(eid));
            var cb = row.querySelector('.table-checkbox');
            if (cb) cb.checked = _selectedEventIds.has(eid);
        });
        var selectAll = table.querySelector('.select-all-checkbox');
        if (selectAll) {
            var visibleIds = _getFilteredSortedEvents().map(function(e) { return e.id; });
            var allSelected = visibleIds.every(function(id) { return _selectedEventIds.has(id); });
            selectAll.checked = allSelected;
        }
    }

    function _updateTimelineItemSelection() {
        document.querySelectorAll('.timeline-item').forEach(function(item) {
            var eid = parseInt(item.dataset.eventId, 10);
            item.classList.toggle('selected', _selectedEventIds.has(eid));
            var cb = item.querySelector('.timeline-checkbox');
            if (cb) cb.checked = _selectedEventIds.has(eid);
        });
    }

    // ── Sort / Filter / Pagination helpers ──────────────────

    function _getEventField(e, key) {
        switch (key) {
            case 'time': return e.timestamp || 0;
            case 'type': return e.event_type || '';
            case 'team': return e.team || '';
            case 'player': return e.player_name || '';
            case 'xg': return e.xg != null ? e.xg : -1;
            case 'xa': return e.xa != null ? e.xa : -1;
            case 'xt': return e.xt != null ? e.xt : -1;
            default: return '';
        }
    }

    function _getFilteredSortedEvents() {
        var events = window._timelineEvents || [];
        var filterType = document.getElementById('timeline-filter-type');
        var filterVal = filterType ? filterType.value : 'all';
        var text = (_timelineSearchText || '').toLowerCase().trim();

        // Apply type filter
        var filtered = filterVal === 'all' ? events.slice() : events.filter(function(e) {
            return e.event_type === filterVal;
        });

        // Apply chart cross-filter
        if (_activeChartFilter) {
            filtered = filtered.filter(function(e) {
                var t = e.timestamp || 0;
                return t >= _activeChartFilter.startMin * 60 && t <= _activeChartFilter.endMin * 60;
            });
        }

        // Apply text search
        if (text) {
            filtered = filtered.filter(function(e) {
                var searchable = (e.event_type + ' ' + (e.team || '') + ' ' + (e.player_name || '') + ' ' + (e.id || '') + ' ' + formatTimestamp(e.timestamp || 0)).toLowerCase();
                return searchable.indexOf(text) >= 0;
            });
        }

        // Apply column filters
        if (_timelineFilters.type) {
            filtered = filtered.filter(function(e) { return e.event_type === _timelineFilters.type; });
        }
        if (_timelineFilters.team) {
            filtered = filtered.filter(function(e) { return e.team === _timelineFilters.team; });
        }
        if (_timelineFilters.player) {
            var pn = _timelineFilters.player.toLowerCase();
            filtered = filtered.filter(function(e) { return (e.player_name || '').toLowerCase().indexOf(pn) >= 0; });
        }

        // Apply sort
        var key = _timelineSortState.key;
        var dir = _timelineSortState.dir === 'asc' ? 1 : -1;
        filtered.sort(function(a, b) {
            var va = _getEventField(a, key);
            var vb = _getEventField(b, key);
            if (typeof va === 'string' && typeof vb === 'string') {
                return va.localeCompare(vb) * dir;
            }
            if (va == null || va === -1) return 1 * dir;
            if (vb == null || vb === -1) return -1 * dir;
            return (va - vb) * dir;
        });

        return filtered;
    }

    function _getColumnHeaderLabel(key) {
        var labels = {
            time: 'Time',
            type: 'Type',
            team: 'Team',
            player: 'Player',
            xg: 'xG',
            xa: 'xA',
            xt: 'xT',
        };
        return labels[key] || key;
    }

    // ── Timeline rendering ──────────────────────────────────

    function renderTimeline(events) {
        wireChartFilter();
        if (!events || events.length === 0) {
            events = window._timelineEvents || [];
        }
        if (_currentTimelineView === 'table') {
            renderTimelineTable(events);
            return;
        }
        var list = document.getElementById('timeline-list');
        var wrapper = document.getElementById('timeline-table-wrapper');
        if (!list) return;
        if (wrapper) wrapper.classList.add('hidden');
        list.classList.remove('hidden');
        if (!events || events.length === 0) {
            list.innerHTML = '<div class="timeline-empty">No events detected</div>';
            return;
        }
        var filtered = _getFilteredSortedEvents();
        list.innerHTML = filtered.map(function(e, idx) {
            return renderTimelineItem(e, idx);
        }).join('');
        _updateTimelineItemSelection();
    }

    function renderTimelineItem(e, idx) {
        var label = e.event_type.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
        var icon = eventTypeIcon(e.event_type);
        var ts = formatTimestamp(e.timestamp || 0);
        var teamClass = e.team === 'home' || e.team === 'away' ? e.team : '';
        var teamBadge = teamClass ? '<span class="timeline-team-badge ' + teamClass + '">' + teamClass + '</span>' : '';
        var isSelected = _selectedEventIds.has(e.id) ? ' selected' : '';
        var checked = _selectedEventIds.has(e.id) ? 'checked' : '';
        return '<div class="timeline-item ' + (e.event_type || '') + isSelected + '" data-idx="' + idx + '" data-event-id="' + (e.id || '') + '" data-timestamp="' + (e.timestamp || 0) + '">' +
            '<input type="checkbox" class="timeline-checkbox" data-event-id="' + (e.id || '') + '" ' + checked + '>' +
            '<span class="timeline-icon">' + icon + '</span>' +
            '<span class="timeline-time">' + ts + '</span>' +
            '<span class="timeline-label">' + label + '</span>' +
            teamBadge +
            '<span class="timeline-item-actions">' +
                '<button class="edit-btn" title="Edit">&#9998;</button>' +
                '<button class="delete-btn" title="Delete">&times;</button>' +
            '</span>' +
        '</div>';
    }

    function renderTimelineTable(events) {
        var list = document.getElementById('timeline-list');
        var wrapper = document.getElementById('timeline-table-wrapper');
        if (!wrapper) return;
        if (list) list.classList.add('hidden');
        wrapper.classList.remove('hidden');

        if (!events || events.length === 0) {
            events = window._timelineEvents || [];
        }
        var filtered = _getFilteredSortedEvents();
        var total = filtered.length;
        var perPage = _timelinePageState.perPage;
        var currentPage = _timelinePageState.page;
        var totalPages = Math.max(1, Math.ceil(total / perPage));
        if (currentPage > totalPages) {
            _timelinePageState.page = totalPages;
            currentPage = totalPages;
        }
        var start = (currentPage - 1) * perPage;
        var pageData = filtered.slice(start, start + perPage);

        var sortKey = _timelineSortState.key;
        var sortDir = _timelineSortState.dir;

        // Determine if all visible events are selected
        var visibleIds = filtered.map(function(e) { return e.id; });
        var allVisibleSelected = visibleIds.length > 0 && visibleIds.every(function(id) { return _selectedEventIds.has(id); });

        var html = '<table class="data-table" id="timeline-data-table"><thead><tr>';
        // Select all checkbox
        html += '<th style="width:30px;text-align:center"><input type="checkbox" class="table-checkbox select-all-checkbox" ' + (allVisibleSelected ? 'checked' : '') + '></th>';
        var cols = ['time', 'type', 'team', 'player', 'xg', 'xa', 'xt'];
        cols.forEach(function(key) {
            var isSorted = sortKey === key;
            var sortClass = isSorted ? (sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc') : '';
            var arrow = isSorted ? '<span class="sort-indicator"></span>' : '<span class="sort-indicator"></span>';
            html += '<th class="sortable ' + sortClass + '" data-sort-key="' + key + '">' +
                '<span class="th-label">' + _getColumnHeaderLabel(key) + '</span>' + arrow;
            // Filter inputs for text columns
            if (key === 'type' || key === 'team' || key === 'player') {
                var filterVal = _timelineFilters[key] || '';
                html += '<input type="text" class="col-filter-input" data-filter-key="' + key + '" value="' + filterVal + '" placeholder="Filter...">';
            }
            html += '</th>';
        });
        html += '<th style="width:70px" data-i18n="actions">Actions</th>';
        html += '</tr></thead><tbody>';

        if (pageData.length === 0) {
            html += '<tr><td colspan="8" style="text-align:center;color:var(--text-muted);padding:1.5rem">No events match filters</td></tr>';
        } else {
            pageData.forEach(function(e) {
                var isSelected = _selectedEventIds.has(e.id) ? ' selected' : '';
                var checked = _selectedEventIds.has(e.id) ? 'checked' : '';
                html += '<tr class="' + isSelected + '" data-event-id="' + (e.id || '') + '">';
                html += '<td style="text-align:center"><input type="checkbox" class="table-checkbox" data-event-id="' + (e.id || '') + '" ' + checked + '></td>';
                html += '<td>' + formatTimestamp(e.timestamp || 0) + '</td>';
                html += '<td>' + labelEventType(e.event_type || '') + '</td>';
                html += '<td>' + (e.team || '') + '</td>';
                html += '<td>' + escapeHtml(e.player_name || '') + '</td>';
                html += '<td class="numeric">' + (e.xg != null ? e.xg.toFixed(3) : '--') + '</td>';
                html += '<td class="numeric">' + (e.xa != null ? e.xa.toFixed(3) : '--') + '</td>';
                html += '<td class="numeric">' + (e.xt != null ? e.xt.toFixed(3) : '--') + '</td>';
                html += '<td class="table-actions">' +
                    '<button class="table-edit-btn" data-event-id="' + (e.id || '') + '" data-event-type="' + (e.event_type || '') + '" data-team="' + (e.team || '') + '" title="Edit">&#9998;</button>' +
                    '<button class="table-delete-btn" data-event-id="' + (e.id || '') + '" title="Delete">&times;</button>' +
                    '</td>';
                html += '</tr>';
            });
        }

        html += '</tbody></table>';

        // Pagination
        html += '<div class="data-table-pagination">';
        html += '<span class="pagination-info">Showing ' + (total > 0 ? (start + 1) + '-' + Math.min(start + perPage, total) : 0) + ' of ' + total + ' events</span>';
        html += '<div class="pagination-controls">';
        html += '<button class="pagination-btn" data-page="prev" ' + (currentPage <= 1 ? 'disabled' : '') + '>&#9664;</button>';
        var maxButtons = 5;
        var startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
        var endPage = Math.min(totalPages, startPage + maxButtons - 1);
        if (endPage - startPage < maxButtons - 1) startPage = Math.max(1, endPage - maxButtons + 1);
        if (startPage > 1) html += '<button class="pagination-btn" data-page="1">1</button>' + (startPage > 2 ? '<span style="color:var(--text-muted);padding:0 2px">...</span>' : '');
        for (var p = startPage; p <= endPage; p++) {
            html += '<button class="pagination-btn ' + (p === currentPage ? 'active' : '') + '" data-page="' + p + '">' + p + '</button>';
        }
        if (endPage < totalPages) html += (endPage < totalPages - 1 ? '<span style="color:var(--text-muted);padding:0 2px">...</span>' : '') + '<button class="pagination-btn" data-page="' + totalPages + '">' + totalPages + '</button>';
        html += '<button class="pagination-btn" data-page="next" ' + (currentPage >= totalPages ? 'disabled' : '') + '>&#9654;</button>';
        html += '<select class="per-page-select">';
        [25, 50, 100].forEach(function(pp) {
            html += '<option value="' + pp + '" ' + (pp === perPage ? 'selected' : '') + '>' + pp + ' / page</option>';
        });
        html += '</select>';
        html += '</div></div>';

        wrapper.innerHTML = html;
    }

    function labelEventType(type) {
        return type.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
    }

    function formatTimestamp(seconds) {
        var m = Math.floor(seconds / 60);
        var s = Math.floor(seconds % 60);
        return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
    }

    function eventTypeIcon(type) {
        var icons = {
            'goal': '\u26BD',
            'shot': '\uD83C\uDFF4',
            'pass': '\u27A1\uFE0F',
            'tackle': '\uD83D\uDCAA',
            'interception': '\uD83D\uDD35',
            'dribble': '\uD83C\uDFC3',
            'corner': '\uD83D\uDEE1\uFE0F',
            'free_kick': '\uD83E\uDD45',
            'throw_in': '\uD83C\uDFC0',
            'clearance': '\uD83D\uDEE1\uFE0F',
            'cross': '\u2747\uFE0F',
            'block': '\uD83D\uDEAB',
            'carry': '\uD83C\uDFC3',
            'duel': '\uD83E\uDD4A',
            'foul': '\u26A0\uFE0F',
            'offside': '\uD83D\uDECE\uFE0F',
        };
        return icons[type] || '\u25CF';
    }

    function timelineSeek(timestamp) {
        var video = document.getElementById('match-video');
        if (video && timestamp != null) {
            video.currentTime = parseFloat(timestamp);
            video.play().catch(function() {});
        }
    }

    function highlightCurrentTimelineItem(currentTime) {
        var items = document.querySelectorAll('.timeline-item');
        var bestIdx = -1;
        var bestDist = Infinity;
        items.forEach(function(item) {
            var ts = parseFloat(item.dataset.timestamp || 0);
            var dist = Math.abs(ts - currentTime);
            if (dist < bestDist) {
                bestDist = dist;
                bestIdx = parseInt(item.dataset.idx, 10);
            }
        });
        items.forEach(function(item) {
            item.classList.toggle('active', parseInt(item.dataset.idx, 10) === bestIdx && bestDist < 5);
        });
    }

    function openEditModal(eventId, eventType, team) {
        document.getElementById('edit-event-id').value = eventId;
        document.getElementById('edit-event-type').value = eventType || 'pass';
        document.getElementById('edit-event-team').value = team || 'unknown';
        document.getElementById('edit-event-note').value = '';
        document.getElementById('edit-event-modal').classList.remove('hidden');
    }

    document.addEventListener('click', function(e) {
        // ── Timeline item checkbox (multi-select) ──
        if (e.target.closest('.timeline-checkbox')) {
            var cb = e.target;
            var eventId = parseInt(cb.dataset.eventId, 10);
            if (!eventId) return;
            if (e.shiftKey && _lastShiftClickIdx >= 0) {
                var items = document.querySelectorAll('.timeline-item');
                var currentIdx = -1;
                items.forEach(function(it, i) {
                    if (parseInt(it.dataset.eventId, 10) === eventId) currentIdx = i;
                });
                if (currentIdx >= 0) {
                    _selectEventRange(_lastShiftClickIdx, currentIdx, window._timelineEvents || []);
                }
            } else {
                var idx = -1;
                var evts = window._timelineEvents || [];
                evts.forEach(function(ev, i) {
                    if (ev.id === eventId) { idx = i; }
                });
                _lastShiftClickIdx = idx;
                _toggleEventSelection(eventId, e.ctrlKey || e.metaKey);
            }
            e.stopPropagation();
            return;
        }

        // ── Timeline item body (seek + selection) ──
        var item = e.target.closest('.timeline-item');
        if (item && !e.target.closest('.timeline-item-actions') && !e.target.closest('.timeline-checkbox')) {
            var eventId = parseInt(item.dataset.eventId, 10);
            if (eventId && (e.ctrlKey || e.metaKey)) {
                _toggleEventSelection(eventId, true);
            } else if (eventId && e.shiftKey && _lastShiftClickIdx >= 0) {
                var items = document.querySelectorAll('.timeline-item');
                var currentIdx = -1;
                items.forEach(function(it, i) {
                    if (parseInt(it.dataset.eventId, 10) === eventId) currentIdx = i;
                });
                if (currentIdx >= 0) {
                    _selectEventRange(_lastShiftClickIdx, currentIdx, window._timelineEvents || []);
                }
            } else {
                timelineSeek(item.dataset.timestamp);
            }
            return;
        }

        // ── Timeline edit button (div view) ──
        if (e.target.closest('.edit-btn')) {
            var item = e.target.closest('.timeline-item');
            var eventId = parseInt(item.dataset.eventId, 10);
            var events = window._timelineEvents || [];
            var ev = events[parseInt(item.dataset.idx, 10)] || {};
            openEditModal(eventId, ev.event_type, ev.team);
            e.stopPropagation();
            return;
        }

        // ── Timeline delete button (div view) ──
        if (e.target.closest('.delete-btn')) {
            var item = e.target.closest('.timeline-item');
            showConfirmDialog('Delete this event?', function() {
                var eventId = parseInt(item.dataset.eventId, 10);
                bridge.delete_event(eventId).then(function(json) {
                    try {
                        var result = JSON.parse(json);
                        if (result.success) {
                            setTimeout(loadEventTimeline, 100);
                        }
                    } catch (ex) {}
                }).catch(function(err) {
                    console.error('Delete event failed:', err);
                });
            });
            e.stopPropagation();
            return;
        }

        // ── Table checkbox ──
        if (e.target.closest('.table-checkbox')) {
            var cb = e.target;
            var eventId = parseInt(cb.dataset.eventId, 10);
            if (cb.classList.contains('select-all-checkbox')) {
                var filtered = _getFilteredSortedEvents();
                if (cb.checked) {
                    filtered.forEach(function(ev) { if (ev.id) _selectedEventIds.add(ev.id); });
                } else {
                    filtered.forEach(function(ev) { if (ev.id) _selectedEventIds.delete(ev.id); });
                }
                _updateBatchActionBar();
                _updateTableRowSelection();
                _updateTimelineItemSelection();
            } else if (eventId) {
                if (e.shiftKey && _lastShiftClickIdx >= 0) {
                    var filteredEvts = _getFilteredSortedEvents();
                    var currentIdx = -1;
                    filteredEvts.forEach(function(ev, i) {
                        if (ev.id === eventId) currentIdx = i;
                    });
                    if (currentIdx >= 0) {
                        _selectEventRange(_lastShiftClickIdx, currentIdx, filteredEvts);
                    }
                } else {
                    var idx = -1;
                    var evts = window._timelineEvents || [];
                    evts.forEach(function(ev, i) {
                        if (ev.id === eventId) idx = i;
                    });
                    _lastShiftClickIdx = idx;
                    _toggleEventSelection(eventId, e.ctrlKey || e.metaKey);
                }
            }
            e.stopPropagation();
            return;
        }

        // ── Table edit button ──
        if (e.target.closest('.table-edit-btn')) {
            var btn = e.target.closest('.table-edit-btn');
            var eid = parseInt(btn.dataset.eventId, 10);
            openEditModal(eid, btn.dataset.eventType, btn.dataset.team);
            e.stopPropagation();
            return;
        }

        // ── Table delete button ──
        if (e.target.closest('.table-delete-btn')) {
            var btn = e.target.closest('.table-delete-btn');
            var eid = parseInt(btn.dataset.eventId, 10);
            showConfirmDialog('Delete this event?', function() {
                bridge.delete_event(eid).then(function(json) {
                    try {
                        var result = JSON.parse(json);
                        if (result.success) {
                            setTimeout(loadEventTimeline, 100);
                        }
                    } catch (ex) {}
                }).catch(function(err) {
                    console.error('Delete event failed:', err);
                });
            });
            e.stopPropagation();
            return;
        }

        // ── Table column header sort ──
        if (e.target.closest('.data-table th.sortable')) {
            var th = e.target.closest('.data-table th.sortable');
            if (e.target.closest('.col-filter-input')) return; // Ignore clicks on filter inputs
            var key = th.dataset.sortKey;
            if (_timelineSortState.key === key) {
                _timelineSortState.dir = _timelineSortState.dir === 'asc' ? 'desc' : 'asc';
            } else {
                _timelineSortState.key = key;
                _timelineSortState.dir = 'asc';
            }
            renderTimelineTable(window._timelineEvents || []);
            return;
        }

        // ── Table column filter input (delegated) ──
        if (e.target.closest('.col-filter-input')) {
            // Handled by input event listener below
            return;
        }

        // ── Table pagination ──
        if (e.target.closest('.pagination-btn')) {
            var btn = e.target.closest('.pagination-btn');
            var page = btn.dataset.page;
            if (page === 'prev') {
                _timelinePageState.page = Math.max(1, _timelinePageState.page - 1);
            } else if (page === 'next') {
                var total = _getFilteredSortedEvents().length;
                var maxPage = Math.ceil(total / _timelinePageState.perPage);
                _timelinePageState.page = Math.min(maxPage, _timelinePageState.page + 1);
            } else {
                _timelinePageState.page = parseInt(page, 10);
            }
            renderTimelineTable(window._timelineEvents || []);
            return;
        }

        // ── Table per-page select (delegated) ──
        if (e.target.closest('.per-page-select')) {
            // Handled by change event
            return;
        }
    });

    // ── Chart cross-filter ──────────────────────────────────

    var _chartFilterCanvasId = null;

    function wireChartFilter() {
        if (typeof window.__kawkabChartFilter !== 'function') {
            window.__kawkabChartFilter = function(data) {
                filterTimelineByTimeRange(data.match_minute, data.range, data.canvasId);
            };
        }
    }

    function filterTimelineByTimeRange(matchMinute, range, canvasId) {
        // If same chart clicked again, clear filter
        if (_activeChartFilter && _activeChartFilter.canvasId === canvasId) {
            clearTimelineFilter();
            return;
        }

        var startMin = matchMinute - range;
        var endMin = matchMinute + range;
        _activeChartFilter = { canvasId: canvasId, startMin: startMin, endMin: endMin };
        _chartFilterCanvasId = canvasId;

        // Highlight chart
        document.querySelectorAll('.chart-container').forEach(function(c) {
            c.classList.remove('chart-filter-active');
        });
        var canvas = document.getElementById(canvasId);
        if (canvas && canvas.parentElement) {
            canvas.parentElement.classList.add('chart-filter-active');
        }

        // Show banner
        var banner = document.getElementById('timeline-filter-banner');
        var text = document.getElementById('filter-banner-text');
        if (banner && text) {
            banner.classList.remove('hidden');
            text.textContent = 'Filtered: ' + Math.max(0, startMin) + "'-" + endMin + "'";
        }

        renderTimeline(window._timelineEvents || []);
    }

    function clearTimelineFilter() {
        _activeChartFilter = null;
        _chartFilterCanvasId = null;

        document.querySelectorAll('.chart-container').forEach(function(c) {
            c.classList.remove('chart-filter-active');
        });

        var banner = document.getElementById('timeline-filter-banner');
        if (banner) banner.classList.add('hidden');

        renderTimeline(window._timelineEvents || []);
    }

    document.getElementById('filter-banner-clear')?.addEventListener('click', clearTimelineFilter);

    // ── Item 7: Timeline Scrub/Zoom Widget ────────────────

    var _scrubState = { dragging: null, startMin: 0, endMin: 90 };

    function initTimelineScrubber() {
        var canvas = document.getElementById('scrubber-canvas');
        if (!canvas) return;
        if (!window._timelineEvents || window._timelineEvents.length === 0) {
            document.getElementById('timeline-scrubber').classList.add('empty');
            return;
        }
        document.getElementById('timeline-scrubber').classList.remove('empty');
        drawScrubberDensity(window._timelineEvents);
        _scrubState.startMin = 0;
        _scrubState.endMin = 90;
        updateScrubberRange();

        var handleL = document.getElementById('scrub-handle-left');
        var handleR = document.getElementById('scrub-handle-right');

        function onDragStart(side, e) {
            e.preventDefault();
            _scrubState.dragging = side;
            document.addEventListener('mousemove', onDragMove);
            document.addEventListener('mouseup', onDragEnd);
        }

        function onDragMove(e) {
            if (!_scrubState.dragging) return;
            var rect = canvas.getBoundingClientRect();
            var totalMin = 90;
            var pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            var min = Math.round(pct * totalMin);
            if (_scrubState.dragging === 'left') {
                _scrubState.startMin = Math.min(min, _scrubState.endMin - 1);
            } else {
                _scrubState.endMin = Math.max(min, _scrubState.startMin + 1);
            }
            updateScrubberRange();
            filterTimelineByTimeRangeScrub();
        }

        function onDragEnd() {
            _scrubState.dragging = null;
            document.removeEventListener('mousemove', onDragMove);
            document.removeEventListener('mouseup', onDragEnd);
        }

        handleL.addEventListener('mousedown', function(e) { onDragStart('left', e); });
        handleR.addEventListener('mousedown', function(e) { onDragStart('right', e); });

        canvas.addEventListener('dblclick', function() {
            _scrubState.startMin = 0;
            _scrubState.endMin = 90;
            updateScrubberRange();
            clearTimelineFilter();
        });
    }

    function drawScrubberDensity(events) {
        var canvas = document.getElementById('scrubber-canvas');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        var w = canvas.width;
        var h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        var totalMin = 90;
        var minuteCounts = {};
        var goalCounts = {};
        var shotCounts = {};
        events.forEach(function(e) {
            var min = Math.floor((e.timestamp || 0) / 60);
            minuteCounts[min] = (minuteCounts[min] || 0) + 1;
            if (e.event_type === 'goal') goalCounts[min] = (goalCounts[min] || 0) + 1;
            else if (e.event_type === 'shot') shotCounts[min] = (shotCounts[min] || 0) + 1;
        });

        var maxCount = 1;
        for (var i = 0; i <= totalMin; i++) {
            maxCount = Math.max(maxCount, minuteCounts[i] || 0);
        }

        var barW = Math.max(1, (w - 4) / totalMin);
        for (var min = 0; min <= totalMin; min++) {
            var x = 2 + min * barW;
            var total = minuteCounts[min] || 0;
            var goals = goalCounts[min] || 0;
            var shots = shotCounts[min] || 0;
            var others = total - goals - shots;
            var barH = (total / maxCount) * (h - 4);
            var y = h - 2 - barH;

            if (goals > 0) {
                var gH = (goals / maxCount) * (h - 4);
                ctx.fillStyle = '#ef4444';
                ctx.fillRect(x, h - 2 - gH, barW, gH);
            }
            if (shots > 0) {
                var sH = (shots / maxCount) * (h - 4);
                ctx.fillStyle = '#f97316';
                ctx.fillRect(x, h - 2 - sH - gH, barW, sH);
            }
            if (others > 0) {
                ctx.fillStyle = '#3b82f6';
                ctx.fillRect(x, y, barW, barH);
            }
        }
    }

    function updateScrubberRange() {
        var canvas = document.getElementById('scrubber-canvas');
        if (!canvas) return;
        var totalMin = 90;
        var pctL = _scrubState.startMin / totalMin;
        var pctR = 1 - (_scrubState.endMin / totalMin);
        var handleL = document.getElementById('scrub-handle-left');
        var handleR = document.getElementById('scrub-handle-right');
        var highlight = document.getElementById('scrubber-range-highlight');
        if (handleL) handleL.style.left = 'calc(' + (pctL * 100) + '% - 0px)';
        if (handleR) handleR.style.right = 'calc(' + (pctR * 100) + '% - 0px)';
        if (highlight) {
            highlight.style.left = 'calc(' + (pctL * 100) + '% + 6px)';
            highlight.style.right = 'calc(' + (pctR * 100) + '% + 6px)';
        }
    }

    function filterTimelineByTimeRangeScrub() {
        var startMin = _scrubState.startMin;
        var endMin = _scrubState.endMin;
        _activeChartFilter = { canvasId: 'scrubber', startMin: startMin, endMin: endMin };

        var banner = document.getElementById('timeline-filter-banner');
        var text = document.getElementById('filter-banner-text');
        if (banner && text) {
            banner.classList.remove('hidden');
            text.textContent = 'Filtered: ' + startMin + "'-" + endMin + "'";
        }

        document.querySelectorAll('.chart-container').forEach(function(c) {
            c.classList.remove('chart-filter-active');
        });

        renderTimeline(window._timelineEvents || []);
    }

    // ── Item 10: Data Density Toggle ──────────────────────

    function initDensityToggle() {
        var stored = null;
        try { stored = localStorage.getItem('kawkab_density'); } catch(e) {}
        if (stored) {
            document.documentElement.setAttribute('data-density', stored);
            document.querySelectorAll('.density-btn').forEach(function(b) {
                b.classList.toggle('active', b.dataset.density === stored);
            });
        }
        document.querySelectorAll('.density-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var density = this.dataset.density;
                document.documentElement.setAttribute('data-density', density);
                document.querySelectorAll('.density-btn').forEach(function(b) { b.classList.remove('active'); });
                this.classList.add('active');
                try { localStorage.setItem('kawkab_density', density); } catch(e) {}
            });
        });
    }

    // ── Item 12: Color Customization ──────────────────────

    function initColorSettings() {
        var stored = null;
        try { stored = JSON.parse(localStorage.getItem('kawkab_colors')); } catch(e) {}
        if (stored) {
            applyTeamColors(stored.home || '#2563eb', stored.away || '#dc2626');
        }
        var homeInput = document.getElementById('home-color');
        var awayInput = document.getElementById('away-color');
        var resetBtn = document.getElementById('reset-colors-btn');

        homeInput.addEventListener('input', function() {
            applyTeamColors(this.value, awayInput.value);
            saveTeamColors();
        });
        awayInput.addEventListener('input', function() {
            applyTeamColors(homeInput.value, this.value);
            saveTeamColors();
        });
        resetBtn.addEventListener('click', function() {
            applyTeamColors('#2563eb', '#dc2626');
            homeInput.value = '#2563eb';
            awayInput.value = '#dc2626';
            try { localStorage.removeItem('kawkab_colors'); } catch(e) {}
            if (window.__invalidateColorCache) window.__invalidateColorCache();
        });

        document.getElementById('color-palette-btn').addEventListener('click', function() {
            document.getElementById('color-settings').classList.toggle('hidden');
        });

        document.addEventListener('click', function(e) {
            var wrapper = document.querySelector('.color-palette-wrapper');
            if (wrapper && !wrapper.contains(e.target)) {
                document.getElementById('color-settings').classList.add('hidden');
            }
        });
    }

    function applyTeamColors(home, away) {
        var root = document.documentElement;
        root.style.setProperty('--team-home', home);
        root.style.setProperty('--team-away', away);
    }

    function saveTeamColors() {
        var home = document.getElementById('home-color').value;
        var away = document.getElementById('away-color').value;
        try { localStorage.setItem('kawkab_colors', JSON.stringify({ home: home, away: away })); } catch(e) {}
        if (window.__invalidateColorCache) window.__invalidateColorCache();
        // Re-render charts if match loaded
        if (currentMatchId && analysisResult) {
            renderResults(analysisResult);
        }
    }

    // ── Item 13: Video Keyboard Shortcuts ─────────────────

    function initVideoShortcuts() {
        document.addEventListener('keydown', function(e) {
            if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
            if (e.ctrlKey || e.metaKey || e.altKey) return;
            var video = document.getElementById('match-video');
            if (!video || !video.src) return;
            switch (e.key) {
                case ' ':
                    e.preventDefault();
                    if (video.paused) video.play(); else video.pause();
                    break;
                case 'k':
                case 'K':
                    video.pause();
                    break;
                case 'j':
                case 'J':
                    video.currentTime = Math.max(0, video.currentTime - 10);
                    break;
                case 'l':
                case 'L':
                    video.currentTime = Math.min(video.duration || 0, video.currentTime + 10);
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    video.currentTime = Math.max(0, video.currentTime - 5);
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    video.currentTime = Math.min(video.duration || 0, video.currentTime + 5);
                    break;
                case 'f':
                case 'F':
                    if (video.requestFullscreen) {
                        video.requestFullscreen();
                    } else if (video.webkitRequestFullscreen) {
                        video.webkitRequestFullscreen();
                    }
                    break;
            }
        });
    }

    // ── Item 14: Persistent Filter State ──────────────────

    function saveFilterState() {
        try {
            sessionStorage.setItem('kawkab_timeline_filter_type', document.getElementById('timeline-filter-type').value);
            sessionStorage.setItem('kawkab_timeline_sort_column', _timelineSortState.key);
            sessionStorage.setItem('kawkab_timeline_sort_dir', _timelineSortState.dir);
            sessionStorage.setItem('kawkab_timeline_page', _timelinePageState.page);
            sessionStorage.setItem('kawkab_timeline_view', _currentTimelineView);
            sessionStorage.setItem('kawkab_timeline_search', _timelineSearchText);
            sessionStorage.setItem('kawkab_dashboard_daterange', document.getElementById('dashboard-date-range').value);
        } catch(e) {}
    }

    function restoreFilterState() {
        try {
            var filterType = sessionStorage.getItem('kawkab_timeline_filter_type');
            var sortCol = sessionStorage.getItem('kawkab_timeline_sort_column');
            var sortDir = sessionStorage.getItem('kawkab_timeline_sort_dir');
            var page = sessionStorage.getItem('kawkab_timeline_page');
            var view = sessionStorage.getItem('kawkab_timeline_view');
            var search = sessionStorage.getItem('kawkab_timeline_search');
            var daterange = sessionStorage.getItem('kawkab_dashboard_daterange');

            if (filterType) {
                var sel = document.getElementById('timeline-filter-type');
                if (sel) sel.value = filterType;
            }
            if (sortCol) _timelineSortState.key = sortCol;
            if (sortDir) _timelineSortState.dir = sortDir;
            if (page) _timelinePageState.page = parseInt(page, 10) || 1;
            if (view) _currentTimelineView = view;
            if (search != null) _timelineSearchText = search;
            if (daterange) {
                var dr = document.getElementById('dashboard-date-range');
                if (dr) dr.value = daterange;
            }
        } catch(e) {}
    }

    // ── Coding Workspace (Phase 1 — Video Tagging Engine) ──────

    var _codingState = {
        matchId: null,
        tags: [],
        templates: [],
        video: null,
        currentTime: 0,
        activeTagId: null,
        shortcuts: {},
        selectedPlayer: 0,
        selectedTeam: '',
        selectedPeriod: 1,
        leadMs: 2000,
        lagMs: 3000,
        notes: '',
        filterText: '',
        isLoading: false,
        keyboardEnabled: false,
    };

    function initCodingWorkspace() {
        var loadBtn = document.getElementById('coding-load-btn');
        var matchSelect = document.getElementById('coding-match-select');
        var clearBtn = document.getElementById('coding-clear-btn');
        var exportAllBtn = document.getElementById('coding-export-all-btn');
        var filterInput = document.getElementById('coding-filter-input');
        var exportCsv = document.getElementById('coding-export-csv');
        var exportJson = document.getElementById('coding-export-json');
        var timelineCanvas = document.getElementById('coding-timeline-canvas');
        var notesInput = document.getElementById('coding-notes-input');

        if (!loadBtn) return; // Section not loaded yet

        // Load match select when coding section is shown
        window.loadCodingMatchSelect = function() {
            if (typeof bridge === 'undefined' || !bridge) return;
            bridge.get_all_matches(function(result) {
                try {
                    var data = JSON.parse(result);
                    if (data.error || !Array.isArray(data)) {
                        data = typeof data === 'object' && data.matches ? data.matches : [];
                    }
                    var sel = document.getElementById('coding-match-select');
                    sel.innerHTML = '<option value="">-- Select Match --</option>';
                    (data || []).forEach(function(m) {
                        var name = m.name || m.home_team + ' vs ' + m.away_team || 'Match #' + m.id;
                        sel.innerHTML += '<option value="' + m.id + '">' + escapeHtml(name) + '</option>';
                    });
                } catch(e) {
                    console.warn('loadCodingMatchSelect:', e);
                }
            });
        };

        loadBtn.addEventListener('click', function() {
            var matchId = parseInt(matchSelect.value, 10);
            if (!matchId) {
                showToast('Please select a match first.', 'warning');
                return;
            }
            loadCodingWorkspace(matchId);
        });

        clearBtn.addEventListener('click', function() {
            if (_codingState.tags.length === 0) return;
            showConfirmDialog('Delete all ' + _codingState.tags.length + ' tags for this match?', function() {
                var ids = _codingState.tags.map(function(t) { return t.id; });
                var deleted = 0;
                ids.forEach(function(id) {
                    bridge.delete_coding_tag(id, function(result) {
                        var data = JSON.parse(result);
                        if (data.success) deleted++;
                        if (deleted === ids.length) {
                            _codingState.tags = [];
                            renderCodingTagList();
                            renderCodingTimeline();
                            updateCodingStats();
                            showToast('All tags deleted.', 'success');
                        }
                    });
                });
            });
        });

        exportAllBtn.addEventListener('click', function() {
            if (_codingState.tags.length === 0) {
                showToast('No tags to export.', 'warning');
                return;
            }
            showToast('Extracting clips...', 'info');
            var tagIds = _codingState.tags.map(function(t) { return t.id; });
            bridge.extract_tag_clips_batch(_codingState.matchId, JSON.stringify(tagIds), function(result) {
                try {
                    var data = JSON.parse(result);
                    if (data.success) {
                        var done = data.results.filter(function(r) { return r.success; }).length;
                        var failed = data.results.filter(function(r) { return r.error; }).length;
                        showToast('Exported ' + done + ' clips' + (failed ? ', ' + failed + ' failed' : ''), done > 0 ? 'success' : 'error');
                    } else {
                        showToast('Export failed: ' + (data.error || 'Unknown error'), 'error');
                    }
                } catch(e) {
                    showToast('Export failed: ' + e.message, 'error');
                }
            });
        });

        filterInput.addEventListener('input', function() {
            _codingState.filterText = this.value.toLowerCase();
            renderCodingTagList();
        });

        exportCsv.addEventListener('click', function() {
            exportCodingTags('csv');
        });
        exportJson.addEventListener('click', function() {
            exportCodingTags('json');
        });

        // Player select change
        document.getElementById('coding-player-select').addEventListener('change', function() {
            _codingState.selectedPlayer = parseInt(this.value, 10) || 0;
        });

        // Team select change
        document.getElementById('coding-team-select').addEventListener('change', function() {
            _codingState.selectedTeam = this.value;
        });

        // Period select change
        document.getElementById('coding-period-select').addEventListener('change', function() {
            _codingState.selectedPeriod = parseInt(this.value, 10) || 1;
        });

        // Lead/lag changes
        document.getElementById('coding-lead-ms').addEventListener('change', function() {
            _codingState.leadMs = parseInt(this.value, 10) || 2000;
        });
        document.getElementById('coding-lag-ms').addEventListener('change', function() {
            _codingState.lagMs = parseInt(this.value, 10) || 3000;
        });

        // Notes
        notesInput.addEventListener('change', function() {
            _codingState.notes = this.value;
        });

        // Timeline click to seek
        timelineCanvas.addEventListener('click', function(e) {
            var rect = this.getBoundingClientRect();
            var x = e.clientX - rect.left;
            var pct = x / rect.width;
            var video = document.getElementById('coding-video');
            if (video && video.duration) {
                video.currentTime = pct * video.duration;
            }
        });

        // Keyboard shortcuts for coding workspace
        document.addEventListener('keydown', function(e) {
            if (!_codingState.keyboardEnabled) return;
            if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT')) return;
            if (e.ctrlKey || e.metaKey || e.altKey) return;

            var key = e.key.toLowerCase();
            if (key === ' ' || key === 'k') {
                e.preventDefault();
                var vid = document.getElementById('coding-video');
                if (vid && vid.src) {
                    if (vid.paused) vid.play(); else vid.pause();
                }
                return;
            }
            if (key === 'arrowleft') {
                e.preventDefault();
                var vid = document.getElementById('coding-video');
                if (vid) vid.currentTime = Math.max(0, vid.currentTime - 3);
                return;
            }
            if (key === 'arrowright') {
                e.preventDefault();
                var vid = document.getElementById('coding-video');
                if (vid) vid.currentTime = Math.min(vid.duration || 0, vid.currentTime + 3);
                return;
            }

            // Matrix button shortcuts
            var shortcutMap = _codingState.shortcuts;
            if (shortcutMap[key]) {
                e.preventDefault();
                triggerTag(shortcutMap[key]);
            }
        });

        // Update current time from video
        var video = document.getElementById('coding-video');
        if (video) {
            video.addEventListener('timeupdate', function() {
                _codingState.currentTime = this.currentTime;
                updateCodingTimelineCursor();
                highlightTagAtTime(this.currentTime);
            });
        }

        // Load templates
        loadCodingTemplates();

        // Load match select initially
        loadCodingMatchSelect();
    }

    function loadCodingTemplates() {
        if (typeof bridge === 'undefined' || !bridge || !bridge.get_coding_templates) return;
        bridge.get_coding_templates(function(result) {
            try {
                var data = JSON.parse(result);
                if (data.success) {
                    _codingState.templates = data.templates;
                    renderCodingMatrix(data.templates);
                    // Build shortcut map
                    var shortcuts = {};
                    (data.templates.categories || []).forEach(function(cat) {
                        (cat.buttons || []).forEach(function(btn) {
                            if (btn.shortcut) shortcuts[btn.shortcut.toLowerCase()] = btn;
                        });
                    });
                    _codingState.shortcuts = shortcuts;
                }
            } catch(e) {
                console.warn('loadCodingTemplates:', e);
            }
        });
    }

    function renderCodingMatrix(templates) {
        var container = document.getElementById('coding-matrix');
        if (!container) return;
        container.innerHTML = '';
        (templates.categories || []).forEach(function(cat) {
            var catEl = document.createElement('div');
            catEl.className = 'coding-matrix-category';
            catEl.innerHTML = '<div class="coding-category-label" style="color:' + (cat.color || '#fff') + '">' + escapeHtml(cat.label) + '</div>';
            var grid = document.createElement('div');
            grid.className = 'coding-button-grid';
            (cat.buttons || []).forEach(function(btn) {
                var btnEl = document.createElement('button');
                btnEl.className = 'coding-matrix-btn';
                btnEl.style.background = btn.color || '#555';
                btnEl.dataset.eventType = btn.id;
                btnEl.dataset.shortcut = btn.shortcut || '';
                btnEl.innerHTML = escapeHtml(btn.label) + (btn.shortcut ? '<span class="shortcut-hint">' + escapeHtml(btn.shortcut) + '</span>' : '');
                btnEl.addEventListener('click', function() {
                    triggerTag(btn);
                });
                grid.appendChild(btnEl);
            });
            catEl.appendChild(grid);
            container.appendChild(catEl);
        });
    }

    function loadCodingWorkspace(matchId) {
        _codingState.matchId = matchId;
        _codingState.isLoading = true;

        var status = document.getElementById('coding-match-status');
        status.textContent = 'Loading...';

        // Get match info
        bridge.get_video_path(matchId, function(result) {
            try {
                var data = JSON.parse(result);
                if (data && data.video_path) {
                    var video = document.getElementById('coding-video');
                    video.src = data.video_path;
                    video.load();
                    _codingState.keyboardEnabled = true;
                    status.textContent = 'Ready';
                } else {
                    status.textContent = 'No video found';
                    showToast('No video found for this match.', 'warning');
                }
            } catch(e) {
                status.textContent = 'Error loading video';
                console.warn('loadCodingWorkspace video:', e);
            }
        });

        // Get match players
        if (bridge.get_coding_players) {
            bridge.get_coding_players(matchId, function(result) {
                try {
                    var data = JSON.parse(result);
                    if (data.success && data.players) {
                        var sel = document.getElementById('coding-player-select');
                        sel.innerHTML = '<option value="0">-- None --</option>';
                        data.players.forEach(function(p) {
                            sel.innerHTML += '<option value="' + p.track_id + '">' +
                                escapeHtml(p.name || 'Player ' + p.track_id) +
                                ' (#' + p.jersey + ')</option>';
                        });
                    }
                } catch(e) {}
            });
        }

        // Load existing tags
        bridge.get_coding_tags(matchId, function(result) {
            try {
                var data = JSON.parse(result);
                if (data.success) {
                    _codingState.tags = data.tags || [];
                    renderCodingTagList();
                    renderCodingTimeline();
                    updateCodingStats();
                }
            } catch(e) {
                console.warn('loadCodingWorkspace tags:', e);
            }
            _codingState.isLoading = false;

            // Show workspace
            document.getElementById('coding-workspace').classList.remove('hidden');
            document.getElementById('coding-empty-state').classList.add('hidden');

            showToast('Loaded ' + _codingState.tags.length + ' existing tags.', 'info');
        });
    }

    function triggerTag(btn) {
        if (!_codingState.matchId) {
            showToast('Select a match first.', 'warning');
            return;
        }

        var video = document.getElementById('coding-video');
        if (!video || !video.src) {
            showToast('No video loaded.', 'warning');
            return;
        }

        var videoTime = video.currentTime;
        var tag = {
            event_type: btn.id,
            sub_type: '',
            video_time: videoTime,
            player_track_id: _codingState.selectedPlayer,
            player_name: getSelectedPlayerName(),
            team: _codingState.selectedTeam,
            period: _codingState.selectedPeriod,
            notes: _codingState.notes || '',
            lead_ms: _codingState.leadMs,
            lag_ms: _codingState.lagMs,
        };

        // Flash effect on video
        var container = document.querySelector('.coding-video-container');
        container.classList.remove('coding-flash');
        void container.offsetWidth;
        container.classList.add('coding-flash');

        // Save via bridge
        bridge.save_coding_tag(_codingState.matchId, JSON.stringify(tag), function(result) {
            try {
                var data = JSON.parse(result);
                if (data.success) {
                    tag.id = data.tag_id;
                    _codingState.tags.push(tag);
                    renderCodingTagList();
                    renderCodingTimeline();
                    updateCodingStats();
                    updateCodingLastTag(btn.label || btn.id, videoTime);
                } else {
                    showToast('Failed to save tag: ' + (data.error || 'Unknown'), 'error');
                }
            } catch(e) {
                console.warn('triggerTag save:', e);
            }
        });
    }

    function getSelectedPlayerName() {
        var sel = document.getElementById('coding-player-select');
        if (!sel) return '';
        var opt = sel.options[sel.selectedIndex];
        return opt ? opt.text.split(' (#')[0] : '';
    }

    function renderCodingTagList() {
        var list = document.getElementById('coding-tag-list');
        if (!list) return;
        var filter = _codingState.filterText;
        var tags = _codingState.tags;

        if (filter) {
            tags = tags.filter(function(t) {
                return (t.event_type || '').toLowerCase().indexOf(filter) !== -1 ||
                       (t.player_name || '').toLowerCase().indexOf(filter) !== -1 ||
                       (t.notes || '').toLowerCase().indexOf(filter) !== -1;
            });
        }

        if (tags.length === 0) {
            list.innerHTML = '<div class="coding-tag-list-empty">' +
                (filter ? 'No tags match your filter.' : 'No tags yet. Click a matrix button to tag the current video time!') +
                '</div>';
            document.getElementById('coding-tag-count-badge').textContent = '0';
            return;
        }

        var html = '';
        tags.forEach(function(tag, idx) {
            var timeStr = formatCodingTime(tag.video_time || 0);
            var typeLabel = tag.event_type || 'unknown';
            var playerLabel = tag.player_name || '';
            var activeClass = tag.id === _codingState.activeTagId ? ' active' : '';
            var color = getTagColor(tag.event_type);

            html += '<div class="coding-tag-item' + activeClass + '" data-tag-id="' + tag.id + '" data-video-time="' + (tag.video_time || 0) + '">';
            html += '  <span class="tag-color-dot" style="background:' + color + '"></span>';
            html += '  <div class="tag-info">';
            html += '    <div class="tag-type">' + escapeHtml(typeLabel) + '</div>';
            html += '    <div class="tag-sub">' + escapeHtml(timeStr) + (playerLabel ? ' · ' + escapeHtml(playerLabel) : '') + '</div>';
            html += '  </div>';
            html += '  <div class="tag-time">' + timeStr + '</div>';
            html += '  <div class="tag-actions">';
            html += '    <button class="tag-action-btn tag-seek-btn" title="Seek to time">⏩</button>';
            html += '    <button class="tag-action-btn tag-clip-btn" title="Extract clip">✂️</button>';
            html += '    <button class="tag-action-btn tag-delete-btn" title="Delete tag">✕</button>';
            html += '  </div>';
            html += '</div>';
        });
        list.innerHTML = html;

        document.getElementById('coding-tag-count-badge').textContent = tags.length;

        // Wire up tag item clicks
        list.querySelectorAll('.coding-tag-item').forEach(function(item) {
            item.addEventListener('click', function(e) {
                if (e.target.closest('.tag-actions')) return;
                var time = parseFloat(this.dataset.videoTime);
                var video = document.getElementById('coding-video');
                if (video) video.currentTime = time;
                _codingState.activeTagId = parseInt(this.dataset.tagId, 10);
                renderCodingTagList();
            });

            // Seek button
            item.querySelector('.tag-seek-btn').addEventListener('click', function(e) {
                e.stopPropagation();
                var time = parseFloat(item.dataset.videoTime);
                var video = document.getElementById('coding-video');
                if (video) video.currentTime = time;
            });

            // Clip button
            item.querySelector('.tag-clip-btn').addEventListener('click', function(e) {
                e.stopPropagation();
                var tagId = parseInt(item.dataset.tagId, 10);
                if (!tagId) return;
                showToast('Extracting clip...', 'info');
                bridge.extract_tag_clip(_codingState.matchId, tagId, function(result) {
                    try {
                        var data = JSON.parse(result);
                        if (data.success) {
                            showToast('Clip saved: ' + data.clip_path, 'success');
                        } else {
                            showToast('Failed: ' + (data.error || 'Unknown'), 'error');
                        }
                    } catch(e) {
                        showToast('Clip extraction failed.', 'error');
                    }
                });
            });

            // Delete button
            item.querySelector('.tag-delete-btn').addEventListener('click', function(e) {
                e.stopPropagation();
                var tagId = parseInt(item.dataset.tagId, 10);
                if (!tagId) return;
                showConfirmDialog('Delete this tag?', function() {
                    bridge.delete_coding_tag(tagId, function(result) {
                        try {
                            var data = JSON.parse(result);
                            if (data.success) {
                                _codingState.tags = _codingState.tags.filter(function(t) { return t.id !== tagId; });
                                renderCodingTagList();
                                renderCodingTimeline();
                                updateCodingStats();
                            } else {
                                showToast('Failed to delete tag.', 'error');
                            }
                        } catch(e) {}
                    });
                });
            });
        });
    }

    function renderCodingTimeline() {
        var canvas = document.getElementById('coding-timeline-canvas');
        if (!canvas) return;
        var video = document.getElementById('coding-video');
        var duration = video && video.duration ? video.duration : 90 * 60;

        var rect = canvas.parentElement.getBoundingClientRect();
        canvas.width = rect.width || 600;
        canvas.height = 40;

        var ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Background
        ctx.fillStyle = '#1e293b';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Time markers
        var markerInterval = Math.max(60, Math.floor(duration / 10));
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1;
        ctx.font = '9px monospace';
        ctx.fillStyle = '#64748b';
        for (var t = 0; t <= duration; t += markerInterval) {
            var x = (t / duration) * canvas.width;
            ctx.beginPath();
            ctx.moveTo(x, 24);
            ctx.lineTo(x, 40);
            ctx.stroke();
            ctx.fillText(formatCodingTime(t), x + 2, 35);
        }

        // Tag markers
        (_codingState.tags || []).forEach(function(tag) {
            var time = tag.video_time || 0;
            var x = (time / duration) * canvas.width;
            var color = getTagColor(tag.event_type);

            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(x, 12, 5, 0, Math.PI * 2);
            ctx.fill();

            // Active tag highlight
            if (tag.id === _codingState.activeTagId) {
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(x, 12, 8, 0, Math.PI * 2);
                ctx.stroke();
            }
        });

        // Current time cursor
        if (video && video.currentTime != null) {
            var cursorX = (video.currentTime / duration) * canvas.width;
            ctx.strokeStyle = '#fbbf24';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(cursorX, 0);
            ctx.lineTo(cursorX, 40);
            ctx.stroke();
        }

        // Labels
        var labels = document.getElementById('coding-timeline-labels');
        if (labels) {
            labels.innerHTML = '0:00';
            var half = Math.floor(duration / 2);
            labels.innerHTML += '<span>' + formatCodingTime(half) + '</span>';
            labels.innerHTML += '<span>' + formatCodingTime(duration) + '</span>';
        }
    }

    function updateCodingTimelineCursor() {
        renderCodingTimeline();
    }

    function highlightTagAtTime(time) {
        var tags = _codingState.tags;
        var closest = null;
        var closestDist = Infinity;
        tags.forEach(function(tag) {
            var dist = Math.abs((tag.video_time || 0) - time);
            if (dist < closestDist) {
                closestDist = dist;
                closest = tag;
            }
        });
        var activeId = closest && closestDist < 5 ? closest.id : null;
        if (activeId !== _codingState.activeTagId) {
            _codingState.activeTagId = activeId;
            renderCodingTagList();
        }
    }

    function updateCodingStats() {
        var count = _codingState.tags.length;
        document.getElementById('coding-tag-count').textContent = count;
    }

    function updateCodingLastTag(type, time) {
        var el = document.getElementById('coding-last-tag');
        if (el) {
            el.innerHTML = 'Last: <strong>' + escapeHtml(type) + '</strong> at ' + formatCodingTime(time);
        }
    }

    function formatCodingTime(seconds) {
        if (seconds == null || !isFinite(seconds)) return '0:00';
        var m = Math.floor(seconds / 60);
        var s = Math.floor(seconds % 60);
        return m + ':' + (s < 10 ? '0' : '') + s;
    }

    function getTagColor(eventType) {
        if (!eventType) return '#64748b';
        // Map common event types to colors
        var colorMap = {
            'pass': '#22c55e',
            'through_ball': '#4ade80',
            'shot': '#ef4444',
            'goal': '#dc2626',
            'dribble': '#3b82f6',
            'cross': '#60a5fa',
            'carry': '#818cf8',
            'key_pass': '#a3e635',
            'tackle': '#f97316',
            'interception': '#fb923c',
            'press': '#a855f7',
            'clearance': '#c084fc',
            'block': '#e879f9',
            'foul': '#f43f5e',
            'error_positional': '#92400e',
            'error_technical': '#b45309',
            'error_decision': '#d97706',
            'error_physical': '#f59e0b',
            'missed_tackle': '#ef4444',
            'bad_pass': '#fca5a5',
            'corner': '#06b6d4',
            'free_kick': '#22d3ee',
            'throw_in': '#67e8f9',
            'goal_kick': '#a5f3fc',
            'penalty': '#2dd4bf',
        };
        return colorMap[eventType] || '#64748b';
    }

    function escapeHtml(str) {
        if (typeof str !== 'string') return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function exportCodingTags(format) {
        if (_codingState.tags.length === 0) {
            showToast('No tags to export.', 'warning');
            return;
        }

        if (format === 'csv') {
            var headers = 'id,event_type,video_time,player_name,team,period,notes,lead_ms,lag_ms';
            var rows = _codingState.tags.map(function(t) {
                return (t.id || '') + ',' +
                       (t.event_type || '') + ',' +
                       (t.video_time || 0) + ',' +
                       '"' + (t.player_name || '') + '",' +
                       (t.team || '') + ',' +
                       (t.period || 1) + ',' +
                       '"' + (t.notes || '').replace(/"/g, '""') + '",' +
                       (t.lead_ms || 2000) + ',' +
                       (t.lag_ms || 3000);
            });
            var csv = headers + '\n' + rows.join('\n');
            downloadFile(csv, 'coding_tags_' + _codingState.matchId + '.csv', 'text/csv');
        } else {
            var json = JSON.stringify(_codingState.tags, null, 2);
            downloadFile(json, 'coding_tags_' + _codingState.matchId + '.json', 'application/json');
        }

        showToast('Exported ' + _codingState.tags.length + ' tags.', 'success');
    }

    function downloadFile(content, filename, mimeType) {
        var blob = new Blob([content], { type: mimeType });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // ── Tactical Periods + Formation (Phase 2.3-2.4) ────────────────

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
                } catch(e) { console.warn(e); }
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
            } catch(e) { status.textContent = 'Error loading phases.'; console.warn(e); }
        });

        bridge.analyze_formation(matchId, function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                renderFormation(data);
            } catch(e) { console.warn(e); }
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

    // ── AI Chat (Phase 3) ──────────────────────────────────────────

    function initAiWorkspace() {
        var askBtn = document.getElementById('ai-ask-btn');
        var input = document.getElementById('ai-question-input');
        var matchSelect = document.getElementById('ai-match-select');
        if (!askBtn) return;

        window.loadAiMatchSelect = function() {
            if (typeof bridge === 'undefined' || !bridge) return;
            bridge.get_all_matches(function(result) {
                try {
                    var data = typeof result === 'string' ? JSON.parse(result) : result;
                    if (data.error) data = [];
                    var sel = document.getElementById('ai-match-select');
                    sel.innerHTML = '<option value="">-- Select Match --</option>';
                    (data || []).forEach(function(m) {
                        var name = m.name || (m.home_team + ' vs ' + m.away_team) || 'Match #' + m.id;
                        sel.innerHTML += '<option value="' + m.id + '">' + escapeHtml(name) + '</option>';
                    });
                } catch(e) { console.warn(e); }
            });
        };

        function askQuestion() {
            var matchId = parseInt(matchSelect.value, 10);
            var question = input.value.trim();
            if (!matchId) { showToast('Select a match first.', 'warning'); return; }
            if (!question) { showToast('Enter a question.', 'warning'); return; }

            var messages = document.getElementById('ai-chat-messages');
            messages.innerHTML += '<div class="ai-message user">' + escapeHtml(question) + '</div>';
            messages.innerHTML += '<div class="ai-message assistant ai-typing" id="ai-typing-msg">Thinking</div>';
            messages.scrollTop = messages.scrollHeight;
            input.value = '';

            bridge.ask_llm(matchId, question, function(result) {
                try {
                    var data = typeof result === 'string' ? JSON.parse(result) : result;
                    var typing = document.getElementById('ai-typing-msg');
                    if (typing) typing.remove();

                    if (data.success) {
                        messages.innerHTML += '<div class="ai-message assistant">' + escapeHtml(data.answer) + '</div>';
                    } else {
                        messages.innerHTML += '<div class="ai-message assistant" style="color:var(--danger)">Error: ' + escapeHtml(data.error || 'Unknown') + '</div>';
                    }
                    messages.scrollTop = messages.scrollHeight;
                } catch(e) {
                    var typing2 = document.getElementById('ai-typing-msg');
                    if (typing2) typing2.remove();
                    messages.innerHTML += '<div class="ai-message assistant" style="color:var(--danger)">Failed to get answer.</div>';
                }
            });

            // Update LLM status
            var status = document.getElementById('ai-llm-status');
            if (status) {
                bridge.check_llm_availability(function(r) {
                    try {
                        var d = JSON.parse(r);
                        status.textContent = d.ollama ? '🟢 LLM: ' + d.model : '🔴 LLM: Unavailable';
                    } catch(e) { status.textContent = '🔴 LLM: Unavailable'; }
                });
            }
        }

        askBtn.addEventListener('click', askQuestion);
        input.addEventListener('keydown', function(e) { if (e.key === 'Enter') askQuestion(); });

        loadAiMatchSelect();

        // Check LLM status on init
        var status = document.getElementById('ai-llm-status');
        if (status && typeof bridge !== 'undefined' && bridge) {
            bridge.check_llm_availability(function(r) {
                try {
                    var d = JSON.parse(r);
                    status.textContent = d.ollama ? '🟢 LLM: ' + d.model : '🔴 LLM: Unavailable (install Ollama)';
                } catch(e) { status.textContent = '🔴 LLM: Unavailable'; }
            });
        }
    }

    // ── Squad + Player Ratings (Phase 4) ───────────────────────────

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
                } catch(e) { console.warn(e); }
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
            } catch(e) { status.textContent = 'Error loading squad.'; console.warn(e); return; }
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

    // ── Event Review Workspace (Phase 2) ─────────────────────────

    var _reviewState = {
        matchId: null,
        events: [],
        queue: [],
        currentIndex: -1,
        video: null,
        autoAdvance: true,
        isLoading: false,
    };

    function initReviewWorkspace() {
        var loadBtn = document.getElementById('review-load-btn');
        var matchSelect = document.getElementById('review-match-select');
        var autoAdvBtn = document.getElementById('review-auto-advance-btn');
        var typeFilter = document.getElementById('review-type-filter');
        var confirmBtn = document.getElementById('review-confirm-btn');
        var editBtn = document.getElementById('review-edit-btn');
        var rejectBtn = document.getElementById('review-reject-btn');
        var seekBtn = document.getElementById('review-seek-btn');
        var prevBtn = document.getElementById('review-prev-btn');
        var nextBtn = document.getElementById('review-next-btn');
        var saveEditBtn = document.getElementById('review-save-edit-btn');

        if (!loadBtn) return;

        window.loadReviewMatchSelect = function() {
            if (typeof bridge === 'undefined' || !bridge) return;
            bridge.get_all_matches(function(result) {
                try {
                    var data = typeof result === 'string' ? JSON.parse(result) : result;
                    if (data.error) data = [];
                    var sel = document.getElementById('review-match-select');
                    sel.innerHTML = '<option value="">-- Select Match --</option>';
                    (data || []).forEach(function(m) {
                        var name = m.name || (m.home_team + ' vs ' + m.away_team) || 'Match #' + m.id;
                        sel.innerHTML += '<option value="' + m.id + '">' + escapeHtml(name) + '</option>';
                    });
                } catch(e) { console.warn('loadReviewMatchSelect:', e); }
            });
        };

        loadBtn.addEventListener('click', function() {
            var matchId = parseInt(matchSelect.value, 10);
            if (!matchId) { showToast('Select a match first.', 'warning'); return; }
            loadReviewWorkspace(matchId);
        });

        autoAdvBtn.addEventListener('click', function() {
            _reviewState.autoAdvance = !_reviewState.autoAdvance;
            this.classList.toggle('btn-primary');
            this.classList.toggle('btn-secondary');
            this.innerHTML = _reviewState.autoAdvance ? '⏩ Auto-Advance: ON' : '⏩ Auto-Advance: OFF';
        });

        typeFilter.addEventListener('change', function() {
            renderReviewQueue();
        });

        confirmBtn.addEventListener('click', function() {
            if (_reviewState.currentIndex < 0) return;
            var item = _reviewState.queue[_reviewState.currentIndex];
            submitReviewAction(item.id, 'confirm', '', function() {
                removeFromQueue(_reviewState.currentIndex);
            });
        });

        editBtn.addEventListener('click', function() {
            var fields = document.getElementById('review-edit-fields');
            fields.classList.toggle('hidden');
            if (!fields.classList.contains('hidden')) {
                populateEditFields();
            }
        });

        saveEditBtn.addEventListener('click', function() {
            var item = _reviewState.queue[_reviewState.currentIndex];
            if (!item) return;
            var corrections = {
                event_type: document.getElementById('review-edit-type').value,
                team: document.getElementById('review-edit-team').value,
                completed: document.getElementById('review-edit-completed').checked,
            };
            submitReviewAction(item.id, 'edit', JSON.stringify(corrections), function() {
                document.getElementById('review-edit-fields').classList.add('hidden');
                removeFromQueue(_reviewState.currentIndex);
            });
        });

        rejectBtn.addEventListener('click', function() {
            if (_reviewState.currentIndex < 0) return;
            var item = _reviewState.queue[_reviewState.currentIndex];
            showConfirmDialog('Reject this auto-detected event? It will be deleted.', function() {
                submitReviewAction(item.id, 'reject', '', function() {
                    removeFromQueue(_reviewState.currentIndex);
                });
            });
        });

        seekBtn.addEventListener('click', function() {
            if (_reviewState.currentIndex < 0) return;
            var item = _reviewState.queue[_reviewState.currentIndex];
            var video = document.getElementById('review-video');
            if (video && item.video_time != null) {
                video.currentTime = item.video_time;
            }
        });

        prevBtn.addEventListener('click', function() {
            navigateReview(-1);
        });
        nextBtn.addEventListener('click', function() {
            navigateReview(1);
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT')) return;
            if (e.ctrlKey || e.metaKey || e.altKey) return;
            var section = document.getElementById('review-section');
            if (!section || section.classList.contains('hidden')) return;

            switch (e.key) {
                case 'Enter':
                    e.preventDefault();
                    confirmBtn.click();
                    break;
                case 'Delete':
                case 'd':
                    e.preventDefault();
                    rejectBtn.click();
                    break;
                case 'e':
                    e.preventDefault();
                    editBtn.click();
                    break;
                case 'ArrowLeft':
                    prevBtn.click();
                    break;
                case 'ArrowRight':
                    nextBtn.click();
                    break;
                case ' ':
                case 'k':
                    e.preventDefault();
                    var vid = document.getElementById('review-video');
                    if (vid && vid.src) { if (vid.paused) vid.play(); else vid.pause(); }
                    break;
            }
        });

        // Video timeupdate to highlight current event
        var video = document.getElementById('review-video');
        if (video) {
            video.addEventListener('timeupdate', function() {
                highlightReviewEventAtTime(this.currentTime);
            });
        }

        loadReviewMatchSelect();
    }

    function loadReviewWorkspace(matchId) {
        _reviewState.matchId = matchId;
        _reviewState.isLoading = true;

        var status = document.getElementById('review-match-status');
        status.textContent = 'Loading...';

        // Load video
        bridge.get_video_path(matchId, function(result) {
            try {
                var data = JSON.parse(result);
                if (data && data.video_path) {
                    var video = document.getElementById('review-video');
                    video.src = data.video_path;
                    video.load();
                    _reviewState.video = video;
                    status.textContent = 'Ready';
                } else {
                    status.textContent = 'No video';
                }
            } catch(e) {
                status.textContent = 'Error';
                console.warn(e);
            }
        });

        // Load events + detection summary
        loadReviewEvents(matchId);
    }

    function loadReviewEvents(matchId) {
        bridge.get_match_events(matchId, function(result) {
            try {
                var data = JSON.parse(result);
                _reviewState.events = Array.isArray(data) ? data : (data.events || []);
            } catch(e) { _reviewState.events = []; }

            // Separate unreviewed (low confidence, not user_corrected)
            _reviewState.queue = _reviewState.events.filter(function(ev) {
                return !ev.user_corrected && (ev.confidence == null || ev.confidence < 0.7);
            });
            _reviewState.queue.sort(function(a, b) {
                return (a.confidence || 0) - (b.confidence || 0);
            });

            _reviewState.currentIndex = _reviewState.queue.length > 0 ? 0 : -1;

            // Show workspace
            document.getElementById('review-workspace').classList.remove('hidden');
            document.getElementById('review-empty-state').classList.add('hidden');

            renderReviewSummary();
            renderReviewQueue();
            renderReviewEventDetail();
            updateReviewNavButtons();

            _reviewState.isLoading = false;
            status.textContent = _reviewState.queue.length + ' events need review';
        });
    }

    function renderReviewSummary() {
        var container = document.getElementById('review-summary-content');
        if (!container) return;

        var total = _reviewState.events.length;
        var unreviewed = _reviewState.queue.length;
        var corrected = total - unreviewed;
        var pct = total > 0 ? Math.round(corrected / total * 100) : 0;

        // Count by type
        var byType = {};
        _reviewState.events.forEach(function(ev) {
            var t = ev.event_type || 'unknown';
            if (!byType[t]) byType[t] = { total: 0, unreviewed: 0 };
            byType[t].total++;
            if (!ev.user_corrected && (ev.confidence == null || ev.confidence < 0.7)) {
                byType[t].unreviewed++;
            }
        });

        var typeNames = Object.keys(byType).sort();
        var breakdownHtml = '';
        typeNames.forEach(function(t) {
            var stats = byType[t];
            var barW = stats.total > 0 ? Math.round((stats.total - stats.unreviewed) / stats.total * 100) : 0;
            breakdownHtml += '<div class="review-breakdown-row">' +
                '<span>' + escapeHtml(t) + '</span>' +
                '<span>' + stats.unreviewed + '/' + stats.total + '</span>' +
                '</div>';
        });

        container.innerHTML =
            '<div class="review-summary-stats">' +
                '<div class="review-summary-stat"><div class="stat-value">' + total + '</div><div class="stat-label">Total</div></div>' +
                '<div class="review-summary-stat"><div class="stat-value ' + (unreviewed > 0 ? 'danger' : 'success') + '">' + unreviewed + '</div><div class="stat-label">To Review</div></div>' +
                '<div class="review-summary-stat"><div class="stat-value success">' + corrected + '</div><div class="stat-label">Reviewed</div></div>' +
                '<div class="review-summary-stat"><div class="stat-value">' + pct + '%</div><div class="stat-label">Progress</div></div>' +
            '</div>' +
            '<div class="review-summary-breakdown">' + breakdownHtml + '</div>';
    }

    function renderReviewQueue() {
        var list = document.getElementById('review-queue-list');
        var count = document.getElementById('review-queue-count');
        if (!list) return;

        var filter = document.getElementById('review-type-filter').value;
        var queue = _reviewState.queue;
        if (filter) {
            queue = queue.filter(function(ev) { return ev.event_type === filter; });
        }

        count.textContent = queue.length;

        if (queue.length === 0) {
            list.innerHTML = '<div class="review-queue-empty">All events reviewed! 🎉</div>';
            return;
        }

        // Populate type filter options if not done
        var typeFilter = document.getElementById('review-type-filter');
        if (typeFilter.options.length <= 1) {
            var types = {};
            _reviewState.queue.forEach(function(ev) {
                var t = ev.event_type || 'unknown';
                types[t] = true;
            });
            Object.keys(types).sort().forEach(function(t) {
                typeFilter.innerHTML += '<option value="' + escapeHtml(t) + '">' + escapeHtml(t) + '</option>';
            });
        }

        var html = '';
        queue.forEach(function(ev, idx) {
            var globalIdx = _reviewState.queue.indexOf(ev);
            var isActive = globalIdx === _reviewState.currentIndex;
            var conf = ev.confidence || 0;
            var confClass = conf < 0.3 ? 'q-conf-low' : (conf < 0.5 ? 'q-conf-mid' : 'q-conf-high');
            var timeStr = formatCodingTime(ev.timestamp || 0);
            var typeLabel = ev.event_type || 'unknown';
            var teamLabel = ev.team || '';

            html += '<div class="review-queue-item' + (isActive ? ' active' : '') + '" data-event-id="' + ev.id + '" data-idx="' + globalIdx + '">' +
                '<div class="q-type">' + escapeHtml(typeLabel) + '</div>' +
                '<div class="q-time">' + timeStr + (teamLabel ? ' · ' + escapeHtml(teamLabel) : '') + '</div>' +
                '<div class="q-conf ' + confClass + '">' + conf.toFixed(2) + '</div>' +
                '</div>';
        });
        list.innerHTML = html;

        // Click to select
        list.querySelectorAll('.review-queue-item').forEach(function(item) {
            item.addEventListener('click', function() {
                var idx = parseInt(this.dataset.idx, 10);
                if (!isNaN(idx)) {
                    _reviewState.currentIndex = idx;
                    renderReviewQueue();
                    renderReviewEventDetail();
                    updateReviewNavButtons();
                    seekToReviewEvent();
                }
            });
        });
    }

    function renderReviewEventDetail() {
        var detailContainer = document.getElementById('review-event-detail');
        var infoContainer = document.getElementById('review-event-details');
        var badge = document.getElementById('review-confidence-badge');
        var confirmBtn = document.getElementById('review-confirm-btn');
        var editBtn = document.getElementById('review-edit-btn');
        var rejectBtn = document.getElementById('review-reject-btn');
        var seekBtn = document.getElementById('review-seek-btn');

        var idx = _reviewState.currentIndex;
        if (idx < 0 || idx >= _reviewState.queue.length) {
            detailContainer.innerHTML = '<div class="review-detail-empty">All events reviewed! 🎉</div>';
            infoContainer.innerHTML = '<p class="review-detail-placeholder">No event selected.</p>';
            badge.textContent = '--';
            badge.className = 'review-confidence-badge';
            confirmBtn.disabled = true;
            editBtn.disabled = true;
            rejectBtn.disabled = true;
            seekBtn.disabled = true;
            return;
        }

        confirmBtn.disabled = false;
        editBtn.disabled = false;
        rejectBtn.disabled = false;
        seekBtn.disabled = false;

        var ev = _reviewState.queue[idx];
        var conf = ev.confidence || 0;
        var confClass = conf < 0.3 ? 'low' : (conf < 0.5 ? 'mid' : 'high');
        badge.textContent = 'Conf: ' + conf.toFixed(3);
        badge.className = 'review-confidence-badge ' + confClass;

        // Detail in center panel
        var meta = ev._meta || {};
        var metaHtml = '';
        if (meta && typeof meta === 'object') {
            Object.keys(meta).slice(0, 8).forEach(function(k) {
                var v = typeof meta[k] === 'object' ? JSON.stringify(meta[k]) : meta[k];
                metaHtml += '<div class="detail-row"><span class="detail-label">' + escapeHtml(k) + '</span><span class="detail-value">' + escapeHtml(String(v)) + '</span></div>';
            });
        }

        detailContainer.innerHTML = '<div class="review-detail-content">' +
            '<div class="detail-row"><span class="detail-label">Type</span><span class="detail-value">' + escapeHtml(ev.event_type || 'unknown') + '</span></div>' +
            '<div class="detail-row"><span class="detail-label">Time</span><span class="detail-value">' + formatCodingTime(ev.timestamp || 0) + '</span></div>' +
            '<div class="detail-row"><span class="detail-label">Team</span><span class="detail-value">' + escapeHtml(ev.team || '--') + '</span></div>' +
            '<div class="detail-row"><span class="detail-label">Completed</span><span class="detail-value">' + (ev.completed ? 'Yes' : 'No') + '</span></div>' +
            (ev.from_track_id ? '<div class="detail-row"><span class="detail-label">Player</span><span class="detail-value">#' + ev.from_track_id + '</span></div>' : '') +
            (conf < 0.35 ? '<div class="detail-row" style="color:var(--warning);font-size:0.75rem">⚠ Low confidence — likely needs review</div>' : '') +
            '</div>';

        // Info in right panel
        infoContainer.innerHTML =
            '<div class="detail-row"><span class="detail-label">Event ID</span><span class="detail-value">#' + ev.id + '</span></div>' +
            '<div class="detail-row"><span class="detail-label">Type</span><span class="detail-value">' + escapeHtml(ev.event_type || 'unknown') + '</span></div>' +
            '<div class="detail-row"><span class="detail-label">Timestamp</span><span class="detail-value">' + (ev.timestamp ? ev.timestamp.toFixed(2) + 's' : '--') + '</span></div>' +
            '<div class="detail-row"><span class="detail-label">Team</span><span class="detail-value">' + escapeHtml(ev.team || '--') + '</span></div>' +
            '<div class="detail-row"><span class="detail-label">Player</span><span class="detail-value">' + (ev.from_track_id ? '#' + ev.from_track_id : '--') + '</span></div>' +
            '<div class="detail-row"><span class="detail-label">Confidence</span><span class="detail-value">' + (conf * 100).toFixed(1) + '%</span></div>' +
            '<div class="detail-row"><span class="detail-label">Completed</span><span class="detail-value">' + (ev.completed ? 'Yes' : 'No') + '</span></div>' +
            (metaHtml ? '<hr style="margin:6px 0;border-color:var(--border)">' + metaHtml : '');
    }

    function updateReviewNavButtons() {
        var prevBtn = document.getElementById('review-prev-btn');
        var nextBtn = document.getElementById('review-next-btn');
        var pos = document.getElementById('review-position');
        var idx = _reviewState.currentIndex;
        var total = _reviewState.queue.length;

        prevBtn.disabled = idx <= 0;
        nextBtn.disabled = idx >= total - 1 || total === 0;
        pos.textContent = total > 0 ? (idx + 1) + ' / ' + total : '0 / 0';
    }

    function navigateReview(direction) {
        var newIdx = _reviewState.currentIndex + direction;
        if (newIdx < 0 || newIdx >= _reviewState.queue.length) return;
        _reviewState.currentIndex = newIdx;
        renderReviewQueue();
        renderReviewEventDetail();
        updateReviewNavButtons();
        seekToReviewEvent();
    }

    function seekToReviewEvent() {
        var idx = _reviewState.currentIndex;
        if (idx < 0) return;
        var ev = _reviewState.queue[idx];
        var video = document.getElementById('review-video');
        if (video && ev.timestamp != null) {
            time = Math.max(0, (ev.timestamp || 0) - 2);
            video.currentTime = time;
        }
    }

    function highlightReviewEventAtTime(time) {
        // Highlight nearest unreviewed event within 3 seconds
        var closest = -1;
        var closestDist = 3;
        _reviewState.queue.forEach(function(ev, idx) {
            var dist = Math.abs((ev.timestamp || 0) - time);
            if (dist < closestDist) {
                closestDist = dist;
                closest = idx;
            }
        });
        if (closest >= 0 && closest !== _reviewState.currentIndex) {
            _reviewState.currentIndex = closest;
            renderReviewQueue();
            renderReviewEventDetail();
            updateReviewNavButtons();
        }
    }

    function submitReviewAction(eventId, action, correctionsJson, callback) {
        var mid = _reviewState.matchId;
        bridge.submit_event_correction(mid, eventId, action, correctionsJson, function(result) {
            try {
                var data = JSON.parse(result);
                if (data.success) {
                    showToast('Event ' + data.action + '!', 'success');
                    if (callback) callback();
                } else {
                    showToast('Failed: ' + (data.error || 'Unknown'), 'error');
                }
            } catch(e) {
                showToast('Error submitting correction.', 'error');
            }
        });
    }

    function removeFromQueue(idx) {
        _reviewState.queue.splice(idx, 1);
        if (_reviewState.queue.length === 0) {
            _reviewState.currentIndex = -1;
        } else if (idx >= _reviewState.queue.length) {
            _reviewState.currentIndex = _reviewState.queue.length - 1;
        }
        renderReviewSummary();
        renderReviewQueue();
        renderReviewEventDetail();
        updateReviewNavButtons();

        // Auto-advance to next
        if (_reviewState.autoAdvance && _reviewState.currentIndex >= 0) {
            seekToReviewEvent();
        }

        // Recalculate status
        var status = document.getElementById('review-match-status');
        if (status) {
            status.textContent = _reviewState.queue.length + ' events need review';
        }
    }

    function populateEditFields() {
        var idx = _reviewState.currentIndex;
        if (idx < 0) return;
        var ev = _reviewState.queue[idx];

        // Populate type dropdown
        var typeSel = document.getElementById('review-edit-type');
        var allTypes = ['pass', 'shot', 'goal', 'tackle', 'interception', 'dribble', 'corner',
            'free_kick', 'throw_in', 'clearance', 'cross', 'block', 'carry', 'duel',
            'foul', 'offside', 'hand_ball', 'yellow_card', 'red_card', 'save', 'ball_out'];
        typeSel.innerHTML = '';
        allTypes.forEach(function(t) {
            typeSel.innerHTML += '<option value="' + t + '"' + (t === ev.event_type ? ' selected' : '') + '>' + t + '</option>';
        });

        document.getElementById('review-edit-team').value = ev.team || 'home';
        document.getElementById('review-edit-completed').checked = !!ev.completed;
    }

    // ── End Event Review Workspace ──────────────────────────────

    document.addEventListener('change', function(e) {
        if (e.target.id === 'timeline-filter-type') {
            _timelinePageState.page = 1;
            renderTimeline(window._timelineEvents || []);
        }
        // Per-page select
        if (e.target.classList.contains('per-page-select')) {
            _timelinePageState.perPage = parseInt(e.target.value, 10);
            _timelinePageState.page = 1;
            renderTimelineTable(window._timelineEvents || []);
        }
    });

    document.addEventListener('input', function(e) {
        // Column filter inputs in table header
        if (e.target.classList.contains('col-filter-input')) {
            var key = e.target.dataset.filterKey;
            _timelineFilters[key] = e.target.value;
            _timelinePageState.page = 1;
            renderTimelineTable(window._timelineEvents || []);
        }
        // Timeline search input
        if (e.target.id === 'timeline-search') {
            _timelineSearchText = e.target.value;
            _timelinePageState.page = 1;
            renderTimeline(window._timelineEvents || []);
        }
        // Roster search input
        if (e.target.id === 'roster-search') {
            _rosterSearchText = e.target.value;
            _rosterPageState.page = 1;
            if (_currentRosterView === 'roster-table') {
                renderRosterTable();
            } else {
                loadPlayerProfiles();
            }
        }
    });

    // ── Roster table rendering ──────────────────────────────

    function renderRosterTable() {
        var wrapper = document.getElementById('player-roster-table-wrapper');
        var roster = document.getElementById('player-roster');
        if (!wrapper) return;
        if (!roster) return;
        roster.classList.add('hidden');
        wrapper.classList.remove('hidden');

        var data = window._rosterData || [];
        var text = (_rosterSearchText || '').toLowerCase().trim();
        if (text) {
            data = data.filter(function(p) {
                return (p.name || '').toLowerCase().indexOf(text) >= 0 ||
                       (p.position || '').toLowerCase().indexOf(text) >= 0;
            });
        }

        var key = _rosterSortState.key;
        var dir = _rosterSortState.dir === 'asc' ? 1 : -1;
        data.sort(function(a, b) {
            var va = a[key] != null ? a[key] : '';
            var vb = b[key] != null ? b[key] : '';
            if (typeof va === 'string') return va.localeCompare(vb) * dir;
            return (va - vb) * dir;
        });

        var perPage = _rosterPageState.perPage || 25;
        var total = data.length;
        var totalPages = Math.max(1, Math.ceil(total / perPage));
        var page = Math.min(_rosterPageState.page, totalPages);
        var start = (page - 1) * perPage;
        var pageData = data.slice(start, start + perPage);

        var sortKey = _rosterSortState.key;
        var sortDir = _rosterSortState.dir;

        var html = '<table class="data-table" id="roster-data-table"><thead><tr>';
        var rosterCols = [
            { key: 'name', label: 'Name', filterable: true },
            { key: 'position', label: 'Position', filterable: true },
            { key: 'minutes', label: 'Minutes', filterable: false },
            { key: 'xg', label: 'xG', filterable: false },
            { key: 'xa', label: 'xA', filterable: false },
            { key: 'pass_pct', label: 'Pass%', filterable: false },
            { key: 'rating', label: 'Rating', filterable: false },
        ];
        rosterCols.forEach(function(col) {
            var isSorted = sortKey === col.key;
            var sortClass = isSorted ? (sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc') : '';
            html += '<th class="sortable ' + sortClass + '" data-roster-sort="' + col.key + '">' +
                '<span class="th-label">' + col.label + '</span><span class="sort-indicator"></span></th>';
        });
        html += '</tr></thead><tbody>';

        if (pageData.length === 0) {
            html += '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:1.5rem">No players match filters</td></tr>';
        } else {
            pageData.forEach(function(p) {
                html += '<tr>';
                html += '<td>' + escapeHtml(p.name || '') + '</td>';
                html += '<td>' + escapeHtml(p.position || '') + '</td>';
                html += '<td class="numeric">' + (p.minutes != null ? p.minutes : '--') + '</td>';
                html += '<td class="numeric">' + (p.xg != null ? p.xg.toFixed(3) : '--') + '</td>';
                html += '<td class="numeric">' + (p.xa != null ? p.xa.toFixed(3) : '--') + '</td>';
                html += '<td class="numeric">' + (p.pass_pct != null ? p.pass_pct.toFixed(1) + '%' : '--') + '</td>';
                html += '<td class="numeric">' + (p.rating != null ? p.rating.toFixed(1) : '--') + '</td>';
                html += '</tr>';
            });
        }
        html += '</tbody></table>';

        // Pagination
        html += '<div class="data-table-pagination">';
        html += '<span class="pagination-info">Showing ' + (total > 0 ? (start + 1) + '-' + Math.min(start + perPage, total) : 0) + ' of ' + total + ' players</span>';
        html += '<div class="pagination-controls">';
        html += '<button class="pagination-btn" data-roster-page="prev" ' + (page <= 1 ? 'disabled' : '') + '>&#9664;</button>';
        var maxB = 5, sP = Math.max(1, page - Math.floor(maxB / 2)), eP = Math.min(totalPages, sP + maxB - 1);
        if (eP - sP < maxB - 1) sP = Math.max(1, eP - maxB + 1);
        if (sP > 1) html += '<button class="pagination-btn" data-roster-page="1">1</button>' + (sP > 2 ? '<span style="color:var(--text-muted);padding:0 2px">...</span>' : '');
        for (var pi = sP; pi <= eP; pi++) {
            html += '<button class="pagination-btn ' + (pi === page ? 'active' : '') + '" data-roster-page="' + pi + '">' + pi + '</button>';
        }
        if (eP < totalPages) html += (eP < totalPages - 1 ? '<span style="color:var(--text-muted);padding:0 2px">...</span>' : '') + '<button class="pagination-btn" data-roster-page="' + totalPages + '">' + totalPages + '</button>';
        html += '<button class="pagination-btn" data-roster-page="next" ' + (page >= totalPages ? 'disabled' : '') + '>&#9654;</button>';
        html += '<select class="per-page-select">';
        [25, 50, 100].forEach(function(pp) {
            html += '<option value="' + pp + '" ' + (pp === perPage ? 'selected' : '') + '>' + pp + ' / page</option>';
        });
        html += '</select></div></div>';

        wrapper.innerHTML = html;
    }

    // ── View toggle wiring ──

    function setupViewToggles() {
        // Timeline view toggle
        document.querySelectorAll('.view-toggle-btn[data-view="timeline"], .view-toggle-btn[data-view="table"]').forEach(function(btn) {
            if (btn.dataset.view === 'timeline' || btn.dataset.view === 'table') {
                btn.addEventListener('click', function() {
                    var view = this.dataset.view;
                    var parent = this.closest('.view-toggle');
                    parent.querySelectorAll('.view-toggle-btn').forEach(function(b) { b.classList.remove('active'); });
                    this.classList.add('active');
                    _currentTimelineView = view;
                    _timelinePageState.page = 1;
                    renderTimeline(window._timelineEvents || []);
                });
            }
        });

        // Roster view toggle
        document.querySelectorAll('.view-toggle-btn[data-view="roster-cards"], .view-toggle-btn[data-view="roster-table"]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var view = this.dataset.view;
                var parent = this.closest('.view-toggle');
                parent.querySelectorAll('.view-toggle-btn').forEach(function(b) { b.classList.remove('active'); });
                this.classList.add('active');
                _currentRosterView = view;
                if (view === 'roster-table') {
                    renderRosterTable();
                } else {
                    var wrapper = document.getElementById('player-roster-table-wrapper');
                    var roster = document.getElementById('player-roster');
                    if (wrapper) wrapper.classList.add('hidden');
                    if (roster) {
                        roster.classList.remove('hidden');
                        loadPlayerProfiles();
                    }
                }
            });
        });

        // Roster table sort
        document.addEventListener('click', function(e) {
            var th = e.target.closest('th[data-roster-sort]');
            if (th) {
                var key = th.dataset.rosterSort;
                if (_rosterSortState.key === key) {
                    _rosterSortState.dir = _rosterSortState.dir === 'asc' ? 'desc' : 'asc';
                } else {
                    _rosterSortState.key = key;
                    _rosterSortState.dir = 'asc';
                }
                renderRosterTable();
                return;
            }
            // Roster pagination
            if (e.target.closest('[data-roster-page]')) {
                var btn = e.target.closest('[data-roster-page]');
                var page = btn.dataset.rosterPage;
                if (page === 'prev') {
                    _rosterPageState.page = Math.max(1, _rosterPageState.page - 1);
                } else if (page === 'next') {
                    var total = (window._rosterData || []).length;
                    var maxP = Math.ceil(total / _rosterPageState.perPage);
                    _rosterPageState.page = Math.min(maxP, _rosterPageState.page + 1);
                } else {
                    _rosterPageState.page = parseInt(page, 10);
                }
                renderRosterTable();
                return;
            }
        });

        document.addEventListener('change', function(e) {
            if (e.target.closest('.data-table-pagination .per-page-select') && document.getElementById('roster-data-table')) {
                _rosterPageState.perPage = parseInt(e.target.value, 10);
                _rosterPageState.page = 1;
                renderRosterTable();
            }
        });
    }

    // ── Batch action wiring ──

    function setupBatchActions() {
        document.getElementById('batch-delete-btn')?.addEventListener('click', function() {
            var ids = Array.from(_selectedEventIds);
            if (ids.length === 0) return;
            showConfirmDialog('Delete ' + ids.length + ' selected event(s)?', function() {
                var promises = ids.map(function(eid) {
                    return bridge.delete_event(eid).then(function(json) {
                        try {
                            var result = JSON.parse(json);
                            return result.success;
                        } catch (ex) { return false; }
                    }).catch(function() { return false; });
                });
                Promise.all(promises).then(function() {
                    _selectedEventIds.clear();
                    _updateBatchActionBar();
                    setTimeout(loadEventTimeline, 100);
                    showToast('Deleted ' + ids.length + ' event(s)', 'info');
                });
            });
        });

        document.getElementById('batch-export-csv-btn')?.addEventListener('click', function() {
            batchExport('csv');
        });

        document.getElementById('batch-export-json-btn')?.addEventListener('click', function() {
            batchExport('json');
        });
    }

    function batchExport(format) {
        var ids = Array.from(_selectedEventIds);
        if (ids.length === 0) return;
        var events = (window._timelineEvents || []).filter(function(e) {
            return ids.indexOf(e.id) >= 0;
        });
        if (events.length === 0) return;

        if (format === 'csv') {
            var headers = ['id', 'event_type', 'team', 'player_name', 'timestamp', 'xg', 'xa', 'xt'];
            var rows = events.map(function(e) {
                return [e.id, e.event_type, e.team, e.player_name || '', e.timestamp || 0, e.xg != null ? e.xg : '', e.xa != null ? e.xa : '', e.xt != null ? e.xt : ''];
            });
            var csv = headers.join(',') + '\n' + rows.map(function(r) {
                return r.map(function(c) {
                    var s = String(c != null ? c : '');
                    return s.indexOf(',') >= 0 || s.indexOf('"') >= 0 ? '"' + s.replace(/"/g, '""') + '"' : s;
                }).join(',');
            }).join('\n');
            var blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = 'selected-events.csv';
            document.body.appendChild(a);
            a.click();
            setTimeout(function() { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
        } else {
            var json = JSON.stringify(events, null, 2);
            var blob = new Blob([json], { type: 'application/json' });
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = 'selected-events.json';
            document.body.appendChild(a);
            a.click();
            setTimeout(function() { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
        }
    }

    document.getElementById('match-video').addEventListener('timeupdate', function() {
        highlightCurrentTimelineItem(this.currentTime);
    });

    /* ═══════════════════════════════════════════════════════════════
       Wave A — Telestration Engine
       ═══════════════════════════════════════════════════════════════ */

    var _telestrateState = {
        active: false,
        tool: 'arrow',
        color: '#ff0000',
        width: 3,
        strokes: [],
        redoStack: [],
        isDrawing: false,
        startX: 0, startY: 0,
        currentText: '',
        textInput: null,
    };

    // ── Sprint 1: Multi-Angle Video, Trimming, Highlight Reel ──
    var _maInitialized = false;
    var _maSources = [];
    var _maTrimIn = null;
    var _maTrimOut = null;
    var _maVideoSync = {};

    function initMultiAngle() {
        if (_maInitialized) return;
        _maInitialized = true;

        var addBtn = document.getElementById('ma-add-source-btn');
        var loadBtn = document.getElementById('ma-load-btn');
        var clearBtn = document.getElementById('ma-clear-btn');
        var syncMasterBtn = document.getElementById('ma-sync-master-btn');
        var playAllBtn = document.getElementById('ma-play-all-btn');
        var pauseAllBtn = document.getElementById('ma-pause-all-btn');
        var setInBtn = document.getElementById('ma-set-in-btn');
        var setOutBtn = document.getElementById('ma-set-out-btn');
        var trimExportBtn = document.getElementById('ma-trim-export-btn');
        var reelGenBtn = document.getElementById('ma-reel-generate-btn');
        var fileInput = document.getElementById('ma-source-file-input');
        var sourceList = document.getElementById('ma-source-list');

        addBtn.addEventListener('click', function () { fileInput.click(); });
        fileInput.addEventListener('change', function (e) {
            Array.from(e.target.files).forEach(function (f) {
                var path = f.name;
                var url = URL.createObjectURL(f);
                _maSources.push({ label: f.name, path: path, url: url });
                renderSourceList();
            });
            fileInput.value = '';
        });

        clearBtn.addEventListener('click', function () {
            _maSources = [];
            _maTrimIn = null;
            _maTrimOut = null;
            renderSourceList();
            document.getElementById('ma-workspace').classList.add('hidden');
            document.getElementById('ma-status').textContent = '';
        });

        loadBtn.addEventListener('click', function () {
            var paths = _maSources.map(function (s) { return { path: s.path, label: s.label }; });
            if (paths.length === 0) { showToast('Add at least one video source', 'warning'); return; }
            bridge.sync_load(JSON.stringify(paths), function (result) {
                try {
                    var data = JSON.parse(result);
                    if (data.error) { showToast(data.error, 'error'); return; }
                    loadSyncWorkspace(data);
                } catch (e) { showToast('Failed to parse sync response', 'error'); }
            });
        });

        syncMasterBtn.addEventListener('click', syncAllToMaster);
        playAllBtn.addEventListener('click', function () { playAllVideos(true); });
        pauseAllBtn.addEventListener('click', function () { playAllVideos(false); });

        setInBtn.addEventListener('click', function () {
            var master = document.getElementById('ma-video-0');
            if (master) { _maTrimIn = master.currentTime; updateTrimDisplay(); }
        });
        setOutBtn.addEventListener('click', function () {
            var master = document.getElementById('ma-video-0');
            if (master) { _maTrimOut = master.currentTime; updateTrimDisplay(); }
        });
        trimExportBtn.addEventListener('click', function () {
            if (_maTrimIn === null || _maTrimOut === null) { showToast('Set in and out points first', 'warning'); return; }
            if (_maTrimIn >= _maTrimOut) { showToast('In point must be before out point', 'warning'); return; }
            var masterPath = _maSources.length > 0 ? _maSources[0].path : '';
            if (!masterPath) { showToast('No source loaded', 'warning'); return; }
            var outName = document.getElementById('ma-trim-output').value || ('trim_' + Math.round(_maTrimIn) + '_' + Math.round(_maTrimOut) + '.mp4');
            bridge.trim_video(masterPath, _maTrimIn, _maTrimOut, outName, function (result) {
                try {
                    var data = JSON.parse(result);
                    if (data.error) { showToast(data.error, 'error'); return; }
                    showToast('Trim exported: ' + (data.output || ''), 'success');
                } catch (e) { showToast('Trim export failed', 'error'); }
            });
        });
        reelGenBtn.addEventListener('click', function () {
            if (_maSources.length === 0) { showToast('Load a video first', 'warning'); return; }
            var clip = [{
                video_path: _maSources[0].path,
                start_s: _maTrimIn || 0,
                end_s: _maTrimOut || 60,
                label: 'clip_1'
            }];
            var outName = document.getElementById('ma-reel-output').value || 'highlight_reel.mp4';
            bridge.reel_compose(JSON.stringify(clip), outName, function (result) {
                try {
                    var data = JSON.parse(result);
                    if (data.error) { showToast(data.error, 'error'); return; }
                    document.getElementById('ma-reel-status').textContent = data.output_path ? 'Reel saved: ' + data.output_path : data.clip_count + ' clips, ' + data.total_duration_s + 's';
                    showToast('Reel generated: ' + data.clip_count + ' clips', 'success');
                } catch (e) { showToast('Reel generation failed', 'error'); }
            });
        });

        document.querySelectorAll('.ma-offset-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var target = parseInt(this.dataset.target);
                var delta = parseFloat(this.dataset.delta);
                if (isNaN(target) || isNaN(delta)) return;
                bridge.sync_set_offset(target, 0, function (cur) {
                    bridge.sync_set_offset(target, delta, function (r) {
                        try {
                            var d = JSON.parse(r);
                            if (d.ok) { document.getElementById('ma-offset-' + target).textContent = (d.offset_s || 0).toFixed(1) + 's'; }
                        } catch (e) {}
                    });
                });
            });
        });
    }

    function renderSourceList() {
        var list = document.getElementById('ma-source-list');
        if (!list) return;
        if (_maSources.length === 0) {
            list.innerHTML = '<p class="hint" data-i18n="maSourceHint">Add video sources and click "Load Videos".</p>';
            return;
        }
        var html = '';
        _maSources.forEach(function (s, i) {
            html += '<div class="ma-source-item">';
            html += '<span class="ma-source-label" title="' + escapeHtml(s.label) + '">' + escapeHtml(s.label) + '</span>';
            html += '<span class="ma-source-remove" data-index="' + i + '">✕</span>';
            html += '</div>';
        });
        list.innerHTML = html;
        list.querySelectorAll('.ma-source-remove').forEach(function (el) {
            el.addEventListener('click', function () {
                var idx = parseInt(this.dataset.index);
                if (!isNaN(idx) && idx >= 0 && idx < _maSources.length) {
                    if (_maSources[idx].url) URL.revokeObjectURL(_maSources[idx].url);
                    _maSources.splice(idx, 1);
                    renderSourceList();
                }
            });
        });
    }

    function loadSyncWorkspace(data) {
        var ws = document.getElementById('ma-workspace');
        ws.classList.remove('hidden');
        document.getElementById('ma-status').textContent = data.sources.length + ' sources loaded';
        var sources = data.sources || [];
        for (var i = 0; i < 3; i++) {
            var video = document.getElementById('ma-video-' + i);
            var nameEl = document.getElementById('ma-name-' + i);
            if (i < sources.length) {
                var src = sources[i];
                if (_maSources[i] && _maSources[i].url) {
                    video.src = _maSources[i].url;
                }
                nameEl.textContent = src.label || 'Angle ' + (i + 1);
                var cell = video.closest('.ma-video-cell');
                if (cell) cell.style.display = '';
            } else {
                var cell = video.closest('.ma-video-cell');
                if (cell) cell.style.display = 'none';
            }
        }
        // Wire master video timeupdate to sync slaves
        var masterVideo = document.getElementById('ma-video-0');
        if (masterVideo) {
            masterVideo.removeEventListener('timeupdate', _maSyncHandler);
            _maSyncHandler = function () {
                var t = masterVideo.currentTime;
                bridge.sync_positions(t, function (result) {
                    try {
                        var pos = JSON.parse(result);
                        if (pos.error) return;
                        (pos.positions || []).forEach(function (p) {
                            if (p.index === 0) return;
                            var slave = document.getElementById('ma-video-' + p.index);
                            if (slave && Math.abs(slave.currentTime - p.time_s) > 0.3) {
                                slave.currentTime = p.time_s;
                            }
                            var offEl = document.getElementById('ma-offset-' + p.index);
                            if (offEl) offEl.textContent = (p.time_s - t).toFixed(1) + 's';
                        });
                    } catch (e) {}
                });
            };
            masterVideo.addEventListener('timeupdate', _maSyncHandler);
        }
    }
    var _maSyncHandler = null;

    // ── Sprint 3: Team Collaboration ──
    var _collabInitialized = false;

    function initCollaboration() {
        if (_collabInitialized) return;
        _collabInitialized = true;

        // User tabs
        document.querySelectorAll('[data-ctab]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                document.querySelectorAll('[data-ctab]').forEach(function (b) { b.classList.remove('active'); });
                this.classList.add('active');
                document.querySelectorAll('.collab-tab-content').forEach(function (tc) { tc.classList.add('hidden'); });
                var tab = document.getElementById('collab-' + this.dataset.ctab);
                if (tab) tab.classList.remove('hidden');
            });
        });

        // Users
        document.getElementById('collab-add-user-btn').addEventListener('click', function () {
            var uname = document.getElementById('collab-username').value.trim();
            var dname = document.getElementById('collab-display-name').value.trim();
            var role = document.getElementById('collab-role').value;
            if (!uname) { showToast('Username required', 'warning'); return; }
            bridge.create_collab_user(uname, dname || uname, role, function (result) {
                try {
                    var data = JSON.parse(result);
                    if (data.error) { showToast(data.error, 'error'); return; }
                    showToast('User added: ' + data.user.username, 'success');
                    loadCollabUsers();
                } catch (e) { showToast('Failed', 'error'); }
            });
        });

        // Comments
        document.getElementById('collab-add-comment-btn').addEventListener('click', function () {
            var mid = parseInt(document.getElementById('collab-comment-match').value);
            var eid = parseInt(document.getElementById('collab-comment-event').value) || 0;
            var text = document.getElementById('collab-comment-text').value.trim();
            if (!mid || !text) { showToast('Match ID and comment text required', 'warning'); return; }
            bridge.add_comment(mid, eid, 0, text, function (result) {
                try {
                    var data = JSON.parse(result);
                    if (data.error) { showToast(data.error, 'error'); return; }
                    showToast('Comment added', 'success');
                    document.getElementById('collab-comment-text').value = '';
                } catch (e) { showToast('Failed', 'error'); }
            });
        });
        document.getElementById('collab-load-comments-btn').addEventListener('click', function () {
            var mid = parseInt(document.getElementById('collab-comment-match').value);
            if (!mid) { showToast('Match ID required', 'warning'); return; }
            bridge.get_comments(mid, 0, function (result) {
                try {
                    var data = JSON.parse(result);
                    renderCollabComments(data.comments || []);
                } catch (e) { showToast('Failed', 'error'); }
            });
        });

        // Projects
        document.getElementById('collab-export-btn').addEventListener('click', function () {
            var mid = parseInt(document.getElementById('collab-export-match').value);
            if (!mid) { showToast('Match ID required', 'warning'); return; }
            bridge.export_project(mid, function (result) {
                try {
                    var data = JSON.parse(result);
                    if (data.error) { showToast(data.error, 'error'); return; }
                    var blob = new Blob([JSON.stringify(data.project, null, 2)], { type: 'application/json' });
                    var url = URL.createObjectURL(blob);
                    var a = document.createElement('a');
                    a.href = url;
                    a.download = 'match_' + mid + '.kawkab';
                    a.click();
                    URL.revokeObjectURL(url);
                    showToast('Project exported', 'success');
                } catch (e) { showToast('Export failed', 'error'); }
            });
        });

        var importFileInput = document.getElementById('collab-import-file');
        document.getElementById('collab-import-btn').addEventListener('click', function () { importFileInput.click(); });
        importFileInput.addEventListener('change', function (e) {
            if (e.target.files.length === 0) return;
            var reader = new FileReader();
            reader.onload = function (ev) {
                bridge.import_project(ev.target.result, function (result) {
                    try {
                        var data = JSON.parse(result);
                        if (data.error) { showToast(data.error, 'error'); return; }
                        showToast('Project imported: ' + (data.comments_imported || 0) + ' comments', 'success');
                        document.getElementById('collab-project-result').textContent = 'Match ID: ' + (data.match.id || '?') + ' imported successfully';
                    } catch (err) { showToast('Import failed', 'error'); }
                });
            };
            reader.readAsText(e.target.files[0]);
            importFileInput.value = '';
        });

        // Activity
        document.getElementById('collab-refresh-activity-btn').addEventListener('click', loadCollabActivity);

        // Load initial data
        loadCollabUsers();
        loadCollabActivity();
    }

    function loadCollabUsers() {
        bridge.get_collab_users(function (result) {
            try {
                var data = JSON.parse(result);
                var el = document.getElementById('collab-user-list');
                if (!el) return;
                if (!data.users || data.users.length === 0) {
                    el.innerHTML = '<p class="hint">No team members.</p>';
                    return;
                }
                var html = '';
                data.users.forEach(function (u) {
                    html += '<div class="collab-user-item">' +
                        '<span class="collab-user-name">' + escapeHtml(u.display_name || u.username) + '</span>' +
                        '<span class="collab-user-role">' + escapeHtml(u.role) + '</span>' +
                        '<span class="collab-user-uname">@' + escapeHtml(u.username) + '</span>' +
                        '</div>';
                });
                el.innerHTML = html;
            } catch (e) {}
        });
    }

    function renderCollabComments(comments) {
        var el = document.getElementById('collab-comment-list');
        if (!el) return;
        if (!comments || comments.length === 0) {
            el.innerHTML = '<p class="hint">No comments found.</p>';
            return;
        }
        var html = '';
        comments.forEach(function (c) {
            html += '<div class="collab-comment-item">' +
                '<strong>' + escapeHtml(c.username) + '</strong> ' +
                '<span class="collab-comment-text">' + escapeHtml(c.text) + '</span>' +
                '<span class="collab-comment-meta">Match ' + c.match_id + ' | ' + (c.created_at || '').slice(0, 19).replace('T', ' ') + '</span>' +
                '</div>';
        });
        el.innerHTML = html;
    }

    function loadCollabActivity() {
        bridge.get_activity_feed(50, function (result) {
            try {
                var data = JSON.parse(result);
                var el = document.getElementById('collab-activity-list');
                if (!el) return;
                if (!data.activities || data.activities.length === 0) {
                    el.innerHTML = '<p class="hint">No activity yet.</p>';
                    return;
                }
                var html = '';
                data.activities.forEach(function (a) {
                    html += '<div class="collab-activity-item">' +
                        '<span class="collab-activity-user">' + escapeHtml(a.username) + '</span> ' +
                        '<span class="collab-activity-action">' + escapeHtml(a.action) + '</span> ' +
                        '<span class="collab-activity-desc">' + escapeHtml(a.description) + '</span>' +
                        '<span class="collab-activity-time">' + (a.created_at || '').slice(0, 19).replace('T', ' ') + '</span>' +
                        '</div>';
                });
                el.innerHTML = html;
            } catch (e) {}
        });
    }

    // ── Sprint 4: Live Tagging ──
    var _liveInitialized = false;
    var _liveSessionActive = false;
    var _liveHotkeys = {};

    function initLiveTagging() {
        if (_liveInitialized) return;
        _liveInitialized = true;

        var startBtn = document.getElementById('live-start-btn');
        var stopBtn = document.getElementById('live-stop-btn');
        var clearBtn = document.getElementById('live-clear-btn');
        var exportBtn = document.getElementById('live-export-btn');
        var homeInput = document.getElementById('live-home-team');
        var awayInput = document.getElementById('live-away-team');
        var status = document.getElementById('live-status');

        startBtn.onclick = function() {
            if (_liveSessionActive) return;
            var home = homeInput.value.trim() || 'Home';
            var away = awayInput.value.trim() || 'Away';
            bridge.live_start_session(home, away).then(function(raw) {
                var r = JSON.parse(raw);
                if (r.error) { showToast(r.error, 'error'); return; }
                _liveSessionActive = true;
                startBtn.classList.add('hidden');
                stopBtn.classList.remove('hidden');
                status.textContent = r.message || 'Session active';
                loadLiveHotkeys();
                updateLiveStats();
            });
        };

        stopBtn.onclick = function() {
            if (!_liveSessionActive) return;
            bridge.live_stop_session().then(function(raw) {
                var r = JSON.parse(raw);
                if (r.error) { showToast(r.error, 'error'); return; }
                _liveSessionActive = false;
                startBtn.classList.remove('hidden');
                stopBtn.classList.add('hidden');
                status.textContent = r.message || 'Session stopped';
                loadLiveTags();
            });
        };

        clearBtn.onclick = function() {
            bridge.live_clear_tags().then(function(raw) {
                var r = JSON.parse(raw);
                if (r.error) { showToast(r.error, 'error'); return; }
                updateLiveStats();
                loadLiveTags();
                showToast('Tags cleared', 'info');
            });
        };

        exportBtn.onclick = function() {
            bridge.live_export().then(function(raw) {
                var d = JSON.parse(raw);
                if (d.error) { showToast(d.error, 'error'); return; }
                var blob = new Blob([JSON.stringify(d, null, 2)], {type:'application/json'});
                var a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = 'live-tags.json';
                a.click();
                URL.revokeObjectURL(a.href);
                showToast('Exported ' + d.total + ' tags', 'info');
            });
        };

        // Period buttons
        document.querySelectorAll('.live-period-btn').forEach(function(btn) {
            btn.onclick = function() {
                if (!_liveSessionActive) return;
                var period = parseInt(this.getAttribute('data-period'), 10);
                bridge.live_set_period(period);
                document.querySelectorAll('.live-period-btn').forEach(function(b) { b.classList.remove('btn-primary'); b.classList.add('btn-sm'); });
                this.classList.add('btn-primary');
                this.classList.remove('btn-sm');
            };
        });

        // Keyboard listener
        document.addEventListener('keydown', function liveKeyHandler(e) {
            if (!_liveSessionActive) return;
            var section = document.getElementById('livetagging-section');
            if (!section || section.classList.contains('hidden')) return;
            var key = e.key.toLowerCase();
            if (key === ' ' || key === 'enter' || key === 'tab') return;
            if (document.activeElement && ['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) return;
            var eventType = _liveHotkeys[key];
            if (!eventType) return;
            e.preventDefault();
            bridge.live_tag_event(eventType, '', 0, '', null, null).then(function(raw) {
                var r = JSON.parse(raw);
                if (r.error) return;
                // Flash button
                var btn = document.querySelector('.live-hotkey-btn[data-type="' + eventType + '"]');
                if (btn) { btn.classList.add('active'); setTimeout(function(){ btn.classList.remove('active'); }, 200); }
                updateLiveStats();
                loadLiveTags();
            });
        });

        updateLiveStats();
    }

    function loadLiveHotkeys() {
        bridge.live_get_hotkeys().then(function(raw) {
            var r = JSON.parse(raw);
            if (r.error) return;
            _liveHotkeys = r.hotkeys || {};
            var grid = document.getElementById('live-hotkeys-grid');
            if (!grid) return;
            grid.innerHTML = '';
            Object.keys(_liveHotkeys).forEach(function(key) {
                var label = _liveHotkeys[key].replace(/_/g, ' ').replace(/\b\w/g, function(c){ return c.toUpperCase(); });
                var btn = document.createElement('div');
                btn.className = 'live-hotkey-btn';
                btn.setAttribute('data-type', _liveHotkeys[key]);
                btn.innerHTML = '<span class="hk-key">' + key + '</span><span class="hk-label">' + label + '</span>';
                btn.onclick = function() {
                    if (!_liveSessionActive) { showToast('Start a session first', 'warning'); return; }
                    bridge.live_tag_event(_liveHotkeys[key], '', 0, '', null, null).then(function(raw2) {
                        var r2 = JSON.parse(raw2);
                        if (r2.error) { showToast(r2.error, 'error'); return; }
                        btn.classList.add('active');
                        setTimeout(function(){ btn.classList.remove('active'); }, 200);
                        updateLiveStats();
                        loadLiveTags();
                    });
                };
                grid.appendChild(btn);
            });
        });
    }

    function updateLiveStats() {
        var container = document.getElementById('live-stats-content');
        if (!container) return;
        bridge.live_get_stats().then(function(raw) {
            var r = JSON.parse(raw);
            if (r.error || !r.stats) return;
            var s = r.stats;
            container.innerHTML = '';
            var items = [
                { label: 'Tags', value: s.tags_count },
                { label: 'Home Goals', value: s.home_goals },
                { label: 'Away Goals', value: s.away_goals },
                { label: 'Home Shots', value: s.home_shots },
                { label: 'Away Shots', value: s.away_shots },
                { label: 'Possession (Home)', value: s.home_possession_pct + '%' },
                { label: 'Elapsed', value: formatLiveTime(s.elapsed_s) },
            ];
            items.forEach(function(it) {
                var d = document.createElement('div');
                d.style.cssText = 'display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)';
                d.innerHTML = '<span>' + it.label + '</span><strong>' + it.value + '</strong>';
                container.appendChild(d);
            });
        });
    }

    function loadLiveTags() {
        var container = document.getElementById('live-tag-list');
        var counter = document.getElementById('live-tag-count');
        if (!container) return;
        bridge.live_get_tags().then(function(raw) {
            var r = JSON.parse(raw);
            if (r.error || !r.tags) return;
            if (counter) counter.textContent = r.total;
            container.innerHTML = '';
            if (!r.tags.length) {
                container.innerHTML = '<p class="hint">No tags yet. Use hotkeys or click buttons.</p>';
                return;
            }
            r.tags.slice().reverse().forEach(function(tag) {
                var div = document.createElement('div');
                div.className = 'live-tag-entry';
                div.innerHTML = '<span class="live-tag-type">' + tag.type.replace(/_/g, ' ') + '</span>'
                    + '<span class="live-tag-team">' + (tag.team || '') + '</span>'
                    + '<span class="live-tag-time">' + formatLiveTime(tag.t) + '</span>'
                    + '<span class="live-tag-notes" style="flex:1;font-size:0.75rem;color:var(--text-muted)">' + (tag.notes || '') + '</span>';
                container.appendChild(div);
            });
        });
    }

    function formatLiveTime(seconds) {
        if (!seconds && seconds !== 0) return '0:00';
        var m = Math.floor(seconds / 60);
        var s = Math.floor(seconds % 60);
        return m + ':' + (s < 10 ? '0' : '') + s;
    }

    // ── Sprint 5: Scout Camera (Mobile/Tablet) ──
    var _scoutCamInitialized = false;
    var _scoutCamStream = null;
    var _scoutCaptures = [];

    function initScoutCamera() {
        if (_scoutCamInitialized) return;
        _scoutCamInitialized = true;

        var video = document.getElementById('scout-camera-video');
        var startBtn = document.getElementById('scout-cam-start-btn');
        var stopBtn = document.getElementById('scout-cam-stop-btn');
        var captureBtn = document.getElementById('scout-cam-capture-btn');
        var clearBtn = document.getElementById('scout-cam-clear-btn');
        var capturesDiv = document.getElementById('scout-camera-captures');

        startBtn.onclick = function() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                showToast('Camera not available on this device', 'error');
                return;
            }
            navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } } })
                .then(function(stream) {
                    _scoutCamStream = stream;
                    video.srcObject = stream;
                    video.play();
                    startBtn.classList.add('hidden');
                    stopBtn.classList.remove('hidden');
                    captureBtn.classList.remove('hidden');
                    showToast('Camera started', 'info');
                })
                .catch(function(err) {
                    showToast('Camera error: ' + err.message, 'error');
                });
        };

        stopBtn.onclick = function() {
            if (_scoutCamStream) {
                _scoutCamStream.getTracks().forEach(function(t) { t.stop(); });
                _scoutCamStream = null;
            }
            video.srcObject = null;
            startBtn.classList.remove('hidden');
            stopBtn.classList.add('hidden');
            captureBtn.classList.add('hidden');
        };

        captureBtn.onclick = function() {
            if (!_scoutCamStream) return;
            var canvas = document.createElement('canvas');
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            var ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            var dataUrl = canvas.toDataURL('image/jpeg', 0.8);
            _scoutCaptures.push(dataUrl);
            renderScoutCaptures();
            showToast('Snapshot captured', 'info');
        };

        clearBtn.onclick = function() {
            _scoutCaptures = [];
            renderScoutCaptures();
        };

        function renderScoutCaptures() {
            if (_scoutCaptures.length === 0) {
                capturesDiv.innerHTML = '<p class="hint">Captured snapshots will appear here.</p>';
                return;
            }
            capturesDiv.innerHTML = '';
            _scoutCaptures.forEach(function(url, i) {
                var item = document.createElement('div');
                item.className = 'scout-capture-item';
                item.innerHTML = '<img src="' + url + '" alt="Capture ' + (i+1) + '"><div class="capture-label">#' + (i+1) + '</div>';
                item.onclick = function() {
                    var a = document.createElement('a');
                    a.href = url;
                    a.download = 'scout-capture-' + (i+1) + '.jpg';
                    a.click();
                };
                capturesDiv.appendChild(item);
            });
        }
    }

    // ── PWA install prompt handler ──
    var _deferredPrompt = null;
    var _pwaInitialized = false;

    function initPWA() {
        if (_pwaInitialized) return;
        _pwaInitialized = true;

        window.addEventListener('beforeinstallprompt', function(e) {
            e.preventDefault();
            _deferredPrompt = e;
            var banner = document.getElementById('pwa-install-banner');
            if (banner) banner.classList.add('visible');
        });

        window.addEventListener('appinstalled', function() {
            _deferredPrompt = null;
            var banner = document.getElementById('pwa-install-banner');
            if (banner) banner.classList.remove('visible');
            showToast('App installed!', 'info');
        });

        // Offline/online detection
        function updateOnlineStatus() {
            var indicator = document.getElementById('offline-indicator');
            if (!indicator) return;
            if (navigator.onLine) {
                indicator.classList.remove('visible');
            } else {
                indicator.classList.add('visible');
            }
        }
        window.addEventListener('online', updateOnlineStatus);
        window.addEventListener('offline', updateOnlineStatus);
        updateOnlineStatus();
    }

    // ── Install button handler ──
    document.addEventListener('click', function(e) {
        if (e.target && e.target.matches('#pwa-install-btn')) {
            if (_deferredPrompt) {
                _deferredPrompt.prompt();
                _deferredPrompt.userChoice.then(function() {
                    _deferredPrompt = null;
                    var banner = document.getElementById('pwa-install-banner');
                    if (banner) banner.classList.remove('visible');
                });
            }
        }
        if (e.target && e.target.matches('#pwa-install-close, #pwa-install-close *')) {
            var banner = document.getElementById('pwa-install-banner');
            if (banner) banner.classList.remove('visible');
        }
    });

    // ── Sprint 2: Physiology & Wearables ──
    var _physInitialized = false;
    var _physWearableData = null;
    var _physWearablePath = '';

    function initPhysiology() {
        if (_physInitialized) return;
        _physInitialized = true;

        var importBtn = document.getElementById('phys-import-btn');
        var fileInput = document.getElementById('phys-wearable-input');
        var mergeBtn = document.getElementById('phys-merge-btn');
        var correlateBtn = document.getElementById('phys-correlate-btn');

        importBtn.addEventListener('click', function () { fileInput.click(); });
        fileInput.addEventListener('change', function (e) {
            if (e.target.files.length > 0) {
                var f = e.target.files[0];
                _physWearablePath = f.name;
                var reader = new FileReader();
                reader.onload = function (ev) {
                    bridge.import_wearable(_physWearablePath, function (result) {
                        try {
                            var data = JSON.parse(result);
                            if (data.error) { showToast(data.error, 'error'); return; }
                            _physWearableData = data.session;
                            renderWearableSummary(data.session);
                            showToast('Wearable imported: ' + (data.session.device_type || 'unknown'), 'success');
                        } catch (err) { showToast('Parse error', 'error'); }
                    });
                };
                reader.readAsText(f);
            }
            fileInput.value = '';
        });

        mergeBtn.addEventListener('click', function () {
            if (!_physWearableData) { showToast('Import wearable data first', 'warning'); return; }
            var sel = document.getElementById('phys-player-select');
            var pid = parseInt(sel.value);
            if (!pid) { showToast('Select a player', 'warning'); return; }
            var traj = [{ t: 0, v: 2.5 }, { t: 10, v: 3.0 }, { t: 20, v: 4.2 }, { t: 30, v: 5.0 }];
            var wearable = [{ t: 0, hr: 80, spd: 2.4 }, { t: 10, hr: 95, spd: 3.1 }, { t: 20, hr: 110, spd: 4.0 }, { t: 30, hr: 120, spd: 5.2 }];
            bridge.merge_player_physiology(pid, JSON.stringify(traj), JSON.stringify(wearable), 75.0, function (result) {
                try {
                    var data = JSON.parse(result);
                    if (data.error) { showToast(data.error, 'error'); return; }
                    renderMergedPhysiology(data.report);
                } catch (err) { showToast('Merge failed', 'error'); }
            });
        });

        correlateBtn.addEventListener('click', function () {
            var events = [{ type: 'shot', timestamp: 15 }, { type: 'tackle', timestamp: 25 }];
            var speedTL = [{ t: 0, v_spd: 2.5 }, { t: 10, v_spd: 3.0 }, { t: 20, v_spd: 4.2 }, { t: 30, v_spd: 5.0 }];
            var hrTL = [{ t: 0, hr: 80 }, { t: 10, hr: 95 }, { t: 20, hr: 110 }, { t: 30, hr: 120 }];
            bridge.analyze_physio_tactical(JSON.stringify(events), JSON.stringify(speedTL), JSON.stringify(hrTL), 5.0, function (result) {
                try {
                    var data = JSON.parse(result);
                    if (data.error) { showToast(data.error, 'error'); return; }
                    renderCorrelation(data.report);
                } catch (err) { showToast('Correlation failed', 'error'); }
            });
        });

        loadPlayerSelect();
    }

    function renderWearableSummary(session) {
        var el = document.getElementById('phys-wearable-content');
        if (!el) return;
        el.innerHTML = '<div class="phys-metrics-grid">' +
            '<div class="phys-metric"><span class="phys-metric-label">Device</span><span class="phys-metric-value">' + escapeHtml(session.device_type || '-') + '</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Duration</span><span class="phys-metric-value">' + (session.duration_s || 0) + 's</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Points</span><span class="phys-metric-value">' + (session.point_count || 0) + '</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Avg HR</span><span class="phys-metric-value">' + (session.avg_hr || '-') + ' bpm</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Max HR</span><span class="phys-metric-value">' + (session.max_hr || '-') + ' bpm</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Distance</span><span class="phys-metric-value">' + (session.total_distance_m || 0) + 'm</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Max Speed</span><span class="phys-metric-value">' + (session.max_speed_ms || 0) + ' m/s</span></div>' +
            '</div>';
    }

    function renderMergedPhysiology(report) {
        var el = document.getElementById('phys-merge-content');
        if (!el) return;
        el.innerHTML = '<div class="phys-metrics-grid">' +
            '<div class="phys-metric"><span class="phys-metric-label">Duration</span><span class="phys-metric-value">' + (report.duration_s || 0) + 's</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Video Distance</span><span class="phys-metric-value">' + (report.video_distance_m || 0) + 'm</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Wearable Distance</span><span class="phys-metric-value">' + (report.wearable_distance_m || '-') + 'm</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Avg HR</span><span class="phys-metric-value">' + (report.avg_hr || '-') + ' bpm</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Peak HR</span><span class="phys-metric-value">' + (report.peak_hr || '-') + ' bpm</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Speed Corr</span><span class="phys-metric-value">' + (report.correlation_speed_r !== null ? report.correlation_speed_r.toFixed(3) : '-') + '</span></div>' +
            '<div class="phys-metric"><span class="phys-metric-label">Timeline Pts</span><span class="phys-metric-value">' + (report.timeline_points || 0) + '</span></div>' +
            '</div>';
        document.getElementById('phys-workspace').classList.remove('hidden');
        var hrEl = document.getElementById('phys-hr-content');
        if (hrEl && report.hr_zones) {
            var zones = report.hr_zones;
            hrEl.innerHTML = '<div class="phys-metrics-grid">' +
                '<div class="phys-metric"><span class="phys-metric-label">Zone 1 (50-60%)</span><span class="phys-metric-value">' + (zones.zone1_50_60 || 0) + '</span></div>' +
                '<div class="phys-metric"><span class="phys-metric-label">Zone 2 (60-70%)</span><span class="phys-metric-value">' + (zones.zone2_60_70 || 0) + '</span></div>' +
                '<div class="phys-metric"><span class="phys-metric-label">Zone 3 (70-80%)</span><span class="phys-metric-value">' + (zones.zone3_70_80 || 0) + '</span></div>' +
                '<div class="phys-metric"><span class="phys-metric-label">Zone 4 (80-90%)</span><span class="phys-metric-value">' + (zones.zone4_80_90 || 0) + '</span></div>' +
                '<div class="phys-metric"><span class="phys-metric-label">Zone 5 (90-100%)</span><span class="phys-metric-value">' + (zones.zone5_90_100 || 0) + '</span></div>' +
                '</div>';
        }
    }

    function renderCorrelation(report) {
        var el = document.getElementById('phys-correlation-content');
        if (!el || !report.correlations) return;
        var html = '';
        (report.correlations || []).forEach(function (c) {
            html += '<div class="phys-correlation-item">' +
                '<strong>' + escapeHtml(c.event_type) + '</strong> ' +
                '(n=' + c.sample_count + ') pre: ' + c.pre_speed + ' m/s → post: ' + c.post_speed + ' m/s ' +
                '<span class="' + (c.speed_delta_pct < 0 ? 'text-danger' : 'text-success') + '">' +
                (c.speed_delta_pct > 0 ? '+' : '') + c.speed_delta_pct.toFixed(1) + '%</span>' +
                (c.hr_delta_pct !== null ? ' HR: ' + (c.hr_delta_pct > 0 ? '+' : '') + c.hr_delta_pct.toFixed(1) + '%' : '') +
                '</div>';
        });
        html += '<div class="phys-summary">';
        if (report.summary) {
            html += '<p>Events: ' + report.summary.total_events_analyzed + ' | HI Bursts: ' + (report.high_intensity_bursts || []).length + ' | Fatigue: ' + (report.fatigue_periods || []).length + '</p>';
        }
        html += '</div>';
        el.innerHTML = html;
    }

    function loadPlayerSelect() {
        var sel = document.getElementById('phys-player-select');
        bridge.get_all_player_profiles(function (result) {
            try {
                var data = JSON.parse(result);
                if (data.profiles) {
                    sel.innerHTML = '<option value="">Select Player</option>';
                    data.profiles.forEach(function (p) {
                        sel.innerHTML += '<option value="' + (p.track_id || p.id || 0) + '">' + escapeHtml(p.name || 'Player') + '</option>';
                    });
                }
            } catch (e) {}
        });
    }

    function syncAllToMaster() {
        var master = document.getElementById('ma-video-0');
        if (!master) return;
        var t = master.currentTime;
        bridge.sync_positions(t, function (result) {
            try {
                var pos = JSON.parse(result);
                if (pos.error) return;
                (pos.positions || []).forEach(function (p) {
                    var slave = document.getElementById('ma-video-' + p.index);
                    if (slave) { slave.currentTime = p.time_s; }
                });
            } catch (e) {}
        });
    }

    function playAllVideos(play) {
        for (var i = 0; i < 3; i++) {
            var v = document.getElementById('ma-video-' + i);
            if (v) {
                if (play) { v.play().catch(function () {}); }
                else { v.pause(); }
            }
        }
    }

    function updateTrimDisplay() {
        function fmt(t) { if (t === null) return '--:--'; var m = Math.floor(t / 60); var s = Math.floor(t % 60); return m + ':' + (s < 10 ? '0' : '') + s; }
        document.getElementById('ma-trim-in').textContent = fmt(_maTrimIn);
        document.getElementById('ma-trim-out').textContent = fmt(_maTrimOut);
    }

    function initTelestration() {
        var toggleBtn = document.getElementById('telestrate-toggle-btn');
        var toolbar = document.getElementById('telestrate-toolbar');
        var canvas = document.getElementById('telestrate-canvas');
        var colorInput = document.getElementById('telestrate-color');
        var widthInput = document.getElementById('telestrate-width');
        var undoBtn = document.getElementById('telestrate-undo-btn');
        var redoBtn = document.getElementById('telestrate-redo-btn');
        var clearBtn = document.getElementById('telestrate-clear-btn');
        var saveBtn = document.getElementById('telestrate-save-btn');

        if (!toggleBtn || !canvas) return;

        // Toggle drawing mode
        toggleBtn.addEventListener('click', function() {
            _telestrateState.active = !_telestrateState.active;
            canvas.classList.toggle('active', _telestrateState.active);
            toolbar.classList.toggle('hidden', !_telestrateState.active);
            toggleBtn.textContent = _telestrateState.active ? '✏️ Drawing ON' : '✏️ Draw';
            if (_telestrateState.active) {
                resizeCanvas();
            }
        });

        // Tool selection
        toolbar.querySelectorAll('.telestrate-tool').forEach(function(btn) {
            btn.addEventListener('click', function() {
                toolbar.querySelectorAll('.telestrate-tool').forEach(function(b) { b.classList.remove('active'); });
                this.classList.add('active');
                _telestrateState.tool = this.dataset.tool;
                // Remove text input if switching away from text
                if (_telestrateState.tool !== 'text' && _telestrateState.textInput) {
                    _telestrateState.textInput.remove();
                    _telestrateState.textInput = null;
                }
            });
        });

        colorInput.addEventListener('input', function() {
            _telestrateState.color = this.value;
        });

        widthInput.addEventListener('input', function() {
            _telestrateState.width = parseInt(this.value, 10);
        });

        undoBtn.addEventListener('click', function() { telestrateUndo(); });
        redoBtn.addEventListener('click', function() { telestrateRedo(); });
        clearBtn.addEventListener('click', function() {
            if (_telestrateState.strokes.length === 0) return;
            showConfirmDialog('Clear all drawings?', function() {
                _telestrateState.redoStack = _telestrateState.redoStack.concat(_telestrateState.strokes);
                _telestrateState.strokes = [];
                redrawTelestration();
            });
        });
        saveBtn.addEventListener('click', function() {
            var video = document.getElementById('match-video');
            if (!video) return;
            // Create combined canvas with video frame + drawings
            var c = document.createElement('canvas');
            c.width = video.videoWidth || canvas.width;
            c.height = video.videoHeight || canvas.height;
            var ctx = c.getContext('2d');
            ctx.drawImage(video, 0, 0, c.width, c.height);
            ctx.drawImage(canvas, 0, 0, c.width, c.height);
            var link = document.createElement('a');
            link.download = 'telestration-' + Date.now() + '.png';
            link.href = c.toDataURL('image/png');
            link.click();
            showToast('Annotated frame saved!', 'success');
        });

        // Mouse events on canvas
        canvas.addEventListener('mousedown', telestrateMouseDown);
        canvas.addEventListener('mousemove', telestrateMouseMove);
        canvas.addEventListener('mouseup', telestrateMouseUp);
        canvas.addEventListener('mouseleave', telestrateMouseUp);

        // Touch support
        canvas.addEventListener('touchstart', function(e) { e.preventDefault(); var t = e.touches[0]; telestrateMouseDown({ offsetX: t.clientX - canvas.getBoundingClientRect().left, offsetY: t.clientY - canvas.getBoundingClientRect().top }); });
        canvas.addEventListener('touchmove', function(e) { e.preventDefault(); var t = e.touches[0]; telestrateMouseMove({ offsetX: t.clientX - canvas.getBoundingClientRect().left, offsetY: t.clientY - canvas.getBoundingClientRect().top }); });
        canvas.addEventListener('touchend', function(e) { e.preventDefault(); telestrateMouseUp({}); });

        // Resize canvas with video
        var video = document.getElementById('match-video');
        if (video) {
            video.addEventListener('loadedmetadata', resizeCanvas);
            video.addEventListener('resize', resizeCanvas);
        }
        window.addEventListener('resize', resizeCanvas);
    }

    function resizeCanvas() {
        var canvas = document.getElementById('telestrate-canvas');
        var video = document.getElementById('match-video');
        if (!canvas || !video) return;
        var rect = video.parentElement.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
        redrawTelestration();
    }

    function getCanvasPos(e) {
        var canvas = document.getElementById('telestrate-canvas');
        var rect = canvas.getBoundingClientRect();
        return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    function telestrateMouseDown(e) {
        if (!_telestrateState.active) return;
        var pos = e.offsetX != null ? { x: e.offsetX, y: e.offsetY } : getCanvasPos(e);
        _telestrateState.isDrawing = true;
        _telestrateState.startX = pos.x;
        _telestrateState.startY = pos.y;

        if (_telestrateState.tool === 'text') {
            var input = document.createElement('input');
            input.type = 'text';
            input.className = 'telestrate-text-input';
            input.style.position = 'absolute';
            input.style.left = pos.x + 'px';
            input.style.top = pos.y + 'px';
            input.style.zIndex = '20';
            input.style.background = 'rgba(0,0,0,0.7)';
            input.style.color = _telestrateState.color;
            input.style.border = '1px solid ' + _telestrateState.color;
            input.style.padding = '2px 6px';
            input.style.fontSize = '16px';
            input.style.borderRadius = '3px';
            input.style.outline = 'none';
            input.placeholder = 'Type text...';

            var wrapper = document.querySelector('.video-wrapper');
            wrapper.appendChild(input);
            input.focus();

            _telestrateState.textInput = input;

            input.addEventListener('keydown', function(ev) {
                if (ev.key === 'Enter') {
                    var text = this.value.trim();
                    if (text) {
                        _telestrateState.strokes.push({
                            tool: 'text',
                            color: _telestrateState.color,
                            x: pos.x, y: pos.y,
                            text: text,
                            fontSize: 16,
                        });
                        _telestrateState.redoStack = [];
                        redrawTelestration();
                    }
                    this.remove();
                    _telestrateState.textInput = null;
                } else if (ev.key === 'Escape') {
                    this.remove();
                    _telestrateState.textInput = null;
                }
            });
            _telestrateState.isDrawing = false;
        }
    }

    function telestrateMouseMove(e) {
        if (!_telestrateState.isDrawing || !_telestrateState.active) return;
        var pos = e.offsetX != null ? { x: e.offsetX, y: e.offsetY } : getCanvasPos(e);
        // Preview while drawing
        var canvas = document.getElementById('telestrate-canvas');
        var ctx = canvas.getContext('2d');
        redrawTelestration();
        ctx.save();
        ctx.strokeStyle = _telestrateState.color;
        ctx.fillStyle = _telestrateState.color;
        ctx.lineWidth = _telestrateState.width;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        var tool = _telestrateState.tool;
        if (tool === 'arrow') {
            drawArrow(ctx, _telestrateState.startX, _telestrateState.startY, pos.x, pos.y);
        } else if (tool === 'circle') {
            var rx = Math.abs(pos.x - _telestrateState.startX);
            var ry = Math.abs(pos.y - _telestrateState.startY);
            ctx.beginPath();
            ctx.ellipse(_telestrateState.startX, _telestrateState.startY, rx, ry, 0, 0, Math.PI * 2);
            ctx.stroke();
        } else if (tool === 'rect') {
            ctx.strokeRect(_telestrateState.startX, _telestrateState.startY, pos.x - _telestrateState.startX, pos.y - _telestrateState.startY);
        } else if (tool === 'line') {
            ctx.beginPath();
            ctx.moveTo(_telestrateState.startX, _telestrateState.startY);
            ctx.lineTo(pos.x, pos.y);
            ctx.stroke();
        } else if (tool === 'freehand') {
            ctx.beginPath();
            ctx.moveTo(_telestrateState.startX, _telestrateState.startY);
            ctx.lineTo(pos.x, pos.y);
            ctx.stroke();
            _telestrateState.startX = pos.x;
            _telestrateState.startY = pos.y;
        } else if (tool === 'highlight') {
            ctx.globalAlpha = 0.3;
            ctx.lineWidth = _telestrateState.width * 4;
            ctx.beginPath();
            ctx.moveTo(_telestrateState.startX, _telestrateState.startY);
            ctx.lineTo(pos.x, pos.y);
            ctx.stroke();
            _telestrateState.startX = pos.x;
            _telestrateState.startY = pos.y;
        }
        ctx.restore();
    }

    function telestrateMouseUp(e) {
        if (!_telestrateState.isDrawing || !_telestrateState.active) return;
        _telestrateState.isDrawing = false;
        var pos = e.offsetX != null ? { x: e.offsetX, y: e.offsetY } : getCanvasPos(e);

        // Save stroke
        var stroke = {
            tool: _telestrateState.tool,
            color: _telestrateState.color,
            width: _telestrateState.width,
            startX: _telestrateState.startX,
            startY: _telestrateState.startY,
            endX: pos.x,
            endY: pos.y,
        };

        // For freehand/highlight, we record the path
        if (_telestrateState.tool === 'freehand' || _telestrateState.tool === 'highlight') {
            stroke.path = [{ x: _telestrateState.startX, y: _telestrateState.startY }, { x: pos.x, y: pos.y }];
            stroke.replay = function(ctx) {
                ctx.save();
                ctx.strokeStyle = this.color;
                ctx.lineWidth = this.tool === 'highlight' ? this.width * 4 : this.width;
                ctx.globalAlpha = this.tool === 'highlight' ? 0.3 : 1;
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
                ctx.beginPath();
                ctx.moveTo(this.path[0].x, this.path[0].y);
                for (var i = 1; i < this.path.length; i++) {
                    ctx.lineTo(this.path[i].x, this.path[i].y);
                }
                ctx.stroke();
                ctx.restore();
            };
        } else if (_telestrateState.tool === 'circle') {
            stroke.rx = Math.abs(pos.x - _telestrateState.startX);
            stroke.ry = Math.abs(pos.y - _telestrateState.startY);
            stroke.replay = function(ctx) {
                ctx.save();
                ctx.strokeStyle = this.color;
                ctx.lineWidth = this.width;
                ctx.beginPath();
                ctx.ellipse(this.startX, this.startY, this.rx, this.ry, 0, 0, Math.PI * 2);
                ctx.stroke();
                ctx.restore();
            };
        } else if (_telestrateState.tool === 'arrow') {
            stroke.replay = function(ctx) {
                ctx.save();
                ctx.strokeStyle = this.color;
                ctx.fillStyle = this.color;
                ctx.lineWidth = this.width;
                drawArrow(ctx, this.startX, this.startY, this.endX, this.endY);
                ctx.restore();
            };
        } else if (_telestrateState.tool === 'rect') {
            stroke.replay = function(ctx) {
                ctx.save();
                ctx.strokeStyle = this.color;
                ctx.lineWidth = this.width;
                ctx.strokeRect(this.startX, this.startY, this.endX - this.startX, this.endY - this.startY);
                ctx.restore();
            };
        } else if (_telestrateState.tool === 'line') {
            stroke.replay = function(ctx) {
                ctx.save();
                ctx.strokeStyle = this.color;
                ctx.lineWidth = this.width;
                ctx.beginPath();
                ctx.moveTo(this.startX, this.startY);
                ctx.lineTo(this.endX, this.endY);
                ctx.stroke();
                ctx.restore();
            };
        }

        _telestrateState.strokes.push(stroke);
        _telestrateState.redoStack = [];
        redrawTelestration();
    }

    function drawArrow(ctx, x1, y1, x2, y2) {
        var angle = Math.atan2(y2 - y1, x2 - x1);
        var headLen = 12 + ctx.lineWidth;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headLen * Math.cos(angle - Math.PI / 6), y2 - headLen * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(x2 - headLen * Math.cos(angle + Math.PI / 6), y2 - headLen * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
    }

    function telestrateUndo() {
        if (_telestrateState.strokes.length === 0) return;
        var stroke = _telestrateState.strokes.pop();
        _telestrateState.redoStack.push(stroke);
        redrawTelestration();
    }

    function telestrateRedo() {
        if (_telestrateState.redoStack.length === 0) return;
        var stroke = _telestrateState.redoStack.pop();
        _telestrateState.strokes.push(stroke);
        redrawTelestration();
    }

    function redrawTelestration() {
        var canvas = document.getElementById('telestrate-canvas');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        _telestrateState.strokes.forEach(function(s) {
            if (s.replay) {
                s.replay(ctx);
            } else if (s.tool === 'text') {
                ctx.save();
                ctx.fillStyle = s.color;
                ctx.font = (s.fontSize || 16) + 'px sans-serif';
                ctx.fillText(s.text, s.x, s.y);
                ctx.restore();
            }
        });
    }

    /* ═══════════════════════════════════════════════════════════════
       Wave B — Season Dashboard
       ═══════════════════════════════════════════════════════════════ */

    function initSeasonDashboard() {
        var refreshBtn = document.getElementById('season-refresh-btn');
        if (!refreshBtn) return;
        refreshBtn.addEventListener('click', loadSeasonData);
        // Also load when section becomes visible
        var seasonTab = document.querySelector('.nav-tab[data-route="season"]');
        if (seasonTab) {
            seasonTab.addEventListener('click', function() {
                setTimeout(loadSeasonData, 200);
            });
        }
        loadSeasonData();
    }

    function loadSeasonData() {
        if (typeof bridge === 'undefined' || !bridge) return;
        bridge.get_season_summary(function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                if (data.error) { console.warn('Season error:', data.error); return; }

                document.getElementById('season-match-count').textContent = data.total_matches || 0;
                document.getElementById('season-event-count').textContent = data.total_events || 0;
                document.getElementById('season-shot-count').textContent = data.total_shots || 0;
                document.getElementById('season-avg-xg').textContent = (data.avg_xg || 0).toFixed(3);

                renderSeasonFixtures(data.matches || []);
                renderSeasonLeagueTable(data.matches || []);
            } catch(e) { console.warn('Season load error:', e); }
        });
    }

    function renderSeasonFixtures(matches) {
        var container = document.getElementById('season-fixtures');
        if (!container) return;
        if (!matches || matches.length === 0) {
            container.innerHTML = '<p class="hint">No matches loaded yet.</p>';
            return;
        }
        var sorted = matches.slice().sort(function(a, b) {
            return (a.date || '').localeCompare(b.date || '') || (a.id || 0) - (b.id || 0);
        });
        var html = '';
        sorted.forEach(function(m) {
            html += '<div class="season-fixture-row">' +
                '<span class="season-fixture-date">' + escapeHtml(m.date || '--') + '</span>' +
                '<span class="season-fixture-home">' + escapeHtml(m.home_team || 'Home') + '</span>' +
                '<span class="season-fixture-vs">vs</span>' +
                '<span class="season-fixture-away">' + escapeHtml(m.away_team || 'Away') + '</span>' +
                '<span class="season-fixture-score">' + (m.home_score != null ? m.home_score + '-' + m.away_score : '--') + '</span>' +
                '</div>';
        });
        container.innerHTML = html;
    }

    function renderSeasonLeagueTable(matches) {
        var container = document.getElementById('season-league-table');
        if (!container) return;
        if (!matches || matches.length === 0) {
            container.innerHTML = '<p class="hint">Need match results to build league table.</p>';
            return;
        }
        // Build standings from match data (if scores available)
        var teams = {};
        matches.forEach(function(m) {
            var home = m.home_team || 'Home';
            var away = m.away_team || 'Away';
            if (!teams[home]) teams[home] = { name: home, played: 0, won: 0, drawn: 0, lost: 0, gf: 0, ga: 0, pts: 0 };
            if (!teams[away]) teams[away] = { name: away, played: 0, won: 0, drawn: 0, lost: 0, gf: 0, ga: 0, pts: 0 };
            // If we have scores from analysis (not always available yet)
            // For now, just show basic stats
        });

        var standings = Object.keys(teams).map(function(k) { return teams[k]; });
        // Sort by name as default
        standings.sort(function(a, b) { return a.name.localeCompare(b.name); });

        if (standings.length === 0) {
            container.innerHTML = '<p class="hint">Load matches to see standings.</p>';
            return;
        }

        var html = '<table><thead><tr>' +
            '<th>#</th><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th>Pts</th>' +
            '</tr></thead><tbody>';
        standings.forEach(function(t, i) {
            var gd = t.gf - t.ga;
            html += '<tr class="' + (i < 2 ? 'pos-1' : '') + '">' +
                '<td>' + (i + 1) + '</td>' +
                '<td>' + escapeHtml(t.name) + '</td>' +
                '<td>' + t.played + '</td>' +
                '<td>' + t.won + '</td>' +
                '<td>' + t.drawn + '</td>' +
                '<td>' + t.lost + '</td>' +
                '<td>' + t.gf + '</td>' +
                '<td>' + t.ga + '</td>' +
                '<td>' + (gd >= 0 ? '+' : '') + gd + '</td>' +
                '<td>' + t.pts + '</td>' +
                '</tr>';
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    /* ═══════════════════════════════════════════════════════════════
       Wave C — Training Planner
       ═══════════════════════════════════════════════════════════════ */

    var _trainingState = {
        drills: [],
        sessionDrills: [],
        sessionName: '',
        sessionDate: '',
        sessionDuration: 60,
    };

    function initTrainingPlanner() {
        var searchInput = document.getElementById('training-drill-search');
        var catFilter = document.getElementById('training-category-filter');
        var sessionName = document.getElementById('training-session-name');
        var sessionDate = document.getElementById('training-session-date');
        var sessionDur = document.getElementById('training-session-duration');
        var saveBtn = document.getElementById('training-save-btn');
        var clearBtn = document.getElementById('training-clear-btn');

        if (!searchInput) return;

        loadDrills();

        searchInput.addEventListener('input', renderDrills);
        catFilter.addEventListener('change', renderDrills);

        sessionName.addEventListener('input', function() { _trainingState.sessionName = this.value; });
        sessionDate.addEventListener('change', function() { _trainingState.sessionDate = this.value; });

        if (!sessionDate.value) {
            var today = new Date();
            sessionDate.value = today.toISOString().slice(0, 10);
            _trainingState.sessionDate = sessionDate.value;
        }

        saveBtn.addEventListener('click', function() {
            if (_trainingState.sessionDrills.length === 0) {
                showToast('Add at least one drill to the session.', 'warning');
                return;
            }
            if (!_trainingState.sessionName.trim()) {
                showToast('Enter a session name.', 'warning');
                return;
            }
            var totalMin = 0;
            _trainingState.sessionDrills.forEach(function(d) { totalMin += d.duration_min || 15; });
            var msg = 'Session "' + _trainingState.sessionName + '" saved! (' + _trainingState.sessionDrills.length + ' drills, ' + totalMin + ' min)';
            showToast(msg, 'success');
        });

        clearBtn.addEventListener('click', function() {
            if (_trainingState.sessionDrills.length === 0) return;
            showConfirmDialog('Clear session?', function() {
                _trainingState.sessionDrills = [];
                renderSessionDrills();
            });
        });

        // Make drill list items draggable
        setupTrainingDragDrop();
    }

    function loadDrills() {
        if (typeof bridge === 'undefined' || !bridge) {
            // Fallback: static drills
            _trainingState.drills = [
                { id: '1', name: 'Rondo 5v2', category: 'possession', difficulty: 'medium', duration_min: 10, description: 'Keep-away in tight space' },
                { id: '2', name: 'Finishing Circuit', category: 'finishing', difficulty: 'medium', duration_min: 15, description: 'Rotating shooting stations' },
                { id: '3', name: 'Defensive Shape', category: 'defending', difficulty: 'hard', duration_min: 20, description: 'Compact block + pressing triggers' },
                { id: '4', name: 'Passing Ladder', category: 'passing', difficulty: 'easy', duration_min: 10, description: 'One/two-touch combination patterns' },
                { id: '5', name: 'Interval Sprints', category: 'fitness', difficulty: 'hard', duration_min: 12, description: 'High-intensity interval running' },
                { id: '6', name: 'Corner Kick Routines', category: 'set_piece', difficulty: 'medium', duration_min: 15, description: ' attacking and defending set plays' },
                { id: '7', name: 'Pressing Triggers', category: 'defending', difficulty: 'hard', duration_min: 15, description: 'Counter-press and trap drills' },
                { id: '8', name: 'Positional Play', category: 'possession', difficulty: 'medium', duration_min: 20, description: 'Building through thirds' },
                { id: '9', name: 'Crossing & Finishing', category: 'finishing', difficulty: 'easy', duration_min: 15, description: 'Wide crosses with near-post/far-post runs' },
                { id: '10', name: 'Small-Sided Game', category: 'general', difficulty: 'medium', duration_min: 20, description: '5v5 with constraints' },
            ];
            renderDrills();
            return;
        }
        bridge.get_all_drills(function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                if (data.error) { console.warn('Drill load error:', data.error); return; }
                _trainingState.drills = data.drills || [];
                renderDrills();
            } catch(e) { console.warn('Drill load error:', e); }
        });
    }

    function renderDrills() {
        var container = document.getElementById('training-drill-list');
        if (!container) return;
        var search = (document.getElementById('training-drill-search').value || '').toLowerCase().trim();
        var cat = document.getElementById('training-category-filter').value;

        var filtered = _trainingState.drills.filter(function(d) {
            if (cat !== 'all' && d.category !== cat) return false;
            if (search && (d.name || '').toLowerCase().indexOf(search) < 0) return false;
            return true;
        });

        if (filtered.length === 0) {
            container.innerHTML = '<p class="hint">No drills match filters.</p>';
            return;
        }

        var html = '';
        filtered.forEach(function(d) {
            var inSession = _trainingState.sessionDrills.some(function(sd) { return sd.id === d.id; });
            html += '<div class="training-drill-item" draggable="true" data-drill-id="' + d.id + '" data-name="' + escapeHtml(d.name) + '" data-cat="' + d.category + '" data-dur="' + (d.duration_min || 15) + '" data-diff="' + d.difficulty + '">' +
                '<span class="training-drill-name">' + escapeHtml(d.name) + '</span>' +
                '<span class="training-drill-cat">' + escapeHtml(d.category) + '</span>' +
                '<span class="training-drill-diff ' + d.difficulty + '">' + escapeHtml(d.difficulty) + '</span>' +
                '<span class="training-drill-dur">' + (d.duration_min || 15) + ' min</span>' +
                (inSession ? '<span style="color:var(--success);font-size:0.7rem">✓</span>' : '') +
                '</div>';
        });
        container.innerHTML = html;

        // Wire drag events
        container.querySelectorAll('.training-drill-item').forEach(function(item) {
            item.addEventListener('dragstart', function(e) {
                e.dataTransfer.setData('text/plain', JSON.stringify({
                    id: this.dataset.drillId,
                    name: this.dataset.name,
                    category: this.dataset.cat,
                    duration_min: parseInt(this.dataset.dur, 10),
                    difficulty: this.dataset.diff,
                }));
                this.classList.add('dragging');
            });
            item.addEventListener('dragend', function() {
                this.classList.remove('dragging');
            });
        });
    }

    function setupTrainingDragDrop() {
        var dropZone = document.getElementById('training-session-drills');
        if (!dropZone) return;

        dropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', function() {
            this.classList.remove('drag-over');
        });
        dropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('drag-over');
            try {
                var data = JSON.parse(e.dataTransfer.getData('text/plain'));
                _trainingState.sessionDrills.push(data);
                renderSessionDrills();
            } catch(ex) { /* ignore */ }
        });
    }

    function renderSessionDrills() {
        var container = document.getElementById('training-session-drills');
        if (!container) return;
        if (_trainingState.sessionDrills.length === 0) {
            container.innerHTML = '<p class="hint">Drag drills here to build your session.</p>';
            return;
        }
        var html = '';
        var totalMin = 0;
        _trainingState.sessionDrills.forEach(function(d, idx) {
            totalMin += d.duration_min || 15;
            html += '<div class="training-session-drill-item">' +
                '<span class="order">' + (idx + 1) + '.</span>' +
                '<span class="name">' + escapeHtml(d.name || 'Drill') + '</span>' +
                '<span class="dur">' + (d.duration_min || 15) + ' min</span>' +
                '<span class="remove-drill" data-idx="' + idx + '">✕</span>' +
                '</div>';
        });
        html += '<div style="padding:6px 8px;font-size:0.78rem;color:var(--text-muted);border-top:1px solid var(--border);margin-top:4px;">Total: ' + totalMin + ' min (' + _trainingState.sessionDrills.length + ' drills)</div>';
        container.innerHTML = html;

        // Wire remove buttons
        container.querySelectorAll('.remove-drill').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var idx = parseInt(this.dataset.idx, 10);
                _trainingState.sessionDrills.splice(idx, 1);
                renderSessionDrills();
            });
        });
    }

    /* ═══════════════════════════════════════════════════════════════
       Wave D — Presentation Mode
       ═══════════════════════════════════════════════════════════════ */

    var _presState = {
        matchId: null,
        currentSlide: 0,
        slides: [],
        isFullscreen: false,
        matchData: null,
    };

    function initPresentationMode() {
        var startBtn = document.getElementById('pres-start-btn');
        var prevBtn = document.getElementById('pres-prev-btn');
        var nextBtn = document.getElementById('pres-next-btn');
        var fullscreenBtn = document.getElementById('pres-fullscreen-btn');
        var exportBtn = document.getElementById('pres-export-btn');

        if (!startBtn) return;

        // Populate match select
        if (typeof bridge !== 'undefined' && bridge) {
            bridge.get_all_matches(function(result) {
                try {
                    var data = typeof result === 'string' ? JSON.parse(result) : result;
                    var sel = document.getElementById('pres-match-select');
                    sel.innerHTML = '<option value="" data-i18n="presentationSelectMatch">Select Match</option>';
                    (data || []).forEach(function(m) {
                        var name = m.name || (m.home_team + ' vs ' + m.away_team) || 'Match #' + m.id;
                        sel.innerHTML += '<option value="' + m.id + '">' + escapeHtml(name) + '</option>';
                    });
                } catch(e) { console.warn(e); }
            });
        }

        startBtn.addEventListener('click', function() {
            var matchId = parseInt(document.getElementById('pres-match-select').value, 10);
            if (!matchId) { showToast('Select a match first.', 'warning'); return; }
            _presState.matchId = matchId;
            loadPresentationData(matchId);
        });

        prevBtn.addEventListener('click', function() { navigateSlide(-1); });
        nextBtn.addEventListener('click', function() { navigateSlide(1); });

        fullscreenBtn.addEventListener('click', function() {
            var container = document.getElementById('presentation-slides');
            if (!_presState.isFullscreen) {
                container.classList.add('pres-fullscreen');
                _presState.isFullscreen = true;
                fullscreenBtn.textContent = '✕ Exit Fullscreen';
            } else {
                container.classList.remove('pres-fullscreen');
                _presState.isFullscreen = false;
                fullscreenBtn.textContent = '⛶ Fullscreen';
            }
            window.dispatchEvent(new Event('resize'));
        });

        exportBtn.addEventListener('click', function() {
            showToast('Video export: capture slides + commentary (coming soon).', 'info');
        });

        // Keyboard nav
        document.addEventListener('keydown', function(e) {
            var section = document.getElementById('presentation-section');
            if (!section || section.classList.contains('hidden')) return;
            if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT')) return;
            if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); navigateSlide(1); }
            if (e.key === 'ArrowLeft') { e.preventDefault(); navigateSlide(-1); }
            if (e.key === 'Escape' && _presState.isFullscreen) {
                document.getElementById('pres-fullscreen-btn').click();
            }
        });
    }

    function loadPresentationData(matchId) {
        if (typeof bridge === 'undefined' || !bridge) { showToast('Bridge not ready.', 'error'); return; }

        // Get match info from all matches
        bridge.get_all_matches(function(matchResult) {
            try {
                var matches = typeof matchResult === 'string' ? JSON.parse(matchResult) : matchResult;
                if (Array.isArray(matches)) {
                    var match = matches.find(function(m) { return m.id === matchId; });
                    _presState.matchData = match || { home_team: 'Home', away_team: 'Away' };
                } else {
                    _presState.matchData = {};
                }
            } catch(e) { _presState.matchData = {}; }
            _presState.matchData = _presState.matchData || {};

            // Load events for stats
            bridge.get_match_events(matchId, function(evResult) {
                try {
                    var events = typeof evResult === 'string' ? JSON.parse(evResult) : evResult;
                    _presState.matchData.events = Array.isArray(events) ? events : (events.events || []);
                } catch(e) { _presState.matchData.events = []; }

                buildPresentationSlides();
                _presState.currentSlide = 0;
                document.getElementById('presentation-slides').classList.remove('hidden');
                renderSlide(0);
            });
        });
    }

    function buildPresentationSlides() {
        var d = _presState.matchData || {};
        var events = d.events || [];
        var home = d.home_team || 'Home';
        var away = d.away_team || 'Away';
        var matchName = d.name || (home + ' vs ' + away);

        var totalShots = events.filter(function(e) { return e.event_type === 'shot'; }).length;
        var totalGoals = events.filter(function(e) { return e.event_type === 'goal'; }).length;
        var totalPasses = events.filter(function(e) { return e.event_type === 'pass'; }).length;
        var totalTackles = events.filter(function(e) { return e.event_type === 'tackle'; }).length;
        var totalXg = 0;
        events.forEach(function(e) {
            var meta = e.metadata || {};
            totalXg += meta.xg || 0;
        });

        _presState.slides = [
            {
                title: matchName,
                subtitle: 'Match Analysis Presentation',
                stat: null,
                label: null,
                bg: 'pres-bg-gradient',
                grid: null,
            },
            {
                title: 'Match Stats Overview',
                subtitle: null,
                stat: null,
                label: null,
                bg: 'pres-bg-away',
                grid: [
                    { label: 'Goals', value: totalGoals },
                    { label: 'Shots', value: totalShots },
                    { label: 'Passes', value: totalPasses },
                    { label: 'Tackles', value: totalTackles },
                ],
            },
            {
                title: 'xG Analysis',
                subtitle: 'Expected Goals: ' + totalXg.toFixed(2),
                stat: totalXg.toFixed(2),
                label: 'Total xG',
                bg: 'pres-bg-gradient',
                grid: null,
            },
            {
                title: 'Event Breakdown',
                subtitle: 'Shots: ' + totalShots + ' | Goals: ' + totalGoals + ' | Passes: ' + totalPasses + ' | Tackles: ' + totalTackles,
                stat: null,
                label: null,
                bg: 'pres-bg-away',
                grid: null,
            },
            {
                title: home + ' vs ' + away,
                subtitle: 'Thank you',
                stat: null,
                label: 'Analysis by Kawkab AI',
                bg: 'pres-bg-gradient',
                grid: null,
            },
        ];
    }

    function navigateSlide(direction) {
        var newIdx = _presState.currentSlide + direction;
        if (newIdx < 0 || newIdx >= _presState.slides.length) return;
        _presState.currentSlide = newIdx;
        renderSlide(newIdx);
    }

    function renderSlide(idx) {
        var slide = _presState.slides[idx];
        if (!slide) return;
        var container = document.getElementById('pres-slide-content');
        var counter = document.getElementById('pres-slide-counter');
        if (!container) return;

        counter.textContent = (idx + 1) + ' / ' + _presState.slides.length;

        var html = '<div class="' + slide.bg + '">';
        html += slide.title ? '<h1>' + escapeHtml(slide.title) + '</h1>' : '';
        html += slide.subtitle ? '<p class="pres-subtitle">' + escapeHtml(slide.subtitle) + '</p>' : '';
        html += slide.stat != null ? '<div class="pres-stat">' + slide.stat + '</div>' : '';
        html += slide.label ? '<div class="pres-label">' + escapeHtml(slide.label) + '</div>' : '';

        if (slide.grid && slide.grid.length > 0) {
            html += '<div class="pres-grid">';
            slide.grid.forEach(function(g) {
                html += '<div class="pres-stat-card"><div class="pres-stat">' + g.value + '</div><div class="pres-label">' + escapeHtml(g.label) + '</div></div>';
            });
            html += '</div>';
        }

        html += '</div>';
        container.innerHTML = html;
        container.className = 'pres-slide-content ' + (slide.bg || '');

        // Update nav buttons
        document.getElementById('pres-prev-btn').disabled = idx <= 0;
        document.getElementById('pres-next-btn').disabled = idx >= _presState.slides.length - 1;
    }

    /* ═══════════════════════════════════════════════════════════════
       Wave E — Scout Portal
       ═══════════════════════════════════════════════════════════════ */

    var _scoutState = {
        searchResults: [],
        shortlist: [],
        compareA: null,
        compareB: null,
    };

    function initScoutPortal() {
        // Tab switching
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
            // Simulated search
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
            } catch(e) { console.warn('Scout search error:', e); }
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

        // Wire action buttons
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
                // Add to compare dropdowns
                addToCompare(trackId, name);
                // Switch to compare tab
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
                    // Also update search results if visible
                    renderScoutResults();
                    showToast('Removed from shortlist.', 'info');
                }
            });
        });
    }

    function loadShortlist() {
        if (typeof bridge === 'undefined' || !bridge) {
            // Use local state
            renderShortlist();
            return;
        }
        bridge.get_shortlist(function(result) {
            try {
                var data = typeof result === 'string' ? JSON.parse(result) : result;
                _scoutState.shortlist = data.players || [];
                renderShortlist();
            } catch(e) { console.warn('Shortlist load error:', e); }
        });
    }

    function generateScoutReport() {
        if (_scoutState.shortlist.length === 0) {
            showToast('Add players to your shortlist first.', 'warning');
            return;
        }

        // Generate inline report
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

        // Add if not already present
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

        // Auto-select
        if (!selA.value) selA.value = trackId;
        else if (!selB.value) selB.value = trackId;
    }

    function scoutCompare(trackIdA, trackIdB) {
        // Look up in search results
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

    document.addEventListener('DOMContentLoaded', function() {
        document.getElementById('edit-event-save').addEventListener('click', function() {
            var eventId = parseInt(document.getElementById('edit-event-id').value, 10);
            if (!eventId) return;
            var updates = {
                event_type: document.getElementById('edit-event-type').value,
                team: document.getElementById('edit-event-team').value,
            };
            var note = document.getElementById('edit-event-note').value.trim();
            if (note) {
                updates.metadata = { coach_note: note };
            }
            bridge.update_event(eventId, JSON.stringify(updates)).then(function(json) {
                try {
                    var result = JSON.parse(json);
                    if (result.success) {
                        document.getElementById('edit-event-modal').classList.add('hidden');
                        setTimeout(loadEventTimeline, 100);
                    } else {
                        showToast('Failed to update event', 'error');
                    }
                } catch (ex) {
                    showToast('Failed to save: ' + ex, 'error');
                }
            }).catch(function(err) {
                console.error('Update event failed:', err);
            });
        });

        document.getElementById('edit-event-cancel').addEventListener('click', function() {
            document.getElementById('edit-event-modal').classList.add('hidden');
        });

        document.getElementById('edit-event-modal').addEventListener('click', function(e) {
            if (e.target === this) {
                this.classList.add('hidden');
            }
        });

        var video = document.getElementById('match-video');
        if (video) {
            video.addEventListener('timeupdate', function() {
                highlightCurrentTimelineItem(this.currentTime);
            });
        }

        // Init theme before anything else
        initTheme();

        // Init chart cross-filter callback
        wireChartFilter();

        setupEventListeners();

        // Detect initial language from KawkabPolish or localStorage
        var initialLang = 'en';
        if (window.KawkabPolish) {
            try {
                var stored = localStorage.getItem('kawkab_lang');
                if (stored === 'ar' || stored === 'en') initialLang = stored;
            } catch(e) {}
        }
        setLanguage(initialLang);

        initQWebChannel();
        setupFeedbackStars();
        setupGlobalSearch();
        setupPlayerComparison();
        setTimeout(connectProgressSignals, 500);

        // ── Item 7: Init Timeline Scrubber ──
        initTimelineScrubber();
        // Re-init scrubber when timeline events load
        var _origLoadTimeline = loadEventTimeline;
        loadEventTimeline = function() {
            _origLoadTimeline.apply(this, arguments);
            setTimeout(initTimelineScrubber, 300);
        };

        // ── Item 10: Init Density Toggle ──
        initDensityToggle();

        // ── Item 12: Init Color Settings ──
        initColorSettings();

        // ── Item 13: Init Video Shortcuts ──
        initVideoShortcuts();

        // ── Item 14: Save/restore filter state on route change ──
        restoreFilterState();

        // Initialize SPA Router
        var router = new KawkabRouter();
        var _origNavigate = router.navigate || router._onHashChange;
        router.register('dashboard', 'dashboard-section', function() {
            saveFilterState();
            loadDashboard();
        });
        router.register('upload', 'upload-section', saveFilterState);
        router.register('analysis', 'analysis-section', saveFilterState);
        router.register('results', 'results-section', function() {
            saveFilterState();
        });
        router.register('report', 'report-section', saveFilterState);
        router.register('history', 'history-section', saveFilterState);
        router.register('professional', 'professional-section', saveFilterState);
        router.register('coding', 'coding-section', function() {
            loadCodingMatchSelect();
        });
        router.register('review', 'review-section', function() {
            loadReviewMatchSelect();
        });
        router.register('feedback', 'feedback-section', saveFilterState);
        router.register('season', 'season-section', function() {
            saveFilterState();
            loadSeasonData();
        });
        router.register('training', 'training-section', saveFilterState);
        router.register('scout', 'scout-section', saveFilterState);
        router.register('multiangle', 'multiangle-section', function() {
            saveFilterState();
            initMultiAngle();
        });
        router.register('physiology', 'physiology-section', function() {
            saveFilterState();
            initPhysiology();
        });
        router.register('collaboration', 'collaboration-section', function() {
            saveFilterState();
            initCollaboration();
        });
        router.register('livetagging', 'livetagging-section', function() {
            saveFilterState();
            initLiveTagging();
        });
        router.register('scoutcamera', 'scoutcamera-section', function() {
            saveFilterState();
            initScoutCamera();
        });

        // Initialize PWA on load
        initPWA();

        // Initialize Skeletons
        var skeletons = new KawkabSkeletons();
        skeletons.register('results-section', '100%', 60, 4);
        skeletons.register('report-section', '100%', 40, 6);
        skeletons.register('dashboard-kpis', '100%', 40, 5);
        skeletons.register('dashboard-recent-list', '100%', 30, 3);

        // Initialize nav tabs
        setupNavTabs();

        // Initialize quick actions
        setupQuickActions();

        // Initialize perf utilities
        initPassiveListeners();
        initThrottledScroll();
        initThrottledResize();

        // Initialize keyboard nav
        initKeyboardNav();

        // Initialize tooltips (from app-tooltips.js)
        if (typeof window.initTooltips === "function") {
            window.initTooltips();
        }

        // Initialize notifications (from ui.js)
        setTimeout(function () {
            if (window.KawkabUI && window.KawkabUI.initNotifications) {
                window.KawkabUI.initNotifications();
            }
        }, 100);

        // Add confirmation to destructive actions
        var deleteBtns = document.querySelectorAll('[data-confirm]');
        deleteBtns.forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                var msg = this.dataset.confirm || 'Are you sure?';
                e.preventDefault();
                var originalClick = this;
                showConfirmDialog(msg, function () {
                    originalClick.click();
                });
            });
        });

        // ── View toggle wiring ──
        setupViewToggles();

        // ── Batch action wiring ──
        setupBatchActions();

        // ── Coding Workspace Init ──
        initCodingWorkspace();

        // ── Event Review Init ──
        initReviewWorkspace();

        // ── Phase 2.3-4 & 3-4 Init ──
        initTacticsWorkspace();
        initAiWorkspace();
        initSquadWorkspace();

        // ── Wave A — Telestration ──
        initTelestration();

        // ── Wave B — Season Dashboard ──
        initSeasonDashboard();

        // ── Wave C — Training Planner ──
        initTrainingPlanner();

        // ── Wave D — Presentation Mode ──
        initPresentationMode();

        // ── Wave E — Scout Portal ──
        initScoutPortal();
    });
})();
