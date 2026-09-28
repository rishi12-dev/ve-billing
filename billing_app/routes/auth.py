from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from models.core import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("identity", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))
        user = User.query.filter((User.email == identity) | (User.username == identity)).first()
        if user and user.active and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            return redirect(url_for("main.dashboard"))
        flash("Invalid login details.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
