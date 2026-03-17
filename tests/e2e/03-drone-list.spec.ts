import { test, expect } from './fixtures/base';
import { buildState, mockUav } from './helpers/ws-mock';

/**
 * CRITICAL: Drone List Population (ASSETS tab)
 *
 * Validates that drone cards appear and update correctly in the ASSETS tab
 * when state updates arrive via WebSocket.
 */

test.describe('Drone List Population', () => {
  test('drone list is empty before any state arrives', async ({
    palantirPage,
  }) => {
    await palantirPage.switchToAssetsTab();
    await palantirPage.assertDroneCount(0);
  });

  test('drone cards appear after receiving state with UAVs', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({ uavs: [mockUav(1), mockUav(2)] })
    );

    await palantirPage.switchToAssetsTab();

    await palantirPage.assertDroneCount(2);
    await palantirPage.assertDroneCardVisible(1);
    await palantirPage.assertDroneCardVisible(2);
  });

  test('drone card displays UAV ID', async ({ palantirPage, wsMock }) => {
    await wsMock.waitForIdentify();
    await wsMock.sendState(buildState({ uavs: [mockUav(7)] }));

    await palantirPage.switchToAssetsTab();

    await expect(palantirPage.droneCard(7)).toContainText('UAV-7');
  });

  test('drone card displays mode status', async ({ palantirPage, wsMock }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({
        uavs: [
          mockUav(1, { mode: 'idle' }),
          mockUav(2, { mode: 'serving' }),
          mockUav(3, { mode: 'repositioning' }),
        ],
      })
    );

    await palantirPage.switchToAssetsTab();

    await expect(palantirPage.droneCard(1)).toContainText('idle');
    await expect(palantirPage.droneCard(2)).toContainText('serving');
    await expect(palantirPage.droneCard(3)).toContainText('repositioning');
  });

  test('drone cards update when mode changes across state updates', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    // First state: drone 1 is idle
    await wsMock.sendState(buildState({ uavs: [mockUav(1, { mode: 'idle' })] }));
    await palantirPage.switchToAssetsTab();
    await expect(palantirPage.droneCard(1)).toContainText('idle');

    // Second state: drone 1 is now serving
    await wsMock.sendState(
      buildState({ uavs: [mockUav(1, { mode: 'serving' })] })
    );
    await expect(palantirPage.droneCard(1)).toContainText('serving', {
      timeout: 5000,
    });
  });

  test('drone cards are removed when drone leaves state', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    // Two drones initially
    await wsMock.sendState(
      buildState({ uavs: [mockUav(1), mockUav(2)] })
    );
    await palantirPage.switchToAssetsTab();
    await palantirPage.assertDroneCount(2);

    // Drone 2 is removed in next state
    await wsMock.sendState(buildState({ uavs: [mockUav(1)] }));

    await palantirPage.assertDroneCount(1);
    await palantirPage.assertDroneCardVisible(1);
    await expect(palantirPage.droneCard(2)).not.toBeVisible();
  });

  test('drone list handles many drones without error', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    const manyDrones = Array.from({ length: 20 }, (_, i) => mockUav(i + 1));
    await wsMock.sendState(buildState({ uavs: manyDrones }));

    await palantirPage.switchToAssetsTab();
    await palantirPage.assertDroneCount(20);
  });

  test('UAV counter in MISSION tab reflects drone count', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({ uavs: [mockUav(1), mockUav(2), mockUav(3)] })
    );

    // Counter lives in the MISSION tab, so switch to it
    await palantirPage.switchToMissionTab();
    await expect(palantirPage.uavCount).toHaveText('3', { timeout: 5000 });
  });
});
