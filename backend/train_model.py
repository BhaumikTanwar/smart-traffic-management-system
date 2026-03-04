import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
import joblib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

dataset_path = os.path.join(BASE_DIR, "dataset.csv")

df = pd.read_csv(dataset_path)

# convert weather to numbers
df["weather"] = df["weather"].astype("category").cat.codes

# convert congestion level to numbers
df["congestion_level"] = df["congestion_level"].astype("category").cat.codes

# select features
X = df[[
    "vehicle_count",
    "avg_speed_kmph",
    "lane_occupancy_percent",
    "weather",
    "congestion_level"
]]

# target (future traffic)
y = df["vehicle_count"]

# split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# train model
model = RandomForestRegressor(n_estimators=100)

model.fit(X_train, y_train)

# save model
joblib.dump(model, "traffic_prediction_model.pkl")

print("Model trained and saved!")