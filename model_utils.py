"""Shared constants and helpers for training and serving the model."""

FEATURES = [
    "age", "gender", "bmi", "systolic_bp", "diastolic_bp", "glucose",
    "cholesterol", "heart_rate", "spo2", "smoker", "alcohol",
    "exercise_days", "family_history",
]

CLASSES = ["Low", "Moderate", "High"]

# (min, max) accepted by the API
RANGES = {
    "age": (1, 110),
    "gender": (0, 1),               # 0 = female, 1 = male
    "bmi": (10, 60),
    "systolic_bp": (60, 260),
    "diastolic_bp": (30, 160),
    "glucose": (30, 600),           # mg/dL, random/fasting
    "cholesterol": (80, 500),       # mg/dL, total
    "heart_rate": (25, 220),        # bpm
    "spo2": (60, 100),              # %
    "smoker": (0, 1),
    "alcohol": (0, 1),
    "exercise_days": (0, 7),
    "family_history": (0, 1),
}


def critical_vitals(d):
    """Rule-based red flags that need urgent attention regardless of the ML score."""
    flags = []
    if d["systolic_bp"] >= 180 or d["diastolic_bp"] >= 120:
        flags.append("Blood pressure is in the hypertensive-crisis range")
    if d["systolic_bp"] < 80:
        flags.append("Blood pressure is dangerously low")
    if d["glucose"] >= 300:
        flags.append("Blood glucose is very high")
    if d["glucose"] < 54:
        flags.append("Blood glucose is dangerously low")
    if d["spo2"] < 90:
        flags.append("Oxygen saturation is below 90%")
    if d["heart_rate"] > 130:
        flags.append("Resting heart rate is very fast")
    if d["heart_rate"] < 40:
        flags.append("Resting heart rate is very slow")
    return flags


def risk_factors(d):
    """Plain-language list of the inputs that push risk up (or help lower it)."""
    up, down = [], []
    if d["age"] >= 60:
        up.append("Age 60 or above")
    if d["bmi"] >= 30:
        up.append(f"BMI {d['bmi']:.1f} is in the obesity range")
    elif d["bmi"] >= 25:
        up.append(f"BMI {d['bmi']:.1f} is above the healthy range")
    if d["systolic_bp"] >= 140 or d["diastolic_bp"] >= 90:
        up.append(f"Blood pressure {d['systolic_bp']:.0f}/{d['diastolic_bp']:.0f} is high")
    elif d["systolic_bp"] >= 130 or d["diastolic_bp"] >= 85:
        up.append(f"Blood pressure {d['systolic_bp']:.0f}/{d['diastolic_bp']:.0f} is slightly raised")
    if d["glucose"] >= 126:
        up.append(f"Glucose {d['glucose']:.0f} mg/dL is in the diabetic range")
    elif d["glucose"] >= 100:
        up.append(f"Glucose {d['glucose']:.0f} mg/dL is above normal")
    if d["cholesterol"] >= 240:
        up.append(f"Total cholesterol {d['cholesterol']:.0f} mg/dL is high")
    elif d["cholesterol"] >= 200:
        up.append(f"Total cholesterol {d['cholesterol']:.0f} mg/dL is borderline")
    if d["spo2"] < 95:
        up.append(f"Oxygen saturation {d['spo2']:.0f}% is low")
    if d["heart_rate"] > 100:
        up.append("Resting heart rate is above 100 bpm")
    if d["smoker"]:
        up.append("Smoking")
    if d["alcohol"]:
        up.append("Regular alcohol use")
    if d["family_history"]:
        up.append("Family history of heart disease or diabetes")
    if d["exercise_days"] <= 1:
        up.append("Little or no weekly exercise")
    if d["exercise_days"] >= 4:
        down.append("Exercising 4 or more days a week")
    if not d["smoker"]:
        down.append("Non-smoker")
    return up, down


def advice_for(level):
    if level == "High":
        return [
            "Book an appointment with a doctor in the next few days.",
            "Get a full check-up: blood pressure, blood sugar, lipid profile and ECG.",
            "Cut salt, sugar and fried food, and stop smoking if you smoke.",
        ]
    if level == "Moderate":
        return [
            "Plan a routine check-up in the next 1 to 3 months.",
            "Aim for 30 minutes of brisk walking on most days.",
            "Recheck your blood pressure and blood sugar regularly.",
        ]
    return [
        "Keep up your current habits.",
        "Do a basic health check once a year.",
        "Stay active and keep a balanced diet.",
    ]
