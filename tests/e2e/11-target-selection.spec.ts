import { test, expect } from './fixtures/base';
import { buildState, mockTarget } from './helpers/ws-mock';

/**
 * IMPORTANT: Target Selection
 *
 * Validates that clicking an enemy card in the ENEMIES tab triggers the
 * DOM-level interaction. The Cesium flyTo() call itself is not verifiable
 * in headless mode, but we can assert the card is clickable and the UI
 * responds correctly.
 */

test.describe('Target Selection', () => {
  test('enemy cards are clickable elements', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({ targets: [mockTarget(1, { detected: true })] })
    );

    await amcGridPage.switchToEnemiesTab();
    await amcGridPage.assertEnemyCardVisible(1);

    // Verify the card is interactive (no error thrown on click)
    await amcGridPage.enemyCard(1).click();

    // Card should still be visible after click
    await amcGridPage.assertEnemyCardVisible(1);
  });

  test('clicking enemy card does not cause JS errors', async ({
    amcGridPage,
    wsMock,
    page,
  }) => {
    const errors: string[] = [];
    page.on('pageerror', (err) => {
      // Filter out Cesium ion authentication errors (expected in mock mode)
      if (!err.message.includes('Ion') && !err.message.includes('Cesium')) {
        errors.push(err.message);
      }
    });

    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({ targets: [mockTarget(3, { detected: true })] })
    );

    await amcGridPage.switchToEnemiesTab();
    await amcGridPage.enemyCard(3).click();

    // No non-Cesium JS errors after clicking
    expect(errors).toHaveLength(0);
  });

  test('enemy card contains all required data fields', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({
        targets: [
          mockTarget(99, {
            type: 'TEL',
            lon: 27.8765,
            lat: 45.1234,
            detected: true,
          }),
        ],
      })
    );

    await amcGridPage.switchToEnemiesTab();

    const card = amcGridPage.enemyCard(99);
    await expect(card).toContainText('TARGET-99');
    await expect(card).toContainText('TEL');
    await expect(card).toContainText('45.1234');
    await expect(card).toContainText('27.8765');
  });

  test('multiple enemy cards are independently clickable', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendState(
      buildState({
        targets: [
          mockTarget(1, { detected: true }),
          mockTarget(2, { detected: true }),
          mockTarget(3, { detected: true }),
        ],
      })
    );

    await amcGridPage.switchToEnemiesTab();
    await amcGridPage.assertEnemyCount(3);

    // Click each card without errors
    for (const id of [1, 2, 3]) {
      await amcGridPage.enemyCard(id).click();
      await amcGridPage.assertEnemyCardVisible(id);
    }
  });
});
