"""Shared Flask extensions, initialized by the application factory."""
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
