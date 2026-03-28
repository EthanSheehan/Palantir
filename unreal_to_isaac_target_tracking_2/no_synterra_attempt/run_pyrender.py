"""
Standalone Terminal Dive Pipeline — pyrender + trimesh (no Isaac Sim, no NVIDIA).

Drop-in replacement for run_auto.py. Same CLI, same output format.
Works on any machine with OpenGL (GPU) or OSMesa (CPU fallback).

Usage:
  python run_pyrender.py
  python run_pyrender.py --dem path/to/dem.tif --sat path/to/sat.tif --lat 47.2 --lon 27.6
  python run_pyrender.py --headless --no-build
  python run_pyrender.py --yolo              # enable native YOLO inference
  python run_pyrender.py --resolution 1280x720

Output is identical to run_auto.py: _tmp.png + gt_data.json in output/
so the existing WSL2 YOLO watcher and WIN_live_viewer.py work unchanged.
"""
import os
import sys
import json
import time
import argparse
import subprocess as _sp

import numpy as np
from PIL import Image

# ============================================================
# PATH SETUP
# ============================================================
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SCRIPT_DIR)

# ============================================================
# CLI ARGUMENTS
# ============================================================
parser = argparse.ArgumentParser(
    description="Terminal dive pipeline — pyrender + trimesh (no Isaac Sim)")
parser.add_argument("--dem",
    default=os.path.join(_PROJECT_DIR, "GIS", "rasters_COP30", "output_hh.tif"),
    help="Path to DEM GeoTIFF")
parser.add_argument("--sat",
    default=os.path.join(_PROJECT_DIR, "GIS", "iasi_esri_clipped.tif"),
    help="Path to satellite GeoTIFF")
parser.add_argument("--lat", type=float, default=47.21724592886579,
    help="POI latitude")
parser.add_argument("--lon", type=float, default=27.614609502715126,
    help="POI longitude")
parser.add_argument("--max-vertices", type=int, default=15000,
    help="Max terrain vertices")
parser.add_argument("--headless", action="store_true",
    help="Run without opening a viewer window")
parser.add_argument("--no-build", action="store_true",
    help="Skip terrain build (use existing files)")
parser.add_argument("--yolo", action="store_true",
    help="Enable native YOLO inference (replaces WSL2 watcher)")
parser.add_argument("--resolution", default="640x480",
    help="Render resolution WxH (default: 640x480)")
parser.add_argument("--cpu", action="store_true",
    help="Force CPU rendering (OSMesa)")
parser.add_argument("--max-frames", type=int, default=20000,
    help="Maximum frames to render")
args = parser.parse_args()

# Parse resolution
render_w, render_h = [int(x) for x in args.resolution.split("x")]

OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# STEP 1: Build terrain mesh
# ============================================================
obj_path = os.path.join(_SCRIPT_DIR, "terrain_mesh.obj")
tex_path = os.path.join(_SCRIPT_DIR, "terrain_texture.png")
meta_path = os.path.join(_SCRIPT_DIR, "metadata.json")

if not args.no_build or not all(os.path.exists(f) for f in [obj_path, tex_path, meta_path]):
    print("=" * 60)
    print("  BUILDING TERRAIN MESH...")
    print("=" * 60)
    build_script = os.path.join(_SCRIPT_DIR, "build_terrain_mesh.py")
    build_cmd = [
        sys.executable, build_script,
        "--dem", args.dem, "--sat", args.sat,
        "--lat", str(args.lat), "--lon", str(args.lon),
        "--max-vertices", str(args.max_vertices),
        "--output", _SCRIPT_DIR,
    ]
    result = _sp.run(build_cmd, capture_output=True, text=True, timeout=300)
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR building terrain: {result.stderr}")
        sys.exit(1)
else:
    print("Using existing terrain files (--no-build)")

# Load metadata
with open(meta_path, "r") as f:
    meta = json.load(f)

print(f"POI: ({meta['poi_lat']:.4f}, {meta['poi_lon']:.4f}) "
      f"elev={meta['poi_elevation_m']:.1f}m")

# ============================================================
# STEP 2: Initialize renderer, scene, camera
# ============================================================
from renderer import DroneCamera, SceneBuilder, OffscreenRenderer, GroundTruthAnnotator
from flight import FlightConfig, FlightController

print("\n[1/4] Loading terrain and building scene...")
scene_builder = SceneBuilder(obj_path, tex_path, meta)

# Place truck target at POI (same as run_auto.py)
truck_size = 500.0  # cm (5m cube)
truck_pos = np.array([
    meta["poi_local_x_cm"],
    meta["poi_local_y_cm"] + truck_size / 2,  # sit on ground
    meta["poi_local_z_cm"],
])
scene_builder.add_target("truck", "truck", truck_pos, size=truck_size)
print(f"  Truck at ({truck_pos[0]:.0f}, {truck_pos[1]:.0f}, {truck_pos[2]:.0f})")

print("[2/4] Creating camera...")
config = FlightConfig(
    render_width=render_w,
    render_height=render_h,
    max_frames=args.max_frames,
)
camera = DroneCamera(
    width=render_w, height=render_h,
    focal_length_mm=config.focal_length_mm,
    sensor_width_mm=config.sensor_width_mm,
    near=config.near_clip_cm,
    far=config.far_clip_cm,
)
print(f"  Resolution: {render_w}x{render_h}, HFOV: {camera.hfov_deg:.1f}deg")

print("[3/4] Initializing renderer...")
renderer = OffscreenRenderer(render_w, render_h, prefer_gpu=not args.cpu)

print("[4/4] Setting up flight controller...")
target_pos = np.array([
    meta["poi_local_x_cm"],
    meta["poi_local_y_cm"],
    meta["poi_local_z_cm"],
], dtype=np.float64)
controller = FlightController(config, target_pos)
annotator = GroundTruthAnnotator(camera, scene_builder)

# ============================================================
# STEP 3: Launch viewer / YOLO processes
# ============================================================
procs = []

if not args.headless:
    print("\nStarting live viewer...")
    viewer_proc = _sp.Popen(
        [sys.executable, os.path.join(_SCRIPT_DIR, "WIN_live_viewer.py")],
        cwd=_SCRIPT_DIR,
    )
    procs.append(viewer_proc)

if args.yolo:
    yolo_script = os.path.join(_SCRIPT_DIR, "yolo_inference.py")
    if os.path.exists(yolo_script):
        print("Starting native YOLO inference...")
        yolo_proc = _sp.Popen(
            [sys.executable, yolo_script],
            cwd=_SCRIPT_DIR,
        )
        procs.append(yolo_proc)
    else:
        print("WARNING: yolo_inference.py not found, skipping YOLO")

# ============================================================
# STEP 4: Terminal dive loop
# ============================================================
print("\n" + "=" * 60)
print(f"  TERMINAL DIVE — PYRENDER (no Isaac Sim)")
print(f"  Renderer: {renderer.backend}")
print(f"  Press Ctrl+C to stop")
print("=" * 60)

frame = 0
last_time = time.time()
gt_boxes = []
phase_names = {0: "CRUISE", 1: "DIVE", 2: "IMPACT"}

try:
    while frame < config.max_frames:
        now = time.time()
        dt = min(now - last_time, 0.2)
        last_time = now

        # Flight physics
        state = controller.step(dt, gt_boxes, config.render_height / 2.0)

        if state.should_reset:
            print(f"[Frame {frame}] Mission reset #{state.mission_count}")
            frame += 1
            continue

        # Update camera
        camera.set_pose(state.position, np.array([1.0, 0.0, 0.0]), state.pitch)

        # Render
        color, depth = renderer.render(scene_builder.scene, camera)

        # Ground truth annotation
        gt_boxes = annotator.get_annotations(depth)

        # Save frame
        img = Image.fromarray(color)
        img.save(os.path.join(OUTPUT_DIR, "_tmp.png"))

        # Save GT data (identical format to Isaac Sim version)
        gt_json = {
            "boxes": gt_boxes,
            "meta": state.metadata(target_pos[1], config.start_offset_cm),
        }
        try:
            with open(os.path.join(OUTPUT_DIR, "gt_data.json"), "w") as jf:
                json.dump(gt_json, jf)
        except Exception:
            pass

        # Status
        if frame % 30 == 0:
            alt_m = state.altitude_above_target_cm(target_pos[1]) / 100
            fps = 1.0 / max(dt, 0.001)
            phase_name = phase_names.get(state.phase.value, "?")
            print(f"[Frame {frame}] {phase_name} pitch={state.pitch:.1f} "
                  f"alt={alt_m:.0f}m GT:{len(gt_boxes)} fps={fps:.0f} "
                  f"mission#{state.mission_count}")

        frame += 1

except KeyboardInterrupt:
    print("\nStopping...")

print(f"\nDone. {frame} frames, {state.mission_count} missions.")

# Cleanup
renderer.close()
for p in procs:
    try:
        p.terminate()
    except Exception:
        pass
