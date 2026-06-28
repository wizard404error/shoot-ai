module.exports = {
  testEnvironment: 'jest-environment-jsdom',
  testMatch: ['**/tests/**/*.test.{js,mjs}'],
  testPathIgnorePatterns: ['e2e\\.test\\.js$'],
  moduleNameMapper: {
    '\\.(css|less|scss)$': '<rootDir>/__mocks__/styleMock.js'
  },
  transform: {}
};
