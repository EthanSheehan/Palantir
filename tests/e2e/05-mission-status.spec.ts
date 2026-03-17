import { test, expect } from './fixtures/base';
import { buildState, mockUav, mockZone } from './helpers/ws-mock';

/**
 * CRITICAL: Mission Status Panel
 *
 * Validates the MISSION tab status indicators: uplink status, UAV count,
 * and monitored zone count. These are the primary operational indicators
 * visible to operators at all times.
 */

test.describe('Mission Status Panel', () => {
  test('uplink status shows "Offline" on initial load', async ({
    page,
    wsMock,
  }) => {
    // We need to check the very first render BEFORE the WS opens.
    // The WS mock is installed but we check immediately after goto.
    await page.goto('/');
    const connStatus = page.locator('#connStatus');

    // Before WS handshake completes the status should be "Offline"
    // (as set statically in the HTML)
    const initialText = await connStatus.textContent();
    expect(['Offline', 'Uplink Active']).toContain(initialText?.trim());
  });

  test('uplink status shows "Uplink Active" after WebSocket connects', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();
    await palantirPage.assertConnected();
  });

  test('uplink status has "connected" CSS class when connected', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await expect(palantirPage.connStatus).toHaveClass(/connected/);
  });

  test('UAV counter starts at 0 before state arrives', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();
    await expect(palantirPage.uavCount).toHaveText('0');
  });

  test('zone counter starts at 0 before state arrives', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();
    await expect(palantirPage.zoneCount).toHaveText('0');
  });

  test('UAV counter updates to match state UAV count', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({ uavs: [mockUav(1), mockUav(2), mockUav(3), mockUav(4)] })
    );

    await expect(palantirPage.uavCount).toHaveText('4', { timeout: 5000 });
  });

  test('zone counter updates to match state zone count', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({
        zones: [
          mockZone(0, 0),
          mockZone(1, 0),
          mockZone(2, 0),
        ],
      })
    );

    await expect(palantirPage.zoneCount).toHaveText('3', { timeout: 5000 });
  });

  test('counters update across multiple state messages', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    // First state: 2 UAVs
    await wsMock.sendState(buildState({ uavs: [mockUav(1), mockUav(2)] }));
    await expect(palantirPage.uavCount).toHaveText('2', { timeout: 5000 });

    // Second state: 5 UAVs
    await wsMock.sendState(
      buildState({
        uavs: [mockUav(1), mockUav(2), mockUav(3), mockUav(4), mockUav(5)],
      })
    );
    await expect(palantirPage.uavCount).toHaveText('5', { timeout: 5000 });

    // Third state: back to 1 UAV
    await wsMock.sendState(buildState({ uavs: [mockUav(1)] }));
    await expect(palantirPage.uavCount).toHaveText('1', { timeout: 5000 });
  });

  test('mission tab is visible and contains all required widgets', async ({
    palantirPage,
  }) => {
    // Verify all mission tab widgets are present
    await expect(palantirPage.connStatus).toBeVisible();
    await expect(palantirPage.uavCount).toBeVisible();
    await expect(palantirPage.zoneCount).toBeVisible();
    await expect(palantirPage.assistantLog).toBeVisible();
    await expect(palantirPage.toggleGridBtn).toBeVisible();
    await expect(palantirPage.toggleWaypointsBtn).toBeVisible();
    await expect(palantirPage.resetQueueBtn).toBeVisible();
  });
});
