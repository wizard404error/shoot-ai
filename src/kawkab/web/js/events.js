/* Kawkab AI — Event rendering, timeline, match list (ES module) */

import { showToast } from './ui.js';
import { getBridge, getCurrentMatchId } from './core.js';

function escapeHtml(s) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(s || ''));
    return d.innerHTML;
}

export function renderEventList(events, containerId) {
    var container = document.getElementById(containerId || 'events-list');
    if (!container) return;
    if (!events || events.length === 0) {
        container.innerHTML = '<p class="text-muted">No events</p>';
        return;
    }
    var html = '<div class="events-timeline">';
    events.forEach(function(e) {
        var icon = eventTypeIcon(e.type || 'unknown');
        var time = formatTime(e.timestamp || 0);
        var desc = e.type || 'Unknown';
        if (e.player_name) desc += ' - ' + e.player_name;
        html += '<div class="event-item" data-event-id="' + escapeHtml(e.id) + '">';
        html += '<span class="event-icon">' + icon + '</span>';
        html += '<span class="event-time">' + time + '</span>';
        html += '<span class="event-desc">' + escapeHtml(desc) + '</span>';
        html += '</div>';
    });
    html += '</div>';
    container.innerHTML = html;
}

export function renderMatchList(matches, containerId) {
    var container = document.getElementById(containerId || 'match-list');
    if (!container) return;
    if (!matches || matches.length === 0) {
        container.innerHTML = '<p class="text-muted">No matches</p>';
        return;
    }
    var html = '<div class="match-list">';
    matches.forEach(function(m) {
        html += '<div class="match-card" data-match-id="' + escapeHtml(m.id) + '">';
        html += '<strong>' + escapeHtml(m.name || 'Unnamed') + '</strong>';
        html += '<span class="match-date">' + (m.match_date || '') + '</span>';
        html += '</div>';
    });
    html += '</div>';
    container.innerHTML = html;
}

export function loadMatchList() {
    var b = getBridge();
    if (!b || !b.get_all_matches) return;
    b.get_all_matches(function(result) {
        try {
            var matches = JSON.parse(result);
            renderMatchList(matches);
        } catch(e) {
            showToast('Failed to load matches', 'error');
        }
    });
}

export function loadMatchEvents(matchId) {
    var b = getBridge();
    if (!b || !b.get_match_events) return;
    b.get_match_events(matchId, function(result) {
        try {
            var events = JSON.parse(result);
            if (events.error) { showToast(events.error, 'error'); return; }
            renderEventList(events);
            updateTimeline(events);
        } catch(e) {
            showToast('Failed to load events', 'error');
        }
    });
}

function eventTypeIcon(type) {
    var icons = { goal: '⚽', shot: '🎯', pass: '➡️', tackle: '🛑', foul: '⚠️', corner: '🚩', save: '🧤', substitution: '🔄', offside: '🚩', card: '🟨' };
    return icons[type] || '●';
}

function formatTime(seconds) {
    var m = Math.floor(seconds / 60);
    var s = Math.floor(seconds % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
}

function updateTimeline(events) {
    var container = document.getElementById('timeline');
    if (!container) return;
    container.innerHTML = '';
    var sorted = (events || []).slice().sort(function(a, b) { return (a.timestamp || 0) - (b.timestamp || 0); });
    sorted.forEach(function(e) {
        var el = document.createElement('div');
        el.className = 'timeline-event';
        el.textContent = formatTime(e.timestamp || 0) + ' ' + (e.type || '');
        container.appendChild(el);
    });
}
