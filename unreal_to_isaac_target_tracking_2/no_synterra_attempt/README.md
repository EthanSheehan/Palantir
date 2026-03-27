# Automated Terrain-to-Terminal-Dive Pipeline (No UE5/SynTerra)

Single-command pipeline that converts DEM + satellite imagery into an Isaac Sim terminal dive visualization with GPU YOLO detection.

## One Command to Run Everything

```bash
# Default (Iași, Romania):
C:\isaac-sim\python.bat run_auto.py

# Any location (provide your own DEM + satellite GeoTIFFs + POI coordinates):
C:\isaac-sim\python.bat run_auto.py --dem "path\to\dem.tif" --sat "path\to\satellite.tif" --lat 46.02 --lon 7.75

# Higher terrain detail:
C:\isaac-sim\python.bat run_auto.py --dem "dem.tif" --sat "sat.tif" --lat 37.78 --lon -122.42 --max-vertices 30000
```

This single command:
1. Builds terrain mesh from DEM + satellite GeoTIFFs (auto-subsample to target vertex count)
2. Validates CRS (EPSG:4326) and POI bounds
3. Kills old WSL2 watchers and viewer windows
4. Launches WSL2 GPU YOLO watcher (background)
5. Launches Windows live viewer (background)
6. Launches Isaac Sim with GUI
7. Converts terrain OBJ to USD
8. Opens the scene with satellite-textured terrain
9. Places a truck target at the POI with semantic labels
10. Starts simulation playback
11. Runs the terminal dive guidance loop (CRUISE → DIVE → IMPACT → repeat)

No manual interaction needed. Ctrl+C stops everything.

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--dem` | Iași DEM | Path to DEM GeoTIFF (must be EPSG:4326) |
| `--sat` | Iași satellite | Path to satellite imagery GeoTIFF (EPSG:4326, RGB) |
| `--lat` | 47.217 | POI latitude (where target is placed) |
| `--lon` | 27.615 | POI longitude |
| `--max-vertices` | 15000 | Max terrain mesh vertices (auto-calculates subsample) |

## How It Was Achieved

### Problem
The original pipeline required manual steps across 3 tools:
- **UE5 + SynTerra** (GUI-only) to generate terrain from satellite imagery
- **Isaac Sim** (manual script pasting) for visualization
- **WSL2** (separate terminal) for GPU YOLO inference

SynTerra has no API/CLI — it cannot be automated. The UE5 → USD export was manual.

### Solution: Bypass UE5 Entirely

Instead of UE5 + SynTerra, we build the terrain mesh directly from GeoTIFF data using Python:

```
GeoTIFF DEM + Satellite imagery
         ↓
  build_terrain_mesh.py (rasterio + numpy)
         ↓
  terrain_mesh.obj + terrain_texture.png + metadata.json
         ↓
  Isaac Sim asset converter (OBJ → USD)
         ↓
  terrain_auto.usd (loaded programmatically)
```

### Key Technical Decisions

**1. Y-Up Coordinate System**
- OBJ/USD uses Y-up convention
- DEM data is naturally (east, north, up)
- Vertex mapping: `X=east, Y=up, Z=-north`
- All drone movement code adapted accordingly

**2. Isaac Sim SimulationApp**
- Isaac Sim's `--exec` flag doesn't work reliably
- Instead, use `from isaacsim import SimulationApp` to launch Isaac Sim from Python
- This gives full programmatic control: `simulation_app.update()` drives the render loop
- All scene setup, playback, and guidance runs in a single Python process

**3. Async Handling**
- Isaac Sim's Replicator uses `async/await` for `orchestrator.step_async()`
- Cannot use `asyncio.run_until_complete()` (conflicts with Isaac Sim's event loop)
- Solution: `asyncio.ensure_future()` + pump `simulation_app.update()` until done

**4. GPU YOLO via File Sharing**
- Isaac Sim's Python cannot access the GPU for YOLO (device_count=0)
- WSL2 Ubuntu 22.04 with PyTorch nightly (cu128) CAN access the RTX 5070
- Communication: Isaac Sim writes `_tmp.png` + `gt_data.json` to disk
- WSL2 reads via `/mnt/c/` shared filesystem, runs YOLO, writes `latest_gpu_yolo.png`
- Windows live viewer displays `latest_gpu_yolo.png`

**5. numpy Version Lock**
- Isaac Sim 5.1 Replicator requires `numpy==1.26.4`
- Any pip install that upgrades numpy to 2.x breaks Replicator with: `Unable to write from unknown dtype`
- WSL2 also needs `numpy==1.26.4` for cv_bridge compatibility

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  run_auto.py (runs via C:\isaac-sim\python.bat)              │
│                                                              │
│  1. Cleanup old processes                                    │
│  2. Launch WSL2 GPU YOLO watcher ──────────┐                 │
│  3. Launch Windows live viewer ─────────┐  │                 │
│  4. SimulationApp() ← Isaac Sim starts  │  │                 │
│  5. Convert OBJ → USD                   │  │                 │
│  6. Open scene, place truck, labels     │  │                 │
│  7. Play simulation                     │  │                 │
│  8. Terminal dive loop:                 │  │                 │
│     ├─ Move drone                       │  │                 │
│     ├─ Render frame                     │  │                 │
│     ├─ Get GT bounding boxes            │  │                 │
│     ├─ Pitch guidance controller        │  │                 │
│     ├─ Write _tmp.png ─────────────────────→ WSL2 reads      │
│     ├─ Write gt_data.json ─────────────────→ WSL2 reads      │
│     │                                   │  │                 │
│     │  WSL2: GPU YOLO on _tmp.png ──────│──┘                 │
│     │  WSL2: Draw GT+YOLO+HUD ─────────│──→ latest_gpu_yolo  │
│     │                                   │                    │
│     │  Viewer: Display latest_gpu_yolo ←┘                    │
│     └─ Loop                                                  │
└──────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose | Runs On |
|------|---------|---------|
| `run_auto.py` | **Main entry point** — single command runs everything | Isaac Sim Python |
| `build_terrain_mesh.py` | DEM + satellite GeoTIFFs → OBJ mesh + texture | Any Python (rasterio) |
| `download_test_data.py` | Downloads DEM + satellite for test locations | Any Python (dem-stitcher) |
| `WSL2_yolo_gpu_inference.py` | GPU YOLO inference + draws all HUD from JSON | WSL2 Ubuntu |
| `WIN_live_viewer.py` | Displays combined GT+YOLO feed | Windows Python |
| `ISAACSIM_terminal_dive.py` | Standalone version (paste in Script Editor) | Isaac Sim Script Editor |
| `ISAACSIM_apply_labels.py` | Standalone label application | Isaac Sim Script Editor |

### Generated Files (output of build_terrain_mesh.py)

| File | Content |
|------|---------|
| `terrain_mesh.obj` | Terrain triangle mesh (Y-up, cm units) |
| `terrain_mesh.mtl` | Material referencing terrain_texture.png |
| `terrain_texture.png` | Satellite imagery texture (up to 4096px) |
| `metadata.json` | POI coords, elevation, terrain extent, vertex count |
| `terrain_auto.usd` | USD scene (generated by Isaac Sim asset converter) |

### Runtime Output (in output/ directory)

| File | Content | Updated By |
|------|---------|------------|
| `_tmp.png` | Raw drone camera frame | Isaac Sim |
| `gt_data.json` | GT bounding boxes + flight metadata (pitch, alt, phase) | Isaac Sim |
| `latest_gpu_yolo.png` | Combined frame: GT (green) + YOLO (red) + HUD | WSL2 watcher |

## GIS Data

### Input Requirements

| Property | Requirement |
|----------|-------------|
| Format | GeoTIFF (.tif) |
| CRS | EPSG:4326 (WGS84) — script warns if different |
| DEM bands | 1 band (elevation in meters) |
| Satellite bands | 3 bands (RGB) |
| Coverage | Satellite must cover DEM extent (script warns if not) |
| POI | Must fall within DEM bounds (script errors if not) |
| POI position | Can be anywhere on the tile — does NOT need to be centered |

### Included Test Data

Downloaded via `download_test_data.py` (no API keys needed):

| Location | Center | DEM | Satellite | Terrain |
|----------|--------|-----|-----------|---------|
| **Iași, Romania** | 47.217°N, 27.615°E | `GIS/rasters_COP30/output_hh.tif` | `GIS/iasi_esri_clipped.tif` | Rolling hills, 36-230m |
| **San Francisco** | 37.78°N, 122.42°W | `GIS DATA/san_francisco/dem.tif` | `GIS DATA/san_francisco/satellite.tif` | Urban + water + hills |
| **Swiss Alps** | 46.02°N, 7.75°E | `GIS DATA/swiss_alps/dem.tif` | `GIS DATA/swiss_alps/satellite.tif` | Steep mountains, 1480-4385m |
| **Dubai** | 25.20°N, 55.27°E | `GIS DATA/dubai/dem.tif` | `GIS DATA/dubai/satellite.tif` | Flat desert + coast |
| **Tokyo Bay** | 35.65°N, 139.77°E | `GIS DATA/tokyo/dem.tif` | `GIS DATA/tokyo/satellite.tif` | Dense urban + coastline |

### Downloading New Test Data

```bash
# Download all 4 test locations (no API keys):
python download_test_data.py

# Download specific locations:
python download_test_data.py --locations san_francisco swiss_alps

# Uses dem-stitcher (Copernicus 30m from AWS) + Sentinel-2 (from AWS Earth Search)
```

### Running Test Locations

```bash
# San Francisco
C:\isaac-sim\python.bat run_auto.py --dem "GIS DATA\san_francisco\dem.tif" --sat "GIS DATA\san_francisco\satellite.tif" --lat 37.78 --lon -122.42

# Swiss Alps (Matterhorn area)
C:\isaac-sim\python.bat run_auto.py --dem "GIS DATA\swiss_alps\dem.tif" --sat "GIS DATA\swiss_alps\satellite.tif" --lat 46.02 --lon 7.75

# Dubai
C:\isaac-sim\python.bat run_auto.py --dem "GIS DATA\dubai\dem.tif" --sat "GIS DATA\dubai\satellite.tif" --lat 25.20 --lon 55.27

# Tokyo
C:\isaac-sim\python.bat run_auto.py --dem "GIS DATA\tokyo\dem.tif" --sat "GIS DATA\tokyo\satellite.tif" --lat 35.65 --lon 139.77
```

## Terminal Dive Behavior

```
CRUISE (0° pitch, 100m altitude)
  │  Flies straight toward target at 50kph
  │  GT detects truck when in view
  │
  ▼  At 150m from target:
DIVE (pitch increases, altitude drops)
  │  Proportional controller: error_y → pitch adjustment
  │  Kp = 0.15 deg/pixel, clamped to 5°-85°
  │  Descent rate = speed × sin(pitch)
  │
  ▼  At 2m altitude:
IMPACT
  │  Holds for 1 second
  │
  ▼  Resets to start position, repeats
```

## Prerequisites

### Windows
- NVIDIA Isaac Sim 5.1 at `C:\isaac-sim`
- numpy 1.26.4: `C:\isaac-sim\python.bat -m pip install numpy==1.26.4`
- Pillow: `C:\isaac-sim\python.bat -m pip install Pillow`
- rasterio + pyproj: `C:\isaac-sim\python.bat -m pip install rasterio pyproj`
- OpenCV: `pip install opencv-python` (system Python for viewer)

### WSL2 (Ubuntu 22.04)
- ROS2 Humble: `sudo apt install ros-humble-ros-base ros-humble-cv-bridge`
- PyTorch nightly: `pip3 install torch --pre --index-url https://download.pytorch.org/whl/nightly/cu128`
- ultralytics: `pip3 install ultralytics`
- numpy 1.26.4: `pip3 install numpy==1.26.4`
- opencv: `pip3 install opencv-python-headless`

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `Unable to write from unknown dtype` | numpy 2.x in Isaac Sim | `C:\isaac-sim\python.bat -m pip install numpy==1.26.4` |
| Isaac Sim crashes on start | Previous instance still running | Script auto-cleans, or manually: `taskkill /F /IM kit.exe` |
| Multiple viewer windows | Old viewers not killed | Script auto-kills on startup; run once to clear |
| WSL2 watcher shows 0 detections | YOLO not trained for aerial views | Expected — GT does the steering, YOLO is for comparison |
| libpng errors in WSL2 | File read/write contention | Non-fatal, handled with retries |
| `There was an error running python` | Cleanup killed own process | Fixed: cleanup no longer kills kit.exe |
| Terrain appears vertical | OBJ built with wrong axis convention | Fixed: uses Y-up (X=east, Y=up, Z=-north) |
| Camera flips/stutters on steep terrain | Gimbal lock in look-at calculation | Fixed: uses heading+pitch rotation (no cross-product singularity) |
| `ERROR: POI is outside DEM bounds` | POI lat/lon not within DEM extent | Check coordinates; POI must be within the GeoTIFF bounds |
| `WARNING: Satellite does not fully cover DEM` | Satellite raster smaller than DEM | Re-export satellite to cover full DEM extent |
| `WARNING: DEM CRS is not EPSG:4326` | Wrong projection | Reproject with: `gdalwarp -t_srs EPSG:4326 input.tif output.tif` |

## Extending This Pipeline

### Different Location (CLI)
```bash
C:\isaac-sim\python.bat run_auto.py --dem "your_dem.tif" --sat "your_sat.tif" --lat 51.5 --lon -0.12
```

### Off-Center POI
The POI does NOT need to be at the center of the tile. It can be anywhere within the DEM bounds. The terrain renders the full DEM extent; the truck is placed at the POI coordinates. The drone always approaches from 300m offset along the X-axis relative to the POI.

### Different Target Object
Replace the placeholder cube in `run_auto.py` with a USD mesh reference:
```python
# Instead of UsdGeom.Cube.Define(stage, truck_path):
truck_prim = stage.DefinePrim('/Target', 'Xform')
truck_prim.GetReferences().AddReference('path/to/your_object.usd')
```

### Higher/Lower Terrain Detail
```bash
# More vertices = more detail but slower
C:\isaac-sim\python.bat run_auto.py --max-vertices 50000

# Fewer vertices = faster but coarser
C:\isaac-sim\python.bat run_auto.py --max-vertices 5000
```
The subsample factor is auto-calculated: `subsample = sqrt(total_dem_pixels / max_vertices)`

### Drone Flight Parameters
Edit these constants in `run_auto.py` (search for "CONFIG"):
```python
DRONE_ALTITUDE = 10000.0      # cm = 100m starting altitude
START_OFFSET = 30000.0        # cm = 300m start distance from target
DIVE_TRIGGER_DIST = 15000.0   # cm = 150m — dive begins here
SPEED_CM_PER_SEC = 1388.9     # 50kph
INITIAL_PITCH = 0.0           # degrees — level cruise
Kp_PITCH = 0.15               # pitch gain (deg/pixel error)
MIN_PITCH, MAX_PITCH = 5.0, 85.0
MIN_ALTITUDE = 200.0          # cm = 2m — impact threshold
```

### Web Backend Integration
```python
# Flask/FastAPI endpoint
@app.post("/api/missions/visualize")
async def visualize(dem_file, sat_file, poi_lat, poi_lon):
    # 1. Save uploaded files to disk
    dem_path = save_upload(dem_file)
    sat_path = save_upload(sat_file)

    # 2. Launch the full pipeline via subprocess
    import subprocess
    proc = subprocess.Popen([
        r"C:\isaac-sim\python.bat", "run_auto.py",
        "--dem", dem_path,
        "--sat", sat_path,
        "--lat", str(poi_lat),
        "--lon", str(poi_lon),
    ], cwd=r"path\to\no_synterra_attempt")

    # 3. Stream output/latest_gpu_yolo.png to frontend via WebSocket/polling
    return {"status": "running", "pid": proc.pid}
```

### Downloading GIS Data Programmatically
```python
# In your backend, use dem-stitcher + AWS Earth Search:
from dem_stitcher import stitch_dem
import rasterio

# DEM — no auth needed
bounds = [lon-0.05, lat-0.05, lon+0.05, lat+0.05]  # ~10km bbox
X, profile = stitch_dem(bounds, dem_name='glo_30')
with rasterio.open('dem.tif', 'w', **profile) as ds:
    ds.write(X, 1)

# Satellite — see download_test_data.py for full example
```

## Design Decisions Log

| Decision | Why | Alternative Considered |
|----------|-----|----------------------|
| Bypass UE5 entirely | SynTerra is GUI-only, cannot be automated | Cesium for Unreal (has API but adds complexity) |
| OBJ → USD via Isaac Sim converter | pxr (OpenUSD) not available in system Python 3.14 | Direct USD construction with usd-core pip package |
| Y-up coordinate system | OBJ/USD standard; Isaac Sim expects it | Z-up with post-import rotation (fragile) |
| GPU YOLO in WSL2 via file sharing | Isaac Sim's Python has device_count=0 for CUDA | ROS2 bridge (DDS discovery failed cross-OS) |
| JSON sidecar for GT data | Avoids HUD flicker from image compositing | Bake HUD into image on Isaac Sim side |
| Gimbal-lock-safe camera | Cross-product singularity on steep terrain | Quaternion rotation (more complex, same result) |
| Auto-subsample mesh | Different DEM sizes need different detail levels | Fixed subsample (breaks on large/small DEMs) |
| numpy==1.26.4 lock | Replicator C++ extensions compiled against numpy 1.x | None — this is a hard requirement |
| SimulationApp launch | --exec flag unreliable on Isaac Sim 5.1 Windows | Script Editor paste (manual) |
