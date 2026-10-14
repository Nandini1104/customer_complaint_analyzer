"""Entry point:  python app.py   ->  http://127.0.0.1:5000"""
import os
import secrets
from datetime import datetime

from flask import Flask, abort, jsonify, render_template, request, session
from flask_login import LoginManager
from werkzeug.exceptions import HTTPException

from analysis.category_detector import CATEGORIES
from config import Config
from models import Category, Setting, User, db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "database"), exist_ok=True)
    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify(success=False, error="Authentication required."), 401
        from flask import flash, redirect, url_for
        flash("Please sign in to continue.", "warning")
        return redirect(url_for("auth.login", next=request.path))

    # ---------- CSRF protection for browser forms (the API uses an API key instead) ----------
    @app.before_request
    def csrf_protect():
        if request.method in ("POST", "PUT", "DELETE") and not request.path.startswith("/api/"):
            sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not sent or sent != session.get("csrf_token"):
                abort(400)

    @app.context_processor
    def inject_globals():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return {"csrf_token": session["csrf_token"], "current_year": datetime.now().year}

    # ---------- template filters ----------
    badge_classes = {
        "New": "primary", "In Progress": "warning", "Resolved": "success", "Closed": "secondary",
        "Positive": "success", "Negative": "danger", "Neutral": "secondary",
        "Low": "secondary", "Medium": "warning", "High": "danger",
    }
    app.jinja_env.filters["badge"] = lambda value: badge_classes.get(value, "secondary")
    app.jinja_env.filters["dt"] = lambda v, fmt="%d %b %Y, %H:%M": v.strftime(fmt) if v else "-"
    app.jinja_env.filters["pct"] = lambda v: f"{(v or 0) * 100:.0f}%"
    app.jinja_env.filters["hours"] = lambda h: "-" if h is None else (f"{h:.1f} h" if h < 48 else f"{h / 24:.1f} days")

    # ---------- error pages (no tracebacks for users) ----------
    messages = {400: "The request was invalid or the form expired. Please go back and try again.",
                404: "That page could not be found.", 405: "That action is not allowed here.",
                413: "The uploaded file is too large (maximum 2 MB).",
                500: "Something went wrong on our side. Please try again."}

    def handle_error(error):
        code = (error.code or 500) if isinstance(error, HTTPException) else 500
        if code >= 500:
            app.logger.exception(error)
            db.session.rollback()
        text = messages.get(code, "Unexpected error.")
        if request.path.startswith("/api/"):
            return jsonify(success=False, error=text), code
        return render_template("error.html", code=code, message=text), code

    for code in messages:
        app.register_error_handler(code, handle_error)
    app.register_error_handler(Exception, handle_error)   # anything unexpected -> friendly 500 page

    from routes import register_blueprints
    register_blueprints(app)

    with app.app_context():
        initialize_database(app)
    return app


def initialize_database(app):
    """Create tables and seed categories, the admin user and the API key."""
    db.create_all()
    for name in CATEGORIES:
        if not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name))
    if not User.query.first():
        password = app.config["ADMIN_PASSWORD"] or secrets.token_urlsafe(9)
        admin = User(username=app.config["ADMIN_USERNAME"])
        admin.set_password(password)
        db.session.add(admin)
        if not app.config["ADMIN_PASSWORD"]:
            print("=" * 60)
            print(f"First run: admin login created -> username: {admin.username} password: {password}")
            print("Save this password now. Set ADMIN_PASSWORD to choose your own.")
            print("=" * 60)
    if not Setting.get("api_key") and not app.config["API_KEY"]:
        Setting.set("api_key", secrets.token_urlsafe(24))
    if Setting.get("auto_category") is None:
        Setting.set("auto_category", "1")
    db.session.commit()
    from analysis.sentiment_analyzer import get_analyzer
    get_analyzer()                                  # loads (or trains) the sentiment model


app = create_app()

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)), debug=False)
