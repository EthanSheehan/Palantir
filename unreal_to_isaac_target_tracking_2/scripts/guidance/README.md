# Camera Pitch Guidance — Detection-Driven Gimbal Tracking

Single degree of freedom demo: camera pitch adjusts to keep the detected target centered vertically. Drone path is identical to the flyover (straight line, 30m, 50kph). Only the camera angle changes.

A 3D drone mesh (STL) follows the camera through the scene, visible in the Isaac Sim viewport.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Isaac Sim (Windows)                                    │
│                                                         │
│  ISAACSIM_pitch_guidance.py                             │
│    ├─ Drone camera flies straight line at 30m, 50kph    │
│    ├─ Replicator renders frame → GT bounding box        │
│    ├─ error_y = bbox_center_y - screen_center_y         │
│    ├─ camera_pitch += Kp * error_y (clamped 10°-80°)    │
│    ├─ Drone STL mesh follows camera (0.1x scale)        │
│    ├─ Saves _tmp.png (raw) + latest_annotated.png (GT)  │
│    └─ No CPU YOLO — all rendering on GPU                │
│                                                         │
│  Output: output_guidance/_tmp.png                       │
│          output_guidance/latest_annotated.png            │
└──────────────────────┬──────────────────────────────────┘
                       │  File on /mnt/c/ (shared filesystem)
┌──────────────────────▼──────────────────────────────────┐
│  WSL2 (Ubuntu 22.04)                                    │
│                                                         │
│  WSL2_yolo_gpu_inference.py                             │
│    ├─ Reads _tmp.png continuously                       │
│    ├─ Runs YOLOv11n on RTX 5070 GPU (~21ms)             │
│    ├─ Reads latest_annotated.png for GT overlay         │
│    ├─ Composites GT (green) + YOLO (red) into one frame │
│    └─ Saves latest_gpu_yolo.png                         │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Windows                                                │
│                                                         │
│  WIN_live_viewer.py                                     │
│    └─ Displays latest_gpu_yolo.png in OpenCV window     │
└─────────────────────────────────────────────────────────┘
```

When target is above center → pitch decreases (look up)
When target is below center → pitch increases (look down)
As drone passes over → pitch increases to follow target behind

## Files

| File | Runs On | Purpose |
|------|---------|---------|
| `ISAACSIM_apply_labels.py` | Isaac Sim Script Editor | Label objects for GT detection (run first) |
| `ISAACSIM_pitch_guidance.py` | Isaac Sim Script Editor | Drone flyover + pitch tracking + drone mesh |
| `WSL2_yolo_gpu_inference.py` | WSL2 terminal | GPU YOLO inference + GT/YOLO composite |
| `WIN_live_viewer.py` | Windows terminal | Display combined GT+YOLO feed |

## Prerequisites

- **Isaac Sim 5.1** installed at `C:\isaac-sim`
- **numpy 1.26.4** in Isaac Sim's Python: `C:\isaac-sim\python.bat -m pip install numpy==1.26.4`
- **WSL2 Ubuntu 22.04** with:
  - ROS2 Humble: `sudo apt install ros-humble-ros-base ros-humble-cv-bridge`
  - PyTorch nightly (cu128): `pip3 install torch --pre --index-url https://download.pytorch.org/whl/nightly/cu128`
  - ultralytics: `pip3 install ultralytics`
  - numpy 1.26.4: `pip3 install numpy==1.26.4`
- **Drone STL mesh** at `C:\Users\victo\Downloads\unreal_to_isaac_target_tracking_2\Drone.stl`
- **Truck scene USD** exported from UE5 + SynTerra

## How to Run

### 1. Launch Isaac Sim
```
C:\isaac-sim\isaac-sim.bat
```

### 2. Load Scene & Apply Labels
- File → Open → load your truck scene USD
- Open Script Editor (Window → Script Editor)
- Paste and run `ISAACSIM_apply_labels.py`
- Verify console shows "Labeled: /Root/zil_130_body_lowpoly"

### 3. Start Drone Flyover
- **Hit Play** (triangle button on left toolbar)
- Paste and run `ISAACSIM_pitch_guidance.py`
- The drone + camera should start moving in the viewport

### 4. Start GPU YOLO (WSL2)
```bash
source /opt/ros/humble/setup.bash
cd /mnt/c/Users/victo/Downloads/unreal_to_isaac_target_tracking_2/scripts/guidance
python3 WSL2_yolo_gpu_inference.py
```

### 5. Start Live Viewer (Windows)
```bash
cd C:\Users\victo\Downloads\unreal_to_isaac_target_tracking_2\scripts\guidance
python WIN_live_viewer.py
```

Or have Claude Code run it: the viewer watches `output_guidance/latest_gpu_yolo.png`.

### 6. Stop Everything
- Isaac Sim: paste `RUNNING = False` in Script Editor and run
- WSL2: Ctrl+C
- Viewer: press Q

## Tuning

In `ISAACSIM_pitch_guidance.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `Kp_PITCH` | 0.15 | Pitch gain (deg/pixel). Higher = more aggressive tracking |
| `MIN_PITCH` | 10.0 | Minimum downward angle (degrees) |
| `MAX_PITCH` | 80.0 | Maximum downward angle (degrees) |
| `INITIAL_PITCH` | 45.0 | Starting pitch angle |
| `DRONE_ALTITUDE` | 3000.0 | Fixed altitude in cm (30m) |
| `SPEED_CM_PER_SEC` | 1388.9 | Flight speed (50kph) |
| `START_OFFSET` | 10000.0 | Start distance from target in cm (100m) |
| `OVERSHOOT` | 10000.0 | Distance past target before reversing (100m) |
| `DRONE_MESH_SCALE` | 0.1 | STL model scale factor |
| `DRONE_MESH_Z_OFFSET` | 200.0 | Mesh position above camera in cm (+2m) |

## Drone Mesh Notes

- The STL drone model is imported at scene start and follows the camera each frame
- Positioned 2m above the camera so it doesn't block the CV view
- Scaled to 0.1x to match scene proportions
- Orientation corrections applied: 90° CC roll + 90° CC yaw to align with flight direction
- Visible in Isaac Sim viewport but not in the CV camera feed

## What to Watch For

- **Approaching target**: pitch stays ~45°, GT box appears in lower half of frame
- **Over target**: pitch increases toward 80° as drone looks straight down
- **Past target**: pitch stays high, tracking truck behind the drone
- **Reversal**: drone reverses at ±100m, pitch resets to 45° and tracking restarts
- **HUD shows**: TRACKING/SEARCHING state, current pitch angle, error_y in pixels
- **Live viewer**: GREEN = Ground Truth (perfect), RED = YOLO predictions (model inference)
- **libpng errors in WSL2**: normal — file contention between Isaac Sim writing and WSL2 reading, non-fatal

## Known Issues

| Issue | Cause | Workaround |
|-------|-------|------------|
| GT:0 after restart | Semantic labels lost on scene reload | Re-run `ISAACSIM_apply_labels.py` |
| YOLO detects 0 at high altitude | YOLOv8n trained on ground-level COCO | Lower altitude or train custom model |
| libpng errors in WSL2 | File read/write contention | Non-fatal, script handles retries |
| WSL2 watcher hangs | mtime not propagating on /mnt/c/ | Script uses continuous polling with sleep |
| Drone mesh in CV frame | Z offset too small | Increase `DRONE_MESH_Z_OFFSET` |
| YOLO on CPU only in Isaac Sim | PyTorch can't access GPU (device_count=0) | Use WSL2 GPU inference instead |
