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
    amcGridPage,
  }) => {
    await amcGridPage.switchToAssetsTab();
    await amcGridPage.assertDroneCount(0);
  });

  test('drone cards appear after receiving state with UAVs', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({ uavs: [mockUav(1), mockUav(2)] })
    );

    await amcGridPage.switchToAssetsTab();

    await amcGridPage.assertDroneCount(2);
    await amcGridPage.assertDroneCardVisible(1);
    await amcGridPage.assertDroneCardVisible(2);
  });

  test('drone card displays UAV ID', async ({ amcGridPage, wsMock }) => {
    await wsMock.waitForIdentify();
    await wsMock.sendState(buildState({ uavs: [mockUav(7)] }));

    await amcGridPage.switchToAssetsTab();

    await expect(amcGridPage.droneCard(7)).toContainText('UAV-7');
  });

  test('drone card displays mode status', async ({ amcGridPage, wsMock }) => {
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

    await amcGridPage.switchToAssetsTab();

    await expect(amcGridPage.droneCard(1)).toContainText('idle');
    await expect(amcGridPage.droneCard(2)).toContainText('serving');
    await expect(amcGridPage.droneCard(3)).toContainText('repositioning');
  });

  test('drone cards update when mode changes across state updates', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    // First state: drone 1 is idle
    await wsMock.sendState(buildState({ uavs: [mockUav(1, { mode: 'idle' })] }));
    await amcGridPage.switchToAssetsTab();
    await expect(amcGridPage.droneCard(1)).toContainText('idle');

    // Second state: drone 1 is now serving
    await wsMock.sendState(
      buildState({ uavs: [mockUav(1, { mode: 'serving' })] })
    );
    await expect(amcGridPage.droneCard(1)).toContainText('serving', {
      timeout: 5000,
    });
  });

  test('drone cards are removed when drone leaves state', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    // Two drones initially
    await wsMock.sendState(
      buildState({ uavs: [mockUav(1), mockUav(2)] })
    );
    await amcGridPage.switchToAssetsTab();
    await amcGridPage.assertDroneCount(2);

    // Drone 2 is removed in next state
    await wsMock.sendState(buildState({ uavs: [mockUav(1)] }));

    await amcGridPage.assertDroneCount(1);
    await amcGridPage.assertDroneCardVisible(1);
    await expect(amcGridPage.droneCard(2)).not.toBeVisible();
  });

  test('drone list handles many drones without error', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    const manyDrones = Array.from({ length: 20 }, (_, i) => mockUav(i + 1));
    await wsMock.sendState(buildState({ uavs: manyDrones }));

    await amcGridPage.switchToAssetsTab();
    await amcGridPage.assertDroneCount(20);
  });

  test('UAV counter in MISSION tab reflects drone count', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({ uavs: [mockUav(1), mockUav(2), mockUav(3)] })
    );

    // Counter lives in the MISSION tab, so switch to it
    await amcGridPage.switchToMissionTab();
    await expect(amcGridPage.uavCount).toHaveText('3', { timeout: 5000 });
  });
});
