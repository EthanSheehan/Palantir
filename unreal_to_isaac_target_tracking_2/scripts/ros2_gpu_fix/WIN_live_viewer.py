"""
Live OpenCV Viewer — Combined GT + GPU YOLO feed.
Watches for latest_gpu_yolo.png and displays it.

Run from Windows terminal:
    cd to the script directory
    python live_viewer.py

Press Q to quit.
"""
import cv2
import os

INPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "latest_gpu_yolo.png")

cv2.namedWindow("GT + GPU YOLO", cv2.WINDOW_NORMAL)
cv2.resizeWindow("GT + GPU YOLO", 1280, 720)

last_mtime = 0
print(f"Watching: {INPUT}")
print("Press Q to quit")

while True:
    if os.path.exists(INPUT):
        try:
            mtime = os.path.getmtime(INPUT)
            if mtime != last_mtime:
                last_mtime = mtime
                img = cv2.imread(INPUT)
                if img is not None:
                    cv2.imshow("GT + GPU YOLO", img)
        except:
            pass

    key = cv2.waitKey(50) & 0xFF
    if key == ord('q'):
        break

cv2.destroyAllWindows()
