import random
import time
from services.video_service import detect_vehicles_from_video

# Store last vehicle counts (simple memory)
previous_counts = {}


def generate_road_data(name, current_mode):
    global previous_counts

    # --------------------------
    # Mode Based Vehicle Count
    # --------------------------
    if current_mode == "video":
        vehicle_count = detect_vehicles_from_video()
    else:
        vehicle_count = random.randint(10, 120)

    # --------------------------
    # Congestion Logic
    # --------------------------
    if vehicle_count < 30:
        congestion = "Low"
        base_green = 30
    elif vehicle_count < 70:
        congestion = "Medium"
        base_green = 45
    else:
        congestion = "High"
        base_green = 60

    # --------------------------
    # Prediction Logic
    # --------------------------
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

    roads = [
        generate_road_data("Road A", current_mode),
        generate_road_data("Road B", current_mode),
        generate_road_data("Road C", current_mode),
        generate_road_data("Road D", current_mode),
    ]

    most_congested = max(roads, key=lambda x: x["vehicle_count"])

    # --------------------------
    # Adaptive Signal Control
    # --------------------------
    for road in roads:
        if road["road_name"] == most_congested["road_name"]:
            road["adaptive_green_time"] = road["base_green_time"] + 15
        else:
            road["adaptive_green_time"] = max(20, road["base_green_time"] - 5)

    return {
        "timestamp": time.strftime("%H:%M:%S"),
        "roads": roads,
        "most_congested_road": most_congested["road_name"]
    }
