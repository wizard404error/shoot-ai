/* Tests for analytics.js — bridge data loaders (CommonJS) */

var fs = require('fs');
var path = require('path');

var ANALYTICS_JS_PATH = path.resolve(__dirname, '../js/analytics.js');
var analyticsCode = fs.readFileSync(ANALYTICS_JS_PATH, 'utf-8');

// Mock dependencies injected into the eval sandbox
var mockShowToast, mockShowSkeleton, mockHideSkeleton;
var mockBridge, mockGetBridge, mockGetCurrentMatchId;

/** Load analytics module with fresh mocks */
function loadAnalytics() {
    mockShowToast = jest.fn();
    mockShowSkeleton = jest.fn();
    mockHideSkeleton = jest.fn();
    mockGetBridge = jest.fn(function() { return mockBridge; });
    mockGetCurrentMatchId = jest.fn(function() { return 'match-001'; });

    // Rewrite ES module imports to use our mocks
    var patched = analyticsCode
        .replace(
            /import \{ showToast, showSkeleton, hideSkeleton \} from '\.\/ui\.js';/,
            ''
        )
        .replace(
            /import \{ getBridge, getCurrentMatchId \} from '\.\/core\.js';/,
            ''
        )
        .replace(/export function (\w+)/g, 'window.__an_exports.$1 = function');

    // eslint-disable-next-line no-eval
    (function() {
        window.__an_exports = {};
        var showToast = mockShowToast;
        var showSkeleton = mockShowSkeleton;
        var hideSkeleton = mockHideSkeleton;
        var getBridge = mockGetBridge;
        var getCurrentMatchId = mockGetCurrentMatchId;
        eval(patched);
    }).call(global);

    return window.__an_exports;
}

beforeEach(function() {
    document.body.innerHTML = '';
    mockBridge = {};
});

// ── loadXGReport ────────────────────────────────────────────────────────────

describe('loadXGReport', function() {
    it('calls bridge get_xa_report and parses JSON response', function() {
        mockBridge.get_xa_report = function(mid, cb) {
            expect(mid).toBe('match-001');
            cb('{"xg_total": 1.5, "home": 0.8, "away": 0.7}');
        };
        var container = document.createElement('div');
        container.id = 'xg-report-container';
        document.body.appendChild(container);

        var an = loadAnalytics();
        an.loadXGReport('match-001');

        expect(mockShowSkeleton).toHaveBeenCalledWith('xg-report-container');
        expect(mockHideSkeleton).toHaveBeenCalledWith('xg-report-container');
        expect(mockShowToast).not.toHaveBeenCalled();
        expect(container.innerHTML).toContain('1.50');
    });

    it('shows toast on invalid JSON', function() {
        mockBridge.get_xa_report = function(mid, cb) { cb('not json'); };
        var container = document.createElement('div');
        container.id = 'xg-report-container';
        document.body.appendChild(container);

        var an = loadAnalytics();
        an.loadXGReport('match-001');
        expect(mockShowToast).toHaveBeenCalledWith('Failed to load xG report', 'error');
    });

    it('does nothing when bridge is missing', function() {
        mockGetBridge.mockReturnValueOnce(null);
        var an = loadAnalytics();
        an.loadXGReport('match-001');
        expect(mockShowSkeleton).not.toHaveBeenCalled();
    });

    it('does nothing when bridge method is missing', function() {
        var an = loadAnalytics();
        an.loadXGReport('match-001');
        expect(mockShowSkeleton).not.toHaveBeenCalled();
    });
});

describe('loadVAEPReport', function() {
    it('calls bridge get_vaep_report and renders result count', function() {
        mockBridge.get_vaep_report = function(mid, cb) {
            cb('{"results": [{"a":1},{"b":2}]}');
        };
        var container = document.createElement('div');
        container.id = 'vaep-report-container';
        document.body.appendChild(container);

        var an = loadAnalytics();
        an.loadVAEPReport('match-001');
        expect(container.innerHTML).toContain('2');
    });

    it('shows error toast on invalid JSON', function() {
        mockBridge.get_vaep_report = function(mid, cb) { cb('bad'); };
        var container = document.createElement('div');
        container.id = 'vaep-report-container';
        document.body.appendChild(container);

        var an = loadAnalytics();
        an.loadVAEPReport('match-001');
        expect(mockShowToast).toHaveBeenCalledWith('Failed to load VAEP report', 'error');
    });
});

describe('loadXTReport', function() {
    it('calls bridge get_xt_report and renders home/away values', function() {
        mockBridge.get_xt_report = function(mid, cb) {
            cb('{"home": 2.1, "away": 1.3}');
        };
        var container = document.createElement('div');
        container.id = 'xt-report-container';
        document.body.appendChild(container);

        var an = loadAnalytics();
        an.loadXTReport('match-001');
        expect(container.innerHTML).toContain('2.100');
        expect(container.innerHTML).toContain('1.300');
    });

    it('shows error toast on failure', function() {
        mockBridge.get_xt_report = function(mid, cb) { cb('bad'); };
        var container = document.createElement('div');
        container.id = 'xt-report-container';
        document.body.appendChild(container);

        var an = loadAnalytics();
        an.loadXTReport('match-001');
        expect(mockShowToast).toHaveBeenCalledWith('Failed to load xT report', 'error');
    });
});

describe('loadMomentum', function() {
    it('calls bridge get_momentum_index silently', function() {
        mockBridge.get_momentum_index = function(mid, cb) {
            cb('{"timeline": []}');
        };
        var an = loadAnalytics();
        an.loadMomentum('match-001');
        expect(mockShowToast).not.toHaveBeenCalled();
    });

    it('does nothing on invalid JSON (silent)', function() {
        mockBridge.get_momentum_index = function(mid, cb) { cb('bad'); };
        var an = loadAnalytics();
        expect(function() { an.loadMomentum('match-001'); }).not.toThrow();
        expect(mockShowToast).not.toHaveBeenCalled();
    });
});

describe('loadSetPieceReport', function() {
    it('calls bridge get_set_piece_report', function() {
        mockBridge.get_set_piece_report = function(mid, cb) {
            cb('{"corners": 5}');
        };
        var an = loadAnalytics();
        an.loadSetPieceReport('match-001');
        expect(mockShowSkeleton).toHaveBeenCalledWith('setpiece-report-container');
        expect(mockHideSkeleton).toHaveBeenCalledWith('setpiece-report-container');
    });

    it('shows error toast on failure', function() {
        mockBridge.get_set_piece_report = function(mid, cb) { cb('bad'); };
        var an = loadAnalytics();
        an.loadSetPieceReport('match-001');
        expect(mockShowToast).toHaveBeenCalledWith('Failed to load set piece report', 'error');
    });
});

describe('loadPassNetwork', function() {
    it('calls bridge get_pass_flow silently', function() {
        mockBridge.get_pass_flow = function(mid, cb) {
            cb('{"nodes": []}');
        };
        var an = loadAnalytics();
        expect(function() { an.loadPassNetwork('match-001'); }).not.toThrow();
        expect(mockShowToast).not.toHaveBeenCalled();
    });
});

describe('loadMatchNarrative', function() {
    it('sets narrative content from bridge response', function() {
        mockBridge.get_match_narrative = function(mid, lang, cb) {
            expect(lang).toBe('en');
            cb('Team A dominated possession.');
        };
        var container = document.createElement('div');
        container.id = 'narrative-content';
        document.body.appendChild(container);

        var an = loadAnalytics();
        an.loadMatchNarrative('match-001', 'en');
        expect(container.textContent).toBe('Team A dominated possession.');
    });

    it('defaults language to en', function() {
        var capturedLang;
        mockBridge.get_match_narrative = function(mid, lang, cb) {
            capturedLang = lang;
            cb('');
        };
        var container = document.createElement('div');
        container.id = 'narrative-content';
        document.body.appendChild(container);

        var an = loadAnalytics();
        an.loadMatchNarrative('match-001');
        expect(capturedLang).toBe('en');
    });

    it('handles null narrative gracefully', function() {
        mockBridge.get_match_narrative = function(mid, lang, cb) { cb(null); };
        var container = document.createElement('div');
        container.id = 'narrative-content';
        document.body.appendChild(container);

        var an = loadAnalytics();
        an.loadMatchNarrative('match-001', 'ar');
        expect(container.textContent).toBe('');
    });

    it('does nothing when bridge missing', function() {
        mockGetBridge.mockReturnValueOnce(null);
        var an = loadAnalytics();
        expect(function() { an.loadMatchNarrative('match-001'); }).not.toThrow();
    });
});

describe('loadProgressiveReport', function() {
    it('calls bridge get_progressive_report silently', function() {
        mockBridge.get_progressive_report = function(mid, cb) {
            cb('{"carries": 12}');
        };
        var an = loadAnalytics();
        expect(function() { an.loadProgressiveReport('match-001'); }).not.toThrow();
    });
});

describe('loadDefensiveReport', function() {
    it('calls bridge get_defensive_report silently', function() {
        mockBridge.get_defensive_report = function(mid, cb) {
            cb('{"pressures": 45}');
        };
        var an = loadAnalytics();
        expect(function() { an.loadDefensiveReport('match-001'); }).not.toThrow();
    });
});

describe('render functions (internal)', function() {
    it('renderXGReport shows error in container when data has error', function() {
        mockBridge.get_xa_report = function(mid, cb) {
            cb('{"error": "No tracking data"}');
        };
        var container = document.createElement('div');
        container.id = 'xg-report-container';
        document.body.appendChild(container);

        var an = loadAnalytics();
        an.loadXGReport('match-001');
        expect(container.innerHTML).toContain('No tracking data');
        expect(container.querySelector('.error')).toBeTruthy();
    });

    it('render functions handle missing container silently', function() {
        mockBridge.get_xa_report = function(mid, cb) { cb('{"xg_total": 1}'); };
        mockBridge.get_vaep_report = function(mid, cb) { cb('{"results": []}'); };
        mockBridge.get_xt_report = function(mid, cb) { cb('{"home": 1}'); };

        var an = loadAnalytics();
        expect(function() {
            an.loadXGReport('match-001');
            an.loadVAEPReport('match-001');
            an.loadXTReport('match-001');
        }).not.toThrow();
    });
});
