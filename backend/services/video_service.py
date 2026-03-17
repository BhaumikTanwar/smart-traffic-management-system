import cv2
import os
import numpy as np
from ultralytics import YOLO

# ✅ Load model ONCE
model = YOLO("yolov8n.pt")

# ------------------------------
# 1️⃣ Vehicle Detection (for congestion logic)
# ------------------------------
def detect_vehicles_from_video(video_path):

    print("📹 Using video for detection:", video_path)

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("❌ Video not opened:", video_path)
        return 0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_frames == 0:
        print("❌ Empty video")
        return 0

    # 👉 sample 5 frames
    frame_indices = np.linspace(0, total_frames - 1, 5, dtype=int)

    vehicle_counts = []

    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()

        if not ret or frame is None:
            continue

        results = model(frame)

        count = 0
        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])

                # vehicle classes
                if cls in [2, 3, 5, 7]:
                    count += 1

        print(f"Frame {idx} → Count: {count}")
        vehicle_counts.append(count)

    cap.release()

    if len(vehicle_counts) == 0:
        return 0

    avg_count = int(sum(vehicle_counts) / len(vehicle_counts))

    print("🚗 Final vehicle count:", avg_count)

    return avg_count


# ------------------------------
# 2️⃣ Live Video Stream (for dashboard)
# ------------------------------
def generate_video_stream():

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    video_path = os.path.join(BASE_DIR, "backend", "uploaded_video.mp4")

    print("📺 Streaming video from:", video_path)

    while True:

        if not os.path.exists(video_path):
            # wait until video is uploaded
            continue

        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            print("❌ Cannot open video for streaming")
            continue

        while True:
            success, frame = cap.read()

            if not success:
                # restart video loop
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            results = model(frame)

            for r in results:
                for box in r.boxes:
                    class_id = int(box.cls[0])
                    label = model.names[class_id]

                    if label in ["car", "truck", "bus", "motorbike"]:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])

                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                        cv2.putText(
                            frame,
                            label,
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 255, 0),
                            2
                        )

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')