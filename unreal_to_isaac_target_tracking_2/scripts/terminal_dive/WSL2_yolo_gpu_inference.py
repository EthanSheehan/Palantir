#!/usr/bin/env python3
"""
GPU YOLO File Watcher — Draws ALL HUD elements from scratch.
No GT image compositing — avoids frame phasing/stuttering.

Reads raw frame (_tmp.png) from Isaac Sim, runs GPU YOLO, reads GT bbox data
from a sidecar JSON file, and draws everything itself.

Usage (in WSL2 terminal):
    cd to the script directory
    python3 WSL2_yolo_gpu_inference.py
"""
import torch
from ultralytics import YOLO
import cv2
import numpy as np
import time
import os
import json
import hashlib

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output_terminal_dive")
RAW_PATH = os.path.join(BASE, "_tmp.png")
GT_JSON_PATH = os.path.join(BASE, "gt_data.json")
OUTPUT_PATH = os.path.join(BASE, "latest_gpu_yolo.png")

print(f"GPU: {torch.cuda.get_device_name(0)}")
print("Loading YOLO11n on GPU...")
model = YOLO("yolo11n.pt")
model.to("cuda")
print("YOLO ready!")
print(f"Watching: {RAW_PATH}")
print(f"GT data:  {GT_JSON_PATH}")
print(f"Output:   {OUTPUT_PATH}")
print("Press Ctrl+C to stop")

frame_count = 0
total_ms = 0
prev_hash = None

try:
    while True:
        # Read raw frame bytes
        try:
            with open(RAW_PATH, 'rb') as f:
                raw_bytes = f.read()
        except:
            time.sleep(0.05)
            continue

        if len(raw_bytes) < 1000:
            time.sleep(0.05)
            continue

        # Check if frame changed
        cur_hash = hashlib.md5(raw_bytes[:2000]).hexdigest()
        if cur_hash == prev_hash:
            time.sleep(0.02)
            continue
        prev_hash = cur_hash

        # Decode image
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
        h, w = raw_img.shape[:2]
        img = raw_img.copy()

        # === Run GPU YOLO ===
        t0 = time.time()
        results = model.predict(raw_img, conf=0.15, imgsz=640, verbose=False, device='cuda')
        ms = (time.time() - t0) * 1000
        total_ms += ms

        # Draw YOLO detections (RED)
        yolo_count = 0
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                cls_name = model.names[int(box.cls[0])]
                conf = float(box.conf[0])
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(img, f"YOLO:{cls_name} {conf:.0%}", (x1, y2 + 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
                yolo_count += 1

        # === Read GT data from JSON sidecar ===
        gt_boxes = []
        gt_meta = {}
        try:
            with open(GT_JSON_PATH, 'r') as f:
                gt_data = json.load(f)
            gt_boxes = gt_data.get('boxes', [])
            gt_meta = gt_data.get('meta', {})
        except:
            pass

        # Draw GT bounding boxes (GREEN)
        for gt in gt_boxes:
            x_min = gt.get('x_min', 0)
            y_min = gt.get('y_min', 0)
            x_max = gt.get('x_max', 0)
            y_max = gt.get('y_max', 0)
            label = gt.get('label', '?')
            occ = gt.get('occ', 0.0)
            cv2.rectangle(img, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
            cv2.putText(img, f"GT:{label} occ:{occ:.0%}", (x_min, y_min - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

        # === Draw HUD from scratch ===
        cx, cy = w // 2, h // 2

        # Crosshair
        cv2.line(img, (cx - 20, cy), (cx + 20, cy), (255, 255, 0), 1)
        cv2.line(img, (cx, cy - 20), (cx, cy + 20), (255, 255, 0), 1)

        # Top bar
        pitch = gt_meta.get('pitch', 0)
        error_y = gt_meta.get('error_y', 0)
        state = gt_meta.get('state', 'N/A')
        offset_m = gt_meta.get('offset_m', 0)
        phase = gt_meta.get('phase', 'N/A')
        altitude_m = gt_meta.get('altitude_m', 0)
        dist_m = gt_meta.get('dist_to_target_m', 0)

        # Phase color
        phase_colors = {'CRUISE': (0, 255, 255), 'DIVE': (0, 165, 255), 'IMPACT': (0, 0, 255)}
        phase_color = phase_colors.get(phase, (255, 255, 255))

        cv2.rectangle(img, (0, 0), (w, 65), (0, 0, 0), -1)
        cv2.putText(img, f"TERMINAL DIVE | Phase: {phase}",
                   (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, phase_color, 1)

        state_color = (0, 255, 0) if state == 'TRK' else (0, 255, 255)
        cv2.putText(img, f"Pitch: {pitch:.1f} deg | Alt: {altitude_m:.0f}m | Dist: {dist_m:.0f}m",
                   (5, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.45, state_color, 1)

        avg_ms = total_ms / frame_count
        fps = 1000 / avg_ms if avg_ms > 0 else 0
        cv2.putText(img, f"GT:{len(gt_boxes)} | YOLO:{yolo_count} | GPU:{ms:.0f}ms (~{fps:.0f}FPS) | err_y:{error_y:.0f}px",
                   (5, 49), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        # Legend (top right)
        cv2.rectangle(img, (w - 150, 0), (w, 35), (0, 0, 0), -1)
        cv2.putText(img, "GREEN = GT", (w - 145, 14),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        cv2.putText(img, "RED = GPU YOLO", (w - 145, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

        # Bottom bar — altitude gauge + distance
        cv2.rectangle(img, (0, h - 25), (w, h), (0, 0, 0), -1)
        cv2.putText(img, f"ALT: {altitude_m:.0f}m | DIST: {dist_m:.0f}m | Offset: {offset_m:+.0f}m",
                   (5, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)

        bar_y = h - 8
        bar_x0, bar_x1 = 250, w - 10
        cv2.rectangle(img, (bar_x0, bar_y - 3), (bar_x1, bar_y + 3), (80, 80, 80), -1)

        start_offset = gt_meta.get('start_offset', 10000)
        overshoot = gt_meta.get('overshoot', 10000)
        total_range = start_offset + overshoot
        if total_range > 0:
            progress = (offset_m * 100 + start_offset) / total_range
            progress = max(0, min(1, progress))
            tgt_frac = start_offset / total_range
            tgt_x = bar_x0 + int((bar_x1 - bar_x0) * tgt_frac)
            cv2.rectangle(img, (tgt_x - 2, bar_y - 6), (tgt_x + 2, bar_y + 6), (0, 255, 0), -1)
            d_x = bar_x0 + int((bar_x1 - bar_x0) * progress)
            cv2.rectangle(img, (d_x - 3, bar_y - 5), (d_x + 3, bar_y + 5), (255, 255, 0), -1)

        # Save output
        cv2.imwrite(OUTPUT_PATH, img)

        if frame_count % 20 == 0:
            print(f"[Frame {frame_count}] {ms:.0f}ms, ~{fps:.0f}FPS, GT:{len(gt_boxes)} YOLO:{yolo_count} pitch:{pitch:.1f}")

except KeyboardInterrupt:
    print(f"\nStopped. {frame_count} frames, avg {total_ms/max(1,frame_count):.0f}ms")
