# HealthGuard AI

A responsive educational health screening website built with Flask, JavaScript, SQLite, and a saved scikit-learn model. It combines model output with simple vital-sign rules and records screening history for signed-in users.

## Current capabilities

- Public landing page and responsive health check interface
- Account registration and sign-in with Werkzeug password hashing
- CSRF protection for forms and JSON mutations; login and sensitive routes have rate limits
- Per-account prediction and alert history, using SQLite and SQLAlchemy for accounts
- Saved Random Forest inference loaded once at process startup; it is never retrained during web requests
- Risk category chart (Chart.js), CSV history download, and client-side form submission
- Optional SMTP and Twilio delivery integrations
- `/healthz` application liveness endpoint

## Important model limits

The checked-in model is trained on synthetic data and estimates a demo risk category. It is not a diabetes or heart disease model and is not clinically validated. Do not use it to diagnose, triage, or make treatment decisions. Its reported probability is a model score, not a person's calibrated medical probability. The separate diabetes and heart disease models in the supplied project brief are not included because no documented datasets were supplied.

The current emergency contact form is not a verified-contact management system. Configure real notification credentials only for a controlled demonstration and do not enter real patient data. A simulated delivery is labeled as simulation in the page; it does not mean a message was sent.

## Windows setup

In PowerShell, first move to the project directory. This works even when the prompt starts in `C:\Users\DELL`:

```powershell
Set-Location 'D:\health-risk-predictor\health-risk-predictor'
python -m venv --system-site-packages .venv-system
.\.venv-system\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `SECRET_KEY` in `.env` to a long random value. If you want real notification delivery, fill in the SMTP or Twilio values there. Never commit `.env` or real credentials.

Start the application from the project directory:

```powershell
python app.py
```

Or, without changing directories or activating the environment, run it by absolute path:

```powershell
& 'D:\health-risk-predictor\health-risk-predictor\.venv-system\Scripts\python.exe' 'D:\health-risk-predictor\health-risk-predictor\app.py'
```

Open `http://127.0.0.1:5000/`, create an account, and sign in before submitting an assessment. Do not open `templates/index.html` directly or use a static HTML preview: Jinja and Flask's `url_for()` only run when Flask renders the template. If the saved model is missing, train it once with `python train_model.py` before starting Flask. The server does not train a model at startup, so web startup stays quick.

In VS Code, choose **Health Risk Predictor (Flask)** under Run and Debug. It runs the project's `app.py` with the correct working directory and opens the Flask URL.

For a local demo, the sample buttons only populate example vitals and do not add a fake emergency phone number. For production, do not use Flask's development server; set `APP_ENV=production`, a strong secret, set `SESSION_COOKIE_SECURE=1` behind HTTPS, and configure shared storage such as Redis for rate limits.

## Deploying the connected Flask app to Render

The frontend is served by Flask itself: `templates/index.html` is rendered at `/`, static files use Flask's `/static/...` route, and JavaScript calls same-origin endpoints such as `/api/predict`. Do not publish the `templates/` folder as a static site. The repository root for Render must be this nested `health-risk-predictor` directory.

1. Push this project to a GitHub repository. In Render, create a **Web Service** connected to that repository.
2. Set **Root Directory** to `health-risk-predictor`, **Build Command** to `pip install -r requirements.txt`, and **Start Command** to `gunicorn app:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT --timeout 120`. The included `Procfile` has the same command. The one-worker setting keeps this app's in-memory rate limiter consistent.
3. Set the health check path to `/healthz`.
4. Set these environment variables in Render: `APP_ENV=production`, `SECRET_KEY` to a newly generated random value, and `SESSION_COOKIE_SECURE=1`. Add SMTP/Twilio variables only if you configure those providers.
5. This app stores health records in SQLite. For records to survive deploys/restarts on Render, attach a persistent disk mounted at `/var/data` and set `DATABASE_URL=sqlite:////var/data/health.db`. Render's filesystem is otherwise ephemeral, and persistent disks require a paid web service. Do not deploy real health records to an ephemeral filesystem.
6. Deploy, then visit the Render URL and register an account. The frontend and API share the same origin, so no CORS configuration is needed.

For a quick presentation-only deployment without a persistent disk, use synthetic/demo data only; SQLite records can disappear on restart or redeploy. This project uses a synthetic screening model and does not yet verify emergency contacts, so it is not ready for real patient use.

## Configuration

Settings are read from environment variables and `.env`:

- `SECRET_KEY`
- `DATABASE_URL` (optional SQLite URL; non-SQLite databases are not supported yet)
- `SESSION_COOKIE_SECURE`
- `RATELIMIT_STORAGE_URI`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `ALERT_FROM`
- `TWILIO_SID`, `TWILIO_TOKEN`, `TWILIO_FROM`

## Project files

- `app.py` — Flask setup, prediction APIs, SQLite records, ownership filters
- `auth.py` — registration, login, logout
- `config.py`, `extensions.py`, `models.py` — settings, Flask extensions, SQLAlchemy account model
- `alerts.py` — SMTP, Twilio, and explicitly simulated delivery
- `model_utils.py`, `train_model.py` — demo model rules and synthetic-data training
- `templates/`, `static/` — website, forms, and Chart.js history summary
- `.env.example` — configuration template

## Current scope

This is a foundation, not the full platform described in the master prompt. It does not yet include verified emergency contacts, profile management, admin roles and pages, real diabetes/heart datasets and models, model comparison/evaluation pipelines, migrations, PDF reports, audit logs, or automated tests. Those need to be implemented before describing the project as production-ready or as satisfying the complete specification.
