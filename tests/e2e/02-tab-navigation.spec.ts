import { test, expect } from './fixtures/base';

/**
 * CRITICAL: Tab Navigation
 *
 * Validates that the three-tab navigation (MISSION / ASSETS / ENEMIES)
 * correctly shows and hides content panels without requiring a real backend.
 */

test.describe('Tab Navigation', () => {
  test('MISSION tab is active by default on page load', async ({
    palantirPage,
  }) => {
    await palantirPage.assertMissionTabActive();

    // Other tabs are not active
    await expect(palantirPage.tabAssetsBtn).not.toHaveClass(/active/);
    await expect(palantirPage.tabEnemiesBtn).not.toHaveClass(/active/);
    await expect(palantirPage.tabAssetsContent).not.toHaveClass(/active-tab/);
    await expect(palantirPage.tabEnemiesContent).not.toHaveClass(/active-tab/);
  });

  test('clicking ASSETS tab shows assets content and hides others', async ({
    palantirPage,
  }) => {
    await palantirPage.switchToAssetsTab();

    await palantirPage.assertAssetsTabActive();

    await expect(palantirPage.tabMissionBtn).not.toHaveClass(/active/);
    await expect(palantirPage.tabEnemiesBtn).not.toHaveClass(/active/);
    await expect(palantirPage.tabMissionContent).not.toHaveClass(/active-tab/);
    await expect(palantirPage.tabEnemiesContent).not.toHaveClass(/active-tab/);
  });

  test('clicking ENEMIES tab shows enemies content and hides others', async ({
    palantirPage,
  }) => {
    await palantirPage.switchToEnemiesTab();

    await palantirPage.assertEnemiesTabActive();

    await expect(palantirPage.tabMissionBtn).not.toHaveClass(/active/);
    await expect(palantirPage.tabAssetsBtn).not.toHaveClass(/active/);
    await expect(palantirPage.tabMissionContent).not.toHaveClass(/active-tab/);
    await expect(palantirPage.tabAssetsContent).not.toHaveClass(/active-tab/);
  });

  test('cycling through all three tabs works correctly', async ({
    palantirPage,
  }) => {
    // Start: MISSION active
    await palantirPage.assertMissionTabActive();

    // Navigate to ASSETS
    await palantirPage.switchToAssetsTab();
    await palantirPage.assertAssetsTabActive();

    // Navigate to ENEMIES
    await palantirPage.switchToEnemiesTab();
    await palantirPage.assertEnemiesTabActive();

    // Navigate back to MISSION
    await palantirPage.switchToMissionTab();
    await palantirPage.assertMissionTabActive();
  });

  test('tab buttons have accessible text labels', async ({ palantirPage }) => {
    await expect(palantirPage.tabMissionBtn).toHaveText('MISSION');
    await expect(palantirPage.tabAssetsBtn).toHaveText('ASSETS');
    await expect(palantirPage.tabEnemiesBtn).toHaveText('ENEMIES');
  });

  test('only one tab content panel is visible at a time', async ({
    palantirPage,
  }) => {
    const allContents = palantirPage.page.locator('.tab-content');
    const activeTabs = palantirPage.page.locator('.tab-content.active-tab');

    // Initially one active
    await expect(activeTabs).toHaveCount(1);

    // After switching to ASSETS
    await palantirPage.switchToAssetsTab();
    await expect(activeTabs).toHaveCount(1);

    // After switching to ENEMIES
    await palantirPage.switchToEnemiesTab();
    await expect(activeTabs).toHaveCount(1);

    // Total panels should always be 3
    await expect(allContents).toHaveCount(3);
  });
});
