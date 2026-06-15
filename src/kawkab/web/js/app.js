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
                        loadMatchHistory();
                        loadKnowledgeBaseStats();
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

        container.innerHTML = matches.map(match => `
            <div class="match-item" data-match-id="${match.id}">
                <div class="match-info">
                    <span class="match-name">${escapeHtml(match.name)}</span>
                    <span class="match-date">${formatDate(match.created_at)}</span>
                </div>
                <button class="btn btn-secondary">View</button>
            </div>
        `).join('');

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
        // Reload match details and display
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
        });

        analyzeBtn.addEventListener('click', startAnalysis);
        generateReportBtn.addEventListener('click', generateReport);
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
            document.getElementById('results-section').classList.remove('hidden');
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

    document.addEventListener('DOMContentLoaded', function() {
        setupEventListeners();
        setLanguage('en');
        initQWebChannel();

        setTimeout(connectProgressSignals, 500);
    });
})();
