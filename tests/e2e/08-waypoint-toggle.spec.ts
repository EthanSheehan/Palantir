import { test, expect } from './fixtures/base';

/**
 * IMPORTANT: Waypoint Toggle
 *
 * The waypoint toggle is a simple boolean switch. Tests validate the button
 * label transitions without requiring real Cesium entities (no waypoints
 * exist in the mock state so there is nothing Cesium-side to check).
 */

test.describe('Waypoint Toggle', () => {
  test('waypoint toggle button exists on MISSION tab', async ({
    palantirPage,
  }) => {
    await expect(palantirPage.toggleWaypointsBtn).toBeVisible();
  });

  test('initial state is "All Waypoints: OFF"', async ({ palantirPage }) => {
    await palantirPage.assertWaypointsState('OFF');
  });

  test('first click enables "All Waypoints: ON"', async ({
    palantirPage,
  }) => {
    await palantirPage.toggleWaypoints();
    await palantirPage.assertWaypointsState('ON');
  });

  test('second click toggles back to "All Waypoints: OFF"', async ({
    palantirPage,
  }) => {
    await palantirPage.toggleWaypoints(); // OFF -> ON
    await palantirPage.toggleWaypoints(); // ON -> OFF
    await palantirPage.assertWaypointsState('OFF');
  });

  test('toggle cycles ON/OFF correctly across multiple clicks', async ({
    palantirPage,
  }) => {
    for (let i = 0; i < 5; i++) {
      const expectedState = i % 2 === 0 ? 'ON' : 'OFF';
      await palantirPage.toggleWaypoints();
      await palantirPage.assertWaypointsState(expectedState);
    }
  });

  test('button color changes when waypoints are enabled', async ({
    palantirPage,
    page,
  }) => {
    const getColor = () =>
      page
        .locator('#toggleWaypointsBtn')
        .evaluate((el) => (el as HTMLElement).style.color);

    const offColor = await getColor();
    await palantirPage.toggleWaypoints();
    const onColor = await getColor();

    // Colors should differ between ON and OFF states
    expect(onColor).not.toBe(offColor);
  });
});
