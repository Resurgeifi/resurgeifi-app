from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import User
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import random
from db_session import SessionLocal

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not email or not password or not confirm_password:
            flash("Please fill in all fields.", "warning")
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("auth.register"))

        db = SessionLocal()
        try:
            existing_user = db.query(User).filter_by(email=email).first()
            if existing_user:
                flash("Account with that email already exists.", "error")
                return redirect(url_for("auth.login"))

            hashed_pw = generate_password_hash(password)

            new_user = User(
                email=email,
                password_hash=hashed_pw,
                nickname=None,
                display_name=None,
                theme_choice=None,
                consent=None,
                journey_start_date=None,
                timezone="America/New_York"
            )

            db.add(new_user)
            db.commit()

            session['user_id'] = new_user.id
            session['journey'] = "Not Selected"
            session['timezone'] = "America/New_York"

            flash("Registration successful. Let’s begin your journey.", "success")
            return redirect(url_for("onboarding.onboarding"))
        finally:
            db.close()

    return render_template("register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        db = SessionLocal()
        try:
            user = db.query(User).filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                session['journey'] = user.theme_choice or "Not Selected"
                session['timezone'] = user.timezone or "America/New_York"

                if not user.has_completed_onboarding:
                    return redirect(url_for("onboarding.onboarding"))

                flash("Login successful. Welcome back.", "success")
                return redirect(url_for("menu"))
            flash("Incorrect email or password.", "error")
        finally:
            db.close()

    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You’ve been logged out.")
    return redirect(url_for("auth.login"))

@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    message = ""
    db = SessionLocal()
    try:
        if request.method == "POST":
            email = request.form.get("email")
            user = db.query(User).filter_by(email=email).first()
            if user:
                reset_code = str(random.randint(100000, 999999))
                session["reset_code"] = reset_code
                session["reset_email"] = email

                msg = Message("Your Resurgifi Password Reset Code", recipients=[email])
                msg.body = f"Hi there,\n\nUse this code to reset your password: {reset_code}\n\n- The Resurgifi Team"
                from app import mail
                mail.send(msg)

                return redirect(url_for("auth.reset_confirm"))
            else:
                message = "No account found with that email."

        return render_template("reset_password.html", message=message)
    finally:
        db.close()

@auth_bp.route("/reset-confirm", methods=["GET", "POST"])
def reset_confirm():
    message = ""
    db = SessionLocal()
    try:
        if request.method == "POST":
            code_entered = request.form.get("reset_code")
            new_password = request.form.get("new_password")

            if code_entered == session.get("reset_code"):
                user = db.query(User).filter_by(email=session.get("reset_email")).first()
                if user:
                    user.password_hash = generate_password_hash(new_password)
                    db.commit()
                    session.pop("reset_code", None)
                    session.pop("reset_email", None)
                    flash("Your password has been reset. Please log in.")
                    return redirect(url_for("auth.login"))
                else:
                    message = "User not found."
            else:
                message = "Invalid code. Please try again."

        return render_template("reset_confirm.html", message=message)
    finally:
        db.close()
