import cv2
from ultralytics import YOLO
import services.traffic_service as ts  # STOP flag

# -----------------------------
# Load YOLO model once
# -----------------------------
model = YOLO("yolov8n.pt")

# COCO vehicle classes
VEHICLE_CLASSES = [2, 3, 5, 7]  # car, bike, bus, truck

# -----------------------------
# GLOBAL VIDEO CAPTURE
# -----------------------------
cap = None

# -----------------------------
# MAIN FUNCTION
# -----------------------------
def release_video():
    global cap
    if cap is not None:
        cap.release()
        cap = None
        cv2.destroyAllWindows()
        print("📹 Video released")

def generate_video_stream(video_path):

    global cap

    if cap is None:
        cap = cv2.VideoCapture(video_path)

    while True:

        if ts.STOP_VIDEO:
            release_video()
            break

        ret, frame = cap.read()
        if not ret:
            release_video()
            break

        results = model(frame)[0]

        count = 0

        for box in results.boxes:
            cls = int(box.cls[0])

            if cls in VEHICLE_CLASSES:
                count += 1

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)

                label = model.names[cls]
                cv2.putText(frame, label, (x1, y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)

        # encode frame
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
def detect_vehicles_from_video(video_path):

    global cap

    # 🔥 Stop if mode changed
    if ts.STOP_VIDEO:
        print("🛑 Video stopped")
        if cap is not None:
            cap.release()
            cap = None
        return 0

    # 🔥 Open video once
    if cap is None:
        cap = cv2.VideoCapture(video_path)

    count_list = []

    # -----------------------------
    # Read multiple frames
    # -----------------------------
    for _ in range(5):  # process 5 frames

        ret, frame = cap.read()

        if not ret:
            if cap is not None:
                cap.release()
                cap = None
            break

        results = model(frame)[0]

        count = 0

        for box in results.boxes:
            cls = int(box.cls[0])

            if cls in VEHICLE_CLASSES:
                count += 1

        count_list.append(count)

    # -----------------------------
    # Average count
    # -----------------------------
    if len(count_list) == 0:
        return 0

    avg_count = sum(count_list) // len(count_list)

    # 🔥 Slight scaling (optional realism)
    avg_count = int(avg_count * 1.3)

    return avg_count