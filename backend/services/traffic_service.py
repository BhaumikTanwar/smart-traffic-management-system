"""
traffic_service.py
------------------
- SQLite logging via db_service
- Stronger future prediction using linear regression on history
- Clean separation of simulation vs video logic
- STOP_VIDEO flag management
"""

import time
import os
import random
import math

from services.video_service import detect_vehicles_from_video, release_video
from services.model_service  import predict_traffic
from services.db_service     import log_traffic, init_db

# ── Paths ──────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
VIDEO_PATH   = os.path.join(PROJECT_ROOT, "backend", "uploaded_video.mp4")

# ── Global flags ───────────────────────────────────────
STOP_VIDEO = False

# ── History buffer ─────────────────────────────────────
traffic_history = []   # last 10 vehicle counts
MAX_HISTORY     = 10


# ── Future prediction (linear regression) ─────────────
def predict_future(history: list) -> int:
    """
    Fits a simple linear trend over the history window and
    extrapolates one step ahead. More accurate than the old
    first/last difference method.
    """
    n = len(history)
    if n == 0:
        return 0
    if n == 1:
        return history[0]

    # least-squares slope
    x_mean = (n - 1) / 2
    y_mean = sum(history) / n
    numerator   = sum((i - x_mean) * (history[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    slope = numerator / denominator if denominator else 0
    next_val = history[-1] + slope

    return max(int(round(next_val)), 0)


# ── Main status function ───────────────────────────────
def get_traffic_status(mode: str) -> dict:
    global STOP_VIDEO, traffic_history

    # ── Mode guard ────────────────────────────────────
    if mode != "video":
        STOP_VIDEO = True
        release_video()
    else:
        STOP_VIDEO = False

    # ── Vehicle count ─────────────────────────────────
    if mode == "video":
        if not os.path.exists(VIDEO_PATH):
            return {
                "timestamp":    time.strftime("%H:%M:%S"),
                "current_mode": mode,
                "video_ready":  False,
                "roads":        []
            }
        vehicle_count = detect_vehicles_from_video(VIDEO_PATH)

    else:
        # Simulation: gentle random walk so the chart looks realistic
        base = traffic_history[-1] if traffic_history else 20
        delta = random.randint(-5, 8)
        vehicle_count = max(1, min(80, base + delta))

    # ── ML prediction ─────────────────────────────────
    congestion, green_time = predict_traffic(vehicle_count)

    # ── History ───────────────────────────────────────
    traffic_history.append(vehicle_count)
    if len(traffic_history) > MAX_HISTORY:
        traffic_history = traffic_history[-MAX_HISTORY:]

    # ── Future prediction ─────────────────────────────
    future_vehicle  = predict_future(traffic_history)
    future_cong, _  = predict_traffic(future_vehicle)

    # ── Log to SQLite ─────────────────────────────────
    try:
        log_traffic(mode, vehicle_count, congestion, future_cong, green_time)
    except Exception as e:
        print("⚠️  DB log error:", e)

    # ── Response ──────────────────────────────────────
    return {
        "timestamp":    time.strftime("%H:%M:%S"),
        "current_mode": mode,
        "video_ready":  True,
        "roads": [{
            "vehicle_count":       vehicle_count,
            "congestion_level":    congestion,
            "future_congestion":   future_cong,
            "adaptive_green_time": green_time
        }]
    }
