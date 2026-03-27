# GPU YOLO via WSL2 — File-Based Bridge

Run YOLO on GPU (~21ms) via WSL2 while Isaac Sim renders on Windows. Isaac Sim's bundled PyTorch cannot access the RTX 5070 (Blackwell sm_120 not supported), but PyTorch nightly in WSL2 can.

## Architecture

```
Isaac Sim (Windows)                    WSL2 Ubuntu 22.04
┌─────────────────────┐               ┌──────────────────────┐
│ drone_flyover_gpu.py│               │ yolo_gpu_watcher.py  │
│                     │               │                      │
│ Renders scene       │  _tmp.png     │ Reads via /mnt/c/    │
│ GT bounding boxes   │──(file)──→    │ GPU YOLO (21ms)      │
│ Saves raw + GT frame│               │ Overlays GT + YOLO   │
│                     │  latest_      │ Saves combined frame │
│                     │←─gpu_yolo.png─│                      │
└─────────────────────┘               └──────────────────────┘
        │
        ▼
  live_viewer.py (Windows)
  Displays combined feed
```

## Prerequisites

### Windows
- NVIDIA Isaac Sim 5.1 at `C:\isaac-sim`
- **numpy fix**: `C:\isaac-sim\python.bat -m pip install numpy==1.26.4`
- Python with OpenCV: `pip install opencv-python`

### WSL2
```bash
# Install Ubuntu 22.04 in WSL2 if not already
wsl --install -d Ubuntu-22.04

# PyTorch nightly with sm_120 (Blackwell) support
pip3 install torch torchvision --pre --index-url https://download.pytorch.org/whl/nightly/cu128 --force-reinstall

# YOLO + OpenCV
pip3 install ultralytics opencv-python-headless

# Fix numpy for cv_bridge compatibility
pip3 install numpy==1.26.4

# Verify GPU
python3 -c "import torch; print(f'GPU: {torch.cuda.get_device_name(0)}, CUDA: {torch.cuda.is_available()}')"
# Expected: GPU: NVIDIA GeForce RTX 5070 Laptop GPU, CUDA: True
```

## Files

| File | Runs On | Purpose |
|------|---------|---------|
| `ISAACSIM_apply_labels.py` | Isaac Sim Script Editor | Labels scene objects for GT bounding boxes |
| `ISAACSIM_drone_flyover.py` | Isaac Sim Script Editor | Drone flyover, renders frames + GT boxes, saves to disk |
| `WSL2_yolo_gpu_inference.py` | WSL2 terminal | Reads frames via /mnt/c/, runs GPU YOLO, composites GT+YOLO, saves back |
| `WIN_live_viewer.py` | Windows terminal | Displays the combined GT+YOLO feed in an OpenCV window |

## How to Run

### 1. Launch Isaac Sim
```
C:\isaac-sim\isaac-sim.bat
```

### 2. Load Scene
File → Open → your terrain_scene.usd

### 3. Apply Semantic Labels
In Isaac Sim Script Editor (Window → Script Editor), paste and run `ISAACSIM_apply_labels.py`.

### 4. Hit Play
Press ▶️ in the toolbar.

### 5. Run Drone Flyover
Paste `ISAACSIM_drone_flyover.py` in Script Editor and run.

### 6. Launch GPU YOLO Watcher (WSL2)
```bash
cd /mnt/c/Users/victo/Downloads/unreal_to_isaac_target_tracking_2/scripts/ros2_gpu_fix
python3 WSL2_yolo_gpu_inference.py
```

### 7. Launch Live Viewer (Windows)
```bash
cd C:\Users\victo\Downloads\unreal_to_isaac_target_tracking_2\scripts\ros2_gpu_fix
python WIN_live_viewer.py
```

### 8. Stop
- Isaac Sim: paste `RUNNING = False` in Script Editor and run
- WSL2: Ctrl+C
- Live viewer: press Q

## Output

Combined feed shows:
- **GREEN boxes** = Ground Truth (Isaac Sim scene graph — perfect)
- **RED boxes** = GPU YOLO predictions (neural network inference)
- **HUD** = flyover state, offset from target, GPU inference time

Output files in `../../output/`:
- `_tmp.png` — raw frame (no annotations)
- `latest_annotated.png` — GT boxes only
- `latest_gpu_yolo.png` — combined GT + GPU YOLO

## Tuning

Edit `ISAACSIM_drone_flyover.py` CONFIG section:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DRONE_ALTITUDE` | 3000.0 | Altitude in cm (30m) |
| `START_OFFSET` | 10000.0 | Start distance in cm (100m) |
| `OVERSHOOT` | 10000.0 | How far past target (100m) |
| `SPEED_CM_PER_SEC` | 1388.9 | Flight speed (50kph) |
| `CAMERA_PITCH` | 45.0 | Camera angle down (degrees) |
| `CAPTURE_INTERVAL` | 3 | Render every N frames |

## Why Not ROS2 Direct?

We attempted ROS2 DDS (FastDDS) between Windows Isaac Sim and WSL2. Topic discovery works but image data arrives as all zeros — a known limitation with DDS shared memory not crossing the Windows/WSL2 boundary. The file-based approach via `/mnt/c/` adds ~10ms latency but is reliable.

## Why Not GPU Inside Isaac Sim?

Isaac Sim 5.1 bundles PyTorch 2.7.0+cu128 which lacks sm_120 (Blackwell) support:
- `torch.cuda.is_available()` → True
- `torch.cuda.device_count()` → 0

PyTorch nightly (2.12.0.dev+cu128) in WSL2 supports sm_120 and sees the RTX 5070.
