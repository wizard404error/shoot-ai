const { chromium } = require('playwright');
const path = require('path');
const { test, expect, describe, beforeAll, afterAll, beforeEach, afterEach } = require('@playwright/test');

const INDEX_HTML = 'file:///' + path.resolve(__dirname, '..', 'index.html').replace(/\\/g, '/');

describe('Kawkab AI E2E', function() {
  let browser;
  let page;

  beforeAll(async function() {
    browser = await chromium.launch({ headless: true });
  });

  afterAll(async function() {
    if (browser) await browser.close();
  });

  beforeEach(async function() {
    page = await browser.newPage();
  });

  afterEach(async function() {
    await page.close();
  });

  test('page loads with correct title', async function() {
    await page.goto(INDEX_HTML, { waitUntil: 'domcontentloaded' });
    const title = await page.title();
    expect(title).toContain('Kawkab');
  });

  test('page has a canvas element', async function() {
    await page.goto(INDEX_HTML, { waitUntil: 'domcontentloaded' });
    const canvases = await page.$$('canvas');
    expect(canvases.length).toBeGreaterThanOrEqual(1);
  });

  test('page has script tags', async function() {
    await page.goto(INDEX_HTML, { waitUntil: 'domcontentloaded' });
    const scripts = await page.$$('script');
    expect(scripts.length).toBeGreaterThan(0);
  });

  test('page has link tags', async function() {
    await page.goto(INDEX_HTML, { waitUntil: 'domcontentloaded' });
    const links = await page.$$('link');
    expect(links.length).toBeGreaterThan(0);
  });

  test('page body has substantial text content', async function() {
    await page.goto(INDEX_HTML, { waitUntil: 'domcontentloaded' });
    const text = await page.textContent('body');
    expect(text.length).toBeGreaterThan(100);
  });

  test('page has html lang attribute', async function() {
    await page.goto(INDEX_HTML, { waitUntil: 'domcontentloaded' });
    const lang = await page.getAttribute('html', 'lang');
    expect(lang).toBeTruthy();
  });

  test('page has theme meta tag', async function() {
    await page.goto(INDEX_HTML, { waitUntil: 'domcontentloaded' });
    const meta = await page.$('meta[name="theme-color"]');
    expect(meta).toBeTruthy();
  });

  test('page has viewport meta tag', async function() {
    await page.goto(INDEX_HTML, { waitUntil: 'domcontentloaded' });
    const meta = await page.$('meta[name="viewport"]');
    expect(meta).toBeTruthy();
  });

  test('page has img elements', async function() {
    await page.goto(INDEX_HTML, { waitUntil: 'domcontentloaded' });
    const imgs = await page.$$('img');
    expect(imgs.length).toBeGreaterThanOrEqual(1);
  });

  test('page has navigation links', async function() {
    await page.goto(INDEX_HTML, { waitUntil: 'domcontentloaded' });
    const links = await page.$$('a');
    expect(links.length).toBeGreaterThanOrEqual(1);
  });

  test('page renders without console errors', async function() {
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    await page.goto(INDEX_HTML, { waitUntil: 'domcontentloaded' });
    const critical = errors.filter(e =>
      !e.includes('QWebChannel') &&
      !e.includes('favicon') &&
      !e.includes('Failed to load resource') &&
      !e.includes('URL scheme "file" is not supported')
    );
    expect(critical.length).toBe(0);
  });
});
