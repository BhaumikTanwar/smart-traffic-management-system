import os
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import LabelEncoder

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "dataset.csv")

df = pd.read_csv(DATASET_PATH)

# -----------------------------
# Feature Engineering
# -----------------------------

# convert timestamp → hour
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["hour"] = df["timestamp"].dt.hour

# encode weather
weather_encoder = LabelEncoder()
df["weather"] = weather_encoder.fit_transform(df["weather"])

# encode congestion level
congestion_encoder = LabelEncoder()
df["congestion_level"] = congestion_encoder.fit_transform(df["congestion_level"])

# -----------------------------
# Features
# -----------------------------

X = df[
[
    "vehicle_count",
    "avg_speed_kmph",
    "lane_occupancy_percent",
    "hour"
]
]

y = df["congestion_level"]

# -----------------------------
# Train Test Split
# -----------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# -----------------------------
# Train Model
# -----------------------------

model = RandomForestClassifier(
    n_estimators=300,
    max_depth=15,
    class_weight="balanced",
    random_state=42
)

model.fit(X_train, y_train)

# -----------------------------
# Evaluate
# -----------------------------

preds = model.predict(X_test)

accuracy = accuracy_score(y_test, preds)

print("Model Accuracy:", accuracy)

# -----------------------------
# Save Model
# -----------------------------

MODEL_PATH = os.path.join(BASE_DIR, "traffic_congestion_model.pkl")

joblib.dump(
    {
        "model": model,
        "weather_encoder": weather_encoder,
        "congestion_encoder": congestion_encoder
    },
    MODEL_PATH
)
print(df.groupby("congestion_level")["vehicle_count"].describe())
print("Model saved successfully!")