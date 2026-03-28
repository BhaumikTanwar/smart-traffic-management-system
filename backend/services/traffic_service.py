"""
traffic_service.py
------------------
- Thread-safe global state (Lock on all mutable globals)
- Passes confidence from model_service through to the response
- Improved linear-regression forecast (same logic, now using full history)
- Cleaner simulation random walk
"""

import time
import os
import random
import threading

from services.video_service  import detect_vehicles_from_video, release_video
from services.model_service  import predict_traffic
from services.db_service     import log_traffic, init_db

# ── Paths ──────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
VIDEO_PATH   = os.path.join(PROJECT_ROOT, "backend", "uploaded_video.mp4")

# ── Thread-safe state ──────────────────────────────────
_state_lock     = threading.Lock()
_STOP_VIDEO     = False
_traffic_history: list[int] = []
MAX_HISTORY     = 20          # longer window → steadier forecast

# ── Public flag for video_service ─────────────────────
# Read by video_service without locking (acceptable: single bool read is atomic in CPython)
STOP_VIDEO = False


def _set_stop_video(val: bool):
    global STOP_VIDEO, _STOP_VIDEO
    with _state_lock:
        _STOP_VIDEO = val
    STOP_VIDEO = val     # keep the module-level name in sync


# ── Future prediction (linear regression) ─────────────
def _predict_future(history: list) -> int:
    n = len(history)
    if n == 0:
        return 0
    if n == 1:
        return history[0]

    x_mean = (n - 1) / 2
    y_mean = sum(history) / n
    num    = sum((i - x_mean) * (history[i] - y_mean) for i in range(n))
    den    = sum((i - x_mean) ** 2 for i in range(n))
    slope  = num / den if den else 0

    return max(0, int(round(history[-1] + slope)))


# ── Main status function ───────────────────────────────
def get_traffic_status(mode: str) -> dict:
    global _traffic_history

    # ── Mode guard ────────────────────────────────────
    if mode != "video":
        _set_stop_video(True)
        release_video()
    else:
        _set_stop_video(False)

    # ── Vehicle count ─────────────────────────────────
    if mode == "video":
        if not os.path.exists(VIDEO_PATH):
            return {
                "timestamp":    time.strftime("%H:%M:%S"),
                "current_mode": mode,
                "video_ready":  False,
                "roads":        [],
            }
        vehicle_count = detect_vehicles_from_video(VIDEO_PATH)
    else:
        with _state_lock:
            base = _traffic_history[-1] if _traffic_history else 20
        delta         = random.randint(-5, 8)
        vehicle_count = max(1, min(80, base + delta))

    # ── ML prediction (now returns confidence too) ────
    congestion, green_time, confidence = predict_traffic(vehicle_count)

    # ── Update history ────────────────────────────────
    with _state_lock:
        _traffic_history.append(vehicle_count)
        if len(_traffic_history) > MAX_HISTORY:
            _traffic_history = _traffic_history[-MAX_HISTORY:]
        history_snapshot = list(_traffic_history)

    # ── Future prediction ─────────────────────────────
    future_vehicle          = _predict_future(history_snapshot)
    future_cong, _, fut_conf = predict_traffic(future_vehicle)

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
            "vehicle_count":        vehicle_count,
            "congestion_level":     congestion,
            "congestion_confidence": confidence,      # NEW
            "future_congestion":    future_cong,
            "future_confidence":    fut_conf,          # NEW
            "adaptive_green_time":  green_time,
        }],
    }
