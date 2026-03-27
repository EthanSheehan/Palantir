"""Auto-generated: Convert terrain, place truck, run terminal dive."""
import omni.kit.asset_converter
import omni.kit.app
import omni.usd
import omni.replicator.core as rep
import asyncio
import numpy as np
import os
import time
import json
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

BASE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

obj_path = os.path.join(BASE, "terrain_mesh.obj")
usd_path = os.path.join(BASE, "terrain_auto.usd")

with open(os.path.join(BASE, "metadata.json"), 'r') as f:
    meta = json.load(f)

async def full_pipeline():
    # ---- PHASE 1: Convert OBJ to USD ----
    print("[AUTO] Converting OBJ to USD...")
    converter = omni.kit.asset_converter.get_instance()
    context = omni.kit.asset_converter.AssetConverterContext()
    context.ignore_materials = False
    context.ignore_textures = False

    # Delete old USD if exists
    if os.path.exists(usd_path):
        os.remove(usd_path)

    task = converter.create_converter_task(obj_path, usd_path, None, context)
    success = await task.wait_until_finished()
    if not success:
        print(f"[AUTO] Conversion failed!")
        return
    print(f"[AUTO] Converted to {usd_path}")

    # ---- PHASE 2: Open scene ----
    print("[AUTO] Opening scene...")
    omni.usd.get_context().open_stage(usd_path)
    for _ in range(90):
        await omni.kit.app.get_app().next_update_async()

    stage = omni.usd.get_context().get_stage()

    # ---- PHASE 3: Place truck at POI ----
    print("[AUTO] Placing truck at POI...")
    truck_path = Sdf.Path("/TruckTarget")
    truck = UsdGeom.Cube.Define(stage, truck_path)
    truck.GetSizeAttr().Set(500.0)
    xform = UsdGeom.Xformable(truck.GetPrim())
    xform.AddTranslateOp().Set(Gf.Vec3d(
        meta['poi_local_x_cm'],
        meta['poi_local_y_cm'] + 250,
        meta['poi_local_z_cm']
    ))

    # ---- PHASE 4: Apply semantic labels ----
    print("[AUTO] Applying semantic labels...")
    from pxr import Semantics
    sem = Semantics.SemanticsAPI.Apply(truck.GetPrim(), "Semantics")
    sem.CreateSemanticTypeAttr().Set("class")
    sem.CreateSemanticDataAttr().Set("truck")

    print(f"[AUTO] Truck at ({meta['poi_local_x_cm']:.0f}, {meta['poi_local_y_cm']:.0f}, {meta['poi_local_z_cm']:.0f})")

    for _ in range(30):
        await omni.kit.app.get_app().next_update_async()

    # ---- PHASE 5: Auto-play ----
    print("[AUTO] Starting simulation playback...")
    import omni.timeline
    timeline = omni.timeline.get_timeline_interface()
    timeline.play()
    for _ in range(30):
        await omni.kit.app.get_app().next_update_async()
    print("[AUTO] Playback started!")

    # ---- PHASE 6: Run terminal dive ----
    # Inline the terminal dive logic
    RENDER_W = 640
    RENDER_H = 480
    DRONE_ALTITUDE = 10000.0
    START_OFFSET = 30000.0
    DIVE_TRIGGER_DIST = 15000.0
    SPEED_CM_PER_SEC = 1388.9
    INITIAL_PITCH = 0.0
    Kp_PITCH = 0.15
    MIN_PITCH = 5.0
    MAX_PITCH = 85.0
    MIN_ALTITUDE = 200.0

    PHASE_CRUISE = 0
    PHASE_DIVE = 1
    PHASE_TERMINAL = 2

    # Find target
    target_pos = None
    for prim in Usd.PrimRange(stage.GetPseudoRoot()):
        if "Truck" in prim.GetName():
            xf_api = UsdGeom.Xformable(prim)
            target_pos = xf_api.ComputeLocalToWorldTransform(0).ExtractTranslation()
            print(f"[AUTO] Target: {prim.GetPath()} at ({target_pos[0]:.0f},{target_pos[1]:.0f},{target_pos[2]:.0f})")
            break

    if not target_pos:
        print("[AUTO] ERROR: No target!")
        return

    # Create camera
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
        pitch_rad = np.radians(pitch_deg)
        fwd_h = np.array([fly_dir[0], 0.0, fly_dir[2]])
        l = np.linalg.norm(fwd_h)
        if l > 0: fwd_h /= l
        look_dist = 30000.0
        look_at = np.array([
            pos[0] + fwd_h[0] * look_dist * np.cos(pitch_rad),
            pos[1] - look_dist * np.sin(pitch_rad),
            pos[2] + fwd_h[2] * look_dist * np.cos(pitch_rad),
        ])
        eye = Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2]))
        tgt = Gf.Vec3d(float(look_at[0]), float(look_at[1]), float(look_at[2]))
        fwd = (tgt - eye).GetNormalized()
        world_up = Gf.Vec3d(0, 1, 0)
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
        cp = stage.GetPrimAtPath(cam_path)
        xf = UsdGeom.Xformable(cp)
        xf.ClearXformOpOrder()
        xf.AddTransformOp().Set(mat)

    set_cam(drone_pos, flight_dir, drone_pitch)

    # Render product + annotators
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
    mission_count = 0
    impact_time = None
    phase_names = {PHASE_CRUISE: "CRUISE", PHASE_DIVE: "DIVE", PHASE_TERMINAL: "IMPACT"}

    print("[AUTO] Terminal dive running!")

    while frame < 20000:
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
                print(f"[AUTO] Mission reset #{mission_count}")
                set_cam(drone_pos, flight_dir, drone_pitch)
                await omni.kit.app.get_app().next_update_async()
                continue

        current_offset += SPEED_CM_PER_SEC * dt
        drone_pos[0] = target_pos[0] + flight_dir[0] * current_offset
        drone_pos[2] = target_pos[2]
        dist_to_target = abs(current_offset)

        if phase == PHASE_CRUISE:
            drone_pos[1] = target_pos[1] + DRONE_ALTITUDE
            if dist_to_target <= DIVE_TRIGGER_DIST:
                phase = PHASE_DIVE
                print(f"[AUTO] DIVE at dist={dist_to_target/100:.0f}m")
        elif phase == PHASE_DIVE:
            descent_rate = SPEED_CM_PER_SEC * np.sin(np.radians(drone_pitch))
            drone_pos[1] -= descent_rate * dt
            alt = drone_pos[1] - target_pos[1]
            if alt <= MIN_ALTITUDE:
                phase = PHASE_TERMINAL
                print(f"[AUTO] IMPACT alt={alt/100:.1f}m pitch={drone_pitch:.1f}")

        set_cam(drone_pos, flight_dir, drone_pitch)
        await omni.kit.app.get_app().next_update_async()

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
            print(f"[AUTO] Frame {frame} {phase_names[phase]} pitch={drone_pitch:.1f} alt={alt_m:.0f}m GT:{len(gt_boxes)}")

        frame += 1

asyncio.ensure_future(full_pipeline())
