import cv2
import os
import random
from ultralytics import YOLO

model = YOLO("yolov8n.pt")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(os.path.dirname(BASE_DIR), "uploaded_video.mp4")



# ------------------------------
# 1️⃣ Vehicle Detection (for congestion logic)
# ------------------------------
def detect_vehicles_from_video():

    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        return 0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_frames == 0:
        cap.release()
        return 0

    # Pick random frame for fast response
    random_frame_number = random.randint(0, total_frames - 1)
    cap.set(cv2.CAP_PROP_POS_FRAMES, random_frame_number)

    ret, frame = cap.read()
    if not ret:
        cap.release()
        return 0

    vehicle_count = 0

    results = model(frame)

    for r in results:
        for box in r.boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id]

            if label in ["car", "truck", "bus", "motorbike"]:
                vehicle_count += 1

    cap.release()
    return vehicle_count


# ------------------------------
# 2️⃣ Live Video Stream (for dashboard)
# ------------------------------
def generate_video_stream():

    cap = cv2.VideoCapture(VIDEO_PATH)

    while True:
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        results = model(frame)

        for r in results:
            for box in r.boxes:
                class_id = int(box.cls[0])
                label = model.names[class_id]
                confidence = float(box.conf[0])

                if label in ["car", "truck", "bus", "motorbike"]:

                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                    cv2.putText(
                        frame,
                        f"{label} {confidence:.2f}",
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
