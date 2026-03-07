import random
import time
import os
import joblib
import pandas as pd
from services.video_service import detect_vehicles_from_video

# -----------------------------
# Paths
# -----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

VIDEO_PATH = os.path.join(PROJECT_ROOT, "uploaded_video.mp4")
MODEL_PATH = os.path.join(PROJECT_ROOT, "traffic_congestion_model.pkl")
DATASET_PATH = os.path.join(PROJECT_ROOT, "dataset.csv")

dataset = pd.read_csv(DATASET_PATH)

# -----------------------------
# Load ML model
# -----------------------------

model = joblib.load(MODEL_PATH)

# labels used during training
CONGESTION_LABELS = ["Low", "Medium", "High"]

# store previous traffic values
traffic_history = []

# -----------------------------
# Predict congestion using ML
# -----------------------------

def predict_congestion(vehicle_count):

    avg_speed = 40
    lane_occupancy = 50
    weather = 0

    data = [[vehicle_count, avg_speed, lane_occupancy, weather]]

    prediction = model.predict(data)[0]

    return CONGESTION_LABELS[int(prediction)]


# -----------------------------
# Predict future traffic
# -----------------------------

def predict_future_vehicle_count():

    if len(traffic_history) < 3:
        return traffic_history[-1] if traffic_history else 0

    v1, v2, v3 = traffic_history[-3:]

    trend = (v3 - v1) / 2

    future = v3 + trend

    return max(0, int(future))


# -----------------------------
# Signal timing logic
# -----------------------------

def calculate_green_time(congestion):

    if congestion == "Low":
        return 30
    elif congestion == "Medium":
        return 45
    else:
        return 60


# -----------------------------
# Main traffic logic
# -----------------------------

def get_traffic_status(current_mode):

    # video mode but no video uploaded
    if current_mode == "video" and not os.path.exists(VIDEO_PATH):
        return {
            "video_ready": False,
            "current_mode": current_mode
        }

    # detect vehicles
    if current_mode == "video":
        vehicle_count = detect_vehicles_from_video()
    else:
        row = dataset.sample(1).iloc[0]

    vehicle_count = int(row["vehicle_count"])

    congestion = row["congestion_level"]

    # store history
    traffic_history.append(vehicle_count)

    if len(traffic_history) > 10:
        traffic_history.pop(0)

    # current congestion prediction
    if current_mode == "simulation":
        congestion = row["congestion_level"]
    else:
        congestion = predict_congestion(vehicle_count)

    # future traffic prediction
    future_vehicle_count = predict_future_vehicle_count()

    # future congestion prediction
    future_congestion = predict_congestion(future_vehicle_count)

    # signal timing
    green_time = calculate_green_time(congestion)

    return {
        "timestamp": time.strftime("%H:%M:%S"),
        "current_mode": current_mode,
        "video_ready": True,
        "roads": [{
            "vehicle_count": vehicle_count,
            "congestion_level": congestion,
            "future_congestion": future_congestion,
            "adaptive_green_time": green_time
        }]
    }