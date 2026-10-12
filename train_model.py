"""Create a synthetic dataset and train the risk model.

Run:  python train_model.py
The model is written to model/risk_model.joblib.

NOTE: the data is synthetic (generated from medical rules of thumb plus noise),
so this is a learning/demo project, not a clinical tool. To use real data,
replace make_dataset() with pd.read_csv(...) using the same columns.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import train_test_split

from model_utils import FEATURES, CLASSES

MODEL_PATH = Path(__file__).parent / "model" / "risk_model.joblib"
METRICS_PATH = Path(__file__).parent / "model" / "metrics.json"


def make_dataset(n=8000, seed=42):
    rng = np.random.default_rng(seed)
    age = np.clip(rng.normal(45, 15, n), 18, 90)
    gender = rng.integers(0, 2, n)
    bmi = np.clip(rng.normal(26, 5, n), 15, 45)
    sys_bp = np.clip(rng.normal(120 + 0.3 * (age - 45) + 0.6 * (bmi - 26), 15, n), 85, 210)
    dia_bp = np.clip(sys_bp * 0.62 + rng.normal(0, 6, n), 55, 130)
    glucose = np.clip(rng.normal(98 + 0.4 * (bmi - 26) + 0.2 * (age - 45), 25, n), 60, 350)
    chol = np.clip(rng.normal(190 + 0.5 * (age - 45) + 1.0 * (bmi - 26), 35, n), 110, 340)
    hr = np.clip(rng.normal(75, 11, n), 45, 130)
    spo2 = np.clip(rng.normal(97.5, 1.5, n), 82, 100)
    smoker = (rng.random(n) < 0.22).astype(int)
    alcohol = (rng.random(n) < 0.30).astype(int)
    exercise = rng.integers(0, 8, n)
    family = (rng.random(n) < 0.25).astype(int)

    score = (
        np.maximum(0, (age - 40) / 10)
        + np.maximum(0, bmi - 25) * 0.18
        + np.maximum(0, sys_bp - 120) * 0.045
        + np.maximum(0, dia_bp - 80) * 0.02
        + np.maximum(0, glucose - 100) * 0.03
        + np.maximum(0, chol - 200) * 0.015
        + np.maximum(0, hr - 85) * 0.02
        + np.maximum(0, 95 - spo2) * 0.5
        + smoker * 1.5 + alcohol * 0.5 + family * 1.0
        - exercise * 0.25
        + gender * 0.3
        + rng.normal(0, 0.6, n)
    )
    lo, hi = np.quantile(score, [0.50, 0.85])
    label = np.where(score < lo, 0, np.where(score < hi, 1, 2))

    df = pd.DataFrame({
        "age": age, "gender": gender, "bmi": bmi, "systolic_bp": sys_bp,
        "diastolic_bp": dia_bp, "glucose": glucose, "cholesterol": chol,
        "heart_rate": hr, "spo2": spo2, "smoker": smoker, "alcohol": alcohol,
        "exercise_days": exercise, "family_history": family, "risk": label,
    })
    return df


def train():
    df = make_dataset()
    X, y = df[FEATURES], df["risk"]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    model = RandomForestClassifier(
        n_estimators=250, max_depth=12, min_samples_leaf=3,
        class_weight="balanced", random_state=42, n_jobs=-1)
    model.fit(X_tr, y_tr)

    pred = model.predict(X_te)
    acc = accuracy_score(y_te, pred)
    print(f"Test accuracy: {acc:.3f}")
    print(classification_report(y_te, pred, target_names=CLASSES))

    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES, "classes": CLASSES}, MODEL_PATH)
    importances = dict(sorted(
        zip(FEATURES, map(float, model.feature_importances_)),
        key=lambda kv: -kv[1]))
    METRICS_PATH.write_text(json.dumps({"accuracy": round(acc, 4),
                                        "feature_importance": importances}, indent=2))
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    train()
