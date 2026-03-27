"""
Drone Flyover Target Detection — Straight-line pass at 75m altitude, 70kph

The drone flies a straight-line surveillance pass over the target:
  1. Starts 500m in front of target at 75m altitude
  2. Camera fixed at 45° downward pitch, no heading changes
  3. Flies straight over and 100m past the target at 70kph
  4. Reverses direction and flies back
  5. Repeats back-and-forth

GREEN boxes = Ground Truth | RED boxes = YOLO predictions

Run in Isaac Sim Script Editor (after applying semantic labels), then hit Play.
To stop: paste RUNNING = False in Script Editor and run it.
Watch live: python live_viewer.py
"""
import omni.replicator.core as rep
import omni.usd
import omni.kit.app
import omni.kit.viewport.utility as vp_util
import asyncio
import numpy as np
import os
import time
from pxr import UsdGeom, Gf, Sdf, Usd

OUTPUT_DIR = r"C:\Users\victo\Downloads\New folder\unreal_to_isaac_target_tracking_2\output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

stage = omni.usd.get_context().get_stage()

# Load YOLO on CPU
from ultralytics import YOLO
print("Loading YOLO...")
model = YOLO("yolov8n.pt")
model.to("cpu")
print("YOLO ready!")

# ============================================================
# CONFIG
# ============================================================
RENDER_W = 640
RENDER_H = 480
DRONE_ALTITUDE = 7500.0      # cm = 75m
START_OFFSET = 50000.0       # cm = 500m in front
OVERSHOOT = 10000.0          # cm = 100m past target

# 70 kph = 70000 cm / 3600 s = 1944 cm/s
# At ~10 fps that's ~194 cm/frame
# But rendering is variable, so we use real time delta
SPEED_CM_PER_SEC = 194444.0 / 100.0  # 70kph in cm/s = 1944.4 cm/s

CAMERA_PITCH = 45.0          # degrees downward
RUNNING = True

# ============================================================
# AUTO-DETECT TARGET
# ============================================================
target_pos = None
target_name = None

print("Searching for labeled targets...")
for prim in Usd.PrimRange(stage.GetPseudoRoot()):
    for attr in prim.GetAttributes():
        if "semantic" in attr.GetName().lower() and "Semantics" in attr.GetName():
            xf = UsdGeom.Xformable(prim)
            if xf:
                world_xform = xf.ComputeLocalToWorldTransform(0)
                target_pos = world_xform.ExtractTranslation()
                target_name = prim.GetName()
                print(f"  Target: {prim.GetPath()}")
                print(f"  Position: ({target_pos[0]:.0f}, {target_pos[1]:.0f}, {target_pos[2]:.0f})")
            break
    if target_pos is not None:
        break

if target_pos is None:
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

# Flight along X-axis
flight_dir = np.array([1.0, 0.0, 0.0])
direction = 1  # 1=forward, -1=reverse
current_offset = -START_OFFSET
pass_count = 0

pitch_rad = np.radians(CAMERA_PITCH)
look_fwd_dist = 30000.0  # how far ahead camera looks


def set_drone_camera(pos, fly_dir):
    """Set camera at pos, pitched 45° down along fly_dir."""
    fwd_h = np.array([fly_dir[0], fly_dir[1], 0.0])
    fwd_h_len = np.linalg.norm(fwd_h)
    if fwd_h_len > 0:
        fwd_h /= fwd_h_len

    look_at = np.array([
        pos[0] + fwd_h[0] * look_fwd_dist * np.cos(pitch_rad),
        pos[1] + fwd_h[1] * look_fwd_dist * np.cos(pitch_rad),
        pos[2] - look_fwd_dist * np.sin(pitch_rad),
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


# Initial position
drone_pos = np.array([
    target_pos[0] + flight_dir[0] * current_offset,
    target_pos[1],
    target_pos[2] + DRONE_ALTITUDE,
], dtype=np.float64)

set_drone_camera(drone_pos, flight_dir * direction)
print(f"Drone at ({drone_pos[0]:.0f}, {drone_pos[1]:.0f}, {drone_pos[2]:.0f})")
print(f"Alt: {DRONE_ALTITUDE/100:.0f}m | Speed: 70kph | Pitch: {CAMERA_PITCH}°")
print(f"Start: -{START_OFFSET/100:.0f}m | Overshoot: +{OVERSHOOT/100:.0f}m")


# ============================================================
# MAIN LOOP
# ============================================================
async def flyover_loop():
    global drone_pos, current_offset, direction, pass_count, RUNNING

    print("Creating render product...")
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
    screen_cx = RENDER_W / 2
    screen_cy = RENDER_H / 2
    last_time = time.time()

    print("=" * 55)
    print("  DRONE FLYOVER — 70kph @ 75m")
    print(f"  Target: {target_name}")
    print("  GREEN = Ground Truth | RED = YOLO")
    print("  To stop: RUNNING = False")
    print("=" * 55)

    while RUNNING and frame < 10000:
        await rep.orchestrator.step_async()
        for _ in range(3):
            await omni.kit.app.get_app().next_update_async()

        rgb_data = rgb_ann.get_data()
        bbox_data = bbox_ann.get_data()
        if rgb_data is None:
            continue

        # Real-time delta for consistent speed
        now = time.time()
        dt = min(now - last_time, 0.5)  # cap at 0.5s
        last_time = now
        step = SPEED_CM_PER_SEC * dt

        # Move drone
        current_offset += step * direction

        # Reverse at boundaries
        if direction == 1 and current_offset > OVERSHOOT:
            direction = -1
            pass_count += 1
            print(f"[Frame {frame}] REVERSING at +{OVERSHOOT/100:.0f}m (pass #{pass_count})")
        elif direction == -1 and current_offset < -START_OFFSET:
            direction = 1
            pass_count += 1
            print(f"[Frame {frame}] REVERSING at -{START_OFFSET/100:.0f}m (pass #{pass_count})")

        drone_pos[0] = target_pos[0] + flight_dir[0] * current_offset
        drone_pos[1] = target_pos[1] + flight_dir[1] * current_offset
        drone_pos[2] = target_pos[2] + DRONE_ALTITUDE

        set_drone_camera(drone_pos, flight_dir * direction)

        # === YOLO ===
        img = Image.fromarray(rgb_data[:, :, :3])
        tmp = os.path.join(OUTPUT_DIR, "_tmp.png")
        img.save(tmp)

        t0 = time.time()
        yolo_results = model.predict(source=tmp, conf=0.15, imgsz=640, verbose=False, device="cpu")
        yolo_ms = (time.time() - t0) * 1000

        yolo_dets = []
        for r in yolo_results:
            for b in r.boxes:
                x1, y1, x2, y2 = b.xyxy[0].cpu().numpy()
                yolo_dets.append({
                    'x1': int(x1), 'y1': int(y1), 'x2': int(x2), 'y2': int(y2),
                    'cls': model.names[int(b.cls[0])], 'conf': float(b.conf[0]),
                })

        # === GT ===
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

        # === DRAW ===
        draw = ImageDraw.Draw(img)

        # GT (GREEN)
        for gt in gt_boxes:
            draw.rectangle([gt['x_min'], gt['y_min'], gt['x_max'], gt['y_max']], outline='lime', width=2)
            draw.text((gt['x_min'], gt['y_min'] - 12), f"GT:{gt.get('label','?')} occ:{gt['occ']:.0%}", fill='lime')

        # YOLO (RED)
        for det in yolo_dets:
            draw.rectangle([det['x1'], det['y1'], det['x2'], det['y2']], outline='red', width=2)
            draw.text((det['x1'], det['y2'] + 2), f"YOLO:{det['cls']} {det['conf']:.0%}", fill='red')

        # Crosshair
        draw.line([(screen_cx - 20, screen_cy), (screen_cx + 20, screen_cy)], fill='cyan', width=1)
        draw.line([(screen_cx, screen_cy - 20), (screen_cx, screen_cy + 20)], fill='cyan', width=1)

        # Direction arrow
        dir_label = "→ FWD 70kph" if direction == 1 else "← REV 70kph"
        dist_m = current_offset / 100

        # Top bar
        draw.rectangle([0, 0, RENDER_W, 55], fill='black')
        draw.text((5, 3), f"FLYOVER | Frame:{frame} | YOLO:{yolo_ms:.0f}ms | Pass #{pass_count}", fill='white')
        draw.text((5, 16), f"{dir_label} | Offset: {dist_m:+.0f}m from target", fill='yellow')
        draw.text((5, 29), f"GT:{len(gt_boxes)} | YOLO:{len(yolo_dets)}", fill='white')
        draw.text((5, 42), f"Alt:{DRONE_ALTITUDE/100:.0f}m | Pitch:{CAMERA_PITCH}°", fill='gray')

        # Legend
        draw.rectangle([RENDER_W - 130, 0, RENDER_W, 35], fill='black')
        draw.text((RENDER_W - 125, 5), "GREEN = GT", fill='lime')
        draw.text((RENDER_W - 125, 18), "RED = YOLO", fill='red')

        # Bottom bar with position
        draw.rectangle([0, RENDER_H - 30, RENDER_W, RENDER_H], fill='black')
        draw.text((5, RENDER_H - 27),
                  f"Pos:({drone_pos[0]:.0f},{drone_pos[1]:.0f},{drone_pos[2]:.0f})", fill='gray')

        # Progress bar
        total_range = START_OFFSET + OVERSHOOT
        progress = (current_offset + START_OFFSET) / total_range
        bar_y = RENDER_H - 8
        bar_x0 = 10
        bar_x1 = RENDER_W - 10
        bar_w = bar_x1 - bar_x0
        draw.rectangle([bar_x0, bar_y - 3, bar_x1, bar_y + 3], fill='gray')
        # Target marker
        tgt_mark = bar_x0 + int(bar_w * (START_OFFSET / total_range))
        draw.rectangle([tgt_mark - 2, bar_y - 6, tgt_mark + 2, bar_y + 6], fill='lime')
        # Drone marker
        d_mark = bar_x0 + int(bar_w * max(0, min(1, progress)))
        draw.rectangle([d_mark - 3, bar_y - 5, d_mark + 3, bar_y + 5], fill='cyan')

        img.save(os.path.join(OUTPUT_DIR, "latest_annotated.png"))
        if frame % 10 == 0:
            img.save(os.path.join(OUTPUT_DIR, f"flyover_{frame:04d}.png"))
        if frame % 50 == 0:
            print(f"[Frame {frame}] {dir_label} offset={dist_m:+.0f}m GT:{len(gt_boxes)} YOLO:{len(yolo_dets)}")

        frame += 1

    try:
        rep.orchestrator.stop()
    except:
        pass
    print(f"\nFlyover stopped after {frame} frames, {pass_count} passes.")

asyncio.ensure_future(flyover_loop())
