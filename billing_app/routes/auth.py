from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import db
from models.core import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

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


@auth_bp.route("/biometric/register", methods=["POST"])
@login_required
def biometric_register():
    data = request.get_json(silent=True) or {}
    credential_id = data.get("credential_id", "").strip()
    if not credential_id:
        return jsonify({"success": False, "error": "Invalid credential data"}), 400

    current_user.biometric_credential = credential_id
    db.session.commit()
    return jsonify({"success": True, "message": "Biometric login registered successfully on this device!"})


@auth_bp.route("/biometric/login", methods=["POST"])
def biometric_login():
    data = request.get_json(silent=True) or {}
    credential_id = data.get("credential_id", "").strip()
    username = data.get("username", "").strip().lower()

    user = None
    if credential_id:
        user = User.query.filter_by(biometric_credential=credential_id, active=True).first()

    if not user and username:
        user = User.query.filter((User.username == username) | (User.email == username), User.active == True).first()

    if user:
        login_user(user, remember=True)
        return jsonify({"success": True, "redirect": url_for("main.dashboard")})

    return jsonify({"success": False, "error": "Biometric verification not matched. Please log in with password first to enable biometric login."}), 401


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not username or not password:
            flash("All fields are required.", "danger")
            return render_template("auth/register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("auth/register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("auth/register.html")

        if User.query.filter_by(username=username).first():
            flash("Username is already taken. Please choose another.", "danger")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("Email is already registered. Please log in.", "danger")
            return render_template("auth/register.html")

        user_count = User.query.count()
        role = "admin" if user_count == 0 else "staff"

        new_user = User(
            name=name,
            email=email,
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
            active=True,
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash(f"Account created successfully! Welcome, {name}.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


