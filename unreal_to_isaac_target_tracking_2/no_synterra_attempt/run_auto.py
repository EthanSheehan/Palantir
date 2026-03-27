"""
Fully Automated Pipeline — launches Isaac Sim GUI from Python and runs everything.

Usage:
  C:\\isaac-sim\\python.bat run_auto.py

This script:
  1. Launches Isaac Sim with GUI
  2. Converts terrain OBJ → USD
  3. Opens the scene
  4. Places truck at POI with semantic labels
  5. Starts playback
  6. Runs terminal dive with GT annotations
  7. Writes frames for WSL2 GPU YOLO watcher

Run WSL2 watcher separately:
  cd to the script directory (auto-detected at runtime)
  python3 WSL2_yolo_gpu_inference.py

Run live viewer separately:
  python WIN_live_viewer.py
"""
import os
import sys
import json
import time
import argparse

# ============================================================
# CLI ARGUMENTS
# ============================================================
parser = argparse.ArgumentParser(description="Automated terrain → Isaac Sim terminal dive pipeline")
BASE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(BASE)
parser.add_argument("--dem", default=os.path.join(_PROJECT_DIR, "GIS", "rasters_COP30", "output_hh.tif"), help="Path to DEM GeoTIFF")
parser.add_argument("--sat", default=os.path.join(_PROJECT_DIR, "GIS", "iasi_esri_clipped.tif"), help="Path to satellite GeoTIFF")
parser.add_argument("--lat", type=float, default=47.21724592886579, help="POI latitude")
parser.add_argument("--lon", type=float, default=27.614609502715126, help="POI longitude")
parser.add_argument("--max-vertices", type=int, default=15000, help="Max terrain vertices")
args = parser.parse_args()
OUTPUT_DIR = os.path.join(BASE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# CLEANUP: Kill old WSL watchers and viewer windows
# ============================================================
import subprocess as _sp
print("Cleaning up old processes...", flush=True)
_sp.run(["wsl.exe", "-d", "Ubuntu-22.04", "--", "pkill", "-f", "WSL2_yolo_gpu_inference"], capture_output=True)
_sp.run(["wsl.exe", "-d", "Ubuntu-22.04", "--", "pkill", "-f", "yolo_gpu"], capture_output=True)
# Kill old viewer windows (python.exe running WIN_live_viewer.py)
_sp.run(["wsl.exe", "-d", "Ubuntu-22.04", "--", "pkill", "-f", "WIN_live_viewer"], capture_output=True)
try:
    result = _sp.run(["wmic", "process", "where", "commandline like '%WIN_live_viewer%'", "get", "processid"], capture_output=True, text=True)
    for line in result.stdout.strip().split('\n')[1:]:
        pid = line.strip()
        if pid.isdigit():
            _sp.run(["taskkill", "/F", "/PID", pid], capture_output=True)
except:
    pass
print("Cleanup done.", flush=True)

# ============================================================
# STEP -1: Build terrain mesh from DEM + satellite
# ============================================================
print("=" * 60, flush=True)
print("  BUILDING TERRAIN MESH...", flush=True)
print("=" * 60, flush=True)

build_script = os.path.join(BASE, "build_terrain_mesh.py")
build_cmd = [
    sys.executable, build_script,
    "--dem", args.dem,
    "--sat", args.sat,
    "--lat", str(args.lat),
    "--lon", str(args.lon),
    "--max-vertices", str(args.max_vertices),
    "--output", BASE,
]
print(f"Running: {' '.join(build_cmd)}", flush=True)
build_result = _sp.run(build_cmd, capture_output=True, text=True, timeout=300)
print(build_result.stdout, flush=True)
if build_result.returncode != 0:
    print(f"ERROR building terrain: {build_result.stderr}", flush=True)
    sys.exit(1)

# Verify outputs
for f in ["terrain_mesh.obj", "terrain_texture.png", "metadata.json"]:
    if not os.path.exists(os.path.join(BASE, f)):
        print(f"ERROR: Missing {f}", flush=True)
        sys.exit(1)
print("Terrain mesh ready!", flush=True)

# ============================================================
# STEP 0: Launch WSL2 GPU YOLO watcher + Windows live viewer
# ============================================================
import subprocess

wsl_script = os.path.join(BASE, "WSL2_yolo_gpu_inference.py").replace("C:\\", "/mnt/c/").replace("\\", "/")
print(f"Starting WSL2 GPU YOLO: {wsl_script}", flush=True)
wsl_proc = subprocess.Popen(
    ["wsl.exe", "-d", "Ubuntu-22.04", "--", "bash", "-c",
     f"source /opt/ros/humble/setup.bash && cd {BASE.replace(chr(92), '/').replace('C:/', '/mnt/c/')} && python3 WSL2_yolo_gpu_inference.py"],
)

print("Starting Windows live viewer...", flush=True)
viewer_proc = subprocess.Popen(
    [sys.executable, os.path.join(BASE, "WIN_live_viewer.py")],
    cwd=BASE,
)

# ============================================================
# STEP 1: Launch Isaac Sim
# ============================================================
print("=" * 60, flush=True)
print("  LAUNCHING ISAAC SIM...", flush=True)
print("=" * 60, flush=True)

from isaacsim import SimulationApp
config = {
    "headless": False,
    "width": 1280,
    "height": 720,
    "window_width": 1920,
    "window_height": 1080,
}
simulation_app = SimulationApp(config)

print("Isaac Sim launched!")

# Now import omniverse modules (must be after SimulationApp)
import omni.kit.asset_converter
import omni.kit.app
import omni.usd
import omni.timeline
import omni.replicator.core as rep
import numpy as np
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

# Load metadata
with open(os.path.join(BASE, "metadata.json"), 'r') as f:
    meta = json.load(f)

obj_path = os.path.join(BASE, "terrain_mesh.obj")
usd_path = os.path.join(BASE, "terrain_auto.usd")

# ============================================================
# STEP 2: Convert OBJ to USD (synchronous — just wait for file)
# ============================================================
print("\n[1/6] Converting OBJ to USD...", flush=True)

if os.path.exists(usd_path):
    os.remove(usd_path)

import carb
import asyncio

async def _convert():
    converter = omni.kit.asset_converter.get_instance()
    ctx = omni.kit.asset_converter.AssetConverterContext()
    ctx.ignore_materials = False
    ctx.ignore_textures = False
    task = converter.create_converter_task(obj_path, usd_path, None, ctx)
    success = await task.wait_until_finished()
    return success

# Use omni's async scheduling instead of raw asyncio
import omni.kit.app
_convert_done = [False]
_convert_ok = [False]

async def _do_convert():
    _convert_ok[0] = await _convert()
    _convert_done[0] = True

asyncio.ensure_future(_do_convert())

# Pump the app until conversion finishes
while not _convert_done[0]:
    simulation_app.update()

if not _convert_ok[0]:
    print("ERROR: OBJ conversion failed!", flush=True)
    simulation_app.close()
    sys.exit(1)
print(f"Converted to: {usd_path}", flush=True)

# ============================================================
# STEP 3: Open scene
# ============================================================
print("\n[2/6] Opening scene...", flush=True)
omni.usd.get_context().open_stage(usd_path)
for _ in range(120):
    simulation_app.update()

stage = omni.usd.get_context().get_stage()
print("Stage opened.", flush=True)

# ============================================================
# STEP 4: Place truck at POI
# ============================================================
print("\n[3/6] Placing truck at POI...", flush=True)
truck_path = Sdf.Path("/TruckTarget")
truck = UsdGeom.Cube.Define(stage, truck_path)
truck.GetSizeAttr().Set(500.0)
xform = UsdGeom.Xformable(truck.GetPrim())
xform.AddTranslateOp().Set(Gf.Vec3d(
    meta['poi_local_x_cm'],
    meta['poi_local_y_cm'] + 250,
    meta['poi_local_z_cm']
))

from pxr import Semantics
sem = Semantics.SemanticsAPI.Apply(truck.GetPrim(), "Semantics")
sem.CreateSemanticTypeAttr().Set("class")
sem.CreateSemanticDataAttr().Set("truck")
print(f"Truck at ({meta['poi_local_x_cm']:.0f}, {meta['poi_local_y_cm']:.0f}, {meta['poi_local_z_cm']:.0f})", flush=True)

for _ in range(30):
    simulation_app.update()

# ============================================================
# STEP 5: Start playback
# ============================================================
print("\n[4/6] Starting playback...", flush=True)
timeline = omni.timeline.get_timeline_interface()
timeline.play()
for _ in range(60):
    simulation_app.update()
print("Playback started!", flush=True)

# ============================================================
# STEP 6: Setup render product + annotators
# ============================================================
print("\n[5/6] Setting up camera and annotators...", flush=True)

target_pos = None
for prim in Usd.PrimRange(stage.GetPseudoRoot()):
    if "Truck" in prim.GetName():
        xf_api = UsdGeom.Xformable(prim)
        target_pos = xf_api.ComputeLocalToWorldTransform(0).ExtractTranslation()
        print(f"Target: {prim.GetPath()} at ({target_pos[0]:.0f},{target_pos[1]:.0f},{target_pos[2]:.0f})", flush=True)
        break

if not target_pos:
    print("ERROR: No target!", flush=True)
    simulation_app.close()
    sys.exit(1)

RENDER_W, RENDER_H = 640, 480
DRONE_ALTITUDE = 10000.0
START_OFFSET = 30000.0
DIVE_TRIGGER_DIST = 15000.0
SPEED_CM_PER_SEC = 1388.9
INITIAL_PITCH = 0.0
Kp_PITCH = 0.15
MIN_PITCH, MAX_PITCH = 5.0, 85.0
MIN_ALTITUDE = 200.0
PHASE_CRUISE, PHASE_DIVE, PHASE_TERMINAL = 0, 1, 2

cam_path = Sdf.Path("/TerminalDrone")
if stage.GetPrimAtPath(cam_path):
    stage.RemovePrim(cam_path)
cam = UsdGeom.Camera.Define(stage, cam_path)
cam.GetFocalLengthAttr().Set(18.0)
cam.GetHorizontalApertureAttr().Set(36.0)
cam.GetClippingRangeAttr().Set(Gf.Vec2f(1.0, 50000000.0))

flight_dir = np.array([1.0, 0.0, 0.0])
current_offset = -START_OFFSET
drone_pitch = INITIAL_PITCH
phase = PHASE_CRUISE
drone_pos = np.array([
    target_pos[0] + flight_dir[0] * current_offset,
    target_pos[1] + DRONE_ALTITUDE,
    target_pos[2]
], dtype=np.float64)


def set_cam(pos, fly_dir, pitch_deg):
    """Gimbal-lock-safe camera transform. Builds rotation from heading + pitch directly."""
    pitch_rad = np.radians(pitch_deg)

    # Horizontal forward (XZ plane)
    fwd_h = np.array([fly_dir[0], 0.0, fly_dir[2]])
    l = np.linalg.norm(fwd_h)
    if l > 0: fwd_h /= l

    # Heading angle from +X axis in XZ plane
    heading = np.arctan2(fwd_h[2], fwd_h[0])

    # Build rotation: first yaw (heading), then pitch
    # Right vector is always horizontal (perpendicular to heading in XZ)
    right = np.array([-np.sin(heading), 0.0, np.cos(heading)])

    # Forward vector: heading direction pitched down
    cos_p = np.cos(pitch_rad)
    sin_p = np.sin(pitch_rad)
    fwd = np.array([
        fwd_h[0] * cos_p,
        -sin_p,
        fwd_h[2] * cos_p,
    ])

    # Up = right x fwd (guaranteed orthogonal, no gimbal lock)
    up = np.cross(right, fwd)
    up_len = np.linalg.norm(up)
    if up_len > 0:
        up /= up_len

    mat = Gf.Matrix4d(
        right[0], right[1], right[2], 0,
        up[0], up[1], up[2], 0,
        -fwd[0], -fwd[1], -fwd[2], 0,
        pos[0], pos[1], pos[2], 1,
    )
    cp = stage.GetPrimAtPath(cam_path)
    xf = UsdGeom.Xformable(cp)
    xf.ClearXformOpOrder()
    xf.AddTransformOp().Set(mat)


set_cam(drone_pos, flight_dir, drone_pitch)

rp = rep.create.render_product(str(cam_path), (RENDER_W, RENDER_H))
for _ in range(60):
    simulation_app.update()

rgb_ann = rep.AnnotatorRegistry.get_annotator("rgb")
bbox_ann = rep.AnnotatorRegistry.get_annotator("bounding_box_2d_tight")
rgb_ann.attach([rp])
bbox_ann.attach([rp])
for _ in range(60):
    simulation_app.update()

# Step orchestrator via async + pump
_step_done = [False]
async def _step():
    await rep.orchestrator.step_async()
    _step_done[0] = True
asyncio.ensure_future(_step())
while not _step_done[0]:
    simulation_app.update()

for _ in range(30):
    simulation_app.update()

from PIL import Image

# ============================================================
# STEP 7: Terminal dive loop
# ============================================================
print("\n[6/6] Running terminal dive...", flush=True)
print("=" * 60, flush=True)
print("  TERMINAL DIVE — FULLY AUTOMATED", flush=True)
print("  Press Ctrl+C to stop", flush=True)
print("=" * 60, flush=True)

frame = 0
screen_cx, screen_cy = RENDER_W / 2, RENDER_H / 2
last_time = time.time()
gt_boxes = []
error_y = 0
tracking = False
mission_count = 0
impact_time = None
phase_names = {PHASE_CRUISE: "CRUISE", PHASE_DIVE: "DIVE", PHASE_TERMINAL: "IMPACT"}

try:
    while simulation_app.is_running() and frame < 20000:
        now = time.time()
        dt = min(now - last_time, 0.2)
        last_time = now

        if phase == PHASE_TERMINAL:
            if impact_time is None:
                impact_time = now
            elif now - impact_time >= 1.0:
                mission_count += 1
                current_offset = -START_OFFSET
                drone_pitch = INITIAL_PITCH
                phase = PHASE_CRUISE
                impact_time = None
                drone_pos[1] = target_pos[1] + DRONE_ALTITUDE
                print(f"[Frame {frame}] Mission reset #{mission_count}", flush=True)
                set_cam(drone_pos, flight_dir, drone_pitch)
                simulation_app.update()
                continue

        current_offset += SPEED_CM_PER_SEC * dt
        drone_pos[0] = target_pos[0] + flight_dir[0] * current_offset
        drone_pos[2] = target_pos[2]
        dist_to_target = abs(current_offset)

        if phase == PHASE_CRUISE:
            drone_pos[1] = target_pos[1] + DRONE_ALTITUDE
            if dist_to_target <= DIVE_TRIGGER_DIST:
                phase = PHASE_DIVE
                print(f"[Frame {frame}] DIVE at dist={dist_to_target/100:.0f}m", flush=True)
        elif phase == PHASE_DIVE:
            descent_rate = SPEED_CM_PER_SEC * np.sin(np.radians(drone_pitch))
            drone_pos[1] -= descent_rate * dt
            alt = drone_pos[1] - target_pos[1]
            if alt <= MIN_ALTITUDE:
                phase = PHASE_TERMINAL
                print(f"[Frame {frame}] IMPACT alt={alt/100:.1f}m pitch={drone_pitch:.1f}", flush=True)

        set_cam(drone_pos, flight_dir, drone_pitch)
        simulation_app.update()

        # Step replicator via async pump
        _step_done[0] = False
        asyncio.ensure_future(_step())
        ct = 0
        while not _step_done[0] and ct < 20:
            simulation_app.update()
            ct += 1
        simulation_app.update()

        rgb_data = rgb_ann.get_data()
        bbox_data = bbox_ann.get_data()

        if rgb_data is not None:
            img = Image.fromarray(rgb_data[:, :, :3])
            img.save(os.path.join(OUTPUT_DIR, "_tmp.png"))

            gt_boxes = []
            if bbox_data is not None and 'data' in bbox_data:
                labels_map = bbox_data.get('info', {}).get('idToLabels', {})
                for box in bbox_data['data']:
                    gt_boxes.append({
                        'x_min': int(box['x_min']), 'y_min': int(box['y_min']),
                        'x_max': int(box['x_max']), 'y_max': int(box['y_max']),
                        'label': labels_map.get(str(box['semanticId']), {}).get('class', '?'),
                        'occ': float(box['occlusionRatio']),
                    })

            if phase == PHASE_DIVE and gt_boxes:
                tracking = True
                best_gt = max(gt_boxes, key=lambda b: (b['x_max']-b['x_min']) * (b['y_max']-b['y_min']))
                det_cy = (best_gt['y_min'] + best_gt['y_max']) / 2
                error_y = det_cy - screen_cy
                drone_pitch += Kp_PITCH * error_y
                drone_pitch = np.clip(drone_pitch, MIN_PITCH, MAX_PITCH)
            else:
                tracking = len(gt_boxes) > 0
                error_y = 0

            alt_above = drone_pos[1] - target_pos[1]
            gt_json = {
                'boxes': gt_boxes,
                'meta': {
                    'phase': phase_names.get(phase, '?'),
                    'pitch': float(drone_pitch),
                    'error_y': float(error_y),
                    'state': 'TRK' if tracking else 'SCH',
                    'altitude_m': float(alt_above / 100),
                    'dist_to_target_m': float(dist_to_target / 100),
                    'offset_m': float(current_offset / 100),
                    'direction': 'FWD',
                    'pass_num': mission_count,
                    'start_offset': float(START_OFFSET),
                    'overshoot': 0,
                }
            }
            try:
                with open(os.path.join(OUTPUT_DIR, "gt_data.json"), 'w') as jf:
                    json.dump(gt_json, jf)
            except:
                pass

        if frame % 50 == 0:
            alt_m = (drone_pos[1] - target_pos[1]) / 100
            print(f"[Frame {frame}] {phase_names[phase]} pitch={drone_pitch:.1f} alt={alt_m:.0f}m GT:{len(gt_boxes)} mission#{mission_count}", flush=True)

        frame += 1

except KeyboardInterrupt:
    print("\nStopping...", flush=True)

print(f"\nDone. {frame} frames, {mission_count} missions.", flush=True)

# Cleanup subprocesses
try:
    wsl_proc.terminate()
    viewer_proc.terminate()
except:
    pass

simulation_app.close()
