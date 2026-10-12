"""AI Health Risk Prediction System - Flask backend."""
import json
import math
import os
import sqlite3
import csv
import io
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, g, jsonify, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError
from sqlalchemy.engine import make_url

import alerts
from model_utils import (CLASSES, FEATURES, RANGES, advice_for, critical_vitals,
                         risk_factors)
from auth import auth
from config import Config
from extensions import csrf, db as orm_db, limiter, login_manager
from models import User

BASE = Path(__file__).parent
DB_PATH = BASE / "health.db"
MODEL_PATH = BASE / "model" / "risk_model.joblib"

app = Flask(__name__)
app.config.from_object(Config)
database_url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
if database_url.drivername != "sqlite" or not database_url.database:
    raise RuntimeError("This version stores health records with SQLite; set DATABASE_URL to a SQLite database.")
configured_db = Path(database_url.database)
DB_PATH = configured_db if configured_db.is_absolute() else Path(app.instance_path) / configured_db
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if os.getenv("APP_ENV", "development").lower() == "production" and app.config["SECRET_KEY"] == "local-development-only-change-me":
    raise RuntimeError("Set a strong SECRET_KEY in production before starting the app.")
orm_db.init_app(app)
csrf.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login_page"
limiter.init_app(app)
app.register_blueprint(auth)


@app.errorhandler(CSRFError)
def csrf_error(exc):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Your session security token expired. Refresh the page and try again."}), 400
    return "The form expired. Refresh the page and try again.", 400


@app.errorhandler(429)
def rate_limit_error(exc):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Too many requests. Please wait a little and try again."}), 429
    return "Too many requests. Please wait a little and try again.", 429


@login_manager.user_loader
def load_user(user_id):
    try:
        return orm_db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Sign in to access your health records."}), 401
    return redirect(url_for("auth.login_page", next=request.full_path))

# ---------- model ----------
if not MODEL_PATH.exists():
    raise RuntimeError(f"Prediction model is missing at {MODEL_PATH}. Run `python train_model.py` once before starting the server.")
bundle = joblib.load(MODEL_PATH)
MODEL = bundle["model"]
MODEL_FEATURES = bundle.get("features", FEATURES)
MODEL_CLASSES = bundle.get("classes", CLASSES)
if MODEL_FEATURES != FEATURES:
    raise RuntimeError("The saved model feature order does not match model_utils.FEATURES. Retrain the model.")


# ---------- database ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            name TEXT,
            inputs TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            probabilities TEXT NOT NULL,
            emergency INTEGER NOT NULL,
            reasons TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            prediction_id INTEGER,
            contact_name TEXT,
            contact_phone TEXT,
            contact_email TEXT,
            trigger TEXT NOT NULL,
            delivery TEXT NOT NULL,
            message TEXT NOT NULL
        );
        """)
        # SQLite migration for databases created by the earlier demo version.
        for table in ("predictions", "alerts"):
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if "user_id" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_predictions_user_created "
                      "ON predictions(user_id, created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_user_created "
                      "ON alerts(user_id, created_at DESC)")


with app.app_context():
    orm_db.create_all()
    init_db()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- helpers ----------
def parse_inputs(payload):
    """Validate and convert the submitted form values. Returns (data, errors)."""
    data, errors = {}, {}
    for f in FEATURES:
        raw = payload.get(f)
        try:
            val = float(raw)
        except (TypeError, ValueError):
            errors[f] = "Enter a number"
            continue
        if not math.isfinite(val):
            errors[f] = "Enter a finite number"
            continue
        lo, hi = RANGES[f]
        if not lo <= val <= hi:
            errors[f] = f"Must be between {lo} and {hi}"
        data[f] = val
    if "systolic_bp" in data and "diastolic_bp" in data \
            and data["diastolic_bp"] >= data["systolic_bp"]:
        errors["diastolic_bp"] = "Diastolic must be lower than systolic"
    return data, errors


def contact_from(payload):
    c = payload.get("contact") or {}
    if not isinstance(c, dict):
        c = {}
    return {
        "name": str(c.get("name", "")).strip()[:80],
        "phone": str(c.get("phone", "")).strip()[:20],
        "email": str(c.get("email", "")).strip()[:120],
        "consent": c.get("consent") is True,
    }


def send_and_log(prediction_id, contact, message, trigger):
    delivery = alerts.dispatch(contact, message)
    db().execute(
        "INSERT INTO alerts (created_at, prediction_id, contact_name, contact_phone,"
        " contact_email, trigger, delivery, message, user_id) VALUES (?,?,?,?,?,?,?,?,?)",
        (now(), prediction_id, contact["name"], contact["phone"], contact["email"],
         trigger, json.dumps(delivery), message, int(current_user.get_id())))
    db().commit()
    return delivery


# ---------- routes ----------
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "health-risk-screening"})


@app.post("/api/predict")
@login_required
@limiter.limit("30 per hour")
def predict():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "Request body must be a JSON object."}), 400
    data, errors = parse_inputs(payload)
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    row = pd.DataFrame([[data[f] for f in FEATURES]], columns=FEATURES)
    try:
        raw_probs = MODEL.predict_proba(row)[0]
        class_names = [MODEL_CLASSES[int(label)] for label in MODEL.classes_]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        app.logger.exception("Loaded model is incompatible with prediction input")
        return jsonify({"ok": False, "error": "Prediction model is unavailable. Retrain it and restart the app."}), 503
    probs = {name: float(prob) for name, prob in zip(class_names, raw_probs)}
    if set(probs) != set(CLASSES) or not all(math.isfinite(p) for p in probs.values()):
        return jsonify({"ok": False, "error": "Prediction model returned invalid classes or probabilities."}), 503
    level = max(CLASSES, key=lambda name: probs[name])
    probabilities = {name: round(probs[name], 4) for name in CLASSES}

    red_flags = critical_vitals(data)
    # A critical vital sign overrides the model: never tell someone with
    # a crisis-level reading that their risk is "Low".
    if red_flags:
        level = "High"
    # Only critical vitals trigger an automatic alert. A "High" model score alone
    # shows advice, so contacts are not alarmed by a non-crisis reading.
    emergency = bool(red_flags)

    up, down = risk_factors(data)
    name = str(payload.get("name", "")).strip()[:80]
    reasons = red_flags or up[:3]

    cur = db().execute(
        "INSERT INTO predictions (created_at, name, inputs, risk_level, probabilities,"
        " emergency, reasons, user_id) VALUES (?,?,?,?,?,?,?,?)",
        (now(), name, json.dumps(data), level, json.dumps(probabilities),
         int(emergency), json.dumps(reasons), int(current_user.get_id())))
    db().commit()
    prediction_id = cur.lastrowid

    alert_info = None
    contact = contact_from(payload)
    if emergency:
        if contact["consent"] and (contact["phone"] or contact["email"]):
            msg = alerts.build_message(name, level, reasons, data)
            alert_info = {"delivery": send_and_log(prediction_id, contact, msg, "automatic")}
        else:
            alert_info = {"delivery": None, "message": "No contact alert was sent. Add a contact and give consent first."}

    return jsonify({
        "ok": True,
        "prediction_id": prediction_id,
        "risk_level": level,
        "probabilities": probabilities,
        "emergency": emergency,
        "red_flags": red_flags,
        "risk_factors": up,
        "protective_factors": down,
        "advice": advice_for(level),
        "alert": alert_info,
    })


@app.post("/api/alert")
@login_required
@limiter.limit("5 per hour")
def manual_alert():
    """SOS button: send an alert right now, even without a high-risk result."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "Request body must be a JSON object."}), 400
    contact = contact_from(payload)
    if not (contact["phone"] or contact["email"]):
        return jsonify({"ok": False, "error": "Add an emergency contact phone or email first."}), 400

    prediction_id = payload.get("prediction_id")
    if prediction_id is not None:
        try:
            prediction_id = int(prediction_id)
            if prediction_id < 1:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Prediction ID must be a positive integer."}), 400
    name = str(payload.get("name", "")).strip()[:80]
    message = f"EMERGENCY: {name or 'A user'} has pressed the SOS button and needs help. " \
              "Please contact them now. In India call 108 (ambulance) or 112."
    if prediction_id:
        row = db().execute("SELECT * FROM predictions WHERE id=? AND user_id=?",
                           (prediction_id, int(current_user.get_id()))).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Prediction was not found."}), 404
        message = (f"Manual SOS request from {name or row['name'] or 'a user'}. "
                   "Please contact them now. This request is not a diagnosis. "
                   "If they report severe symptoms, contact local emergency services.")
    delivery = send_and_log(prediction_id, contact, message, "manual SOS")
    return jsonify({"ok": True, "delivery": delivery})


@app.get("/api/history")
@login_required
def history():
    rows = db().execute(
        "SELECT id, created_at, name, risk_level, emergency FROM predictions "
        "WHERE user_id=? ORDER BY id DESC LIMIT 50", (int(current_user.get_id()),)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/history.csv")
@login_required
@limiter.limit("10 per hour")
def history_csv():
    rows = db().execute(
        "SELECT id, created_at, name, inputs, risk_level, probabilities, emergency, reasons "
        "FROM predictions WHERE user_id=? ORDER BY id DESC",
        (int(current_user.get_id()),)).fetchall()
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(("id", "created_at_utc", "name", "inputs_json", "screening_category",
                     "model_scores_json", "urgent_vital_flag", "reasons_json"))
    for row in rows:
        values = list(row)
        # Prevent spreadsheet formula execution when a CSV is opened in office software.
        name_value = str(values[2] or "")
        values[2] = "'" + name_value if name_value.startswith(("=", "+", "-", "@")) else name_value
        writer.writerow(values)
    response = make_response(stream.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=healthguard-history.csv"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/alerts")
@login_required
def alert_log():
    rows = db().execute(
        "SELECT id, created_at, contact_name, trigger, delivery FROM alerts "
        "WHERE user_id=? ORDER BY id DESC LIMIT 50", (int(current_user.get_id()),)).fetchall()
    return jsonify([{**dict(r), "delivery": json.loads(r["delivery"])} for r in rows])


if __name__ == "__main__":
    app.run(debug=False)
