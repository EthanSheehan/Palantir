import { test, expect } from './fixtures/base';

/**
 * IMPORTANT: Sidebar Resize
 *
 * Validates that the drag-to-resize handle allows users to change the
 * sidebar width. The resizer is a thin div on the right edge of #uiPanel.
 */

test.describe('Sidebar Resize', () => {
  test('sidebar resizer element exists in DOM', async ({ palantirPage }) => {
    await expect(palantirPage.sidebarResizer).toBeVisible();
  });

  test('sidebar has an initial width greater than zero', async ({
    palantirPage,
  }) => {
    const width = await palantirPage.getSidebarWidth();
    expect(width).toBeGreaterThan(0);
  });

  test('dragging resizer rightward increases sidebar width', async ({
    palantirPage,
  }) => {
    const initialWidth = await palantirPage.getSidebarWidth();

    // Drag resizer 80px to the right → sidebar should grow
    await palantirPage.dragSidebarResizer(80);

    // Wait briefly for layout to settle
    await palantirPage.page.waitForTimeout(200);

    const newWidth = await palantirPage.getSidebarWidth();
    expect(newWidth).toBeGreaterThan(initialWidth);
  });

  test('dragging resizer leftward decreases sidebar width', async ({
    palantirPage,
  }) => {
    const initialWidth = await palantirPage.getSidebarWidth();

    // Drag resizer 80px to the left → sidebar should shrink
    await palantirPage.dragSidebarResizer(-80);

    await palantirPage.page.waitForTimeout(200);

    const newWidth = await palantirPage.getSidebarWidth();
    expect(newWidth).toBeLessThan(initialWidth);
  });

  test('sidebar content remains visible after resize', async ({
    palantirPage,
  }) => {
    await palantirPage.dragSidebarResizer(60);
    await palantirPage.page.waitForTimeout(200);

    // Core UI elements should still be accessible
    await expect(palantirPage.tabMissionBtn).toBeVisible();
    await expect(palantirPage.tabAssetsBtn).toBeVisible();
    await expect(palantirPage.tabEnemiesBtn).toBeVisible();
    await expect(palantirPage.connStatus).toBeVisible();
  });

  test('Cesium container exists and fills remaining space', async ({
    palantirPage,
    page,
  }) => {
    await expect(palantirPage.cesiumContainer).toBeVisible();

    const viewportWidth = page.viewportSize()?.width ?? 1280;
    const sidebarWidth = await palantirPage.getSidebarWidth();
    const cesiumBox = await palantirPage.cesiumContainer.boundingBox();

    expect(cesiumBox).not.toBeNull();
    // Cesium container should occupy the majority of remaining space
    if (cesiumBox) {
      expect(cesiumBox.width).toBeGreaterThan(viewportWidth - sidebarWidth - 20);
    }
  });
});
