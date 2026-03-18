# Grid 7: Inline Drone Control Dropdown

This iteration modifies the UI architecture by removing the floating `droneControlPanel` and embedding its functionalities directly into the Drones Tab list via **Delta DOM Expanding Cards**.

## Overview of Changes

1.  **Inline UI Architecture:**
    *   The floating `#droneControlPanel` (which previously sat in the top-right corner) has been completely removed from `index.html`.
    *   The Javascript Delta DOM rendering loop in `app.js` now dynamically builds an expanded `.drone-details` block *inside* the actively tracked UAV's list item.
    *   This `.drone-details` block includes the drone's real-time telemetry (Altitude, Coordinates) and the interactive "Set Waypoint" button.

2.  **Event Listener Isolation:**
    *   Previously, a single global "Set Waypoint" button controlled waypoint states, leading to potential race conditions if tracking changed rapidly.
    *   Now, each `<button class="command-btn">` is dynamically injected into the active card with a unique ID (`inlineSetWaypointBtn_X`).
    *   The click listener for this button is bound locally inside the Delta DOM update loop, ensuring it can safely toggle the `isSettingWaypoint` state without conflicting with other drone cards. Click events on this embedded button use `e.stopPropagation()` to prevent accidentally re-triggering the parent card's `macro` tracking lock.

3.  **Return to Global Context:**
    *   The "Return to Global View" button has been properly wired to gracefully collapse the inline dropdown. Clicking it explicitly clears `trackedDroneEntity` and `isSettingWaypoint`, forcing the Delta DOM loop to unmount the `.drone-details` block on the next 100ms tick.

## Setup Instructions

1.  **Backend:**
    *   Navigate to the `backend/` directory.
    *   Start the simulation server: `python romania_grid.py`
    *   *(Note: The `app.js` websocket configuration is still defaulted to port `8008` so it can leverage the existing Grid 6 backend if running, or a new instance of it.)*

2.  **Frontend:**
    *   Navigate to the `frontend/` directory.
    *   Start the web server: `python -m http.server 8089`
    *   Open your browser to `http://localhost:8089`

## Verification
- Clicking a drone in the Drones Tab should smoothly expand the card downward, revealing the stats and the green "Set Waypoint" button.
- Clicking another drone should instantly collapse the first card and expand the new one.
- Clicking "Set Waypoint" inside the dropdown should turn it green and label it "Select Target...". You can then click the 3D map to command the drone.
- Clicking "Return to Global View" should immediately collapse the open drone card and reset the camera.

## Grid 9 & 10 Updates

- **Drone Range Visualization:** Added a new "Range" button to the drone cards in the Assets tab. This renders an animated 3D cone (consisting of 10 expanding wireframe rings) beneath the drone, stretching down to a 50km radius at ground level.
- **Dynamic Waypoint Anchoring:** When a waypoint is set for a drone, the range visualization cone snaps to the waypoint destination to visualize its "dash range" upon arrival. Once the destination is reached, it snaps back to the drone.
- **Base Map Provider Swap:** Replaced the Stadia Maps "Alidade Smooth Dark" tile provider with "CartoDB Dark Matter" to eliminate API rate limit restrictions (429 errors).
- **Map Brightness Adjustments:** Increased the brightness and gamma of the imagery layer to soften the map.
- **Grid 10 3D Buildings:** Integrated `Cesium.createOsmBuildingsAsync()` to load global 3D geometry for cities based on OpenStreetMap data, seamlessly extruded from the terrain.
- **Grid 10 Independence:** Updated WebSocket and HTTP server ports (8011, 8092) to decouple from Grid 9.
