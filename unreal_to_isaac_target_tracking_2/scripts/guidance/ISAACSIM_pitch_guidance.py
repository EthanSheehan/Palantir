"""
Camera Pitch Guidance — Detection-driven gimbal tracking (single DOF)

Same straight-line flyover as ros2_gpu_fix, but camera pitch adjusts
to keep the detected target centered vertically in frame.

Drone path: straight line, fixed altitude, fixed heading (unchanged)
Camera pitch: VARIABLE — proportional controller centers detection

GREEN = Ground Truth | Crosshair = screen center | Yellow line = error vector

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

OUTPUT_DIR = r"C:\Users\victo\Downloads\unreal_to_isaac_target_tracking_2\output_guidance"
os.makedirs(OUTPUT_DIR, exist_ok=True)

stage = omni.usd.get_context().get_stage()

# ============================================================
# CONFIG
# ============================================================
RENDER_W = 640
RENDER_H = 480
DRONE_ALTITUDE = 3000.0       # cm = 30m
START_OFFSET = 10000.0        # cm = 100m in front
OVERSHOOT = 10000.0           # cm = 100m past target
SPEED_CM_PER_SEC = 1388.9     # 50kph

# Pitch guidance
INITIAL_PITCH = 45.0          # degrees down — starting angle
Kp_PITCH = 0.15               # degrees per pixel error
MIN_PITCH = 10.0              # minimum downward pitch
MAX_PITCH = 80.0              # maximum downward pitch

RUNNING = True

# ============================================================
# FIND TARGET
# ============================================================
target_pos = None
target_name = None

# Check for semantic labels (both API-applied and GUI-applied formats)
for prim in Usd.PrimRange(stage.GetPseudoRoot()):
    attr_name_list = [attr.GetName() for attr in prim.GetAttributes()]
    has_semantic = any(
        ("semantic" in a.lower() and "Semantics" in a) or  # API format
        ("semantics:labels" in a)                            # GUI format
        for a in attr_name_list
    )
    if has_semantic:
        xf = UsdGeom.Xformable(prim)
        if xf:
            target_pos = xf.ComputeLocalToWorldTransform(0).ExtractTranslation()
            target_name = prim.GetName()
            print(f"Found target via semantic label: {prim.GetPath()}")
        break

# Fallback: search by prim name
if target_pos is None:
    for prim in Usd.PrimRange(stage.GetPseudoRoot()):
        name = prim.GetName().lower()
        if "zil" in name or "truck" in name:
            xf = UsdGeom.Xformable(prim)
            if xf:
                target_pos = xf.ComputeLocalToWorldTransform(0).ExtractTranslation()
                target_name = prim.GetName()
                print(f"Found target via name fallback: {prim.GetPath()}")
            break

if not target_pos:
    print("ERROR: No target found! Label objects or ensure 'truck'/'zil' in prim name.")

# ============================================================
# CREATE DRONE CAMERA
# ============================================================
cam_path = Sdf.Path("/GuidanceDrone")
if stage.GetPrimAtPath(cam_path):
    stage.RemovePrim(cam_path)

cam = UsdGeom.Camera.Define(stage, cam_path)
cam.GetFocalLengthAttr().Set(18.0)
cam.GetHorizontalApertureAttr().Set(36.0)
cam.GetClippingRangeAttr().Set(Gf.Vec2f(1.0, 50000000.0))

flight_dir = np.array([1.0, 0.0, 0.0])
direction = 1
current_offset = -START_OFFSET
pass_count = 0
camera_pitch = INITIAL_PITCH  # This is now VARIABLE

drone_pos = np.array([
    target_pos[0] + flight_dir[0] * current_offset,
    target_pos[1],
    target_pos[2] + DRONE_ALTITUDE
], dtype=np.float64)


# Drone mesh prim path (imported STL)
drone_mesh_path = Sdf.Path("/DroneModel")
DRONE_MESH_SCALE = 0.1   # Scale down the STL model
DRONE_MESH_Z_OFFSET = 200.0   # cm above camera (positive = drone body above camera eye)

def set_drone_camera_pitched(pos, fly_dir, pitch_deg):
    """Set camera AND drone mesh position/orientation with variable pitch."""
    pitch_rad = np.radians(pitch_deg)
    fwd_h = np.array([fly_dir[0], fly_dir[1], 0.0])
    l = np.linalg.norm(fwd_h)
    if l > 0: fwd_h /= l

    look_dist = 30000.0
    look_at = np.array([
        pos[0] + fwd_h[0] * look_dist * np.cos(pitch_rad),
        pos[1] + fwd_h[1] * look_dist * np.cos(pitch_rad),
        pos[2] - look_dist * np.sin(pitch_rad),
    ])

    eye = Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2]))
    tgt = Gf.Vec3d(float(look_at[0]), float(look_at[1]), float(look_at[2]))
    fwd = (tgt - eye).GetNormalized()
    world_up = Gf.Vec3d(0, 0, 1)
    right = (fwd ^ world_up)
    if right.GetLength() < 0.001:
        world_up = Gf.Vec3d(0, 1, 0)
        right = (fwd ^ world_up)
    right = right.GetNormalized()
    up = (right ^ fwd).GetNormalized()
    mat = Gf.Matrix4d(
        right[0], right[1], right[2], 0,
        up[0], up[1], up[2], 0,
        -fwd[0], -fwd[1], -fwd[2], 0,
        pos[0], pos[1], pos[2], 1,
    )

    # Set camera transform
    cam_prim = stage.GetPrimAtPath(cam_path)
    xform = UsdGeom.Xformable(cam_prim)
    xform.ClearXformOpOrder()
    xform.AddTransformOp().Set(mat)

    # Move drone mesh to same position (drone body is level, only camera pitches)
    mesh_prim = stage.GetPrimAtPath(drone_mesh_path)
    if mesh_prim and mesh_prim.IsValid():
        # Drone body flies level (pitch=0), aligned with flight direction
        body_fwd = Gf.Vec3d(float(fwd_h[0]), float(fwd_h[1]), 0.0).GetNormalized()
        body_right = (body_fwd ^ Gf.Vec3d(0, 0, 1)).GetNormalized()
        body_up = Gf.Vec3d(0, 0, 1)

        # Apply corrections: 90° CC roll, 90° CC yaw, then 90° CC pitch (about right axis)
        step1_right = Gf.Vec3d(-body_fwd[0], -body_fwd[1], -body_fwd[2])
        step1_fwd = Gf.Vec3d(body_right[0], body_right[1], body_right[2])
        step1_up = body_up

        # Roll 90° CC about step1_right (horizontal, perpendicular to travel): fwd→up, up→-fwd
        corrected_right = step1_right
        corrected_fwd = Gf.Vec3d(step1_up[0], step1_up[1], step1_up[2])
        corrected_up = Gf.Vec3d(-step1_fwd[0], -step1_fwd[1], -step1_fwd[2])

        body_mat = Gf.Matrix4d(
            corrected_right[0], corrected_right[1], corrected_right[2], 0,
            corrected_fwd[0], corrected_fwd[1], corrected_fwd[2], 0,
            corrected_up[0], corrected_up[1], corrected_up[2], 0,
            pos[0], pos[1], pos[2] + DRONE_MESH_Z_OFFSET, 1,
        )

        mesh_xform = UsdGeom.Xformable(mesh_prim)
        mesh_xform.ClearXformOpOrder()
        mesh_xform.AddTransformOp().Set(body_mat)
        mesh_xform.AddScaleOp().Set(Gf.Vec3f(DRONE_MESH_SCALE, DRONE_MESH_SCALE, DRONE_MESH_SCALE))


set_drone_camera_pitched(drone_pos, flight_dir * direction, camera_pitch)
print(f"Target: {target_name} at ({target_pos[0]:.0f},{target_pos[1]:.0f},{target_pos[2]:.0f})")
print(f"Drone at ({drone_pos[0]:.0f},{drone_pos[1]:.0f},{drone_pos[2]:.0f})")
print(f"Initial pitch: {camera_pitch:.1f} deg")


# ============================================================
# MAIN LOOP
# ============================================================
async def guidance_loop():
    global drone_pos, current_offset, direction, pass_count, camera_pitch, RUNNING

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
    tracking = False
    error_y = 0
    CAPTURE_INTERVAL = 3

    print("=" * 60)
    print(f"  PITCH GUIDANCE — 50kph @ 30m | Kp={Kp_PITCH}")
    print(f"  Target: {target_name}")
    print("  Camera pitch adjusts to center detection vertically")
    print("  GREEN = GT | Yellow line = pitch error")
    print("  To stop: RUNNING = False")
    print("=" * 60)

    while RUNNING and frame < 20000:
        now = time.time()
        dt = min(now - last_time, 0.2)
        last_time = now

        # Move drone (same as flyover — straight line)
        current_offset += SPEED_CM_PER_SEC * dt * direction
        if direction == 1 and current_offset > OVERSHOOT:
            direction = -1
            pass_count += 1
            camera_pitch = INITIAL_PITCH  # Reset pitch on reverse
            print(f"[Frame {frame}] REVERSING (pass #{pass_count}) — pitch reset to {INITIAL_PITCH:.0f}")
        elif direction == -1 and current_offset < -START_OFFSET:
            direction = 1
            pass_count += 1
            camera_pitch = INITIAL_PITCH
            print(f"[Frame {frame}] REVERSING (pass #{pass_count}) — pitch reset to {INITIAL_PITCH:.0f}")

        drone_pos[0] = target_pos[0] + flight_dir[0] * current_offset
        drone_pos[1] = target_pos[1] + flight_dir[1] * current_offset
        drone_pos[2] = target_pos[2] + DRONE_ALTITUDE

        # Apply current pitch
        set_drone_camera_pitched(drone_pos, flight_dir * direction, camera_pitch)

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

                # Get GT bounding boxes
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

                # Write GT data as JSON sidecar for WSL2 watcher
                gt_json = {
                    'boxes': gt_boxes,
                    'meta': {
                        'pitch': float(camera_pitch),
                        'error_y': float(error_y),
                        'state': 'TRK' if tracking else 'SCH',
                        'offset_m': float(current_offset / 100),
                        'direction': 'FWD' if direction == 1 else 'REV',
                        'pass_num': pass_count,
                        'start_offset': float(START_OFFSET),
                        'overshoot': float(OVERSHOOT),
                    }
                }
                json_path = os.path.join(OUTPUT_DIR, "gt_data.json")
                try:
                    with open(json_path, 'w') as jf:
                        json.dump(gt_json, jf)
                except Exception as e:
                    print(f"JSON write error: {e}")

                # ========================================
                # PITCH GUIDANCE CONTROLLER
                # ========================================
                if gt_boxes:
                    tracking = True
                    # Use largest GT box (closest/most visible target)
                    best_gt = max(gt_boxes, key=lambda b: (b['x_max']-b['x_min']) * (b['y_max']-b['y_min']))
                    det_cy = (best_gt['y_min'] + best_gt['y_max']) / 2

                    # Vertical error: positive = target below center
                    error_y = det_cy - screen_cy

                    # Proportional pitch adjustment
                    pitch_correction = Kp_PITCH * error_y
                    camera_pitch += pitch_correction
                    camera_pitch = np.clip(camera_pitch, MIN_PITCH, MAX_PITCH)
                else:
                    tracking = False
                    error_y = 0
                    # Hold current pitch when no detection

                # All HUD drawing moved to WSL2 watcher (reads gt_data.json)

        if frame % 100 == 0:
            state = "TRK" if tracking else "SCH"
            print(f"[Frame {frame}] {state} pitch={camera_pitch:.1f} err_y={error_y:+.0f} offset={current_offset/100:+.0f}m GT:{len(gt_boxes)}")

        frame += 1

    try:
        rep.orchestrator.stop()
    except:
        pass
    print(f"\nDone. {frame} frames, {pass_count} passes.")

asyncio.ensure_future(guidance_loop())
