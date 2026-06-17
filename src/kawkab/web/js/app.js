// Kawkab AI - Frontend JavaScript
// Communicates with Python backend via QWebChannel

(function() {
    'use strict';

    let bridge = null;
    let currentLanguage = 'en';
    let currentMatchId = null;
    let currentVideoPath = null;
    let analysisResult = null;

    const i18n = {
        en: {
            uploadTitle: '📹 Upload Match Video',
            dragDrop: 'Drag & drop your match video here',
            or: 'or',
            browse: 'Browse Files',
            supportsHint: 'Supports MP4, MOV, AVI (up to 4GB)',
            analysisTitle: '⚙️ Analysis',
            matchNamePlaceholder: 'Match name (e.g., Team A vs Team B)',
            analyze: '🚀 Analyze Match',
            resultsTitle: '📊 Analysis Results',
            matchSummary: 'Match Summary',
            possession: 'Possession',
            homeStats: 'Home Team Stats',
            awayStats: 'Away Team Stats',
            overallConfidence: 'Overall Confidence',
            generateReport: '🤖 Generate Coach Report',
            exportPdf: '📄 Export PDF',
            reportTitle: '🤖 Coach Report',
            historyTitle: '📚 Match History',
            noMatches: 'No matches yet. Upload your first match above!',
            llmChecking: '🔴 LLM: Checking...',
            llmOnline: '🟢 LLM: Online',
            llmOffline: '🔴 LLM: Offline',
            gpuInfo: '🎮 GPU Information',
            gpuName: 'GPU',
            gpuTier: 'Tier',
            recSettings: 'Recommended Settings',
            currSettings: 'Current Settings',
            close: 'Close',
        },
        ar: {
            uploadTitle: '📹 تحميل فيديو المباراة',
            dragDrop: 'اسحب وأفلت فيديو المباراة هنا',
            or: 'أو',
            browse: 'تصفح الملفات',
            supportsHint: 'يدعم MP4, MOV, AVI (حتى 4 جيجابايت)',
            analysisTitle: '⚙️ التحليل',
            matchNamePlaceholder: 'اسم المباراة (مثال: الفريق أ ضد الفريق ب)',
            analyze: '🚀 تحليل المباراة',
            resultsTitle: '📊 نتائج التحليل',
            matchSummary: 'ملخص المباراة',
            possession: 'الاستحواذ',
            homeStats: 'إحصائيات الفريق المضيف',
            awayStats: 'إحصائيات الفريق الضيف',
            overallConfidence: 'مستوى الثقة العام',
            generateReport: '🤖 إنشاء تقرير المدرب',
            exportPdf: '📄 تصدير PDF',
            reportTitle: '🤖 تقرير المدرب',
            historyTitle: '📚 سجل المباريات',
            noMatches: 'لا توجد مباريات حتى الآن. حمّل أول مباراة أعلاه!',
            llmChecking: '🔴 LLM: جاري التحقق...',
            llmOnline: '🟢 LLM: متصل',
            llmOffline: '🔴 LLM: غير متصل',
            gpuInfo: '🎮 معلومات GPU',
            gpuName: 'GPU',
            gpuTier: 'الفئة',
            recSettings: 'الإعدادات الموصى بها',
            currSettings: 'الإعدادات الحالية',
            close: 'إغلاق',
        }
    };

    function t(key) {
        return (i18n[currentLanguage] && i18n[currentLanguage][key]) || i18n.en[key] || key;
    }

    function setLanguage(lang) {
        currentLanguage = lang;
        document.documentElement.lang = lang;
        document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';

        document.querySelector('#upload-section h2').textContent = t('uploadTitle');
        document.querySelector('#drop-zone p:first-child').textContent = t('dragDrop');
        document.querySelector('#browse-btn').textContent = t('browse');
        document.querySelector('#drop-zone .hint').textContent = t('supportsHint');
        document.querySelector('#analysis-section h2').textContent = t('analysisTitle');
        document.querySelector('#match-name').placeholder = t('matchNamePlaceholder');
        document.querySelector('#analyze-btn').textContent = t('analyze');
        document.querySelector('#results-section h2').textContent = t('resultsTitle');
        document.querySelector('#generate-report-btn').textContent = t('generateReport');
        document.querySelector('#export-pdf-btn').textContent = t('exportPdf');
        document.querySelector('#report-section h2').textContent = t('reportTitle');
        document.querySelector('#history-section h2').textContent = t('historyTitle');

        if (currentMatchId) {
            renderHistory();
        }
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
                        console.log('QWebChannel connected successfully');

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
                console.log('Waiting for Qt web channel transport...');
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
                    const data = JSON.parse(await bridge.search_football_team(query));
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
            const result = JSON.parse(await bridge.import_football_team_squad(matchId, apiTeamId, side));
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
            const data = JSON.parse(await bridge.verify_match_with_api(currentMatchId, apiMatchId));
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
                    const data = JSON.parse(await bridge.search_bzzoiro_team(query));
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
            const result = JSON.parse(await bridge.import_bzzoiro_team_squad(matchId, teamId, side));
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
            const data = JSON.parse(await bridge.verify_match_bzzoiro(currentMatchId, eventId));
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
            const data = JSON.parse(await bridge.get_bzzoiro_predictions(eventId));
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
            const data = JSON.parse(await bridge.get_bzzoiro_standings(leagueId));
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
                    const data = JSON.parse(await bridge.search_apifootball_team(query));
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
            const result = JSON.parse(await bridge.import_apifootball_squad(matchId, teamId, side));
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
            const data = JSON.parse(await bridge.verify_match_apifootball(currentMatchId, fixtureId));
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
            const data = JSON.parse(await bridge.get_apifootball_predictions(fixtureId));
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
            const data = JSON.parse(await bridge.get_easy_soccer_event(eventId));
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
            const data = JSON.parse(await bridge.get_easy_soccer_incidents(eventId));
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
                    const data = JSON.parse(await bridge.search_thesportsdb_team(query));
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
            const data = JSON.parse(await bridge.get_thesportsdb_team_info(teamId));
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
            const data = JSON.parse(await bridge.get_statsbomb_events(matchId));
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
            const data = JSON.parse(await bridge.get_statsbomb_lineups(matchId));
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
            const data = JSON.parse(await bridge.search_statsbomb_team(query));
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
                const data = JSON.parse(await bridge.search_openfootball_team(query));
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
            const data = JSON.parse(await bridge.simulate_trajectory(speed, angle, spin, direction, 2.5));
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
            const data = JSON.parse(await bridge.set_manual_weather(temp, precip, wind, humidity, conditions));
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
            const data = JSON.parse(await bridge.fetch_match_weather(lat, lon, date, false));
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
            const data = JSON.parse(await bridge.classify_video_weather(videoPath));
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
            const data = JSON.parse(await bridge.classify_event_rule(event, x, y, side));
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
            const data = JSON.parse(await bridge.check_offside(ax, dx, bx, 'right'));
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
            const data = JSON.parse(await bridge.compute_xgot(shotX, shotY, 'foot', false));
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
            const data = JSON.parse(await bridge.simulate_ball_cfd(wind, spin, radius));
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
            const data = JSON.parse(await bridge.rf_draw_pitch(scale));
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
            const matches = JSON.parse(await bridge.get_all_matches());
            renderMatchList(matches);
        } catch (e) {
            console.error('Failed to load matches:', e);
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
            alert('Please select a video file');
            return;
        }

        if (file.size > 4 * 1024 * 1024 * 1024) {
            alert('File too large. Maximum 4GB.');
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

        try {
            const matchId = await bridge.save_match(matchName, currentVideoPath);
            if (matchId === 0) {
                throw new Error('Failed to save match');
            }

            currentMatchId = matchId;

            const resultJson = await bridge.analyze_match(matchId, currentVideoPath);
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
            alert(`Analysis failed: ${e.message || e}`);
        } finally {
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

        setupVideoOverlay();
        setTimeout(generateVisualizations, 500);
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

    async function generateReport() {
        if (!bridge || !analysisResult || !currentMatchId) return;

        const generateBtn = document.getElementById('generate-report-btn');
        const reportContent = document.getElementById('report-content');
        const reportSection = document.getElementById('report-section');

        generateBtn.disabled = true;
        reportContent.textContent = 'Generating report... (this may take 30-60 seconds)';
        reportSection.classList.remove('hidden');

        try {
            const summary = JSON.stringify(analysisResult);
            const report = await bridge.generate_report(currentMatchId, currentLanguage, summary);
            reportContent.textContent = report;
        } catch (e) {
            console.error('Report generation failed:', e);
            reportContent.textContent = `Error: ${e.message || e}`;
        } finally {
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
            const data = JSON.parse(await bridge.get_all_player_profiles());
            const roster = document.getElementById('player-roster');
            if (!data.profiles || data.profiles.length === 0) {
                roster.innerHTML = '<p class="hint">No players yet. Create your first profile above.</p>';
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
        }
    }

    async function loadFaceGallery() {
        if (!bridge) return;
        try {
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
        }
    }

    async function uploadFacePhoto() {
        if (!bridge) return;
        const fileInput = document.getElementById('face-photo-input');
        const jersey = parseInt(document.getElementById('face-jersey-input').value) || 0;
        const name = document.getElementById('face-name-input').value.trim();

        if (!fileInput.files || !fileInput.files[0]) {
            alert('Please select a photo file');
            return;
        }
        if (!name) {
            alert('Please enter the player name');
            return;
        }

        try {
            const path = fileInput.files[0].path;
            const result = JSON.parse(await bridge.upload_face_photo(path, name, jersey));
            if (result.success) {
                alert(`Face enrolled for ${result.display_name} (confidence: ${(result.confidence * 100).toFixed(0)}%)`);
                fileInput.value = '';
                document.getElementById('face-jersey-input').value = '';
                document.getElementById('face-name-input').value = '';
                await loadFaceGallery();
            } else {
                alert('Error: ' + (result.error || 'No face detected'));
            }
        } catch (e) {
            console.error('Face upload failed:', e);
            alert('Failed to upload face photo');
        }
    }

    async function matchFacesInMatch() {
        if (!bridge || !currentMatchId) {
            alert('Please select a match first');
            return;
        }
        if (!confirm('Run face recognition on all tracked players in the current match?')) return;
        try {
            const result = JSON.parse(await bridge.match_faces_in_match(currentMatchId));
            if (result.success) {
                alert(`Face matching complete! Identified ${result.identified_count} player(s).`);
            } else {
                alert('Error: ' + (result.error || 'Unknown error'));
            }
        } catch (e) {
            console.error('Face matching failed:', e);
            alert('Failed to run face recognition');
        }
    }

    async function createPlayerProfile() {
        if (!bridge) return;
        const name = document.getElementById('player-name').value.trim();
        const jersey = parseInt(document.getElementById('player-jersey').value) || 0;
        const position = document.getElementById('player-position').value.trim();

        if (!name || !position) {
            alert('Please enter player name and position');
            return;
        }

        try {
            const result = JSON.parse(await bridge.create_player_profile(name, '', jersey, position));
            if (result.success) {
                alert(`Player profile created! ID: ${result.profile_id}`);
                document.getElementById('player-name').value = '';
                document.getElementById('player-jersey').value = '';
                document.getElementById('player-position').value = '';
                await loadPlayerProfiles();
            } else {
                alert('Error: ' + (result.error || 'Unknown error'));
            }
        } catch (e) {
            console.error('Create player failed:', e);
            alert('Failed to create player profile');
        }
    }

    async function populateMatchDropdowns() {
        if (!bridge) return;
        try {
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
        }
    }

    async function compareMatches() {
        if (!bridge) return;
        const m1 = document.getElementById('compare-match-1').value;
        const m2 = document.getElementById('compare-match-2').value;
        const focus = document.getElementById('compare-focus').value.trim();

        if (!m1 || !m2) {
            alert('Please select two matches to compare');
            return;
        }

        try {
            const result = JSON.parse(await bridge.compare_matches(m1, m2, focus));
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
        } catch (e) {
            console.error('Compare matches failed:', e);
            alert('Failed to compare matches');
        }
    }

    async function exportMatchData(format) {
        if (!bridge) return;
        const matchId = document.getElementById('export-match-select').value;
        if (!matchId) {
            alert('Please select a match to export');
            return;
        }

        try {
            const result = JSON.parse(
                format === 'csv'
                    ? await bridge.export_match_csv(matchId)
                    : await bridge.export_match_json(matchId)
            );
            if (result.success) {
                alert(`Export complete! File saved to: ${result.path}`);
            } else {
                alert('Export failed: ' + (result.error || 'Unknown error'));
            }
        } catch (e) {
            console.error('Export failed:', e);
            alert('Failed to export match data');
        }
    }

    async function getQualityReport() {
        if (!bridge) return;
        const matchId = document.getElementById('quality-match-select').value;
        if (!matchId) {
            alert('Please select a match');
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
            alert('Failed to get quality report');
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
            alert(`Analysis error: ${error}`);
        });
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
            const result = JSON.parse(await bridge.submit_feedback(payload));
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
            const result = JSON.parse(await bridge.submit_issue(payload));
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
                alert('Export failed: ' + result.error);
            } else {
                alert('Report saved! Open in browser and print to PDF:\n' + result.path);
            }
        } catch (e) {
            console.error('PDF export failed:', e);
            alert('Failed to export report');
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

    async function swapTeams() {
        if (!bridge || !currentMatchId) return;
        if (!confirm('Swap home and away team assignment?')) return;
        try {
            const result = JSON.parse(await bridge.swap_teams(currentMatchId));
            if (result.error) {
                alert('Swap failed: ' + result.error);
            } else {
                alert('Teams swapped! ' + result.home + ' is now home, ' + result.away + ' is now away. Re-analyze to update stats.');
            }
        } catch (e) {
            console.error('Swap teams failed:', e);
            alert('Failed to swap teams');
        }
    }

    async function generateVisualizations() {
        if (!bridge || !currentMatchId) return;
        try {
            const result = JSON.parse(await bridge.generate_visualizations(currentMatchId));
            if (result.error) {
                alert('Visualization failed: ' + result.error);
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
            alert('Failed to generate visualizations');
        }
    }

    function loadEventTimeline() {
        if (!currentMatchId) return;
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
        });
    }

    function renderTimeline(events) {
        const list = document.getElementById('timeline-list');
        if (!list) return;
        if (!events || events.length === 0) {
            list.innerHTML = '<div class="timeline-empty">No events detected</div>';
            return;
        }
        const filterType = document.getElementById('timeline-filter-type');
        const filterVal = filterType ? filterType.value : 'all';
        const filtered = filterVal === 'all' ? events : events.filter(function(e) {
            return e.event_type === filterVal;
        });
        filtered.sort(function(a, b) { return (a.timestamp || 0) - (b.timestamp || 0); });
        list.innerHTML = filtered.map(function(e, idx) {
            return renderTimelineItem(e, idx);
        }).join('');
    }

    function renderTimelineItem(e, idx) {
        var label = e.event_type.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
        var icon = eventTypeIcon(e.event_type);
        var ts = formatTimestamp(e.timestamp || 0);
        var teamClass = e.team === 'home' || e.team === 'away' ? e.team : '';
        var teamBadge = teamClass ? '<span class="timeline-team-badge ' + teamClass + '">' + teamClass + '</span>' : '';
        var activeClass = '';
        return '<div class="timeline-item ' + (e.event_type || '') + ' ' + activeClass + '" data-idx="' + idx + '" data-event-id="' + (e.id || '') + '" data-timestamp="' + (e.timestamp || 0) + '">' +
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
        var item = e.target.closest('.timeline-item');
        if (item && !e.target.closest('.timeline-item-actions')) {
            timelineSeek(item.dataset.timestamp);
            return;
        }
        if (e.target.closest('.edit-btn')) {
            var item = e.target.closest('.timeline-item');
            var eventId = parseInt(item.dataset.eventId, 10);
            var events = window._timelineEvents || [];
            var ev = events[parseInt(item.dataset.idx, 10)] || {};
            openEditModal(eventId, ev.event_type, ev.team);
            e.stopPropagation();
            return;
        }
        if (e.target.closest('.delete-btn')) {
            if (!confirm('Delete this event?')) return;
            var item = e.target.closest('.timeline-item');
            var eventId = parseInt(item.dataset.eventId, 10);
            bridge.delete_event(eventId).then(function(json) {
                try {
                    var result = JSON.parse(json);
                    if (result.success) {
                        setTimeout(loadEventTimeline, 100);
                    }
                } catch (ex) {}
            });
            e.stopPropagation();
            return;
        }
    });

    document.addEventListener('change', function(e) {
        if (e.target.id === 'timeline-filter-type') {
            renderTimeline(window._timelineEvents || []);
        }
    });

    document.getElementById('match-video').addEventListener('timeupdate', function() {
        highlightCurrentTimelineItem(this.currentTime);
    });

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
                        alert('Failed to update event');
                    }
                } catch (ex) {
                    alert('Failed to save: ' + ex);
                }
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

        setupEventListeners();
        setLanguage('en');
        initQWebChannel();
        setupFeedbackStars();
        setTimeout(connectProgressSignals, 500);
    });
})();
