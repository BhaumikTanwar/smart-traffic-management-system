import cv2
import os
from ultralytics import YOLO

print("Loading YOLO model...")
model = YOLO("yolov8n.pt")  # downloads automatically first time

# Get absolute path of this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
video_path = os.path.join(BASE_DIR, "traffic_video.mp4")

print("Looking for video at:", video_path)

# Check if file exists
if not os.path.exists(video_path):
    print("Error: traffic_video.mp4 not found in backend folder.")
    exit()

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video file.")
    exit()

vehicle_count = 0
frame_number = 0

print("Processing video...")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_number += 1

    # Process every 10th frame for speed
    if frame_number % 10 != 0:
        continue

    results = model(frame)

    for r in results:
        for box in r.boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id]

            if label in ["car", "truck", "bus", "motorbike"]:
                vehicle_count += 1

cap.release()

print("Vehicle detection complete.")
print("Total vehicles detected:", vehicle_count)
