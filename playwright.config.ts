import { defineConfig, devices } from '@playwright/test';

/**
 * AMC-Grid C2 Playwright Configuration
 *
 * The frontend is a vanilla JS app served by Python's http.server on :3000.
 * The WebSocket backend runs on :8000. Tests use a mock WebSocket by default
 * so they run without the real backend. Tests tagged @live require both
 * services to be running.
 *
 * Run all tests:        npm run test:e2e
 * Run with UI:          npm run test:e2e:ui
 * Run headed:           npm run test:e2e:headed
 * Run live (needs servers): npm run test:e2e:live
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false, // Cesium is GPU-heavy; run serially to avoid resource contention
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: 1,
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['junit', { outputFile: 'test-results/junit.xml' }],
    ['list'],
  ],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
    // Longer timeouts for Cesium CDN loads
    navigationTimeout: 30000,
    actionTimeout: 10000,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Needed for Cesium WebGL rendering in headless mode
        launchOptions: {
          args: [
            '--enable-webgl',
            '--ignore-gpu-blocklist',
            '--use-gl=swiftshader',
            '--disable-web-security',
          ],
        },
      },
    },
  ],
  outputDir: 'test-results/',
  // Global timeout for each test
  timeout: 60000,
  // Expect timeout for assertions
  expect: {
    timeout: 10000,
  },
  // Do not start a webserver automatically — developer starts it manually
  // or via the npm scripts below. Use webServer block only in CI.
  ...(process.env.CI
    ? {
        webServer: {
          command: 'cd src/frontend && python3 -m http.server 3000',
          url: 'http://localhost:3000',
          reuseExistingServer: false,
          timeout: 15000,
        },
      }
    : {}),
});
