"""Registration and session routes."""
import re
from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from extensions import db, limiter
from models import User

auth = Blueprint("auth", __name__)


@auth.get("/register")
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("register.html")


@auth.post("/register")
@limiter.limit("5 per hour")
def register():
    name = request.form.get("name", "").strip()[:80]
    email = request.form.get("email", "").strip().lower()[:254]
    password = request.form.get("password", "")
    if not name or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        flash("Enter your name and a valid email address.", "error")
        return render_template("register.html"), 400
    if len(password) < 12:
        flash("Use a password with at least 12 characters.", "error")
        return render_template("register.html"), 400
    if len(password) > 128:
        flash("Password must be 128 characters or fewer.", "error")
        return render_template("register.html"), 400
    if User.query.filter(func.lower(User.email) == email).first():
        flash("An account with that email already exists.", "error")
        return render_template("register.html"), 409
    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return redirect(url_for("index"))


@auth.get("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html")


@auth.post("/login")
@limiter.limit("10 per minute")
def login():
    email = request.form.get("email", "").strip().lower()[:254]
    password = request.form.get("password", "")
    user = User.query.filter(func.lower(User.email) == email).first()
    if not user or not user.check_password(password):
        flash("Email or password is incorrect.", "error")
        return render_template("login.html"), 401
    login_user(user, remember=False, fresh=True)
    next_url = request.args.get("next", "")
    candidate = urljoin(request.host_url, next_url)
    if urlparse(candidate).netloc != urlparse(request.host_url).netloc:
        candidate = url_for("index")
    return redirect(candidate)


@auth.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))
