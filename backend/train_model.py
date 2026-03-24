import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib

# -----------------------------
# Load dataset
# -----------------------------
df = pd.read_csv("dataset.csv")

# -----------------------------
# Clean labels
# -----------------------------
df['congestion_level'] = df['congestion_level'].astype(str).str.strip().str.capitalize()

df['congestion_level'] = df['congestion_level'].map({
    'Low': 0,
    'Medium': 1,
    'High': 2
})

df = df.dropna(subset=['congestion_level'])

# -----------------------------
# Features (IMPORTANT CHANGE)
# -----------------------------
features = ['vehicle_count', 'avg_speed_kmh', 'delay_index']

X = df[features]
y = df['congestion_level']

# -----------------------------
# Split
# -----------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y  # 🔥 important
)

# -----------------------------
# Model (tuned)
# -----------------------------
model = RandomForestClassifier(
    n_estimators=300,
    max_depth=10,
    random_state=42
)

model.fit(X_train, y_train)

# -----------------------------
# Accuracy
# -----------------------------
preds = model.predict(X_test)
accuracy = accuracy_score(y_test, preds)

print("✅ Accuracy:", round(accuracy * 100, 2), "%")

# -----------------------------
# Save
# -----------------------------
joblib.dump(model, "traffic_model.pkl")

print("💾 Model saved")