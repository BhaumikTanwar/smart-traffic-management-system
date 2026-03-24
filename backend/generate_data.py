import pandas as pd
import random

data = []

for _ in range(1000):

    vehicle_count = random.randint(1, 60)

    # Add overlap between classes
    if vehicle_count < 20:
        congestion = random.choices(
            ["Low", "Medium"], weights=[0.8, 0.2]
        )[0]

    elif vehicle_count < 40:
        congestion = random.choices(
            ["Medium", "Low", "High"], weights=[0.7, 0.15, 0.15]
        )[0]

    else:
        congestion = random.choices(
            ["High", "Medium"], weights=[0.8, 0.2]
        )[0]

    # Add noise (IMPORTANT)
    avg_speed = max(5, 60 - vehicle_count + random.randint(-7, 7))
    delay = max(0, vehicle_count / 5 + random.uniform(-1.5, 1.5))

    data.append([
        vehicle_count,
        avg_speed,
        delay,
        congestion
    ])

df = pd.DataFrame(data, columns=[
    "vehicle_count",
    "avg_speed_kmh",
    "delay_index",
    "congestion_level"
])

df.to_csv("dataset.csv", index=False)

print("✅ Improved dataset created")