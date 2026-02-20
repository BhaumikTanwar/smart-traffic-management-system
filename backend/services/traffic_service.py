import random
import time
import os
from services.video_service import detect_vehicles_from_video

previous_counts = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
VIDEO_PATH = os.path.join(PROJECT_ROOT, "uploaded_video.mp4")


def generate_road_data(name, current_mode):
    global previous_counts

    # VIDEO MODE WITHOUT UPLOAD → STOP
    if current_mode == "video":
        if not os.path.exists(VIDEO_PATH):
            return None
        vehicle_count = detect_vehicles_from_video()
    else:
        vehicle_count = random.randint(10, 120)

    # Congestion Logic
    if vehicle_count < 30:
        congestion = "Low"
        base_green = 30
    elif vehicle_count < 70:
        congestion = "Medium"
        base_green = 45
    else:
        congestion = "High"
        base_green = 60

    previous = previous_counts.get(name, vehicle_count)

    if vehicle_count > previous:
        predicted_trend = "Increasing"
    elif vehicle_count < previous:
        predicted_trend = "Decreasing"
    else:
        predicted_trend = "Stable"

    if predicted_trend == "Increasing" and congestion == "Medium":
        predicted_congestion = "High"
    elif predicted_trend == "Decreasing" and congestion == "Medium":
        predicted_congestion = "Low"
    else:
        predicted_congestion = congestion

    previous_counts[name] = vehicle_count

    return {
        "road_name": name,
        "vehicle_count": vehicle_count,
        "congestion_level": congestion,
        "predicted_congestion": predicted_congestion,
        "trend": predicted_trend,
        "base_green_time": base_green
    }


def get_traffic_status(current_mode):

    import os

    VIDEO_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "uploaded_video.mp4"
    )

    # 🔴 If video mode but no uploaded file → STOP
    if current_mode == "video" and not os.path.exists(VIDEO_PATH):
        return {
            "video_ready": False,
            "current_mode": current_mode
        }

    # Otherwise continue normally
    if current_mode == "video":
        vehicle_count = detect_vehicles_from_video()
    else:
        vehicle_count = random.randint(10, 120)

    # Congestion logic
    if vehicle_count < 30:
        congestion = "Low"
        base_green = 30
    elif vehicle_count < 70:
        congestion = "Medium"
        base_green = 45
    else:
        congestion = "High"
        base_green = 60

    adaptive_green = base_green + 15

    return {
        "timestamp": time.strftime("%H:%M:%S"),
        "current_mode": current_mode,
        "video_ready": True,
        "roads": [{
            "vehicle_count": vehicle_count,
            "congestion_level": congestion,
            "adaptive_green_time": adaptive_green
        }]
    }