"""
train_model.py
--------------
Trains a RandomForestClassifier on the dataset with:
  - Real independent features (hour, day_of_week, is_weekend)
  - Stratified k-fold cross-validation
  - Confusion matrix + per-class F1 report
  - Feature importance breakdown
  - Saves model as traffic_model.pkl
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder

# ── Load dataset ───────────────────────────────────────
df = pd.read_csv("dataset.csv")

df["congestion_level"] = (
    df["congestion_level"].astype(str).str.strip().str.capitalize()
)

label_map = {"Low": 0, "Medium": 1, "High": 2}
df["congestion_label"] = df["congestion_level"].map(label_map)
df = df.dropna(subset=["congestion_label"])

print(f"Dataset: {len(df)} rows")
print("Class distribution:")
print(df["congestion_level"].value_counts())
print()

# ── Features ───────────────────────────────────────────
# These are now genuine independent inputs — hour and day_of_week
# carry real predictive signal beyond just vehicle_count.
FEATURES = [
    "vehicle_count",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "avg_speed_kmh",
    "delay_index",
]

X = df[FEATURES]
y = df["congestion_label"]

# ── Train / test split ─────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ── Model ──────────────────────────────────────────────
model = RandomForestClassifier(
    n_estimators=400,
    max_depth=12,
    min_samples_leaf=3,
    class_weight="balanced",   # handles any class imbalance
    random_state=42,
    n_jobs=-1,
)

# ── Cross-validation ───────────────────────────────────
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="f1_weighted")
print(f"5-fold CV F1 (weighted): {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
print()

# ── Train on full training set ─────────────────────────
model.fit(X_train, y_train)

# ── Evaluation ─────────────────────────────────────────
preds = model.predict(X_test)
acc   = accuracy_score(y_test, preds)

print(f"Test accuracy:  {round(acc * 100, 2)}%")
print()
print("Classification report:")
target_names = ["Low", "Medium", "High"]
print(classification_report(y_test, preds, target_names=target_names))

print("Confusion matrix (rows=actual, cols=predicted):")
cm = confusion_matrix(y_test, preds)
header = "        " + "  ".join(f"{n:>8}" for n in target_names)
print(header)
for name, row in zip(target_names, cm):
    print(f"{name:>8}  " + "  ".join(f"{v:>8}" for v in row))
print()

# ── Feature importance ─────────────────────────────────
print("Feature importances:")
for feat, imp in sorted(
    zip(FEATURES, model.feature_importances_), key=lambda x: -x[1]
):
    bar = "█" * int(imp * 40)
    print(f"  {feat:<18} {imp:.3f}  {bar}")
print()

# ── Save ───────────────────────────────────────────────
joblib.dump(model, "traffic_model.pkl")
print("💾 Model saved → traffic_model.pkl")
