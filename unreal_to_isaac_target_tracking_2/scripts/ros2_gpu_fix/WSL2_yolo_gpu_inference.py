#!/usr/bin/env python3
"""
GPU YOLO File Watcher — Combined GT + GPU YOLO output.
Reads frames continuously, runs GPU YOLO, composites with GT, saves result.

GREEN = Ground Truth (from Isaac Sim)
RED = GPU YOLO detections (~21ms on RTX 5070)

Usage (in WSL2 terminal):
    cd /mnt/c/Users/victo/Downloads/unreal_to_isaac_target_tracking_2/scripts/ros2_gpu_fix
    python3 yolo_gpu_watcher.py
"""
import torch
from ultralytics import YOLO
import cv2
import numpy as np
import time
import os
import hashlib

BASE = "/mnt/c/Users/victo/Downloads/unreal_to_isaac_target_tracking_2/output"
RAW_PATH = os.path.join(BASE, "_tmp.png")
GT_PATH = os.path.join(BASE, "latest_annotated.png")
OUTPUT_PATH = os.path.join(BASE, "latest_gpu_yolo.png")

print(f"GPU: {torch.cuda.get_device_name(0)}")
print("Loading YOLOv8n on GPU...")
model = YOLO("yolov8n.pt")
model.to("cuda")
print("YOLO ready!")
print(f"Watching: {RAW_PATH}")

frame_count = 0
total_ms = 0
prev_hash = None

try:
    while True:
        try:
            with open(RAW_PATH, 'rb') as f:
                raw_bytes = f.read()
        except:
            time.sleep(0.05)
            continue

        if len(raw_bytes) < 100:
            time.sleep(0.05)
            continue

        cur_hash = hashlib.md5(raw_bytes[:1000]).hexdigest()
        if cur_hash == prev_hash:
            time.sleep(0.03)
            continue
        prev_hash = cur_hash

        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        try:
            raw_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except:
            time.sleep(0.05)
            continue
        if raw_img is None:
            time.sleep(0.05)
            continue

        frame_count += 1

        # Read GT frame
        gt_img = None
        try:
            with open(GT_PATH, 'rb') as f:
                gt_bytes = f.read()
            gt_arr = np.frombuffer(gt_bytes, dtype=np.uint8)
            gt_img = cv2.imdecode(gt_arr, cv2.IMREAD_COLOR)
        except:
            pass

        if gt_img is not None and gt_img.shape == raw_img.shape:
            img = gt_img.copy()
        else:
            img = raw_img.copy()

        # GPU YOLO
        t0 = time.time()
        results = model.predict(raw_img, conf=0.15, imgsz=640, verbose=False, device='cuda')
        ms = (time.time() - t0) * 1000
        total_ms += ms

        # Draw YOLO (RED)
        det_count = 0
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                cls_name = model.names[int(box.cls[0])]
                conf = float(box.conf[0])
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(img, f"GPU:{cls_name} {conf:.0%}", (x1, y2 + 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                det_count += 1

        # HUD
        avg_ms = total_ms / frame_count
        h, w = img.shape[:2]
        cv2.rectangle(img, (0, h - 45), (350, h - 20), (0, 0, 0), -1)
        cv2.putText(img, f"GPU YOLO: {ms:.0f}ms | avg:{avg_ms:.0f}ms | dets:{det_count}",
                   (5, h - 27), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

        cv2.rectangle(img, (w - 145, 0), (w, 35), (0, 0, 0), -1)
        cv2.putText(img, "GREEN = GT", (w - 140, 14),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        cv2.putText(img, "RED = GPU YOLO", (w - 140, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

        cv2.imwrite(OUTPUT_PATH, img)

        if frame_count % 20 == 0:
            fps = 1000 / avg_ms if avg_ms > 0 else 0
            print(f"[Frame {frame_count}] {ms:.0f}ms, avg:{avg_ms:.0f}ms, ~{fps:.0f}FPS, {det_count} dets")

except KeyboardInterrupt:
    print(f"\nStopped. {frame_count} frames, avg {total_ms/max(1,frame_count):.0f}ms")
