"""
Terminal Dive Guidance — 2DOF Pitch + Descent

Camera is FIXED to drone body (no gimbal). The entire drone pitches and
descends toward the target. Simulates a terminal approach/dive.

Phases:
  CRUISE  — Straight line at 100m altitude, shallow pitch
  DIVE    — Within 150m: pitch increases, altitude drops, drone dives at target
  TERMINAL — Near ground: script stops, "IMPACT" state

Run in Isaac Sim Script Editor (after applying semantic labels), then hit Play.
To stop: paste RUNNING = False in Script Editor and run it.

Pair with:
  WSL2:    python3 WSL2_yolo_gpu_inference.py
  Windows: python WIN_live_viewer.py
"""
import omni.replicator.core as rep
import omni.usd
import omni.kit.app
import asyncio
import numpy as np
import os
import time
import json
from pxr import UsdGeom, Gf, Sdf, Usd

OUTPUT_DIR = r"C:\Users\victo\Downloads\unreal_to_isaac_target_tracking_2\no_synterra_attempt\output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

stage = omni.usd.get_context().get_stage()

# ============================================================
# CONFIG
# ============================================================
RENDER_W = 640
RENDER_H = 480
DRONE_ALTITUDE = 10000.0      # cm = 100m starting altitude
START_OFFSET = 30000.0        # cm = 300m in front of target
DIVE_TRIGGER_DIST = 15000.0   # cm = 150m — dive begins here
SPEED_CM_PER_SEC = 1388.9     # 50kph
INITIAL_PITCH = 0.0           # degrees — level cruise, looking straight ahead
Kp_PITCH = 0.15               # degrees per pixel error
MIN_PITCH = 5.0               # minimum pitch
MAX_PITCH = 85.0              # near vertical for terminal phase
MIN_ALTITUDE = 200.0          # cm = 2m — impact threshold

RUNNING = True

# Phase constants
PHASE_CRUISE = 0
PHASE_DIVE = 1
PHASE_TERMINAL = 2

# ============================================================
# FIND TARGET
# ============================================================
target_pos = None
target_name = None

for prim in Usd.PrimRange(stage.GetPseudoRoot()):
    attr_name_list = [attr.GetName() for attr in prim.GetAttributes()]
    has_semantic = any(
        ("semantic" in a.lower() and "Semantics" in a) or
        ("semantics:labels" in a)
        for a in attr_name_list
    )
    if has_semantic:
        xf = UsdGeom.Xformable(prim)
        if xf:
            target_pos = xf.ComputeLocalToWorldTransform(0).ExtractTranslation()
            target_name = prim.GetName()
            print(f"Found target: {prim.GetPath()}")
        break

if target_pos is None:
    for prim in Usd.PrimRange(stage.GetPseudoRoot()):
        name = prim.GetName().lower()
        if "zil" in name or "truck" in name:
            xf = UsdGeom.Xformable(prim)
            if xf:
                target_pos = xf.ComputeLocalToWorldTransform(0).ExtractTranslation()
                target_name = prim.GetName()
                print(f"Found target via name: {prim.GetPath()}")
            break

if not target_pos:
    print("ERROR: No target found!")

# ============================================================
# CREATE DRONE CAMERA
# ============================================================
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

# Y-up convention: X=east, Y=up, Z=south
# target_pos[0]=X, target_pos[1]=Y(up), target_pos[2]=Z
drone_pos = np.array([
    target_pos[0] + flight_dir[0] * current_offset,
    target_pos[1] + DRONE_ALTITUDE,    # Y is up
    target_pos[2]
], dtype=np.float64)

# Drone mesh
drone_mesh_path = Sdf.Path("/DroneModel")
DRONE_MESH_SCALE = 0.1
DRONE_MESH_Z_OFFSET = 200.0


def set_drone_and_camera(pos, fly_dir, pitch_deg):
    """Set camera AND drone mesh with SAME pitch — camera fixed to body. Y-UP."""
    pitch_rad = np.radians(pitch_deg)
    # Horizontal forward direction (XZ plane, Y is up)
    fwd_h = np.array([fly_dir[0], 0.0, fly_dir[2]])
    l = np.linalg.norm(fwd_h)
    if l > 0: fwd_h /= l

    look_dist = 30000.0
    look_at = np.array([
        pos[0] + fwd_h[0] * look_dist * np.cos(pitch_rad),
        pos[1] - look_dist * np.sin(pitch_rad),              # Y is up, pitch down = -Y
        pos[2] + fwd_h[2] * look_dist * np.cos(pitch_rad),
    ])

    eye = Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2]))
    tgt = Gf.Vec3d(float(look_at[0]), float(look_at[1]), float(look_at[2]))
    fwd = (tgt - eye).GetNormalized()
    world_up = Gf.Vec3d(0, 1, 0)   # Y-up
    right = (fwd ^ world_up)
    if right.GetLength() < 0.001:
        world_up = Gf.Vec3d(0, 0, 1)
        right = (fwd ^ world_up)
    right = right.GetNormalized()
    up = (right ^ fwd).GetNormalized()

    mat = Gf.Matrix4d(
        right[0], right[1], right[2], 0,
        up[0], up[1], up[2], 0,
        -fwd[0], -fwd[1], -fwd[2], 0,
        pos[0], pos[1], pos[2], 1,
    )

    # Camera transform
    cam_prim = stage.GetPrimAtPath(cam_path)
    xform = UsdGeom.Xformable(cam_prim)
    xform.ClearXformOpOrder()
    xform.AddTransformOp().Set(mat)

    # Drone mesh — SAME rotation as camera (body pitches with camera)
    mesh_prim = stage.GetPrimAtPath(drone_mesh_path)
    if mesh_prim and mesh_prim.IsValid():
        # Use the pitched forward direction for the body too
        body_fwd = fwd
        body_right = right
        body_up = up

        # Apply STL orientation corrections (90° CC roll + 90° CC yaw + 90° CC pitch)
        step1_right = Gf.Vec3d(-body_fwd[0], -body_fwd[1], -body_fwd[2])
        step1_fwd = Gf.Vec3d(body_right[0], body_right[1], body_right[2])
        step1_up = body_up

        corrected_right = step1_right
        corrected_fwd = Gf.Vec3d(step1_up[0], step1_up[1], step1_up[2])
        corrected_up = Gf.Vec3d(-step1_fwd[0], -step1_fwd[1], -step1_fwd[2])

        # Offset mesh above camera along the local up direction
        offset_vec = np.array([up[0], up[1], up[2]]) * DRONE_MESH_Z_OFFSET

        body_mat = Gf.Matrix4d(
            corrected_right[0], corrected_right[1], corrected_right[2], 0,
            corrected_fwd[0], corrected_fwd[1], corrected_fwd[2], 0,
            corrected_up[0], corrected_up[1], corrected_up[2], 0,
            pos[0] + offset_vec[0], pos[1] + offset_vec[1], pos[2] + offset_vec[2], 1,
        )

        mesh_xform = UsdGeom.Xformable(mesh_prim)
        mesh_xform.ClearXformOpOrder()
        mesh_xform.AddTransformOp().Set(body_mat)
        mesh_xform.AddScaleOp().Set(Gf.Vec3f(DRONE_MESH_SCALE, DRONE_MESH_SCALE, DRONE_MESH_SCALE))


set_drone_and_camera(drone_pos, flight_dir, drone_pitch)
print(f"Target: {target_name} at ({target_pos[0]:.0f},{target_pos[1]:.0f},{target_pos[2]:.0f})")
print(f"Drone at ({drone_pos[0]:.0f},{drone_pos[1]:.0f},{drone_pos[2]:.0f})")
print(f"Altitude: {DRONE_ALTITUDE/100:.0f}m | Start offset: {START_OFFSET/100:.0f}m | Dive at: {DIVE_TRIGGER_DIST/100:.0f}m")


# ============================================================
# MAIN LOOP
# ============================================================
async def terminal_dive_loop():
    global drone_pos, current_offset, drone_pitch, phase, RUNNING

    rp = rep.create.render_product(str(cam_path), (RENDER_W, RENDER_H))
    for _ in range(60):
        await omni.kit.app.get_app().next_update_async()

    rgb_ann = rep.AnnotatorRegistry.get_annotator("rgb")
    bbox_ann = rep.AnnotatorRegistry.get_annotator("bounding_box_2d_tight")
    rgb_ann.attach([rp])
    bbox_ann.attach([rp])
    for _ in range(60):
        await omni.kit.app.get_app().next_update_async()

    await rep.orchestrator.step_async()
    for _ in range(30):
        await omni.kit.app.get_app().next_update_async()

    from PIL import Image

    frame = 0
    screen_cx, screen_cy = RENDER_W / 2, RENDER_H / 2
    last_time = time.time()
    gt_boxes = []
    error_y = 0
    tracking = False
    CAPTURE_INTERVAL = 1

    phase_names = {PHASE_CRUISE: "CRUISE", PHASE_DIVE: "DIVE", PHASE_TERMINAL: "IMPACT"}

    print("=" * 60)
    print(f"  TERMINAL DIVE — 50kph, 100m start, dive at 150m")
    print(f"  Target: {target_name}")
    print("  Camera FIXED to drone body — whole drone pitches")
    print("  To stop: RUNNING = False")
    print("=" * 60)

    mission_count = 0
    impact_time = None

    while RUNNING and frame < 20000:
        now = time.time()
        dt = min(now - last_time, 0.2)
        last_time = now

        # Check for mission reset after impact
        if phase == PHASE_TERMINAL:
            if impact_time is None:
                impact_time = now
            elif now - impact_time >= 1.0:
                # Reset mission
                mission_count += 1
                current_offset = -START_OFFSET
                drone_pitch = INITIAL_PITCH
                phase = PHASE_CRUISE
                impact_time = None
                drone_pos[1] = target_pos[1] + DRONE_ALTITUDE  # Y is up
                print(f"[Frame {frame}] === MISSION RESET #{mission_count} ===")
                set_drone_and_camera(drone_pos, flight_dir, drone_pitch)
                await omni.kit.app.get_app().next_update_async()
                continue

        # Horizontal movement (X axis, always)
        current_offset += SPEED_CM_PER_SEC * dt
        drone_pos[0] = target_pos[0] + flight_dir[0] * current_offset
        drone_pos[2] = target_pos[2]  # Z stays at target Z level

        # Distance to target (horizontal)
        dist_to_target = abs(current_offset)

        # Phase transitions (Y-up: altitude is drone_pos[1])
        if phase == PHASE_CRUISE:
            # Fixed altitude during cruise
            drone_pos[1] = target_pos[1] + DRONE_ALTITUDE

            if dist_to_target <= DIVE_TRIGGER_DIST:
                phase = PHASE_DIVE
                print(f"[Frame {frame}] === DIVE INITIATED === dist={dist_to_target/100:.0f}m alt={(drone_pos[1]-target_pos[1])/100:.0f}m")

        elif phase == PHASE_DIVE:
            # Descend based on pitch angle (Y is up)
            descent_rate = SPEED_CM_PER_SEC * np.sin(np.radians(drone_pitch))
            drone_pos[1] -= descent_rate * dt

            # Check for impact
            alt_above_target = drone_pos[1] - target_pos[1]
            if alt_above_target <= MIN_ALTITUDE:
                phase = PHASE_TERMINAL
                print(f"[Frame {frame}] === IMPACT === alt={alt_above_target/100:.1f}m pitch={drone_pitch:.1f}")

        # Apply transform
        set_drone_and_camera(drone_pos, flight_dir, drone_pitch)
        await omni.kit.app.get_app().next_update_async()

        if frame % CAPTURE_INTERVAL == 0:
            await rep.orchestrator.step_async()
            for _ in range(2):
                await omni.kit.app.get_app().next_update_async()

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

                # Pitch controller (only during DIVE)
                if phase == PHASE_DIVE and gt_boxes:
                    tracking = True
                    best_gt = max(gt_boxes, key=lambda b: (b['x_max']-b['x_min']) * (b['y_max']-b['y_min']))
                    det_cy = (best_gt['y_min'] + best_gt['y_max']) / 2
                    error_y = det_cy - screen_cy
                    pitch_correction = Kp_PITCH * error_y
                    drone_pitch += pitch_correction
                    drone_pitch = np.clip(drone_pitch, MIN_PITCH, MAX_PITCH)
                elif phase == PHASE_CRUISE:
                    tracking = len(gt_boxes) > 0
                    error_y = 0
                else:
                    tracking = False
                    error_y = 0

                # JSON sidecar
                alt_above_target = drone_pos[1] - target_pos[1]
                gt_json = {
                    'boxes': gt_boxes,
                    'meta': {
                        'phase': phase_names.get(phase, '?'),
                        'pitch': float(drone_pitch),
                        'error_y': float(error_y),
                        'state': 'TRK' if tracking else 'SCH',
                        'altitude_m': float(alt_above_target / 100),
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
                except Exception as e:
                    print(f"JSON error: {e}")

        if frame % 50 == 0:
            alt_m = (drone_pos[1] - target_pos[1]) / 100
            print(f"[Frame {frame}] {phase_names[phase]} pitch={drone_pitch:.1f} alt={alt_m:.0f}m dist={dist_to_target/100:.0f}m GT:{len(gt_boxes)}")

        frame += 1

    try:
        rep.orchestrator.stop()
    except:
        pass
    print(f"\nDone. {frame} frames, {mission_count} missions. Final pitch: {drone_pitch:.1f}")

asyncio.ensure_future(terminal_dive_loop())
