import { test as base, Page } from '@playwright/test';
import { AMCGridPage } from '../pages/AMCGridPage';
import { WsMock, createWsMock } from '../helpers/ws-mock';

/**
 * Extended fixtures for Grid-Sentinel C2 E2E tests.
 *
 * Every test that uses `amcGridPage` automatically gets:
 *   - A `AMCGridPage` instance (POM)
 *   - A `WsMock` that intercepts the WebSocket BEFORE page load
 *   - The page is navigated to '/' inside the fixture setup
 *
 * The IDENTIFY handshake is NOT awaited in the fixture so individual tests
 * can choose their own assertion strategy.
 */

type AMCGridFixtures = {
  /** Full page wrapper — use in tests that need both the POM and WS mock. */
  amcGridPage: AMCGridPage;
  /** Standalone WebSocket mock — available even when only `amcGridPage` is used. */
  wsMock: WsMock;
};

export const test = base.extend<AMCGridFixtures>({
  wsMock: async ({ page }: { page: Page }, use: (mock: WsMock) => Promise<void>) => {
    // Install the route BEFORE goto so it's in place when the page script runs
    const mock = await createWsMock(page);
    await use(mock);
  },

  amcGridPage: async ({ page, wsMock }: { page: Page; wsMock: WsMock }, use: (p: AMCGridPage) => Promise<void>) => {
    void wsMock; // ensure wsMock fixture is initialised (route installed) first
    const amcGridPage = new AMCGridPage(page);
    await amcGridPage.goto();
    await use(amcGridPage);
  },
});

export { expect } from '@playwright/test';
