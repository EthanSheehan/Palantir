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
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    // No targets in state
    await wsMock.sendState(buildState({ targets: [] }));

    await palantirPage.switchToEnemiesTab();
    await palantirPage.assertEmptyEnemyState();
  });

  test('shows empty state before any WebSocket message', async ({
    palantirPage,
  }) => {
    await palantirPage.switchToEnemiesTab();
    await palantirPage.assertEmptyEnemyState();
  });

  test('enemy cards appear for detected targets', async ({
    palantirPage,
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

    await palantirPage.switchToEnemiesTab();
    await palantirPage.assertEnemyCount(2);
    await palantirPage.assertEnemyCardVisible(1);
    await palantirPage.assertEnemyCardVisible(2);
  });

  test('undetected targets do NOT appear in enemy list', async ({
    palantirPage,
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

    await palantirPage.switchToEnemiesTab();

    // Only detected target should appear
    await palantirPage.assertEnemyCount(1);
    await palantirPage.assertEnemyCardVisible(1);
    await expect(palantirPage.enemyCard(2)).not.toBeVisible();
    await expect(palantirPage.enemyCard(3)).not.toBeVisible();
  });

  test('enemy card displays target ID', async ({ palantirPage, wsMock }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({ targets: [mockTarget(42, { detected: true })] })
    );

    await palantirPage.switchToEnemiesTab();
    await expect(palantirPage.enemyCard(42)).toContainText('TARGET-42');
  });

  test('enemy card displays target type', async ({ palantirPage, wsMock }) => {
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

    await palantirPage.switchToEnemiesTab();

    await expect(palantirPage.enemyCard(1)).toContainText('SAM');
    await expect(palantirPage.enemyCard(2)).toContainText('TEL');
    await expect(palantirPage.enemyCard(3)).toContainText('TRUCK');
    await expect(palantirPage.enemyCard(4)).toContainText('CP');
  });

  test('enemy card displays lat/lon coordinates', async ({
    palantirPage,
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

    await palantirPage.switchToEnemiesTab();

    // The card shows "latStr, lonStr" — check for the lat value
    await expect(palantirPage.enemyCard(5)).toContainText('44.5678');
    await expect(palantirPage.enemyCard(5)).toContainText('26.1234');
  });

  test('enemy card disappears when target goes undetected', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    // Target first detected
    await wsMock.sendState(
      buildState({ targets: [mockTarget(10, { detected: true })] })
    );

    await palantirPage.switchToEnemiesTab();
    await palantirPage.assertEnemyCardVisible(10);

    // Target loses detection
    await wsMock.sendState(
      buildState({ targets: [mockTarget(10, { detected: false })] })
    );

    await expect(palantirPage.enemyCard(10)).not.toBeVisible({ timeout: 5000 });
    await palantirPage.assertEmptyEnemyState();
  });

  test('empty state is removed when first target is detected', async ({
    palantirPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    // Start with no targets
    await wsMock.sendState(buildState({ targets: [] }));
    await palantirPage.switchToEnemiesTab();
    await palantirPage.assertEmptyEnemyState();

    // Target becomes detected
    await wsMock.sendState(
      buildState({ targets: [mockTarget(1, { detected: true })] })
    );

    await expect(
      palantirPage.enemyListContainer.locator('.empty-state')
    ).not.toBeVisible({ timeout: 5000 });
    await palantirPage.assertEnemyCount(1);
  });
});
