/* Kawkab AI — Analytics loading handlers (ES module) */

import { showToast, showSkeleton, hideSkeleton } from './ui.js';
import { getBridge, getCurrentMatchId } from './core.js';

export function loadXGReport(matchId) {
    var b = getBridge();
    if (!b || !b.get_xa_report) return;
    showSkeleton('xg-report-container');
    b.get_xa_report(matchId, function(result) {
        hideSkeleton('xg-report-container');
        try { var data = JSON.parse(result); renderXGReport(data); } catch(e) { showToast('Failed to load xG report', 'error'); }
    });
}

export function loadVAEPReport(matchId) {
    var b = getBridge();
    if (!b || !b.get_vaep_report) return;
    showSkeleton('vaep-report-container');
    b.get_vaep_report(matchId, function(result) {
        hideSkeleton('vaep-report-container');
        try { var data = JSON.parse(result); renderVAEPReport(data); } catch(e) { showToast('Failed to load VAEP report', 'error'); }
    });
}

export function loadXTReport(matchId) {
    var b = getBridge();
    if (!b || !b.get_xt_report) return;
    showSkeleton('xt-report-container');
    b.get_xt_report(matchId, function(result) {
        hideSkeleton('xt-report-container');
        try { var data = JSON.parse(result); renderXTReport(data); } catch(e) { showToast('Failed to load xT report', 'error'); }
    });
}

export function loadMomentum(matchId) {
    var b = getBridge();
    if (!b || !b.get_momentum_index) return;
    b.get_momentum_index(matchId, function(result) {
        try { var data = JSON.parse(result); renderMomentumChart(data); } catch(e) {}
    });
}

export function loadSetPieceReport(matchId) {
    var b = getBridge();
    if (!b || !b.get_set_piece_report) return;
    showSkeleton('setpiece-report-container');
    b.get_set_piece_report(matchId, function(result) {
        hideSkeleton('setpiece-report-container');
        try { var data = JSON.parse(result); renderSetPieceReport(data); } catch(e) { showToast('Failed to load set piece report', 'error'); }
    });
}

export function loadPassNetwork(matchId) {
    var b = getBridge();
    if (!b || !b.get_pass_flow) return;
    b.get_pass_flow(matchId, function(result) {
        try { var data = JSON.parse(result); renderPassNetwork(data); } catch(e) {}
    });
}

export function loadMatchNarrative(matchId, lang) {
    var b = getBridge();
    if (!b || !b.get_match_narrative) return;
    b.get_match_narrative(matchId, lang || 'en', function(result) {
        var container = document.getElementById('narrative-content');
        if (container) container.textContent = result || '';
    });
}

export function loadProgressiveReport(matchId) {
    var b = getBridge();
    if (!b || !b.get_progressive_report) return;
    b.get_progressive_report(matchId, function(result) {
        try { var data = JSON.parse(result); renderProgressiveReport(data); } catch(e) {}
    });
}

export function loadDefensiveReport(matchId) {
    var b = getBridge();
    if (!b || !b.get_defensive_report) return;
    b.get_defensive_report(matchId, function(result) {
        try { var data = JSON.parse(result); renderDefensiveReport(data); } catch(e) {}
    });
}

// Render stubs — these get enriched by app.js IIFE
function renderXGReport(data) {
    var container = document.getElementById('xg-report-container');
    if (!container) return;
    if (data.error) { container.textContent = data.error; return; }
    container.innerHTML = '<div class="stat-row"><span>xG Total</span><span>' + (data.xg_total || 0).toFixed(2) + '</span></div>';
}

function renderVAEPReport(data) {
    var container = document.getElementById('vaep-report-container');
    if (!container) return;
    if (data.error) { container.textContent = data.error; return; }
    container.innerHTML = '<div class="stat-row"><span>VAEP Events</span><span>' + (data.results ? data.results.length : 0) + '</span></div>';
}

function renderXTReport(data) {
    var container = document.getElementById('xt-report-container');
    if (!container) return;
    if (data.error) { container.textContent = data.error; return; }
    container.innerHTML = '<div class="stat-row"><span>xT Home</span><span>' + (data.home || 0).toFixed(3) + '</span></div><div class="stat-row"><span>xT Away</span><span>' + (data.away || 0).toFixed(3) + '</span></div>';
}

function renderMomentumChart(data) {}
function renderSetPieceReport(data) {}
function renderPassNetwork(data) {}
function renderProgressiveReport(data) {}
function renderDefensiveReport(data) {}
