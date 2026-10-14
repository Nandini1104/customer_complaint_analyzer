from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from analysis.sentiment_analyzer import get_analyzer
from models import Setting, db

bp = Blueprint("settings", __name__)


def current_api_key():
    return current_app.config["API_KEY"] or Setting.get("api_key")


@bp.route("/settings")
@login_required
def settings():
    analyzer = get_analyzer()
    return render_template("settings.html", auto_category=Setting.get("auto_category", "1") == "1",
                           api_key=current_api_key(), key_from_env=bool(current_app.config["API_KEY"]),
                           model=analyzer.meta)


@bp.route("/settings/preferences", methods=["POST"])
@login_required
def save_preferences():
    Setting.set("auto_category", "1" if request.form.get("auto_category") else "0")
    flash("Preferences saved.", "success")
    return redirect(url_for("settings.settings"))


@bp.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    old, new, confirm = (request.form.get(k, "") for k in ("old_password", "new_password", "confirm_password"))
    if not current_user.check_password(old):
        flash("Current password is incorrect.", "danger")
    elif len(new) < 8:
        flash("New password must be at least 8 characters.", "danger")
    elif new != confirm:
        flash("New passwords do not match.", "danger")
    else:
        current_user.set_password(new)
        db.session.commit()
        flash("Password changed.", "success")
    return redirect(url_for("settings.settings"))


@bp.route("/settings/retrain", methods=["POST"])
@login_required
def retrain():
    try:
        meta = get_analyzer().retrain()
        flash(f"Model retrained on {meta['samples']} samples (cross-validated accuracy {meta['cv_accuracy']:.0%}).", "success")
    except Exception:
        flash("Retraining failed. Check data/training_data.csv.", "danger")
    return redirect(url_for("settings.settings"))


@bp.route("/settings/api-key", methods=["POST"])
@login_required
def regenerate_key():
    import secrets
    if current_app.config["API_KEY"]:
        flash("The API key is set by the API_KEY environment variable and cannot be regenerated here.", "warning")
    else:
        Setting.set("api_key", secrets.token_urlsafe(24))
        flash("New API key generated. Update your integrations.", "success")
    return redirect(url_for("settings.settings"))
