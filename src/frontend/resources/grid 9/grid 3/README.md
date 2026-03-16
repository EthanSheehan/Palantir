# Cesium 3D Macro Grid (Grid 3)

This folder contains the "Mission Planner" visualization of the Romania macro transport grid. It builds upon Grid 2 by introducing **Interactive Third-Person Drone Tracking**, a **3-Tiered Level of Detail (LOD)** rendering system, and a rebalanced macro-economy.

## Architecture

* **Backend (`backend/`)**: A FastAPI Python server simulating supply/demand dynamics across a 50x50 hex/cellular matrix (2,500 cells). It operates a soft-real-time loop running at 10Hz, pushing binary `state` JSON objects over a WebSocket.
* **Frontend (`frontend/`)**: A vanilla JavaScript and HTML UI utilizing CesiumJS. It maintains a WebSocket uplink to ingest simulation ticks and leverages WebGL geometry batching for zero-latency DOM updates.

## How to Run

1. **Start the Simulation Backend (Port 8005)**
   ```powershell
   cd "backend"
   python -m uvicorn main:app --reload --port 8005
   ```
   *(Note: Ensure you run this from an environment with `uvicorn` and `fastapi` installed, such as `uav-cesium-sim\backend\venv`)*

2. **Start the UX Frontend (Port 8085)**
   ```powershell
   cd "frontend"
   python -m http.server 8085
   ```

3. Open `http://localhost:8085` in a WebGL-capable browser.

## Key Technical Decisions & Features

### 1. 3-Tiered Level of Detail (LOD) Rendering
To balance cinematic realism with high-performance massive-scale rendering, the drone visualization fluidly scales across three geometric representations based on camera altitude, managed by `Cesium.DistanceDisplayCondition`:

*   **Extreme Orbit (> 200km)**: Drones are represented by highly efficient, simple 6-pixel dots colored by their current state machine status.
*   **Standard Macro View (2km - 200km)**: Drones use a custom, cached SVG `Billboard` featuring a precise hollow square and a dynamic color-coded status bar to better communicate identity and state.
*   **Active Tracking View (< 2km)**: The UI markers completely fade out, revealing the true 1:1 scale, high-resolution 3D `.glb` CAD geometry (hardcoded to grey).

### 2. Interactive Camera Tracking
You can cleanly click on any drone in the scene to engage tracking mode.
*   The camera will smoothly swoop down using `viewer.flyTo()` over 1.5 seconds and lock onto a position configured via `viewFrom` (300 meters behind and 150 meters above the drone).
*   A new "Return to Global View" UI button appears. Clicking it drops the `viewer.trackedEntity` lock and smoothly flies the camera back up to the 500km macro orbit.

### 3. Kinematic Header Smoothing & Orientation
Because the backend physics engine updates position over a 10Hz websocket, standard orientation calculations result in violent visual "stutter" as the drone corrects course by fractions of a degree. Grid 3 implements two fixes in `app.js`:
*   **Deadzone**: Heading calculations are skipped if the movement delta is `< 0.002` degrees, preventing micro-jitter from snapping the drone 180 degrees.
*   **Low-Pass Filtering**: The rotation quaternion is interpolated. The drone smoothly banks towards the new vector (`current + (diff * 0.3)`) rather than instantly snapping.
*   *Note*: A strict `+180 degrees` (Math.PI) rotational offset is applied to the `.glb` CAD model via `HeadingPitchRoll` to correct for its natively reversed coordinate system.

### 4. Dynamic Economy Scaling (Red to Blue)
The backend economic weights in `romania_grid.py` were reworked to favor stability over chaos, making the baseline map "Cool Blue / Surplus":
*   **`base_lambda = 0.1`**: Reduced the baseline "unassigned demand" generation by 80%.
*   **`MU_CAPACITY_FACTOR = 10.0`**: Increased the stabilizing influence (blue capacity) of a single drone by 10x.

### 5. Piercing Map Injection
You can Double-Click on the map to manually inject a massive demand anomaly (Red Cylinder) of `+120 queue` (updated in `sim.py` to match the new high UAV capacity).
*   `viewer.scene.drillPick()` is used so that double-clicking directly on a massive 3D drone will piece through its geometry and correctly strike the map coordinate directly below it.

## API Keys Required
- **Cesium Ion Default Access Token**: Required for the world terrain (`Cesium.Terrain.fromWorldTerrain()`). Hardcoded into `app.js`.
- **Stadia Maps API Key**: Required for the `alidade_smooth_dark` map tile service. Instantiated in `viewer.imageryLayers`.
