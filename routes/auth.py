import time
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from models import User

bp = Blueprint("auth", __name__)

# Very small in-memory brute-force limiter: 5 failures per IP -> 15 minute lock.
FAILURES = {}
MAX_FAILURES, LOCK_SECONDS = 5, 15 * 60


def _blocked(ip):
    count, first = FAILURES.get(ip, (0, 0))
    if count >= MAX_FAILURES and time.time() - first < LOCK_SECONDS:
        return True
    if count >= MAX_FAILURES:
        FAILURES.pop(ip, None)
    return False


def _safe_next(target):
    """Only allow redirects to paths on this site."""
    if target and urlparse(target).netloc == "" and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("dashboard.index")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        if _blocked(ip):
            flash("Too many failed attempts. Please try again in 15 minutes.", "danger")
            return render_template("login.html"), 429
        user = User.query.filter_by(username=request.form.get("username", "").strip()).first()
        if user and user.check_password(request.form.get("password", "")):
            FAILURES.pop(ip, None)
            session.clear()                                  # new session on login
            login_user(user)
            return redirect(_safe_next(request.args.get("next")))
        count, first = FAILURES.get(ip, (0, time.time()))
        FAILURES[ip] = (count + 1, first)
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))
