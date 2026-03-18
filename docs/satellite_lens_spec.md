# Satellite Lens Feature — Technical Specification

> **Scope**: Frontend only. All code lives in `frontend/app.js` and `frontend/workspace-shell.css`. No backend changes required.

---

## 1. Overview

The **satellite lens** is a circular "magic window" projected onto the globe surface that overlays Bing Maps Aerial satellite imagery on top of the dark CartoDB base map. It is anchored to the compass cursor ring — the same circular ring the user can resize with `Ctrl+scroll`.

When active, the lens:
- Shows satellite imagery inside the compass ring, perspective-corrected to match the camera angle
- Keeps the compass needle, compass ring, and tracked drone billboard rendered visibly on top of the satellite imagery
- Does not interfere with globe interaction (pan, zoom, rotate) or existing click handlers

Button: `🔭` (`#satelliteLensBtn`) in the camera controls block inside `#cesiumContainer`.

---

## 2. Implementation Architecture

### 2.1 Two-Viewer Approach

A second, independent `Cesium.Viewer` (`_lensViewer`) is created inside a `<div id="satellite-lens">` element. This viewer:
- Has only Bing Maps Aerial imagery loaded (Ion asset ID `2`)
- Has `requestRenderMode: true` and `maximumRenderTimeChange: Infinity` (renders only on demand)
- Has `screenSpaceCameraController.enableInputs = false` (user cannot accidentally interact with it)
- Has its camera synced to the main viewer's camera each `postRender` frame

`_lensViewer` is created lazily — only on the first click of the satellite lens button.

### 2.2 Perspective-Correct Clipping

Rather than a fixed circular CSS mask (which would not match the camera perspective), the lens div's `clip-path` is a CSS `polygon()` rebuilt every frame.

In the main viewer's `postRender` event:
1. The compass center (`getCompassCenter()`) is projected to the ENU frame
2. 48 equally-spaced points on the compass ring circumference (radius = `1500.0 * _compassScale`) are computed in world space using `Cesium.Matrix4.multiplyByPoint`
3. Each point is projected to screen space via `Cesium.SceneTransforms.wgs84ToWindowCoordinates(viewer.scene, worldPt)`
4. The resulting pixel coordinates form a `polygon(x1px y1px, x2px y2px, ...)` applied as `lensEl.style.clipPath`

This makes the visible satellite area match the perspective-distorted ellipse of the ground ring at any camera tilt, including oblique angles.

### 2.3 DOM Layering

```
#cesiumContainer
├── <canvas>          ← main Cesium viewer (terrain, grid, drones, compass)
├── #satellite-lens   ← _lensViewer canvas (satellite only, ON TOP of main canvas)
└── #cameraControls   ← camera buttons (🌐 ✖ ⊡ 🔭)
```

The `#satellite-lens` div is appended to `#cesiumContainer` at button-click time (first activation). Being a later sibling of the main canvas, it renders on top.

### 2.4 Entity Mirroring (Z-Ordering Fix)

Because the lens is on top of the main canvas, Cesium entities (drone icons, compass needle/ring) rendered in the main canvas are obscured by the satellite imagery inside the ring. This is solved by adding **mirror entities** to `_lensViewer` that use the same `CallbackProperty` closures:

| Mirror entity ID | Mirrors | What it draws |
|------------------|---------|---------------|
| `lens_compass` | `compassEntity` | Yellow compass needle (heading-aware) |
| `lens_compassRing` | `compassRingEntity` | Yellow 64-segment ring at compass radius |
| `lens_drone` | tracked `uavEntities[id]` | Drone billboard icon at current drone position |

All three use `Cesium.CallbackProperty(fn, false)` closures that reference the same module-level variables (`getCompassCenter`, `_compassScale`, `trackedDroneEntity`, `uavEntities`). Since `_lensViewer.scene.requestRender()` is called each postRender frame, callbacks recalculate every frame.

Key differences from main-viewer entities:
- `clampToGround: false` — the lens viewer has no terrain; positions are already at height=0 from `getCompassCenter()` (which explicitly sets `carto.height = 0`)
- `lens_drone` billboard uses `HeightReference.NONE` (no terrain to clamp to)
- `lens_drone` image is a `CallbackProperty` returning `getDronePin(marker._lastMode || '#3b82f6')` — `_lastMode` is the CSS color string stored on the uavEntity marker when its mode changes

---

## 3. Key Variables

All defined at module scope in `app.js` (lines ~814–816):

| Variable | Type | Purpose |
|----------|------|---------|
| `_compassScale` | `number` | Multiplier for compass needle length and ring radius. Default `1.0`. Modified by `Ctrl+scroll`. |
| `_lensActive` | `boolean` | Whether the satellite lens overlay is visible. Toggled by `#satelliteLensBtn`. |
| `_lensViewer` | `Cesium.Viewer \| null` | The second viewer instance. `null` until first activation. |

---

## 4. Compass Scale (`Ctrl+scroll`)

```javascript
viewer.canvas.addEventListener('wheel', (e) => {
    if (!e.ctrlKey) return;
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    _compassScale = Math.max(0.1, Math.min(10.0, _compassScale * factor));
    viewer.scene.requestRender();
}, { passive: false });
```

`_compassScale` is consumed by:
- `compassEntity` positions callback — needle length: `2000.0 * _compassScale` metres
- `compassRingEntity` positions callback — ring radius: `1500.0 * _compassScale` metres
- `postRender` lens clip-path — ring polygon: `1500.0 * _compassScale` metres
- `lens_compass` / `lens_compassRing` callbacks (same references)

---

## 5. Compass Center Logic

`getCompassCenter()` returns the anchor point for all compass and lens calculations:

```javascript
function getCompassCenter() {
    if (trackedDroneEntity) {
        const dronePos = trackedDroneEntity.position.getValue(viewer.clock.currentTime);
        if (dronePos) {
            let carto = Cesium.Cartographic.fromCartesian(dronePos);
            carto.height = 0;
            return Cesium.Cartographic.toCartesian(carto);
        }
    }
    return currentMousePosition;  // fallback: mouse cursor on globe surface
}
```

When a drone is tracked, the lens and compass are anchored to the drone's ground projection regardless of where the mouse is. When no drone is tracked, they follow the mouse.

---

## 6. postRender Lens Update (lines ~967–1007 in `app.js`)

Runs every rendered frame of the main viewer:

```
1. Read _lensActive / _lensViewer guard
2. getCompassCenter() → center Cartesian3
3. wgs84ToWindowCoordinates(center) → windowCenter (unused except as null guard)
4. Build eastNorthUpToFixedFrame transform at center
5. Loop 48 angles → world pts on ring circumference → screen pts
6. lensEl.style.clipPath = polygon(...)
7. Sync _lensViewer.camera.{position, direction, up, right} from viewer.camera
8. _lensViewer.scene.requestRender()
```

If any ring point projects off-screen, `wgs84ToWindowCoordinates` returns `null` and the function returns early (lens clip-path stays at its last value until the point comes back on screen).

---

## 7. CSS

In `workspace-shell.css` and `style.css`:

```css
#satellite-lens {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    pointer-events: none;
    z-index: 50;
    display: none;
}
```

`pointer-events: none` ensures clicks pass through the lens div to the main canvas. `display: none` is toggled to `block` on activation.

---

## 8. Known Limitations & Future Work

- **Other entities inside the ring** (range rings, waypoint lines, tether lines, etc.) are NOT mirrored into `_lensViewer` and will be occluded by the satellite overlay when they fall inside the compass ring. Only the drone billboard and compass needle/ring are currently mirrored.
- **Lens viewer has no terrain** — satellite imagery is rendered on the WGS84 ellipsoid, so at steep camera angles there may be slight misregistration vs. the main viewer's terrain-draped imagery.
- **Ion asset ID `2`** is Bing Maps Aerial (requires a valid Cesium Ion token). If the token lacks access to asset 2, imagery will fail silently (`imageryLayers.removeAll()` is called first so no fallback layer remains).
- **Performance**: `_lensViewer` is a full Cesium scene. On low-end hardware, two simultaneous Cesium viewers may cause frame drops. `requestRenderMode` mitigates this at idle but both scenes render on every main-viewer frame when the lens is active.
- **Resize**: The lens div is `100%` width/height of `#cesiumContainer`, which is itself sized by the workspace shell layout. On workspace resize, both viewers resize automatically because they are children of the same container.
