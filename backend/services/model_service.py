import joblib
import pandas as pd
import os

# -----------------------------
# Load model
# -----------------------------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "traffic_model.pkl")

model = joblib.load(MODEL_PATH)

# -----------------------------
# Prediction function
# -----------------------------
def predict_traffic(vehicle_count):

    # 🔥 derive features (must match training)
    avg_speed_kmh = max(10, 60 - vehicle_count)
    delay_index = vehicle_count / 5

    input_data = pd.DataFrame([[
        vehicle_count,
        avg_speed_kmh,
        delay_index
    ]], columns=[
        'vehicle_count',
        'avg_speed_kmh',
        'delay_index'
    ])

    try:
        pred = model.predict(input_data)[0]
    except Exception as e:
        print("❌ Model error:", e)
        return "Low", 15

    # Map output
    mapping = {0: "Low", 1: "Medium", 2: "High"}
    congestion = mapping[pred]

    # Signal timing
    if congestion == "Low":
        green_time = 15
    elif congestion == "Medium":
        green_time = 30
    else:
        green_time = 45

    return congestion, green_time