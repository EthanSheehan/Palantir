import omni.replicator.core as rep
import omni.usd
import omni.kit.app
import omni.kit.viewport.utility as vp_util
import asyncio
import numpy as np
import os
import time

OUTPUT_DIR = r"C:\Users\victo\Downloads\New folder\unreal_to_isaac_target_tracking_2\output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

from ultralytics import YOLO
print("Loading YOLO...")
model = YOLO("yolov8n.pt")
model.to("cpu")
print("YOLO ready!")

RENDER_W = 640
RENDER_H = 480
RUNNING = True

vp = vp_util.get_active_viewport()
cam_path = str(vp.get_active_camera())
print(f"Camera: {cam_path}")

async def test_loop():
    global RUNNING
    rp = rep.create.render_product(cam_path, (RENDER_W, RENDER_H))
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

    print("Ready! Navigate to see the truck. GT=green, YOLO=red")
    print("To stop: RUNNING = False")

    frame = 0
    while RUNNING and frame < 5000:
        await rep.orchestrator.step_async()
        for _ in range(3):
            await omni.kit.app.get_app().next_update_async()

        rgb_data = rgb_ann.get_data()
        bbox_data = bbox_ann.get_data()
        if rgb_data is None:
            continue

        img = Image.fromarray(rgb_data[:, :, :3])
        tmp = os.path.join(OUTPUT_DIR, "_tmp.png")
        img.save(tmp)

        t0 = time.time()
        yolo_results = model.predict(source=tmp, conf=0.15, imgsz=640, verbose=False, device="cpu")
        yolo_ms = (time.time() - t0) * 1000

        draw = ImageDraw.Draw(img)

        # GT (GREEN)
        gt_count = 0
        if bbox_data is not None and 'data' in bbox_data:
            labels_map = bbox_data.get('info', {}).get('idToLabels', {})
            for box in bbox_data['data']:
                x_min, y_min = int(box['x_min']), int(box['y_min'])
                x_max, y_max = int(box['x_max']), int(box['y_max'])
                sem_id = str(box['semanticId'])
                label = labels_map.get(sem_id, {}).get('class', '?')
                occ = float(box['occlusionRatio'])
                draw.rectangle([x_min, y_min, x_max, y_max], outline='lime', width=2)
                draw.text((x_min, y_min - 12), f"GT:{label} occ:{occ:.0%}", fill='lime')
                gt_count += 1

        # YOLO (RED)
        yolo_count = 0
        for r in yolo_results:
            for b in r.boxes:
                cls_name = model.names[int(b.cls[0])]
                conf = float(b.conf[0])
                x1, y1, x2, y2 = b.xyxy[0].cpu().numpy().astype(int)
                draw.rectangle([x1, y1, x2, y2], outline='red', width=2)
                draw.text((x1, y2 + 2), f"YOLO:{cls_name} {conf:.0%}", fill='red')
                yolo_count += 1

        draw.rectangle([0, 0, RENDER_W, 30], fill='black')
        draw.text((5, 3), f"Frame:{frame} | YOLO:{yolo_ms:.0f}ms | GT:{gt_count} | YOLO:{yolo_count}", fill='white')

        draw.rectangle([RENDER_W - 130, 0, RENDER_W, 30], fill='black')
        draw.text((RENDER_W - 125, 3), "GREEN=GT", fill='lime')
        draw.text((RENDER_W - 125, 16), "RED=YOLO", fill='red')

        img.save(os.path.join(OUTPUT_DIR, "latest_annotated.png"))
        if frame % 10 == 0:
            print(f"[Frame {frame}] GT:{gt_count} YOLO:{yolo_count} ({yolo_ms:.0f}ms)")

        frame += 1

    try:
        rep.orchestrator.stop()
    except:
        pass
    print(f"Stopped after {frame} frames.")

asyncio.ensure_future(test_loop())
