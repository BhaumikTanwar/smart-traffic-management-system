"""
model_service.py
----------------
- Loads the trained RandomForest model
- Derives the same 6 features used at training time
- Returns congestion label, confidence %, and green_time
"""

import datetime
import joblib
import pandas as pd
import os

# ── Load model ─────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "traffic_model.pkl")

model = joblib.load(MODEL_PATH)

LABEL_MAP = {0: "Low", 1: "Medium", 2: "High"}

# ── Prediction ─────────────────────────────────────────
def predict_traffic(vehicle_count: int) -> tuple[str, int, float]:
    """
    Returns (congestion_label, green_time_seconds, confidence_pct).

    Features must exactly match those used in training:
      vehicle_count, hour_of_day, day_of_week, is_weekend,
      avg_speed_kmh, delay_index
    """
    now         = datetime.datetime.now()
    hour        = now.hour
    day_of_week = now.weekday()          # 0=Monday … 6=Sunday
    is_weekend  = 1 if day_of_week >= 5 else 0

    # These still correlate with count but now have real companions
    # (hour, day) so the model uses all features meaningfully
    avg_speed   = max(10, 65 - vehicle_count * 0.8)
    delay_index = max(0,  vehicle_count / 4.5)

    X = pd.DataFrame([[
        vehicle_count,
        hour,
        day_of_week,
        is_weekend,
        avg_speed,
        delay_index,
    ]], columns=[
        "vehicle_count",
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "avg_speed_kmh",
        "delay_index",
    ])

    try:
        pred_idx    = int(model.predict(X)[0])
        proba       = model.predict_proba(X)[0]
        confidence  = round(float(proba[pred_idx]) * 100, 1)
    except Exception as e:
        print("❌ Model error:", e)
        return "Low", 15, 0.0

    congestion = LABEL_MAP.get(pred_idx, "Low")

    green_time = {"Low": 15, "Medium": 30, "High": 45}[congestion]

    return congestion, green_time, confidence
