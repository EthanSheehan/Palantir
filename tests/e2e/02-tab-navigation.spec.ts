import { test, expect } from './fixtures/base';

/**
 * CRITICAL: Tab Navigation
 *
 * Validates that the three-tab navigation (MISSION / ASSETS / ENEMIES)
 * correctly shows and hides content panels without requiring a real backend.
 */

test.describe('Tab Navigation', () => {
  test('MISSION tab is active by default on page load', async ({
    amcGridPage,
  }) => {
    await amcGridPage.assertMissionTabActive();

    // Other tabs are not active
    await expect(amcGridPage.tabAssetsBtn).not.toHaveClass(/active/);
    await expect(amcGridPage.tabEnemiesBtn).not.toHaveClass(/active/);
    await expect(amcGridPage.tabAssetsContent).not.toHaveClass(/active-tab/);
    await expect(amcGridPage.tabEnemiesContent).not.toHaveClass(/active-tab/);
  });

  test('clicking ASSETS tab shows assets content and hides others', async ({
    amcGridPage,
  }) => {
    await amcGridPage.switchToAssetsTab();

    await amcGridPage.assertAssetsTabActive();

    await expect(amcGridPage.tabMissionBtn).not.toHaveClass(/active/);
    await expect(amcGridPage.tabEnemiesBtn).not.toHaveClass(/active/);
    await expect(amcGridPage.tabMissionContent).not.toHaveClass(/active-tab/);
    await expect(amcGridPage.tabEnemiesContent).not.toHaveClass(/active-tab/);
  });

  test('clicking ENEMIES tab shows enemies content and hides others', async ({
    amcGridPage,
  }) => {
    await amcGridPage.switchToEnemiesTab();

    await amcGridPage.assertEnemiesTabActive();

    await expect(amcGridPage.tabMissionBtn).not.toHaveClass(/active/);
    await expect(amcGridPage.tabAssetsBtn).not.toHaveClass(/active/);
    await expect(amcGridPage.tabMissionContent).not.toHaveClass(/active-tab/);
    await expect(amcGridPage.tabAssetsContent).not.toHaveClass(/active-tab/);
  });

  test('cycling through all three tabs works correctly', async ({
    amcGridPage,
  }) => {
    // Start: MISSION active
    await amcGridPage.assertMissionTabActive();

    // Navigate to ASSETS
    await amcGridPage.switchToAssetsTab();
    await amcGridPage.assertAssetsTabActive();

    // Navigate to ENEMIES
    await amcGridPage.switchToEnemiesTab();
    await amcGridPage.assertEnemiesTabActive();

    // Navigate back to MISSION
    await amcGridPage.switchToMissionTab();
    await amcGridPage.assertMissionTabActive();
  });

  test('tab buttons have accessible text labels', async ({ amcGridPage }) => {
    await expect(amcGridPage.tabMissionBtn).toHaveText('MISSION');
    await expect(amcGridPage.tabAssetsBtn).toHaveText('ASSETS');
    await expect(amcGridPage.tabEnemiesBtn).toHaveText('ENEMIES');
  });

  test('only one tab content panel is visible at a time', async ({
    amcGridPage,
  }) => {
    const allContents = amcGridPage.page.locator('.tab-content');
    const activeTabs = amcGridPage.page.locator('.tab-content.active-tab');

    // Initially one active
    await expect(activeTabs).toHaveCount(1);

    // After switching to ASSETS
    await amcGridPage.switchToAssetsTab();
    await expect(activeTabs).toHaveCount(1);

    // After switching to ENEMIES
    await amcGridPage.switchToEnemiesTab();
    await expect(activeTabs).toHaveCount(1);

    // Total panels should always be 3
    await expect(allContents).toHaveCount(3);
  });
});
