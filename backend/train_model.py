import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib

# -----------------------------
# Load dataset
# -----------------------------

data = pd.read_csv("dataset.csv")

# -----------------------------
# Create additional features
# -----------------------------

def generate_features(row):
    vc = row["vehicle_count"]

    if vc < 10:
        avg_speed = 50
        lane_occupancy = 30
    elif vc < 25:
        avg_speed = 35
        lane_occupancy = 60
    else:
        avg_speed = 20
        lane_occupancy = 90

    weather = 0

    return pd.Series([avg_speed, lane_occupancy, weather])

data[["avg_speed", "lane_occupancy", "weather"]] = data.apply(generate_features, axis=1)

# -----------------------------
# Features & Labels
# -----------------------------

X = data[["vehicle_count", "avg_speed", "lane_occupancy", "weather"]]
y = data["congestion_level"]

# -----------------------------
# Train model
# -----------------------------

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)

# -----------------------------
# Save model
# -----------------------------

joblib.dump(model, "traffic_congestion_model.pkl")

print("✅ Model trained and saved successfully!")