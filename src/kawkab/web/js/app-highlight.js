(function () {
    'use strict';

    var _hli = false;
    var _hlMatchId = null;
    var _hlEvents = [];
    var _hlSelected = new Set();
    var _hlReelId = null;
    var _hlPollInterval = null;

    function initHighlightWorkspace() {
        if (_hli) return;
        _hli = true;

        var matchSelect = document.getElementById('highlight-match-select');
        var loadBtn = document.getElementById('highlight-load-events-btn');
        var genBtn = document.getElementById('highlight-generate-btn');
        var filterInput = document.getElementById('highlight-event-filter');
        var contextInput = document.getElementById('highlight-context-seconds');

        if (!matchSelect) return;

        // Load matches
        loadMatchesIntoSelect(matchSelect);

        matchSelect.addEventListener('change', function () {
            _hlMatchId = parseInt(this.value) || null;
        });

        loadBtn.addEventListener('click', function () {
            if (!_hlMatchId) {
                showToast('Select a match first', 'warning');
                return;
            }
            loadHighlightEvents(_hlMatchId);
        });

        filterInput.addEventListener('input', function () {
            renderHighlightEventList();
        });

        document.querySelectorAll('.highlight-type-filter').forEach(function (cb) {
            cb.addEventListener('change', function () {
                renderHighlightEventList();
            });
        });

        genBtn.addEventListener('click', function () {
            generateHighlightReel();
        });
    }

    function loadMatchesIntoSelect(select) {
        var bridgeMethod = (typeof bridge !== 'undefined' && bridge.get_all_matches)
            ? 'get_all_matches' : null;
        if (!bridgeMethod) {
            if (bridge && typeof bridge === 'object') {
                for (var k in bridge) {
                    if (k.indexOf('get_all_matches') >= 0 || k.indexOf('getAllMatches') >= 0) {
                        bridgeMethod = k;
                        break;
                    }
                }
            }
        }
        if (!bridgeMethod) {
            select.innerHTML = '<option value="">Bridge not available</option>';
            return;
        }
        bridge[bridgeMethod]().then(function (raw) {
            try {
                var data = typeof raw === 'string' ? JSON.parse(raw) : raw;
                var matches = Array.isArray(data) ? data : (data.matches || data.data || []);
                select.innerHTML = '<option value="">Select a match...</option>';
                matches.forEach(function (m) {
                    var opt = document.createElement('option');
                    opt.value = m.id || m.match_id || '';
                    opt.textContent = m.name || m.match_name || 'Match ' + (m.id || '');
                    select.appendChild(opt);
                });
            } catch (e) {
                select.innerHTML = '<option value="">Error loading matches</option>';
            }
        }).catch(function () {
            select.innerHTML = '<option value="">Bridge call failed</option>';
        });
    }

    function loadHighlightEvents(matchId) {
        var container = document.getElementById('highlight-events-container');
        var list = document.getElementById('highlight-event-list');
        if (!container || !list) return;

        container.classList.remove('hidden');
        list.innerHTML = '<p class="hint">Loading events...</p>';

        var method = (typeof bridge !== 'undefined' && bridge.get_match_events)
            ? bridge.get_match_events : null;
        if (!method) {
            list.innerHTML = '<p class="hint">Bridge not available</p>';
            return;
        }

        method(matchId).then(function (raw) {
            try {
                var data = typeof raw === 'string' ? JSON.parse(raw) : raw;
                _hlEvents = Array.isArray(data) ? data : (data.events || data.data || []);
                _hlSelected = new Set();
                renderHighlightEventList();
            } catch (e) {
                list.innerHTML = '<p class="hint">Error parsing events</p>';
            }
        }).catch(function () {
            list.innerHTML = '<p class="hint">Failed to load events</p>';
        });
    }

    function renderHighlightEventList() {
        var list = document.getElementById('highlight-event-list');
        if (!list) return;

        var filterText = (document.getElementById('highlight-event-filter').value || '').toLowerCase();
        var activeTypes = new Set();
        document.querySelectorAll('.highlight-type-filter:checked').forEach(function (cb) {
            activeTypes.add(cb.value);
        });

        var filtered = _hlEvents.filter(function (e) {
            var type = (e.event_type || e.type || '').toLowerCase();
            if (activeTypes.size > 0 && !activeTypes.has(type)) return false;
            if (filterText) {
                var match = type.indexOf(filterText) >= 0
                    || (e.team || '').toLowerCase().indexOf(filterText) >= 0
                    || (e.player || e.track_id || '').toString().toLowerCase().indexOf(filterText) >= 0;
                if (!match) return false;
            }
            return true;
        });

        if (filtered.length === 0) {
            list.innerHTML = '<p class="hint">No matching events</p>';
            return;
        }

        list.innerHTML = filtered.slice(0, 200).map(function (e, i) {
            var eid = e.id || e.event_id || i;
            var type = e.event_type || e.type || 'unknown';
            var team = e.team || '';
            var player = e.player || e.track_id || '';
            var ts = e.timestamp || e.minute || 0;
            var checked = _hlSelected.has(eid) ? 'checked' : '';
            var typeClass = type.toLowerCase().replace(/\s+/g, '_');
            return '<div class="highlight-event-item" data-eid="' + eid + '">'
                + '<input type="checkbox" class="hl-event-cb" data-eid="' + eid + '" ' + checked + '>'
                + '<span class="highlight-event-type-badge ' + typeClass + '">' + type + '</span>'
                + '<span class="highlight-event-team">' + (team ? escapeHtml(team) : '') + '</span>'
                + '<span class="highlight-event-player">' + (player ? '#' + escapeHtml(player.toString()) : '') + '</span>'
                + '<span class="highlight-event-time">' + formatTimestamp(ts) + '</span>'
                + '</div>';
        }).join('');

        // Wire checkboxes
        list.querySelectorAll('.hl-event-cb').forEach(function (cb) {
            cb.addEventListener('change', function () {
                var eid = parseInt(this.dataset.eid);
                if (this.checked) _hlSelected.add(eid);
                else _hlSelected.delete(eid);
            });
        });
        list.querySelectorAll('.highlight-event-item').forEach(function (item) {
            item.addEventListener('click', function (e) {
                if (e.target.tagName === 'INPUT') return;
                var cb = this.querySelector('.hl-event-cb');
                if (cb) {
                    cb.checked = !cb.checked;
                    cb.dispatchEvent(new Event('change'));
                }
            });
        });
    }

    function generateHighlightReel() {
        if (_hlSelected.size === 0) {
            showToast('Select at least one event', 'warning');
            return;
        }
        if (!_hlMatchId) {
            showToast('No match selected', 'warning');
            return;
        }

        var contextSeconds = parseFloat(document.getElementById('highlight-context-seconds').value) || 3;
        var progressContainer = document.getElementById('highlight-progress-container');
        var progressFill = document.getElementById('highlight-progress-fill');
        var progressMsg = document.getElementById('highlight-progress-message');
        var resultDiv = document.getElementById('highlight-result');
        var resultText = document.getElementById('highlight-result-text');

        progressContainer.classList.remove('hidden');
        resultDiv.classList.add('hidden');
        progressFill.style.width = '0%';
        progressMsg.textContent = 'Preparing reel...';

        // Collect selected events
        var selectedEvents = _hlEvents.filter(function (e) {
            var eid = e.id || e.event_id;
            return _hlSelected.has(eid);
        });

        // Get video path - use first event or match data
        var videoPath = '';
        if (typeof bridge.get_video_path === 'function' && _hlMatchId) {
            bridge.get_video_path(_hlMatchId).then(function (raw) {
                try {
                    var data = typeof raw === 'string' ? JSON.parse(raw) : raw;
                    videoPath = data.path || '';
                } catch (e) {}
                doGenerate(selectedEvents, videoPath, contextSeconds, progressFill, progressMsg, progressContainer, resultDiv, resultText);
            }).catch(function () {
                doGenerate(selectedEvents, '', contextSeconds, progressFill, progressMsg, progressContainer, resultDiv, resultText);
            });
        } else {
            doGenerate(selectedEvents, '', contextSeconds, progressFill, progressMsg, progressContainer, resultDiv, resultText);
        }
    }

    function doGenerate(events, videoPath, contextSeconds, progressFill, progressMsg, progressContainer, resultDiv, resultText) {
        progressFill.style.width = '20%';
        progressMsg.textContent = 'Sending events to backend...';

        var eventsJson = JSON.stringify(events.map(function (e) {
            return {
                id: e.id || e.event_id,
                event_type: e.event_type || e.type,
                timestamp: e.timestamp || e.minute || 0,
                team: e.team || '',
                track_id: e.track_id || e.player || '',
            };
        }));

        if (typeof bridge.reel_from_events === 'function') {
            bridge.reel_from_events(_hlMatchId, eventsJson, videoPath).then(function (raw) {
                try {
                    var data = typeof raw === 'string' ? JSON.parse(raw) : raw;
                    progressFill.style.width = '100%';
                    if (data.error) {
                        progressMsg.textContent = 'Error: ' + data.error;
                        showToast('Reel generation failed: ' + data.error, 'error');
                    } else {
                        progressMsg.textContent = 'Reel generated!';
                        resultDiv.classList.remove('hidden');
                        resultText.textContent = 'Output: ' + (data.output_path || 'N/A') + ' | Clips: ' + (data.clip_count || 0) + ' | Duration: ' + (data.total_duration_s || 0) + 's';
                        showToast('Highlight reel generated!', 'success');
                    }
                } catch (e) {
                    progressFill.style.width = '100%';
                    progressMsg.textContent = 'Reel generated';
                    resultDiv.classList.remove('hidden');
                    resultText.textContent = 'Reel created successfully';
                    showToast('Highlight reel generated!', 'success');
                }
                setTimeout(function () { progressContainer.classList.add('hidden'); }, 3000);
            }).catch(function (err) {
                progressFill.style.width = '100%';
                progressMsg.textContent = 'Failed: ' + (err.message || 'unknown error');
                showToast('Reel generation failed', 'error');
            });
        } else {
            progressFill.style.width = '100%';
            progressMsg.textContent = 'Bridge method not available';
            showToast('reel_from_events not available', 'error');
        }
    }

    function formatTimestamp(ts) {
        if (ts == null) return '';
        var m = Math.floor(ts / 60);
        var s = Math.floor(ts % 60);
        return m + ":" + (s < 10 ? "0" : "") + s;
    }

    function escapeHtml(str) {
        if (typeof str !== 'string') str = String(str || '');
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    window.initHighlightWorkspace = initHighlightWorkspace;
})();
