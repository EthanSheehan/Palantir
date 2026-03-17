import { test as base, Page } from '@playwright/test';
import { PalantirPage } from '../pages/PalantirPage';
import { WsMock, createWsMock } from '../helpers/ws-mock';

/**
 * Extended fixtures for Palantir C2 E2E tests.
 *
 * Every test that uses `palantirPage` automatically gets:
 *   - A `PalantirPage` instance (POM)
 *   - A `WsMock` that intercepts the WebSocket BEFORE page load
 *   - The page is navigated to '/' inside the fixture setup
 *
 * The IDENTIFY handshake is NOT awaited in the fixture so individual tests
 * can choose their own assertion strategy.
 */

type PalantirFixtures = {
  /** Full page wrapper — use in tests that need both the POM and WS mock. */
  palantirPage: PalantirPage;
  /** Standalone WebSocket mock — available even when only `palantirPage` is used. */
  wsMock: WsMock;
};

export const test = base.extend<PalantirFixtures>({
  wsMock: async ({ page }: { page: Page }, use: (mock: WsMock) => Promise<void>) => {
    // Install the route BEFORE goto so it's in place when the page script runs
    const mock = await createWsMock(page);
    await use(mock);
  },

  palantirPage: async ({ page, wsMock }: { page: Page; wsMock: WsMock }, use: (p: PalantirPage) => Promise<void>) => {
    void wsMock; // ensure wsMock fixture is initialised (route installed) first
    const palantirPage = new PalantirPage(page);
    await palantirPage.goto();
    await use(palantirPage);
  },
});

export { expect } from '@playwright/test';
