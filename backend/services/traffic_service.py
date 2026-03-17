import random
import time
import os
import joblib
import pandas as pd
import numpy as np
from services.video_service import detect_vehicles_from_video

# -----------------------------
# Paths
# -----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

VIDEO_PATH = os.path.join(PROJECT_ROOT, "backend", "uploaded_video.mp4")
MODEL_PATH = os.path.join(PROJECT_ROOT, "traffic_congestion_model.pkl")
DATASET_PATH = os.path.join(PROJECT_ROOT, "dataset.csv")

dataset = pd.read_csv(DATASET_PATH)

# -----------------------------
# Load ML model (LOAD ONCE ✅)
# -----------------------------

model = joblib.load(MODEL_PATH)

CONGESTION_LABELS = ["Low", "Medium", "High"]

# store previous traffic values
traffic_history = []

# -----------------------------
# Predict congestion using ML
# -----------------------------

def predict_congestion(vehicle_count):

    # derive features from vehicle count
    if vehicle_count < 10:
        avg_speed = 50
        lane_occupancy = 30
    elif vehicle_count < 25:
        avg_speed = 35
        lane_occupancy = 60
    else:
        avg_speed = 20
        lane_occupancy = 90

    weather = 0

    features = np.array([[vehicle_count, avg_speed, lane_occupancy, weather]])

    prediction = model.predict(features)[0]

    return prediction


# -----------------------------
# Predict future traffic
# -----------------------------

def predict_future_vehicle_count(history):
    if len(history) < 3:
        return history[-1] if history else 0

    trend = (history[-1] - history[0]) / len(history)
    future = int(history[-1] + trend)

    return max(future, 0)


# -----------------------------
# Signal timing logic
# -----------------------------

def calculate_signal_time(vehicle_count):

    if vehicle_count < 10:
        return 25
    elif vehicle_count < 25:
        return 45
    elif vehicle_count < 40:
        return 70
    else:
        return 90


# -----------------------------
# Main traffic logic
# -----------------------------

def get_traffic_status(current_mode):

    global traffic_history

    # video mode but no video uploaded
    if current_mode == "video" and not os.path.exists(VIDEO_PATH):
        return {
            "video_ready": False,
            "current_mode": current_mode
        }

    # -----------------------------
    # VEHICLE DETECTION
    # -----------------------------
    if current_mode == "video":
        vehicle_count = detect_vehicles_from_video(VIDEO_PATH)
        congestion = predict_congestion(vehicle_count)
    else:
        row = dataset.sample(1).iloc[0]
        vehicle_count = int(row["vehicle_count"])
        congestion = row["congestion_level"]

    # -----------------------------
    # STORE HISTORY
    # -----------------------------
    traffic_history.append(vehicle_count)

    # keep last 5 values only (cleaner)
    traffic_history = traffic_history[-5:]

    # -----------------------------
    # FUTURE PREDICTION (FIXED ✅)
    # -----------------------------
    future_vehicle_count = predict_future_vehicle_count(traffic_history)
    future_congestion = predict_congestion(future_vehicle_count)

    # -----------------------------
    # SIGNAL TIMING
    # -----------------------------
    green_time = calculate_signal_time(vehicle_count)

    # -----------------------------
    # FINAL RESPONSE
    # -----------------------------
    return {
        "timestamp": time.strftime("%H:%M:%S"),
        "current_mode": current_mode,
        "video_ready": True,
        "roads": [{
            "vehicle_count": vehicle_count,
            "congestion_level": congestion,
            "future_vehicle_count": future_vehicle_count,
            "future_congestion": future_congestion,
            "adaptive_green_time": green_time
        }]
    }