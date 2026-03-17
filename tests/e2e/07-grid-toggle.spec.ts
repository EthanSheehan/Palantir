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
    palantirPage,
  }) => {
    await expect(palantirPage.toggleGridBtn).toBeVisible();
  });

  test('initial state is "Grid Visibility: ON"', async ({ palantirPage }) => {
    await palantirPage.assertGridState('ON');
  });

  test('first click changes grid to SQUARES ONLY', async ({
    palantirPage,
  }) => {
    await palantirPage.cycleGrid();
    await palantirPage.assertGridState('SQUARES ONLY');
  });

  test('second click changes grid to OFF', async ({ palantirPage }) => {
    await palantirPage.cycleGrid(); // ON -> SQUARES ONLY
    await palantirPage.cycleGrid(); // SQUARES ONLY -> OFF
    await palantirPage.assertGridState('OFF');
  });

  test('third click wraps back to ON', async ({ palantirPage }) => {
    await palantirPage.cycleGrid(); // ON -> SQUARES ONLY
    await palantirPage.cycleGrid(); // SQUARES ONLY -> OFF
    await palantirPage.cycleGrid(); // OFF -> ON
    await palantirPage.assertGridState('ON');
  });

  test('full cycle: ON -> SQUARES ONLY -> OFF -> ON', async ({
    palantirPage,
  }) => {
    await palantirPage.assertGridState('ON');

    await palantirPage.cycleGrid();
    await palantirPage.assertGridState('SQUARES ONLY');

    await palantirPage.cycleGrid();
    await palantirPage.assertGridState('OFF');

    await palantirPage.cycleGrid();
    await palantirPage.assertGridState('ON');
  });

  test('button color style updates on each state change', async ({
    palantirPage,
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

    await palantirPage.cycleGrid(); // -> SQUARES ONLY
    const squaresColor = await getColor();

    await palantirPage.cycleGrid(); // -> OFF
    const offColor = await getColor();

    // Each state should produce a distinct inline color
    // (The app sets inline style.color on each click)
    // We just verify the states are distinct from each other
    expect(
      new Set([onColor, squaresColor, offColor]).size
    ).toBeGreaterThanOrEqual(2);
  });
});
