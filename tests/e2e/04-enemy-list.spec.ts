import { test, expect } from './fixtures/base';
import { buildState, mockTarget } from './helpers/ws-mock';

/**
 * CRITICAL: Enemy List Population (ENEMIES tab)
 *
 * Validates that target cards appear in the ENEMIES tab for detected targets
 * and that undetected targets are filtered out.
 */

test.describe('Enemy List Population', () => {
  test('shows empty state message when no targets detected', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    // No targets in state
    await wsMock.sendState(buildState({ targets: [] }));

    await amcGridPage.switchToEnemiesTab();
    await amcGridPage.assertEmptyEnemyState();
  });

  test('shows empty state before any WebSocket message', async ({
    amcGridPage,
  }) => {
    await amcGridPage.switchToEnemiesTab();
    await amcGridPage.assertEmptyEnemyState();
  });

  test('enemy cards appear for detected targets', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({
        targets: [
          mockTarget(1, { detected: true }),
          mockTarget(2, { detected: true }),
        ],
      })
    );

    await amcGridPage.switchToEnemiesTab();
    await amcGridPage.assertEnemyCount(2);
    await amcGridPage.assertEnemyCardVisible(1);
    await amcGridPage.assertEnemyCardVisible(2);
  });

  test('undetected targets do NOT appear in enemy list', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({
        targets: [
          mockTarget(1, { detected: true }),
          mockTarget(2, { detected: false }), // should be hidden
          mockTarget(3, { detected: false }), // should be hidden
        ],
      })
    );

    await amcGridPage.switchToEnemiesTab();

    // Only detected target should appear
    await amcGridPage.assertEnemyCount(1);
    await amcGridPage.assertEnemyCardVisible(1);
    await expect(amcGridPage.enemyCard(2)).not.toBeVisible();
    await expect(amcGridPage.enemyCard(3)).not.toBeVisible();
  });

  test('enemy card displays target ID', async ({ amcGridPage, wsMock }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({ targets: [mockTarget(42, { detected: true })] })
    );

    await amcGridPage.switchToEnemiesTab();
    await expect(amcGridPage.enemyCard(42)).toContainText('TARGET-42');
  });

  test('enemy card displays target type', async ({ amcGridPage, wsMock }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({
        targets: [
          mockTarget(1, { type: 'SAM', detected: true }),
          mockTarget(2, { type: 'TEL', detected: true }),
          mockTarget(3, { type: 'TRUCK', detected: true }),
          mockTarget(4, { type: 'CP', detected: true }),
        ],
      })
    );

    await amcGridPage.switchToEnemiesTab();

    await expect(amcGridPage.enemyCard(1)).toContainText('SAM');
    await expect(amcGridPage.enemyCard(2)).toContainText('TEL');
    await expect(amcGridPage.enemyCard(3)).toContainText('TRUCK');
    await expect(amcGridPage.enemyCard(4)).toContainText('CP');
  });

  test('enemy card displays lat/lon coordinates', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({
        targets: [
          mockTarget(5, {
            lon: 26.1234,
            lat: 44.5678,
            detected: true,
          }),
        ],
      })
    );

    await amcGridPage.switchToEnemiesTab();

    // The card shows "latStr, lonStr" — check for the lat value
    await expect(amcGridPage.enemyCard(5)).toContainText('44.5678');
    await expect(amcGridPage.enemyCard(5)).toContainText('26.1234');
  });

  test('enemy card disappears when target goes undetected', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    // Target first detected
    await wsMock.sendState(
      buildState({ targets: [mockTarget(10, { detected: true })] })
    );

    await amcGridPage.switchToEnemiesTab();
    await amcGridPage.assertEnemyCardVisible(10);

    // Target loses detection
    await wsMock.sendState(
      buildState({ targets: [mockTarget(10, { detected: false })] })
    );

    await expect(amcGridPage.enemyCard(10)).not.toBeVisible({ timeout: 5000 });
    await amcGridPage.assertEmptyEnemyState();
  });

  test('empty state is removed when first target is detected', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    // Start with no targets
    await wsMock.sendState(buildState({ targets: [] }));
    await amcGridPage.switchToEnemiesTab();
    await amcGridPage.assertEmptyEnemyState();

    // Target becomes detected
    await wsMock.sendState(
      buildState({ targets: [mockTarget(1, { detected: true })] })
    );

    await expect(
      amcGridPage.enemyListContainer.locator('.empty-state')
    ).not.toBeVisible({ timeout: 5000 });
    await amcGridPage.assertEnemyCount(1);
  });
});
