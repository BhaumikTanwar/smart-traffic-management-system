"""
video_service.py
----------------
- ByteTrack (via Ultralytics tracker) for unique vehicle counting
- threading.Lock on all cap.read() calls
- Frame skipping for performance
- Confidence threshold filtering
- open_video() / release_video() for controlled lifecycle
"""

import cv2
import threading
from ultralytics import YOLO
import services.traffic_service as ts

# ── Model ──────────────────────────────────────────────
model = YOLO("yolov8n.pt")

VEHICLE_CLASSES = [2, 3, 5, 7]   # car, motorcycle, bus, truck
CONF_THRESHOLD  = 0.45            # ignore detections below this confidence
FRAME_SKIP      = 3               # process every Nth frame, interpolate the rest

# ── Global cap + lock ──────────────────────────────────
cap      = None
cap_lock = threading.Lock()

# ByteTrack keeps a set of track IDs seen so far → unique count
_tracked_ids   = set()
_track_lock    = threading.Lock()
_last_count    = 0                # last known unique vehicle count


# ── Lifecycle ──────────────────────────────────────────
def open_video(video_path: str):
    """Open cap safely. Call once from upload route."""
    global cap, _tracked_ids, _last_count
    with cap_lock:
        if cap is not None:
            cap.release()
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    with _track_lock:
        _tracked_ids.clear()
        _last_count = 0
    print(f"📹 Video opened: {video_path}")


def release_video():
    global cap
    with cap_lock:
        if cap is not None:
            cap.release()
            cap = None
            cv2.destroyAllWindows()
            print("📹 Video released")


# ── Stream generator (for /video_feed) ────────────────
def generate_video_stream(video_path: str):
    """
    Yields MJPEG frames with:
      - YOLO detection boxes drawn
      - ByteTrack ID labels
      - Frame skipping for speed
    """
    global cap, _tracked_ids, _last_count

    if cap is None:
        open_video(video_path)

    frame_idx = 0

    while True:
        if ts.STOP_VIDEO:
            release_video()
            break

        with cap_lock:
            if cap is None or not cap.isOpened():
                break
            ret, frame = cap.read()

        if not ret:
            release_video()
            break

        frame_idx += 1

        # ── Run YOLO + ByteTrack every Nth frame ──
        if frame_idx % FRAME_SKIP == 0:
            results = model.track(
                frame,
                persist=True,           # keep track state between calls
                tracker="bytetrack.yaml",
                conf=CONF_THRESHOLD,
                classes=VEHICLE_CLASSES,
                verbose=False
            )[0]

            if results.boxes.id is not None:
                for box, track_id, cls_id in zip(
                    results.boxes.xyxy,
                    results.boxes.id.int().tolist(),
                    results.boxes.cls.int().tolist()
                ):
                    if cls_id not in VEHICLE_CLASSES:
                        continue

                    with _track_lock:
                        _tracked_ids.add(track_id)
                        _last_count = len(_tracked_ids)

                    x1, y1, x2, y2 = map(int, box)
                    label = f"{model.names[cls_id]} #{track_id}"
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (34, 197, 94), 2)
                    cv2.putText(frame, label, (x1, y1 - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (34, 197, 94), 1)

            # overlay unique count
            with _track_lock:
                count_text = f"Unique Vehicles: {_last_count}"
            cv2.putText(frame, count_text, (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, count_text, (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (34, 197, 94), 1)

        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')


# ── Count for traffic API ──────────────────────────────
def detect_vehicles_from_video(video_path: str) -> int:
    """
    Returns the current unique vehicle count tracked by ByteTrack.
    Falls back to per-frame detection if stream hasn't started yet.
    """
    global cap, _last_count

    if ts.STOP_VIDEO:
        release_video()
        return 0

    # If stream is running, just return the tracker's count
    with _track_lock:
        if _last_count > 0:
            return _last_count

    # Cold start: open cap and sample a few frames
    if cap is None:
        open_video(video_path)

    counts = []
    for _ in range(5):
        with cap_lock:
            if cap is None or not cap.isOpened():
                break
            ret, frame = cap.read()

        if not ret:
            break

        results = model(
            frame,
            conf=CONF_THRESHOLD,
            classes=VEHICLE_CLASSES,
            verbose=False
        )[0]

        count = sum(1 for cls in results.boxes.cls.int().tolist()
                    if cls in VEHICLE_CLASSES)
        counts.append(count)

    if not counts:
        return 0

    avg = int((sum(counts) / len(counts)) * 1.3)
    return avg
