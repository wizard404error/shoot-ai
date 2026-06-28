/**
 * @jest-environment jsdom
 */
describe('KawkabUtils', function() {
  beforeEach(function() {
    require('../js/utils.js');
    document.body.innerHTML = '';
  });

  describe('formatDate', function() {
    test('returns empty string for null/undefined', function() {
      expect(window.KawkabUtils.formatDate(null)).toBe('');
      expect(window.KawkabUtils.formatDate(undefined)).toBe('');
    });
    test('formats valid date string', function() {
      var result = window.KawkabUtils.formatDate('2024-01-15');
      expect(result).toBe('15 Jan 2024');
    });
    test('returns original string for invalid date', function() {
      expect(window.KawkabUtils.formatDate('not-a-date')).toBe('not-a-date');
    });
  });

  describe('escapeHtml', function() {
    test('returns empty for null/undefined', function() {
      expect(window.KawkabUtils.escapeHtml(null)).toBe('');
      expect(window.KawkabUtils.escapeHtml(undefined)).toBe('');
    });
    test('escapes HTML tags', function() {
      expect(window.KawkabUtils.escapeHtml('<script>alert("xss")</script>')).toBe('&lt;script&gt;alert(\"xss\")&lt;/script&gt;');
    });
    test('returns plain text unchanged', function() {
      expect(window.KawkabUtils.escapeHtml('hello world')).toBe('hello world');
    });
  });

  describe('eventTypeIcon', function() {
    test('returns correct icon for GOAL', function() {
      expect(window.KawkabUtils.eventTypeIcon('GOAL')).toBe('\u26BD');
    });
    test('returns correct icon for SHOT', function() {
      expect(window.KawkabUtils.eventTypeIcon('SHOT')).toBe('\uD83C\uDFAF');
    });
    test('returns bullet for unknown type', function() {
      expect(window.KawkabUtils.eventTypeIcon('UNKNOWN')).toBe('\u2022');
    });
    test('returns bullet for null', function() {
      expect(window.KawkabUtils.eventTypeIcon(null)).toBe('\u2022');
    });
  });

  describe('formatTime', function() {
    test('formats 0 seconds', function() {
      expect(window.KawkabUtils.formatTime(0)).toBe('00:00');
    });
    test('formats 90 seconds as 01:30', function() {
      expect(window.KawkabUtils.formatTime(90)).toBe('01:30');
    });
    test('formats 3600 seconds as 60:00', function() {
      expect(window.KawkabUtils.formatTime(3600)).toBe('60:00');
    });
    test('handles null/NaN', function() {
      expect(window.KawkabUtils.formatTime(null)).toBe('00:00');
      expect(window.KawkabUtils.formatTime(NaN)).toBe('00:00');
    });
  });

  describe('deepClone', function() {
    test('clones a simple object', function() {
      var original = { a: 1, b: { c: 2 } };
      var cloned = window.KawkabUtils.deepClone(original);
      expect(cloned).toEqual(original);
      expect(cloned).not.toBe(original);
    });
    test('modifying clone does not affect original', function() {
      var original = { a: [1, 2, 3] };
      var cloned = window.KawkabUtils.deepClone(original);
      cloned.a.push(4);
      expect(original.a).toEqual([1, 2, 3]);
    });
  });

  describe('truncate', function() {
    test('returns short strings unchanged', function() {
      expect(window.KawkabUtils.truncate('short', 30)).toBe('short');
    });
    test('truncates long strings with ellipsis', function() {
      var long = 'abcdefghijklmnopqrstuvwxyz';
      expect(window.KawkabUtils.truncate(long, 10)).toBe('abcdefg...');
    });
    test('handles null/undefined', function() {
      expect(window.KawkabUtils.truncate(null)).toBe('');
      expect(window.KawkabUtils.truncate(undefined)).toBe('');
    });
  });

  describe('now', function() {
    test('returns ISO string', function() {
      var result = window.KawkabUtils.now();
      expect(typeof result).toBe('string');
      expect(result).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    });
  });
});
