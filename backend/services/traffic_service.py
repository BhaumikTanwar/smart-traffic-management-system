import random
import time
import os
import joblib
from services.video_service import detect_vehicles_from_video

traffic_history = []

previous_counts = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
VIDEO_PATH = os.path.join(PROJECT_ROOT, "uploaded_video.mp4")
MODEL_PATH = os.path.join(PROJECT_ROOT, "traffic_prediction_model.pkl")

model = joblib.load(MODEL_PATH)

def predict_traffic(vehicle_count):

    # temporary default values for other features
    avg_speed = 40
    lane_occupancy = 50
    weather = 0
    congestion = 1

    data = [[vehicle_count, avg_speed, lane_occupancy, weather, congestion]]

    prediction = model.predict(data)

    return int(prediction[0])

def calculate_green_time(vehicle_count):

    CLEARANCE_TIME_PER_VEHICLE = 2   # seconds
    MIN_GREEN = 20
    MAX_GREEN = 90

    green_time = vehicle_count * CLEARANCE_TIME_PER_VEHICLE

    # keep within limits
    green_time = max(MIN_GREEN, min(green_time, MAX_GREEN))

    return green_time

def predict_future_traffic():

    global traffic_history

    if len(traffic_history) < 3:
        return traffic_history[-1] if traffic_history else 0

    last_values = traffic_history[-3:]

    prediction = sum(last_values) / len(last_values)

    return int(prediction)

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

    predicted_traffic = predict_traffic(vehicle_count)

    green_time = predicted_traffic * 2
    green_time = max(20, min(green_time, 90))

# store history
    traffic_history.append(vehicle_count)

# keep last 10 values
    if len(traffic_history) > 10:
        traffic_history.pop(0)

# predict future traffic
    predicted_traffic = predict_future_traffic()

# calculate green time
    adaptive_green = calculate_green_time(predicted_traffic)

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
        "predicted_traffic": predicted_traffic,
        "adaptive_green_time": green_time
    }]
}