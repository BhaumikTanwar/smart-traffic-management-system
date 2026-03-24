import time
import os
import random
from services.video_service import detect_vehicles_from_video
from services.model_service import predict_traffic
from services.video_service import release_video

# -----------------------------
# PATH
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

VIDEO_PATH = os.path.join(PROJECT_ROOT, "backend", "uploaded_video.mp4")

# -----------------------------
# GLOBAL FLAG (IMPORTANT)
# -----------------------------
STOP_VIDEO = False

# -----------------------------
# HISTORY
# -----------------------------
traffic_history = []

# -----------------------------
# FUTURE
# -----------------------------
def predict_future(vehicle_history):
    if len(vehicle_history) < 3:
        return vehicle_history[-1] if vehicle_history else 0

    trend = (vehicle_history[-1] - vehicle_history[0]) / len(vehicle_history)
    return max(int(vehicle_history[-1] + trend), 0)

# -----------------------------
# MAIN FUNCTION
# -----------------------------
def get_traffic_status(mode):

    global STOP_VIDEO
    global traffic_history

    # 🔥 STOP video if mode changed
    if mode != "video":
        STOP_VIDEO = True
        release_video()
        if os.path.exists(VIDEO_PATH):
            try:
                os.remove(VIDEO_PATH)
                print("🗑️ Video deleted")
            except Exception as e:
                print("❌ Error deleting video:", e)
    else:
        STOP_VIDEO = False

    # -----------------------------
    # VIDEO MODE
    # -----------------------------
    if mode == "video":

        if not os.path.exists(VIDEO_PATH):
            return {
                "timestamp": time.strftime("%H:%M:%S"),
                "current_mode": mode,
                "video_ready": False,
                "roads": []
            }

        vehicle_count = detect_vehicles_from_video(VIDEO_PATH)

    # -----------------------------
    # SIMULATION MODE
    # -----------------------------
    else:
        vehicle_count = random.randint(5, 50)

    # -----------------------------
    # ML PREDICTION
    # -----------------------------
    congestion, green_time = predict_traffic(vehicle_count)

    # -----------------------------
    # HISTORY
    # -----------------------------
    traffic_history.append(vehicle_count)
    traffic_history = traffic_history[-5:]

    # -----------------------------
    # FUTURE
    # -----------------------------
    future_vehicle = predict_future(traffic_history)
    future_congestion, _ = predict_traffic(future_vehicle)

    # -----------------------------
    # RESPONSE
    # -----------------------------
    return {
        "timestamp": time.strftime("%H:%M:%S"),
        "current_mode": mode,
        "video_ready": True,
        "roads": [{
            "vehicle_count": vehicle_count,
            "congestion_level": congestion,
            "future_congestion": future_congestion,
            "adaptive_green_time": green_time
        }]
    }