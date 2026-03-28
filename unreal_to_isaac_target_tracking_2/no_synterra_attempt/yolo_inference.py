"""
Native YOLO Inference — runs on the same machine (no WSL2 required).

Drop-in replacement for WSL2_yolo_gpu_inference.py.
Watches _tmp.png + gt_data.json, runs YOLO, draws GT+YOLO+HUD.

Usage:
  python yolo_inference.py
  python yolo_inference.py --model yolo11n.pt --conf 0.15 --device cuda
  python yolo_inference.py --device cpu    # force CPU inference
"""
import os
import sys
import json
import time
import hashlib
import argparse

import cv2
import numpy as np

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "output")

parser = argparse.ArgumentParser(description="Native YOLO inference (no WSL2)")
parser.add_argument("--model", default=os.path.join(_SCRIPT_DIR, "yolo11n.pt"),
    help="Path to YOLO model weights")
parser.add_argument("--conf", type=float, default=0.15, help="Confidence threshold")
parser.add_argument("--device", default="auto",
    help="Inference device: auto, cuda, cpu")
args = parser.parse_args()

# Resolve device
device = args.device
if device == "auto":
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        device = "cpu"

print(f"YOLO inference on {device}")
print(f"Model: {args.model}")
print(f"Watching: {OUTPUT_DIR}")

# Load YOLO model
try:
    from ultralytics import YOLO
    model = YOLO(args.model)
    print(f"Model loaded: {args.model}")
except ImportError:
    print("ERROR: ultralytics not installed. Run: pip install ultralytics")
    sys.exit(1)
except Exception as e:
    print(f"ERROR loading model: {e}")
    sys.exit(1)

RAW_PATH = os.path.join(OUTPUT_DIR, "_tmp.png")
GT_PATH = os.path.join(OUTPUT_DIR, "gt_data.json")
OUT_PATH = os.path.join(OUTPUT_DIR, "latest_gpu_yolo.png")

prev_hash = ""
fps_counter = 0
fps_time = time.time()
fps_val = 0.0

# Phase colors (same as WSL2 version)
PHASE_COLORS = {
    "CRUISE": (0, 255, 0),    # green
    "DIVE": (0, 165, 255),    # orange
    "IMPACT": (0, 0, 255),    # red
}

print("Waiting for frames...")

try:
    while True:
        if not os.path.exists(RAW_PATH):
            time.sleep(0.05)
            continue

        # Check if frame changed (MD5 of first 2000 bytes)
        try:
            with open(RAW_PATH, "rb") as f:
                raw_bytes = f.read(2000)
            cur_hash = hashlib.md5(raw_bytes).hexdigest()
            if cur_hash == prev_hash:
                time.sleep(0.01)
                continue
            prev_hash = cur_hash
        except Exception:
            time.sleep(0.05)
            continue

        # Read frame
        try:
            img = cv2.imread(RAW_PATH)
            if img is None:
                continue
        except Exception:
            continue

        h, w = img.shape[:2]

        # Run YOLO
        results = model.predict(img, conf=args.conf, imgsz=max(w, h),
                                device=device, verbose=False)

        # Draw YOLO predictions (RED)
        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            label = f"{model.names[cls]} {conf:.2f}"
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(img, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        # Read GT data
        gt_data = None
        try:
            with open(GT_PATH, "r") as f:
                gt_data = json.load(f)
        except Exception:
            pass

        if gt_data:
            # Draw GT boxes (GREEN)
            for gt in gt_data.get("boxes", []):
                cv2.rectangle(img,
                    (gt["x_min"], gt["y_min"]),
                    (gt["x_max"], gt["y_max"]),
                    (0, 255, 0), 2)
                cv2.putText(img, f"GT:{gt['label']}",
                    (gt["x_min"], gt["y_min"] - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

            # Draw HUD
            meta = gt_data.get("meta", {})
            phase = meta.get("phase", "?")
            pitch = meta.get("pitch", 0)
            alt = meta.get("altitude_m", 0)
            dist = meta.get("dist_to_target_m", 0)
            state_str = meta.get("state", "?")
            pass_num = meta.get("pass_num", 0)

            color = PHASE_COLORS.get(phase, (255, 255, 255))

            # Crosshair
            cx, cy = w // 2, h // 2
            cv2.line(img, (cx - 15, cy), (cx + 15, cy), color, 1)
            cv2.line(img, (cx, cy - 15), (cx, cy + 15), color, 1)

            # Phase + stats
            cv2.putText(img, f"{phase} [{state_str}]", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            cv2.putText(img, f"Pitch: {pitch:.1f}deg", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            cv2.putText(img, f"Alt: {alt:.0f}m", (10, 55),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            cv2.putText(img, f"Dist: {dist:.0f}m", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            cv2.putText(img, f"Pass #{pass_num}", (10, 85),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

            # FPS
            fps_counter += 1
            if time.time() - fps_time >= 1.0:
                fps_val = fps_counter / (time.time() - fps_time)
                fps_counter = 0
                fps_time = time.time()
            cv2.putText(img, f"FPS: {fps_val:.0f}", (w - 80, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

            # Device badge
            cv2.putText(img, f"YOLO@{device}", (w - 100, h - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 255), 1)

        # Save annotated frame
        try:
            cv2.imwrite(OUT_PATH, img)
        except Exception:
            pass

except KeyboardInterrupt:
    print("\nYOLO inference stopped.")
