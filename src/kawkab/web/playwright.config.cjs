module.exports = {
  testDir: './tests',
  testMatch: '**/e2e.test.js',
  timeout: 30000,
  use: {
    headless: true,
    viewport: { width: 1280, height: 720 },
  },
  webServer: undefined,
};
