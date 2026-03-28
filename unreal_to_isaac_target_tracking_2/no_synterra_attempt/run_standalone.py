"""
Standalone Pipeline — runs the full terminal dive WITHOUT Isaac Sim.
Uses PyVista (VTK) for CPU-based 3D rendering. Works on Intel Iris / any GPU.

Usage:
  python run_standalone.py
  python run_standalone.py --dem path/to/dem.tif --sat path/to/sat.tif --lat 47.2 --lon 27.6

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
import pyvista as pv

# ============================================================
# PATH SETUP
# ============================================================
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SCRIPT_DIR)

# ============================================================
# CLI ARGUMENTS
# ============================================================
parser = argparse.ArgumentParser(description="Standalone terrain → terminal dive (no Isaac Sim)")
parser.add_argument("--dem", default=os.path.join(_PROJECT_DIR, "GIS", "rasters_COP30", "output_hh.tif"),
                    help="Path to DEM GeoTIFF")
parser.add_argument("--sat", default=os.path.join(_PROJECT_DIR, "GIS", "iasi_esri_clipped.tif"),
                    help="Path to satellite GeoTIFF")
parser.add_argument("--lat", type=float, default=47.21724592886579, help="POI latitude")
parser.add_argument("--lon", type=float, default=27.614609502715126, help="POI longitude")
parser.add_argument("--max-vertices", type=int, default=15000, help="Max terrain vertices")
parser.add_argument("--headless", action="store_true", help="Run without opening a viewer window")
parser.add_argument("--no-build", action="store_true", help="Skip terrain build (use existing files)")
args = parser.parse_args()

OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# STEP 1: Build terrain mesh (reuse existing build_terrain_mesh.py)
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
with open(meta_path, 'r') as f:
    meta = json.load(f)

print(f"POI: ({meta['poi_lat']:.4f}, {meta['poi_lon']:.4f}) elev={meta['poi_elevation_m']:.1f}m")

# ============================================================
# STEP 2: Load terrain mesh + texture into PyVista
# ============================================================
print("\n[1/4] Loading terrain mesh...")
terrain = pv.read(obj_path)
print(f"  Vertices: {terrain.n_points}, Faces: {terrain.n_cells}")

# Load and apply satellite texture
print("[2/4] Applying satellite texture...")
tex_image = pv.read_texture(tex_path)

# ============================================================
# STEP 3: Create truck target at POI
# ============================================================
print("[3/4] Placing truck target at POI...")
truck_size = 500.0  # cm (5m cube, same as Isaac Sim version)
truck_center = np.array([
    meta['poi_local_x_cm'],
    meta['poi_local_y_cm'] + truck_size / 2,  # sit on ground
    meta['poi_local_z_cm'],
])
truck_mesh = pv.Cube(center=truck_center, x_length=truck_size, y_length=truck_size, z_length=truck_size)
print(f"  Truck at ({truck_center[0]:.0f}, {truck_center[1]:.0f}, {truck_center[2]:.0f})")

# ============================================================
# STEP 4: Setup renderer
# ============================================================
print("[4/4] Setting up renderer...")

RENDER_W, RENDER_H = 640, 480
FOCAL_LENGTH = 18.0       # mm
SENSOR_WIDTH = 36.0       # mm (horizontal aperture)
HFOV_DEG = 2 * np.degrees(np.arctan(SENSOR_WIDTH / (2 * FOCAL_LENGTH)))  # ~90° for 18mm on 36mm

# Flight parameters (identical to run_auto.py)
DRONE_ALTITUDE = 10000.0      # cm = 100m
START_OFFSET = 30000.0        # cm = 300m
DIVE_TRIGGER_DIST = 15000.0   # cm = 150m
SPEED_CM_PER_SEC = 1388.9     # 50kph
INITIAL_PITCH = 0.0
Kp_PITCH = 0.15
MIN_PITCH, MAX_PITCH = 5.0, 85.0
MIN_ALTITUDE = 200.0          # cm = 2m
PHASE_CRUISE, PHASE_DIVE, PHASE_TERMINAL = 0, 1, 2

# Target position (Y-up: X=east, Y=up, Z=-north)
target_pos = np.array([
    meta['poi_local_x_cm'],
    meta['poi_local_y_cm'],
    meta['poi_local_z_cm'],
], dtype=np.float64)

# Initial drone state
flight_dir = np.array([1.0, 0.0, 0.0])
current_offset = -START_OFFSET
drone_pitch = INITIAL_PITCH
phase = PHASE_CRUISE
drone_pos = np.array([
    target_pos[0] + flight_dir[0] * current_offset,
    target_pos[1] + DRONE_ALTITUDE,
    target_pos[2],
], dtype=np.float64)


def compute_camera_vectors(pos, fly_dir, pitch_deg):
    """Compute camera position, focal point, and up vector for PyVista."""
    pitch_rad = np.radians(pitch_deg)

    # Horizontal forward (XZ plane)
    fwd_h = np.array([fly_dir[0], 0.0, fly_dir[2]])
    norm = np.linalg.norm(fwd_h)
    if norm > 0:
        fwd_h /= norm

    # Forward vector pitched down
    cos_p = np.cos(pitch_rad)
    sin_p = np.sin(pitch_rad)
    fwd = np.array([
        fwd_h[0] * cos_p,
        -sin_p,
        fwd_h[2] * cos_p,
    ])

    # Look-at point (far ahead along view direction)
    focal_point = pos + fwd * 50000.0

    # Up vector (perpendicular to right and forward)
    heading = np.arctan2(fwd_h[2], fwd_h[0])
    right = np.array([-np.sin(heading), 0.0, np.cos(heading)])
    up = np.cross(right, fwd)
    up_norm = np.linalg.norm(up)
    if up_norm > 0:
        up /= up_norm

    return pos.tolist(), focal_point.tolist(), up.tolist()


def project_bbox_to_screen(plotter, box_corners):
    """Project 3D bounding box corners to 2D screen coordinates."""
    renderer = plotter.renderer
    coord = pv.pyvista_ndarray(box_corners)

    screen_points = []
    for pt in coord:
        # Use VTK's world-to-display coordinate transform
        renderer.SetWorldPoint(pt[0], pt[1], pt[2], 1.0)
        renderer.WorldToDisplay()
        display = renderer.GetDisplayPoint()
        sx = display[0]
        sy = RENDER_H - display[1]  # flip Y (VTK origin is bottom-left)
        screen_points.append((sx, sy))

    screen_points = np.array(screen_points)
    x_min = max(0, int(np.min(screen_points[:, 0])))
    y_min = max(0, int(np.min(screen_points[:, 1])))
    x_max = min(RENDER_W, int(np.max(screen_points[:, 0])))
    y_max = min(RENDER_H, int(np.max(screen_points[:, 1])))

    if x_max <= x_min or y_max <= y_min:
        return None
    return {'x_min': x_min, 'y_min': y_min, 'x_max': x_max, 'y_max': y_max,
            'label': 'truck', 'occ': 0.0}


# 8 corners of the truck bounding box
truck_half = truck_size / 2
truck_corners = np.array([
    [truck_center[0] + dx, truck_center[1] + dy, truck_center[2] + dz]
    for dx in [-truck_half, truck_half]
    for dy in [-truck_half, truck_half]
    for dz in [-truck_half, truck_half]
])

# ============================================================
# STEP 5: Create offscreen plotter and run flight loop
# ============================================================
print("\n" + "=" * 60)
print("  TERMINAL DIVE — STANDALONE (no Isaac Sim)")
print("  Press Ctrl+C to stop")
print("=" * 60)

# Use offscreen rendering
pv.global_theme.background = 'black'
plotter = pv.Plotter(off_screen=True, window_size=[RENDER_W, RENDER_H])
plotter.add_mesh(terrain, texture=tex_image, lighting=True)
plotter.add_mesh(truck_mesh, color='olive', opacity=1.0)
plotter.add_light(pv.Light(position=(0, 100000, 0), light_type='scenelight'))

# Set initial camera
cam_pos, cam_focal, cam_up = compute_camera_vectors(drone_pos, flight_dir, drone_pitch)
plotter.camera.position = cam_pos
plotter.camera.focal_point = cam_focal
plotter.camera.up = cam_up
plotter.camera.view_angle = HFOV_DEG
plotter.camera.clipping_range = (100.0, 5000000.0)

# Launch the live viewer in background
print("Starting live viewer...")
viewer_proc = _sp.Popen(
    [sys.executable, os.path.join(_SCRIPT_DIR, "WIN_live_viewer.py")],
    cwd=_SCRIPT_DIR,
)

frame = 0
screen_cx, screen_cy = RENDER_W / 2, RENDER_H / 2
last_time = time.time()
gt_boxes = []
error_y = 0.0
tracking = False
mission_count = 0
impact_time = None
phase_names = {PHASE_CRUISE: "CRUISE", PHASE_DIVE: "DIVE", PHASE_TERMINAL: "IMPACT"}

try:
    while frame < 20000:
        now = time.time()
        dt = min(now - last_time, 0.2)
        last_time = now

        # --- IMPACT reset ---
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
                print(f"[Frame {frame}] Mission reset #{mission_count}")
                frame += 1
                continue

        # --- Flight physics ---
        current_offset += SPEED_CM_PER_SEC * dt
        drone_pos[0] = target_pos[0] + flight_dir[0] * current_offset
        drone_pos[2] = target_pos[2]
        dist_to_target = abs(current_offset)

        if phase == PHASE_CRUISE:
            drone_pos[1] = target_pos[1] + DRONE_ALTITUDE
            if dist_to_target <= DIVE_TRIGGER_DIST:
                phase = PHASE_DIVE
                print(f"[Frame {frame}] DIVE at dist={dist_to_target / 100:.0f}m")
        elif phase == PHASE_DIVE:
            descent_rate = SPEED_CM_PER_SEC * np.sin(np.radians(drone_pitch))
            drone_pos[1] -= descent_rate * dt
            alt = drone_pos[1] - target_pos[1]
            if alt <= MIN_ALTITUDE:
                phase = PHASE_TERMINAL
                print(f"[Frame {frame}] IMPACT alt={alt / 100:.1f}m pitch={drone_pitch:.1f}")

        # --- Update camera ---
        cam_pos, cam_focal, cam_up = compute_camera_vectors(drone_pos, flight_dir, drone_pitch)
        plotter.camera.position = cam_pos
        plotter.camera.focal_point = cam_focal
        plotter.camera.up = cam_up

        # --- Render frame ---
        plotter.render()
        img_array = plotter.screenshot(return_img=True)

        if img_array is not None:
            img = Image.fromarray(img_array)
            img.save(os.path.join(OUTPUT_DIR, "_tmp.png"))

            # --- Compute GT bounding box ---
            gt_boxes = []
            bbox = project_bbox_to_screen(plotter, truck_corners)
            if bbox is not None:
                gt_boxes.append(bbox)

            # --- Pitch guidance (same controller as run_auto.py) ---
            if phase == PHASE_DIVE and gt_boxes:
                tracking = True
                best_gt = max(gt_boxes, key=lambda b: (b['x_max'] - b['x_min']) * (b['y_max'] - b['y_min']))
                det_cy = (best_gt['y_min'] + best_gt['y_max']) / 2
                error_y = det_cy - screen_cy
                drone_pitch += Kp_PITCH * error_y
                drone_pitch = float(np.clip(drone_pitch, MIN_PITCH, MAX_PITCH))
            else:
                tracking = len(gt_boxes) > 0
                error_y = 0.0

            # --- Write gt_data.json (same format as Isaac Sim version) ---
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
            except Exception:
                pass

        # --- Status ---
        if frame % 30 == 0:
            alt_m = (drone_pos[1] - target_pos[1]) / 100
            fps = 1.0 / max(dt, 0.001)
            print(f"[Frame {frame}] {phase_names[phase]} pitch={drone_pitch:.1f} "
                  f"alt={alt_m:.0f}m GT:{len(gt_boxes)} fps={fps:.0f} mission#{mission_count}")

        frame += 1

except KeyboardInterrupt:
    print("\nStopping...")

print(f"\nDone. {frame} frames, {mission_count} missions.")

# Cleanup
try:
    viewer_proc.terminate()
except Exception:
    pass
plotter.close()
