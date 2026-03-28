"""
generate_data.py
----------------
Generates a realistic synthetic dataset with genuine independent features:
  - vehicle_count      : random, varies by time of day
  - hour_of_day        : 0-23
  - day_of_week        : 0=Monday … 6=Sunday
  - is_weekend         : 0 or 1
  - avg_speed_kmh      : noisy, inversely correlated with count
  - delay_index        : noisy, positively correlated with count
  - congestion_level   : Low / Medium / High  (label)

Unlike the old dataset, avg_speed and delay_index now include real noise
so they are not purely deterministic from vehicle_count.
"""

import pandas as pd
import random
import math

ROWS = 3000
random.seed(42)

# Rush hour profile: returns a multiplier for vehicle count given hour
def rush_multiplier(hour):
    # Morning rush 7-9, evening rush 17-19
    if 7 <= hour <= 9:
        return 1.6
    if 17 <= hour <= 19:
        return 1.8
    if 22 <= hour or hour <= 5:
        return 0.4   # night
    return 1.0

data = []

for _ in range(ROWS):
    hour        = random.randint(0, 23)
    day_of_week = random.randint(0, 6)
    is_weekend  = 1 if day_of_week >= 5 else 0

    # Weekend has less rush-hour effect
    mult = rush_multiplier(hour)
    if is_weekend:
        mult = max(0.5, mult * 0.7)

    base_count   = int(random.randint(5, 55) * mult)
    vehicle_count = max(1, min(90, base_count))

    # Speed: inversely correlated but with real noise
    avg_speed = max(5, 65 - vehicle_count * 0.8 + random.gauss(0, 6))
    avg_speed = round(min(80, avg_speed), 1)

    # Delay: positively correlated but with real noise
    delay_index = max(0, vehicle_count / 4.5 + random.gauss(0, 2.5))
    delay_index = round(delay_index, 2)

    # Label: based on vehicle_count with time-of-day influence + overlap
    if vehicle_count < 25:
        label = random.choices(["Low", "Medium"], weights=[0.82, 0.18])[0]
    elif vehicle_count < 50:
        label = random.choices(["Low", "Medium", "High"], weights=[0.12, 0.70, 0.18])[0]
    else:
        label = random.choices(["Medium", "High"], weights=[0.20, 0.80])[0]

    # Rush hours push toward High
    if mult >= 1.6 and label == "Medium" and random.random() < 0.35:
        label = "High"

    data.append([
        vehicle_count,
        hour,
        day_of_week,
        is_weekend,
        avg_speed,
        delay_index,
        label,
    ])

df = pd.DataFrame(data, columns=[
    "vehicle_count",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "avg_speed_kmh",
    "delay_index",
    "congestion_level",
])

df.to_csv("dataset.csv", index=False)
print(f"✅ Dataset created: {len(df)} rows")
print(df["congestion_level"].value_counts())
