"""
Drone Flyover — GT only, no CPU YOLO. GPU YOLO runs externally via yolo_gpu_watcher.py

Fast flyover: no CPU inference bottleneck. Saves raw frames for GPU watcher in WSL2.
GREEN boxes = Ground Truth only.
GPU YOLO results visible in separate live_viewer.py window.

Run in Isaac Sim Script Editor (after applying semantic labels), then hit Play.
To stop: paste RUNNING = False in Script Editor and run it.

Pair with:
  WSL2:    python3 yolo_gpu_watcher.py
  Windows: python live_viewer.py
"""
import omni.replicator.core as rep
import omni.usd
import omni.kit.app
import asyncio
import numpy as np
import os
import time
from pxr import UsdGeom, Gf, Sdf, Usd

OUTPUT_DIR = r"C:\Users\victo\Downloads\unreal_to_isaac_target_tracking_2\output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

stage = omni.usd.get_context().get_stage()

# ============================================================
# CONFIG
# ============================================================
RENDER_W = 640
RENDER_H = 480
DRONE_ALTITUDE = 3000.0      # cm = 30m
START_OFFSET = 50000.0       # cm = 500m in front
OVERSHOOT = 10000.0          # cm = 100m past target
SPEED_CM_PER_SEC = 1388.9    # 50kph
CAMERA_PITCH = 45.0
RUNNING = True

# ============================================================
# FIND TARGET
# ============================================================
target_pos = None
target_name = None
for prim in Usd.PrimRange(stage.GetPseudoRoot()):
    for attr in prim.GetAttributes():
        if "semantic" in attr.GetName().lower() and "Semantics" in attr.GetName():
            xf = UsdGeom.Xformable(prim)
            if xf:
                target_pos = xf.ComputeLocalToWorldTransform(0).ExtractTranslation()
                target_name = prim.GetName()
            break
    if target_pos:
        break

if not target_pos:
    print("ERROR: No labeled target found!")

# ============================================================
# CREATE DRONE CAMERA
# ============================================================
cam_path = Sdf.Path("/FlyoverDrone")
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
pitch_rad = np.radians(CAMERA_PITCH)

drone_pos = np.array([
    target_pos[0] + flight_dir[0] * current_offset,
    target_pos[1],
    target_pos[2] + DRONE_ALTITUDE
], dtype=np.float64)


def set_drone_camera(pos, fly_dir):
    fwd_h = np.array([fly_dir[0], fly_dir[1], 0.0])
    l = np.linalg.norm(fwd_h)
    if l > 0: fwd_h /= l
    look_at = np.array([
        pos[0] + fwd_h[0] * 30000 * np.cos(pitch_rad),
        pos[1] + fwd_h[1] * 30000 * np.cos(pitch_rad),
        pos[2] - 30000 * np.sin(pitch_rad),
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
    prim = stage.GetPrimAtPath(cam_path)
    xform = UsdGeom.Xformable(prim)
    xform.ClearXformOpOrder()
    xform.AddTransformOp().Set(mat)


set_drone_camera(drone_pos, flight_dir * direction)
print(f"Target: {target_name} at ({target_pos[0]:.0f},{target_pos[1]:.0f},{target_pos[2]:.0f})")


# ============================================================
# MAIN LOOP
# ============================================================
async def flyover_loop():
    global drone_pos, current_offset, direction, pass_count, RUNNING

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

    from PIL import Image, ImageDraw

    frame = 0
    screen_cx, screen_cy = RENDER_W / 2, RENDER_H / 2
    last_time = time.time()
    gt_boxes = []
    CAPTURE_INTERVAL = 3  # Capture every N frames for speed

    print("=" * 55)
    print(f"  DRONE FLYOVER — 50kph @ 30m (GPU YOLO via WSL2)")
    print(f"  Target: {target_name}")
    print("  GREEN = Ground Truth")
    print("  GPU YOLO: run yolo_gpu_watcher.py in WSL2")
    print("  To stop: RUNNING = False")
    print("=" * 55)

    while RUNNING and frame < 20000:
        now = time.time()
        dt = min(now - last_time, 0.2)
        last_time = now

        current_offset += SPEED_CM_PER_SEC * dt * direction
        if direction == 1 and current_offset > OVERSHOOT:
            direction = -1
            pass_count += 1
            print(f"[Frame {frame}] REVERSING (pass #{pass_count})")
        elif direction == -1 and current_offset < -START_OFFSET:
            direction = 1
            pass_count += 1
            print(f"[Frame {frame}] REVERSING (pass #{pass_count})")

        drone_pos[0] = target_pos[0] + flight_dir[0] * current_offset
        drone_pos[1] = target_pos[1] + flight_dir[1] * current_offset
        drone_pos[2] = target_pos[2] + DRONE_ALTITUDE
        set_drone_camera(drone_pos, flight_dir * direction)

        await omni.kit.app.get_app().next_update_async()

        if frame % CAPTURE_INTERVAL == 0:
            await rep.orchestrator.step_async()
            for _ in range(2):
                await omni.kit.app.get_app().next_update_async()

            rgb_data = rgb_ann.get_data()
            bbox_data = bbox_ann.get_data()

            if rgb_data is not None:
                img = Image.fromarray(rgb_data[:, :, :3])

                # Save raw frame for GPU watcher
                img.save(os.path.join(OUTPUT_DIR, "_tmp.png"))

                # Draw GT + HUD on separate annotated frame
                draw = ImageDraw.Draw(img)

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

                for gt in gt_boxes:
                    draw.rectangle([gt['x_min'], gt['y_min'], gt['x_max'], gt['y_max']], outline='lime', width=2)
                    draw.text((gt['x_min'], gt['y_min'] - 12), f"GT:{gt.get('label','?')}", fill='lime')

                draw.line([(screen_cx-20, screen_cy), (screen_cx+20, screen_cy)], fill='cyan', width=1)
                draw.line([(screen_cx, screen_cy-20), (screen_cx, screen_cy+20)], fill='cyan', width=1)

                dist_m = current_offset / 100
                dir_label = "FWD" if direction == 1 else "REV"

                draw.rectangle([0, 0, RENDER_W, 30], fill='black')
                draw.text((5, 3), f"FLYOVER | {dir_label} 50kph | {dist_m:+.0f}m | GT:{len(gt_boxes)} | Pass #{pass_count}", fill='white')

                total_range = START_OFFSET + OVERSHOOT
                progress = (current_offset + START_OFFSET) / total_range
                bar_y = RENDER_H - 8
                draw.rectangle([10, bar_y-3, RENDER_W-10, bar_y+3], fill='gray')
                tgt_mark = 10 + int((RENDER_W-20) * (START_OFFSET / total_range))
                draw.rectangle([tgt_mark-2, bar_y-6, tgt_mark+2, bar_y+6], fill='lime')
                d_mark = 10 + int((RENDER_W-20) * max(0, min(1, progress)))
                draw.rectangle([d_mark-3, bar_y-5, d_mark+3, bar_y+5], fill='cyan')

                img.save(os.path.join(OUTPUT_DIR, "latest_annotated.png"))

        if frame % 100 == 0:
            print(f"[Frame {frame}] offset={current_offset/100:+.0f}m GT:{len(gt_boxes)} pass#{pass_count}")

        frame += 1

    try:
        rep.orchestrator.stop()
    except:
        pass
    print(f"\nDone. {frame} frames, {pass_count} passes.")

asyncio.ensure_future(flyover_loop())
