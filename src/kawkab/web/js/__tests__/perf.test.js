describe('app-perf.js — UI performance utilities', function () {
  beforeEach(function () {
    jest.resetModules();
    document.body.innerHTML = '';
    jest.useFakeTimers();
    require('../app-perf.js');
  });

  afterEach(function () {
    jest.useRealTimers();
  });

  describe('$K — memoized DOM query', function () {
    test('returns element by id', function () {
      var el = document.createElement('div');
      el.id = 'test-el';
      document.body.appendChild(el);
      expect(window.$K('test-el')).toBe(el);
    });

    test('returns null for non-existent id', function () {
      expect(window.$K('nonexistent')).toBeNull();
    });

    test('caches result after first call', function () {
      var el = document.createElement('div');
      el.id = 'cache-test';
      document.body.appendChild(el);
      var first = window.$K('cache-test');
      el.remove();
      var second = window.$K('cache-test');
      expect(second).toBe(first);
    });
  });

  describe('throttle', function () {
    test('calls function immediately on first invocation', function () {
      var fn = jest.fn();
      var throttled = window.throttle(fn, 100);
      throttled();
      expect(fn).toHaveBeenCalledTimes(1);
    });

    test('coalesces calls within delay window', function () {
      var fn = jest.fn();
      var throttled = window.throttle(fn, 100);
      throttled();
      throttled();
      throttled();
      expect(fn).toHaveBeenCalledTimes(1);
      jest.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(2);
    });

    test('calls with correct arguments and context', function () {
      var context = {};
      var fn = jest.fn(function () {
        expect(this).toBe(context);
      });
      var throttled = window.throttle(fn, 50);
      throttled.call(context, 1, 2);
      expect(fn).toHaveBeenCalledWith(1, 2);
    });
  });

  describe('debounce', function () {
    test('delays execution', function () {
      var fn = jest.fn();
      var debounced = window.debounce(fn, 100);
      debounced();
      expect(fn).not.toHaveBeenCalled();
      jest.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    test('resets timer on repeated calls', function () {
      var fn = jest.fn();
      var debounced = window.debounce(fn, 100);
      debounced();
      jest.advanceTimersByTime(50);
      debounced();
      jest.advanceTimersByTime(50);
      expect(fn).not.toHaveBeenCalled();
      jest.advanceTimersByTime(50);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    test('calls with correct arguments', function () {
      var fn = jest.fn();
      var debounced = window.debounce(fn, 50);
      debounced('a', 'b');
      jest.advanceTimersByTime(50);
      expect(fn).toHaveBeenCalledWith('a', 'b');
    });
  });

  describe('initPassiveListeners', function () {
    test('adds passive touch listeners to document', function () {
      var addSpy = jest.spyOn(document, 'addEventListener');
      window.initPassiveListeners();
      expect(addSpy).toHaveBeenCalledWith('touchstart', expect.any(Function), { passive: true });
      expect(addSpy).toHaveBeenCalledWith('touchmove', expect.any(Function), { passive: true });
      expect(addSpy).toHaveBeenCalledWith('wheel', expect.any(Function), { passive: true });
      addSpy.mockRestore();
    });
  });

  describe('initThrottledScroll', function () {
    test('adds passive scroll listener to window', function () {
      var addSpy = jest.spyOn(window, 'addEventListener');
      window.initThrottledScroll();
      expect(addSpy).toHaveBeenCalledWith('scroll', expect.any(Function), { passive: true });
      addSpy.mockRestore();
    });
  });

  describe('initThrottledResize', function () {
    test('adds passive resize listener with callback', function () {
      var addSpy = jest.spyOn(window, 'addEventListener');
      var callback = jest.fn();
      window.initThrottledResize(callback);
      expect(addSpy).toHaveBeenCalledWith('resize', expect.any(Function), { passive: true });
      addSpy.mockRestore();
    });
  });
});
