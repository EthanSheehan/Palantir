# Unreal Engine → Isaac Sim: Target Tracking Pipeline

Satellite imagery → UE5 terrain → USD export → Isaac Sim → CV detection + autonomous drone tracking.

## Quick Start

1. Export your UE5+SynTerra scene as USD (see [UE5 Export](#step-3-usd-export-from-ue5))
2. Install Isaac Sim 5.1 binary to `C:\isaac-sim`
3. **Fix numpy**: `C:\isaac-sim\python.bat -m pip install numpy==1.26.4`
4. Open scene in Isaac Sim, run `apply_semantic_labels.py` in Script Editor
5. Hit Play, run any script from `scripts/`, watch with `python live_viewer.py`

---

## Pipeline Overview

```
Satellite Imagery
       ↓
UE5 + SynTerra  →  3D terrain with real satellite textures
       ↓
Add targets (cars, buildings from Fab marketplace)
       ↓
Export as OpenUSD (.usd) with baked materials
       ↓
NVIDIA Isaac Sim 5.1  →  Load scene, apply semantic labels
       ↓
Scripts (pick one):
  gt_bbox_viewer.py     →  Ground truth bounding boxes only
  gt_plus_yolo.py       →  Ground truth + YOLO side-by-side comparison
  drone_tracking.py     →  Autonomous drone: orbit → acquire → track
       ↓
live_viewer.py  →  Real-time OpenCV display window
```

---

## Prerequisites

| Software | Version | Notes |
|----------|---------|-------|
| Unreal Engine | 5.6.1 | Via Epic Games Launcher |
| SynTerra Plugin | Latest | From Fab marketplace |
| NVIDIA Isaac Sim | 5.1 | Binary install to `C:\isaac-sim` |
| numpy | **1.26.4** | **CRITICAL** — see below |
| ultralytics | Latest | For YOLO scripts only |
| opencv-python | 4.x | For live_viewer.py only |

**Hardware**: NVIDIA RTX GPU (tested on RTX 5070 Laptop), 32GB+ RAM.

---

## Step 1: UE5 + SynTerra Setup

1. Install UE5 5.6.1 via Epic Games Launcher
2. Enable plugins (Edit → Plugins):
   - **SynTerra** — satellite terrain generation
   - **Interchange OpenUSD** — USD export
   - **USD Core** — USD format support
3. Create blank project, open SynTerra panel
4. Select a terrain tile, click Generate
5. Add CV target objects (cars, buildings) from the Fab marketplace

## Step 2: Add CV Targets

Place static mesh assets on the terrain. Asset **names matter** — the semantic labeling script auto-detects prims containing "sedan", "car", "office", or "building" in their names.

## Step 3: USD Export from UE5

File → Export All → USD format:

| Setting | Value |
|---------|-------|
| Bake Materials | **ON** |
| Meters Per Unit | **0.01** |
| Up Axis | **Z-up** |

Save as `terrain_scene.usd`.

## Step 4: Isaac Sim Setup

### Install
Download Isaac Sim 5.1 binary, extract to `C:\isaac-sim`.

### CRITICAL: numpy Fix

Installing `ultralytics` (or any pip package) upgrades numpy to 2.x, which **breaks Replicator's C++ extensions**. The error:
```
Unable to write from unknown dtype, kind=i, size=0
```

**Fix** (run after every pip install):
```bash
C:\isaac-sim\python.bat -m pip install numpy==1.26.4
```

Verify:
```bash
C:\isaac-sim\python.bat -c "import numpy; print(numpy.__version__)"
# Must show: 1.26.4
```

### Install YOLO (for gt_plus_yolo and drone_tracking scripts)
```bash
C:\isaac-sim\python.bat -m pip install ultralytics
C:\isaac-sim\python.bat -m pip install numpy==1.26.4  # fix numpy again!
```

## Step 5: Load Scene and Label Objects

1. Launch Isaac Sim → File → Open → `terrain_scene.usd`
2. Open Script Editor (Window → Script Editor)
3. Paste and run `scripts/apply_semantic_labels.py`
4. Verify labels printed in console, then Ctrl+S to save

**Why not use the GUI?** The Semantics Schema Editor has reliability issues with UE5-exported prims. The `pxr.Semantics.SemanticsAPI.Apply()` method writes labels directly and Replicator reads them consistently.

---

## Scripts

All scripts run inside Isaac Sim's Script Editor. Hit **Play** first, then run the script.
All scripts output to `output/latest_annotated.png` for the live viewer.
All scripts stop with: paste `RUNNING = False` in Script Editor and run it.

### `scripts/apply_semantic_labels.py`
Applies "car" / "building" semantic labels to prims. **Run this first**, once per scene load.

### `scripts/gt_bbox_viewer.py`
Follows viewport camera. Draws **green ground truth bounding boxes** from Replicator annotators. No AI model — Isaac Sim knows where objects are from the scene graph.

### `scripts/gt_plus_yolo.py`
Follows viewport camera. Draws both:
- **GREEN** = Ground truth (perfect, from scene graph)
- **RED** = YOLOv8 predictions (what the model actually sees)

Shows where YOLO fails vs perfect ground truth. YOLO runs on CPU (~50ms/frame).

### `scripts/drone_tracking.py`
Autonomous drone target acquisition and tracking demo. Creates a `/TrackingDrone` camera that:

1. **ORBITING** (yellow) — Circles at 50m altitude, 80m radius, searching
2. **ACQUIRED** (orange) — YOLO detected target, drone steers to center it
3. **LOCKED** (green) — Target centered in frame, maintaining track with fine corrections

HUD shows: state, pixel error, crosshair, steering vector, GT+YOLO boxes, distance.

If YOLO loses the target for 20+ frames, drops back to orbit.

### `live_viewer.py`
Run in a **separate terminal**:
```bash
python live_viewer.py
```
Displays the annotated frames in a resizable OpenCV window. Press Q to quit.

---

## File Structure

```
unreal_to_isaac_target_tracking_2/
├── README.md                      # This file
├── live_viewer.py                 # OpenCV live display (run separately)
├── output/                        # Created at runtime
│   └── latest_annotated.png       # Continuously updated by scripts
└── scripts/
    ├── apply_semantic_labels.py   # Run first — labels scene objects
    ├── gt_bbox_viewer.py          # Ground truth bounding boxes only
    ├── gt_plus_yolo.py            # Ground truth + YOLO comparison
    └── drone_tracking.py          # Autonomous drone tracking demo
```

Your USD scene file (`terrain_scene.usd` + `Assets/` folder) should be placed alongside or referenced by path in the scripts.

---

## Known Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| "Unable to write from unknown dtype" | numpy 2.x installed | `pip install numpy==1.26.4` |
| Semantic labels not detected | GUI editor unreliable with UE5 exports | Use `apply_semantic_labels.py` |
| YOLO hangs on GPU | Isaac Sim owns GPU exclusively | Force `model.to("cpu")` |
| Textures missing in Isaac Sim | Bake Materials was OFF during export | Re-export with Bake Materials ON |
| RTX Real-Time shows grey/black | Material compatibility | Switch to RTX Interactive |
| Satellite texture fades at ground level | SynTerra LOD blending in UE5 | Expected; doesn't affect export |

---

## How It Works

**Ground truth bounding boxes** are NOT from an AI model. Isaac Sim's Replicator reads semantic labels from the scene graph and computes pixel-perfect 2D bounding boxes by projecting 3D prim bounds onto the camera. This is free labeled training data.

**YOLO** (in gt_plus_yolo and drone_tracking) runs generic YOLOv8n on CPU. It wasn't trained on overhead views, so it often misclassifies or misses objects. The gap between green (perfect) and red (YOLO) boxes is exactly what you'd close by training a custom model on this synthetic data.

**The drone tracking** uses YOLO detections to steer. The pixel error between the detection center and screen center drives lateral movement. This is a simplified proportional controller — replace `MOVE_GAIN` and `DRONE_SPEED` with your actual flight dynamics model.
