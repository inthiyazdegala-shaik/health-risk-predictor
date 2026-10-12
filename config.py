"""Environment-backed application settings."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "local-development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'health.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    WTF_CSRF_TIME_LIMIT = 3600
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
