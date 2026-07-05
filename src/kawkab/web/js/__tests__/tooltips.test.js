describe('app-tooltips.js — Tooltip system', function () {
  beforeEach(function () {
    jest.resetModules();
    document.body.innerHTML = '';
    jest.useFakeTimers();
    require('../app-tooltips.js');
  });

  afterEach(function () {
    jest.useRealTimers();
  });

  function createTooltipEl(text) {
    var el = document.createElement('button');
    el.setAttribute('data-tooltip', text);
    document.body.appendChild(el);
    return el;
  }

  describe('initTooltips', function () {
    test('attaches mouseenter/mouseleave handlers to data-tooltip elements', function () {
      var el = createTooltipEl('hello tip');
      window.initTooltips();
      el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
      jest.advanceTimersByTime(300);
      var tip = document.querySelector('.kawkab-tooltip');
      expect(tip).not.toBeNull();
      expect(tip.innerHTML).toBe('hello tip');
    });

    test('shows tooltip on focus event', function () {
      var el = createTooltipEl('focus tip');
      window.initTooltips();
      el.dispatchEvent(new Event('focus', { bubbles: true }));
      jest.advanceTimersByTime(300);
      var tip = document.querySelector('.kawkab-tooltip');
      expect(tip).not.toBeNull();
      expect(tip.innerHTML).toBe('focus tip');
    });

    test('hides tooltip on mouseleave after delay', function () {
      var el = createTooltipEl('disappear');
      window.initTooltips();
      el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
      jest.advanceTimersByTime(300);
      var tip = document.querySelector('.kawkab-tooltip');
      expect(tip.style.opacity).toBe('1');
      el.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));
      jest.advanceTimersByTime(100);
      expect(tip.style.opacity).toBe('0');
    });
  });

  describe('reinitTooltips', function () {
    test('binds new tooltip elements without duplicating listeners', function () {
      var el = createTooltipEl('reinit test');
      window.reinitTooltips();
      expect(el.getAttribute('data-tooltip-bound')).toBe('1');
      el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
      jest.advanceTimersByTime(300);
      var tip = document.querySelector('.kawkab-tooltip');
      expect(tip.innerHTML).toBe('reinit test');
    });

    test('does not double-bind elements', function () {
      var el = createTooltipEl('double');
      window.reinitTooltips();
      window.reinitTooltips();
      expect(el.getAttribute('data-tooltip-bound')).toBe('1');
    });
  });

  describe('Tooltip positioning', function () {
    test('positions tooltip below by default when space allows', function () {
      var el = createTooltipEl('pos test');
      Object.defineProperty(el, 'getBoundingClientRect', {
        value: function () {
          return { left: 100, top: 100, right: 180, bottom: 140, width: 80, height: 40 };
        }
      });
      Object.defineProperty(window, 'innerWidth', { value: 800, configurable: true });
      Object.defineProperty(window, 'innerHeight', { value: 600, configurable: true });

      window.initTooltips();
      el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
      jest.advanceTimersByTime(300);
      var tip = document.querySelector('.kawkab-tooltip');
      expect(parseInt(tip.style.left)).toBeGreaterThanOrEqual(4);
      expect(parseInt(tip.style.top)).toBeGreaterThanOrEqual(4);
    });

    test('repositions tooltip when below viewport is insufficient', function () {
      var el = createTooltipEl('viewport edge');
      Object.defineProperty(el, 'getBoundingClientRect', {
        value: function () {
          return { left: 100, top: 590, right: 180, bottom: 630, width: 80, height: 40 };
        }
      });
      Object.defineProperty(window, 'innerWidth', { value: 800, configurable: true });
      Object.defineProperty(window, 'innerHeight', { value: 600, configurable: true });

      window.initTooltips();
      el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
      jest.advanceTimersByTime(300);
      var tip = document.querySelector('.kawkab-tooltip');
      var top = parseInt(tip.style.top);
      expect(top).toBeLessThanOrEqual(596);
    });

    test('clamps tooltip to viewport boundaries', function () {
      var el = createTooltipEl('clamp');
      Object.defineProperty(el, 'getBoundingClientRect', {
        value: function () {
          return { left: -100, top: 100, right: -20, bottom: 140, width: 80, height: 40 };
        }
      });
      Object.defineProperty(window, 'innerWidth', { value: 800, configurable: true });
      Object.defineProperty(window, 'innerHeight', { value: 600, configurable: true });

      window.initTooltips();
      el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
      jest.advanceTimersByTime(300);
      var tip = document.querySelector('.kawkab-tooltip');
      expect(parseInt(tip.style.left)).toBeGreaterThanOrEqual(4);
      expect(parseInt(tip.style.top)).toBeGreaterThanOrEqual(4);
    });
  });
});
