from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from extensions import db
from models import User

premium_bp = Blueprint("premium", __name__)


@premium_bp.route("/premium")
@login_required
def premium_page():
    return render_template("premium.html")


@premium_bp.route("/premium/activate-demo", methods=["POST"])
@login_required
def activate_demo():
    user = db.session.get(User, current_user.id)
    if not user:
        flash("Could not update your account.", "error")
        return redirect(url_for("premium.premium_page"))

    if user.is_premium:
        flash("You already have Premium (demo).", "success")
    else:
        user.is_premium = True
        db.session.commit()
        if hasattr(current_user, "is_premium"):
            current_user.is_premium = True
        session.pop("premium_upsell_dismissed", None)
        flash("Premium activated (demo). Enjoy the full experience!", "success")

    nxt = (request.form.get("next") or request.args.get("next") or "").strip()
    if not nxt:
        nxt = request.referrer or url_for("quiz.home")
    if not nxt.startswith("/"):
        nxt = url_for("quiz.home")
    return redirect(nxt)
