describe('app-router.js — KawkabRouter', function () {
  beforeEach(function () {
    jest.resetModules();
    document.body.innerHTML = `
      <section id="sec-dashboard" class="section"></section>
      <section id="sec-results" class="section"></section>
      <nav>
        <button class="nav-tab active" data-route="dashboard">Dashboard</button>
        <button class="nav-tab" data-route="results">Results</button>
      </nav>
    `;
    window.location.hash = '';
    require('../app-router.js');
  });

  describe('KawkabRouter constructor (singleton)', function () {
    test('creates instance and stores on window', function () {
      var router = new window.KawkabRouter();
      expect(window.__kawkabRouter).toBe(router);
    });

    test('returns same instance on repeated construction', function () {
      var r1 = new window.KawkabRouter();
      var r2 = new window.KawkabRouter();
      expect(r1).toBe(r2);
    });
  });

  describe('register', function () {
    test('registers a route with section id and onActivate', function () {
      var router = new window.KawkabRouter();
      var activateFn = jest.fn();
      router.register('dashboard', 'sec-dashboard', activateFn);
      router.navigate('dashboard', false);
      expect(activateFn).toHaveBeenCalled();
    });

    test('allows null onActivate', function () {
      var router = new window.KawkabRouter();
      expect(function () {
        router.register('test', 'sec-dashboard', null);
      }).not.toThrow();
    });
  });

  describe('navigate', function () {
    test('shows target section and hides others', function () {
      var router = new window.KawkabRouter();
      router.register('dashboard', 'sec-dashboard');
      router.register('results', 'sec-results');
      router.navigate('results', false);
      expect(document.getElementById('sec-results').classList.contains('hidden')).toBe(false);
      expect(document.getElementById('sec-dashboard').classList.contains('hidden')).toBe(true);
    });

    test('sets window.location.hash when pushState is not false', function () {
      var router = new window.KawkabRouter();
      router.register('dashboard', 'sec-dashboard');
      router.navigate('dashboard');
      expect(window.location.hash).toBe('#dashboard');
    });

    test('does not set hash when pushState is false', function () {
      var router = new window.KawkabRouter();
      router.register('dashboard', 'sec-dashboard');
      var originalHash = window.location.hash;
      router.navigate('dashboard', false);
      expect(window.location.hash).toBe(originalHash);
    });
  });

  describe('getCurrentRoute / getPreviousRoute', function () {
    test('returns current route after navigation', function () {
      var router = new window.KawkabRouter();
      router.register('results', 'sec-results');
      router.navigate('results', false);
      expect(router.getCurrentRoute()).toBe('results');
    });

    test('tracks current and previous route', function () {
      var router = new window.KawkabRouter();
      router.register('dashboard', 'sec-dashboard');
      router.register('results', 'sec-results');
      router.navigate('results', false);
      expect(router.getCurrentRoute()).toBe('results');
      expect(router.getPreviousRoute()).toBe('dashboard');
    });
  });
});
