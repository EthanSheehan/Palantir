import { test, expect } from './fixtures/base';

/**
 * IMPORTANT: Sidebar Resize
 *
 * Validates that the drag-to-resize handle allows users to change the
 * sidebar width. The resizer is a thin div on the right edge of #uiPanel.
 */

test.describe('Sidebar Resize', () => {
  test('sidebar resizer element exists in DOM', async ({ amcGridPage }) => {
    await expect(amcGridPage.sidebarResizer).toBeVisible();
  });

  test('sidebar has an initial width greater than zero', async ({
    amcGridPage,
  }) => {
    const width = await amcGridPage.getSidebarWidth();
    expect(width).toBeGreaterThan(0);
  });

  test('dragging resizer rightward increases sidebar width', async ({
    amcGridPage,
  }) => {
    const initialWidth = await amcGridPage.getSidebarWidth();

    // Drag resizer 80px to the right → sidebar should grow
    await amcGridPage.dragSidebarResizer(80);

    // Wait briefly for layout to settle
    await amcGridPage.page.waitForTimeout(200);

    const newWidth = await amcGridPage.getSidebarWidth();
    expect(newWidth).toBeGreaterThan(initialWidth);
  });

  test('dragging resizer leftward decreases sidebar width', async ({
    amcGridPage,
  }) => {
    const initialWidth = await amcGridPage.getSidebarWidth();

    // Drag resizer 80px to the left → sidebar should shrink
    await amcGridPage.dragSidebarResizer(-80);

    await amcGridPage.page.waitForTimeout(200);

    const newWidth = await amcGridPage.getSidebarWidth();
    expect(newWidth).toBeLessThan(initialWidth);
  });

  test('sidebar content remains visible after resize', async ({
    amcGridPage,
  }) => {
    await amcGridPage.dragSidebarResizer(60);
    await amcGridPage.page.waitForTimeout(200);

    // Core UI elements should still be accessible
    await expect(amcGridPage.tabMissionBtn).toBeVisible();
    await expect(amcGridPage.tabAssetsBtn).toBeVisible();
    await expect(amcGridPage.tabEnemiesBtn).toBeVisible();
    await expect(amcGridPage.connStatus).toBeVisible();
  });

  test('Cesium container exists and fills remaining space', async ({
    amcGridPage,
    page,
  }) => {
    await expect(amcGridPage.cesiumContainer).toBeVisible();

    const viewportWidth = page.viewportSize()?.width ?? 1280;
    const sidebarWidth = await amcGridPage.getSidebarWidth();
    const cesiumBox = await amcGridPage.cesiumContainer.boundingBox();

    expect(cesiumBox).not.toBeNull();
    // Cesium container should occupy the majority of remaining space
    if (cesiumBox) {
      expect(cesiumBox.width).toBeGreaterThan(viewportWidth - sidebarWidth - 20);
    }
  });
});
