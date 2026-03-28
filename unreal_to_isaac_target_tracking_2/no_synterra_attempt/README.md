# Automated Terrain-to-Terminal-Dive Pipeline

Single-command pipeline that converts DEM + satellite imagery into a 3D terminal dive visualization with ground truth annotation and GPU YOLO detection.

**Three rendering backends** — use whichever fits your setup:

| Backend | Command | Requirements |
|---------|---------|-------------|
| **pyrender** (recommended) | `python run_pyrender.py` | Any GPU (Intel/AMD/NVIDIA) or CPU-only |
| **PyVista** | `python run_standalone.py` | Any GPU or CPU-only |
| **Isaac Sim** (legacy) | `C:\isaac-sim\python.bat run_auto.py` | NVIDIA GPU + Isaac Sim 5.1 (~50GB) |

## Quick Start (No NVIDIA Required)

```bash
# Install dependencies (~20MB)
pip install -r requirements.txt

# Default location (Iași, Romania):
python run_pyrender.py

# Any location:
python run_pyrender.py --dem "path/to/dem.tif" --sat "path/to/satellite.tif" --lat 46.02 --lon 7.75

# Higher resolution:
python run_pyrender.py --resolution 1280x720 --max-vertices 30000

# With native YOLO inference (no WSL2 needed):
python run_pyrender.py --yolo

# Force CPU rendering (no GPU needed at all):
python run_pyrender.py --cpu

# Skip terrain rebuild (use existing mesh):
python run_pyrender.py --no-build
```

## Legacy: Isaac Sim Backend

```bash
# Requires NVIDIA Isaac Sim 5.1 at C:\isaac-sim
C:\isaac-sim\python.bat run_auto.py
C:\isaac-sim\python.bat run_auto.py --dem "path\to\dem.tif" --sat "path\to\satellite.tif" --lat 46.02 --lon 7.75
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

### pyrender Pipeline (recommended, no NVIDIA)

```
┌────────────────────────────────────────────────────────────┐
│  python run_pyrender.py                                     │
│                                                             │
│  renderer/                                                  │
│    camera.py      — DroneCamera (FOV, view matrix, proj)    │
│    scene.py       — SceneBuilder (OBJ+texture, targets)     │
│    offscreen.py   — OffscreenRenderer (GPU/CPU auto)        │
│    annotator.py   — GroundTruthAnnotator (3D→2D bbox)       │
│                                                             │
│  flight/                                                    │
│    controller.py  — FlightController (cruise/dive/terminal) │
│    config.py      — FlightConfig (all tunable parameters)   │
│    dynamics.py    — FlightState, Phase enum                 │
│                                                             │
│  Loop:                                                      │
│    flight_controller.step(dt, gt_boxes)                     │
│    camera.set_pose(position, direction, pitch)              │
│    color, depth = renderer.render(scene, camera)            │
│    gt_boxes = annotator.get_annotations(depth)              │
│    → _tmp.png + gt_data.json                                │
│                                                             │
│  Optional: yolo_inference.py (native, no WSL2)              │
│  Optional: WIN_live_viewer.py (OpenCV display)              │
└────────────────────────────────────────────────────────────┘
```

### Isaac Sim Pipeline (legacy)

```
┌──────────────────────────────────────────────────────────────┐
│  run_auto.py (runs via C:\isaac-sim\python.bat)              │
│  SimulationApp → OBJ→USD → Replicator annotators             │
│  Same flight loop, same output format                        │
│  Requires: NVIDIA GPU + Isaac Sim 5.1 (~50GB)               │
└──────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose | Requires |
|------|---------|----------|
| `run_pyrender.py` | **Primary entry point** — pyrender + trimesh (no NVIDIA) | Python + pip deps |
| `run_standalone.py` | PyVista/VTK alternative (no NVIDIA) | Python + pyvista |
| `run_auto.py` | Isaac Sim version (legacy) | NVIDIA Isaac Sim 5.1 |
| `renderer/` | Modular rendering package (camera, scene, offscreen, annotator) | pyrender, trimesh |
| `flight/` | Flight dynamics package (controller, config, state machine) | numpy |
| `yolo_inference.py` | Native YOLO inference (replaces WSL2 bridge) | ultralytics (optional) |
| `build_terrain_mesh.py` | DEM + satellite GeoTIFFs → OBJ mesh + texture | rasterio, pyproj |
| `download_test_data.py` | Downloads DEM + satellite for test locations | dem-stitcher |
| `WSL2_yolo_gpu_inference.py` | GPU YOLO via WSL2 (legacy, still works) | WSL2 Ubuntu |
| `WIN_live_viewer.py` | Displays combined GT+YOLO feed | opencv-python |
| `requirements.txt` | All pip dependencies for pyrender pipeline | pip |

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
python run_pyrender.py --dem "GIS DATA/san_francisco/dem.tif" --sat "GIS DATA/san_francisco/satellite.tif" --lat 37.78 --lon -122.42

# Swiss Alps (Matterhorn area)
python run_pyrender.py --dem "GIS DATA/swiss_alps/dem.tif" --sat "GIS DATA/swiss_alps/satellite.tif" --lat 46.02 --lon 7.75

# Dubai
python run_pyrender.py --dem "GIS DATA/dubai/dem.tif" --sat "GIS DATA/dubai/satellite.tif" --lat 25.20 --lon 55.27

# Tokyo
python run_pyrender.py --dem "GIS DATA/tokyo/dem.tif" --sat "GIS DATA/tokyo/satellite.tif" --lat 35.65 --lon 139.77
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

### pyrender Pipeline (recommended)

```bash
pip install -r requirements.txt
# That's it. Works on Windows, Linux, macOS. Any GPU or CPU-only.
```

Core dependencies (~20MB total):
- `pyrender>=0.1.45` — offscreen 3D rendering
- `trimesh>=4.0` — OBJ mesh loading
- `pyglet>=2.0` — OpenGL context (Windows GPU)
- `numpy`, `Pillow`, `opencv-python`
- `rasterio`, `pyproj` — for terrain mesh building

Optional (for native YOLO):
```bash
pip install ultralytics torch
```

### Isaac Sim Pipeline (legacy)

- NVIDIA Isaac Sim 5.1 at `C:\isaac-sim`
- numpy 1.26.4: `C:\isaac-sim\python.bat -m pip install numpy==1.26.4`
- NVIDIA GPU required

### WSL2 YOLO (legacy, only if not using native yolo_inference.py)

- WSL2 Ubuntu 22.04 with PyTorch + CUDA
- ultralytics, opencv-python-headless

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
python run_pyrender.py --dem "your_dem.tif" --sat "your_sat.tif" --lat 51.5 --lon -0.12
```

### Off-Center POI
The POI does NOT need to be at the center of the tile. It can be anywhere within the DEM bounds. The terrain renders the full DEM extent; the truck is placed at the POI coordinates. The drone always approaches from 300m offset along the X-axis relative to the POI.

### Higher/Lower Terrain Detail
```bash
python run_pyrender.py --max-vertices 50000   # more detail
python run_pyrender.py --max-vertices 5000    # faster
```

### Custom Resolution
```bash
python run_pyrender.py --resolution 1280x720
python run_pyrender.py --resolution 1920x1080
```

### Drone Flight Parameters
Edit `flight/config.py` (FlightConfig dataclass):
```python
FlightConfig(
    drone_altitude_cm=10000.0,     # 100m starting altitude
    start_offset_cm=30000.0,       # 300m start distance
    dive_trigger_dist_cm=15000.0,  # 150m — dive begins
    speed_cm_per_sec=1388.9,       # 50kph
    kp_pitch=0.15,                 # pitch gain (deg/pixel)
    min_pitch=5.0, max_pitch=85.0,
    min_altitude_cm=200.0,         # 2m impact threshold
)
```

### Adding Custom Target Objects
```python
from renderer import SceneBuilder
scene = SceneBuilder("terrain_mesh.obj", "terrain_texture.png", metadata)
scene.add_target("truck", "truck", position=[0, 5000, 0], size=500)
scene.add_target("tank", "tank", position=[1000, 5100, 500], size=800)
```

### Web Backend Integration
```python
@app.post("/api/missions/visualize")
async def visualize(dem_file, sat_file, poi_lat, poi_lon):
    proc = subprocess.Popen([
        sys.executable, "run_pyrender.py",
        "--dem", dem_path, "--sat", sat_path,
        "--lat", str(poi_lat), "--lon", str(poi_lon),
        "--headless",
    ], cwd="path/to/no_synterra_attempt")
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

## Performance Comparison

| Metric | Isaac Sim (`run_auto.py`) | pyrender (`run_pyrender.py`) |
|--------|--------------------------|------------------------------|
| Install size | ~50GB (Isaac Sim binary) | ~20MB (pip packages) |
| Startup time | 60-120 seconds | <2 seconds |
| Render FPS (GPU) | 20-30 FPS (RTX) | 30-40 FPS (OpenGL) |
| Render FPS (CPU) | N/A | 10-20 FPS (OSMesa) |
| GT bbox accuracy | Sub-pixel (Replicator) | Pixel-accurate (projection math) |
| Memory usage | 4-8GB VRAM | 200-500MB RAM |
| Platform | Windows + NVIDIA GPU only | Any OS, any GPU, or CPU-only |
| numpy version | Locked to 1.26.4 | Any 1.24+ or 2.x |
| Python version | Isaac Sim's bundled Python | Any Python 3.10+ |

## Design Decisions Log

| Decision | Why | Alternative Considered |
|----------|-----|----------------------|
| pyrender + trimesh over Isaac Sim | No NVIDIA dependency, 2500x smaller install, faster startup | PyVista/VTK (works but flaky offscreen on Windows) |
| Bypass UE5 entirely | SynTerra is GUI-only, cannot be automated | Cesium for Unreal (has API but adds complexity) |
| Y-up coordinate system | OBJ standard; consistent across all backends | Z-up with post-import rotation (fragile) |
| Camera projection for GT boxes | Pure math, no runtime dependency | Replicator annotators (NVIDIA-only) |
| Depth buffer occlusion | pyrender provides depth; same algorithm as Replicator | Ray casting (slower, more complex) |
| Native YOLO (`yolo_inference.py`) | No WSL2 needed; runs on same GPU | WSL2 bridge (still works as fallback) |
| Gimbal-lock-safe camera | Heading+pitch avoids singularity on steep terrain | Quaternion rotation (more complex, same result) |
| Auto-subsample mesh | Different DEM sizes need different detail levels | Fixed subsample (breaks on large/small DEMs) |
| Modular packages (renderer/, flight/) | Reusable, testable, swappable backends | Monolithic script (harder to maintain) |
