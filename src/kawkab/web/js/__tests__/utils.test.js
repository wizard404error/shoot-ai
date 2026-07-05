describe('utils.js — KawkabUtils', function () {
  beforeEach(function () {
    jest.resetModules();
    document.body.innerHTML = '';
    require('../utils.js');
  });

  describe('escapeHtml', function () {
    test('returns empty string for null/undefined', function () {
      expect(window.KawkabUtils.escapeHtml(null)).toBe('');
      expect(window.KawkabUtils.escapeHtml(undefined)).toBe('');
    });

    test('escapes HTML special characters', function () {
      var result = window.KawkabUtils.escapeHtml('<script>alert("xss")</script>');
      expect(result).toContain('&lt;script&gt;');
      expect(result).toContain('&lt;/script&gt;');
      expect(result).not.toContain('<script>');
    });

    test('returns plain text unchanged', function () {
      expect(window.KawkabUtils.escapeHtml('hello world')).toBe('hello world');
    });

    test('escapes ampersands', function () {
      expect(window.KawkabUtils.escapeHtml('a & b')).toBe('a &amp; b');
    });
  });

  describe('formatDate', function () {
    test('returns empty string for null/undefined', function () {
      expect(window.KawkabUtils.formatDate(null)).toBe('');
      expect(window.KawkabUtils.formatDate(undefined)).toBe('');
    });

    test('formats valid date string', function () {
      var result = window.KawkabUtils.formatDate('2024-01-15');
      expect(result).toBe('15 Jan 2024');
    });

    test('returns original string for invalid date', function () {
      expect(window.KawkabUtils.formatDate('not-a-date')).toBe('not-a-date');
    });

    test('handles empty string', function () {
      expect(window.KawkabUtils.formatDate('')).toBe('');
    });
  });

  describe('formatTime', function () {
    test('formats 0 seconds', function () {
      expect(window.KawkabUtils.formatTime(0)).toBe('00:00');
    });

    test('formats 90 seconds', function () {
      expect(window.KawkabUtils.formatTime(90)).toBe('01:30');
    });

    test('formats 3600 seconds', function () {
      expect(window.KawkabUtils.formatTime(3600)).toBe('60:00');
    });

    test('handles null/NaN/undefined', function () {
      expect(window.KawkabUtils.formatTime(null)).toBe('00:00');
      expect(window.KawkabUtils.formatTime(NaN)).toBe('00:00');
      expect(window.KawkabUtils.formatTime(undefined)).toBe('00:00');
    });
  });

  describe('eventTypeIcon', function () {
    test('returns correct icon for known types', function () {
      expect(window.KawkabUtils.eventTypeIcon('GOAL')).toBe('\u26BD');
      expect(window.KawkabUtils.eventTypeIcon('SHOT')).toBe('\uD83C\uDFAF');
      expect(window.KawkabUtils.eventTypeIcon('PASS')).toBe('\u27A1\uFE0F');
    });

    test('returns bullet for unknown type', function () {
      expect(window.KawkabUtils.eventTypeIcon('UNKNOWN')).toBe('\u2022');
    });

    test('returns bullet for null/undefined', function () {
      expect(window.KawkabUtils.eventTypeIcon(null)).toBe('\u2022');
      expect(window.KawkabUtils.eventTypeIcon(undefined)).toBe('\u2022');
    });
  });

  describe('deepClone', function () {
    test('clones a simple object', function () {
      var original = { a: 1, b: { c: 2 } };
      var cloned = window.KawkabUtils.deepClone(original);
      expect(cloned).toEqual(original);
      expect(cloned).not.toBe(original);
    });

    test('modifying clone does not affect original', function () {
      var original = { a: [1, 2, 3] };
      var cloned = window.KawkabUtils.deepClone(original);
      cloned.a.push(4);
      expect(original.a).toEqual([1, 2, 3]);
    });

    test('clones arrays', function () {
      var arr = [1, 2, { x: 10 }];
      var cloned = window.KawkabUtils.deepClone(arr);
      expect(cloned).toEqual(arr);
      cloned[2].x = 99;
      expect(arr[2].x).toBe(10);
    });
  });

  describe('truncate', function () {
    test('returns short strings unchanged', function () {
      expect(window.KawkabUtils.truncate('short')).toBe('short');
    });

    test('truncates long strings with ellipsis', function () {
      var long = 'abcdefghijklmnopqrstuvwxyz';
      expect(window.KawkabUtils.truncate(long, 10)).toBe('abcdefg...');
    });

    test('uses default maxLen of 30', function () {
      var str = 'x'.repeat(35);
      expect(window.KawkabUtils.truncate(str)).toBe('x'.repeat(27) + '...');
    });

    test('handles null/undefined', function () {
      expect(window.KawkabUtils.truncate(null)).toBe('');
      expect(window.KawkabUtils.truncate(undefined)).toBe('');
    });
  });

  describe('now', function () {
    test('returns ISO string', function () {
      var result = window.KawkabUtils.now();
      expect(typeof result).toBe('string');
      expect(result).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    });
  });

  describe('showToast', function () {
    test('creates toast container if missing', function () {
      expect(document.getElementById('toast-container')).toBeNull();
      window.KawkabUtils.showToast('test message');
      var container = document.getElementById('toast-container');
      expect(container).not.toBeNull();
      expect(container.style.position).toBe('fixed');
    });

    test('adds toast element with correct text', function () {
      window.KawkabUtils.showToast('hello toast');
      var container = document.getElementById('toast-container');
      expect(container.children.length).toBe(1);
      expect(container.children[0].textContent).toBe('hello toast');
      expect(container.children[0].className).toContain('toast-info');
    });

    test('respects type parameter', function () {
      window.KawkabUtils.showToast('error', 'error');
      var toast = document.querySelector('.toast-error');
      expect(toast).not.toBeNull();
      expect(toast.textContent).toBe('error');
    });

    test('removes toast after duration', function () {
      jest.useFakeTimers();
      window.KawkabUtils.showToast('gone', 'info', 500);
      var container = document.getElementById('toast-container');
      expect(container.children.length).toBe(1);
      jest.advanceTimersByTime(500);
      expect(container.children.length).toBe(0);
      jest.useRealTimers();
    });
  });
});
