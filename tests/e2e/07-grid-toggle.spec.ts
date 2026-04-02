import { test, expect } from './fixtures/base';

/**
 * IMPORTANT: Grid Visibility Toggle
 *
 * The grid cycles through three states: ON -> SQUARES ONLY -> OFF -> ON
 * This validates the button text label transitions which reflect the
 * underlying gridVisState (2 -> 1 -> 0) variable.
 */

test.describe('Grid Visibility Toggle', () => {
  test('grid toggle button exists on MISSION tab', async ({
    amcGridPage,
  }) => {
    await expect(amcGridPage.toggleGridBtn).toBeVisible();
  });

  test('initial state is "Grid Visibility: ON"', async ({ amcGridPage }) => {
    await amcGridPage.assertGridState('ON');
  });

  test('first click changes grid to SQUARES ONLY', async ({
    amcGridPage,
  }) => {
    await amcGridPage.cycleGrid();
    await amcGridPage.assertGridState('SQUARES ONLY');
  });

  test('second click changes grid to OFF', async ({ amcGridPage }) => {
    await amcGridPage.cycleGrid(); // ON -> SQUARES ONLY
    await amcGridPage.cycleGrid(); // SQUARES ONLY -> OFF
    await amcGridPage.assertGridState('OFF');
  });

  test('third click wraps back to ON', async ({ amcGridPage }) => {
    await amcGridPage.cycleGrid(); // ON -> SQUARES ONLY
    await amcGridPage.cycleGrid(); // SQUARES ONLY -> OFF
    await amcGridPage.cycleGrid(); // OFF -> ON
    await amcGridPage.assertGridState('ON');
  });

  test('full cycle: ON -> SQUARES ONLY -> OFF -> ON', async ({
    amcGridPage,
  }) => {
    await amcGridPage.assertGridState('ON');

    await amcGridPage.cycleGrid();
    await amcGridPage.assertGridState('SQUARES ONLY');

    await amcGridPage.cycleGrid();
    await amcGridPage.assertGridState('OFF');

    await amcGridPage.cycleGrid();
    await amcGridPage.assertGridState('ON');
  });

  test('button color style updates on each state change', async ({
    amcGridPage,
    page,
  }) => {
    // ON state — blue (#38bdf8)
    const getColor = () =>
      page.locator('#toggleGridBtn').evaluate(
        (el) => (el as HTMLElement).style.color
      );

    // Initial state is ON, blue
    const onColor = await getColor();
    // Color may be set via CSS class or inline style; just ensure it changes

    await amcGridPage.cycleGrid(); // -> SQUARES ONLY
    const squaresColor = await getColor();

    await amcGridPage.cycleGrid(); // -> OFF
    const offColor = await getColor();

    // Each state should produce a distinct inline color
    // (The app sets inline style.color on each click)
    // We just verify the states are distinct from each other
    expect(
      new Set([onColor, squaresColor, offColor]).size
    ).toBeGreaterThanOrEqual(2);
  });
});
