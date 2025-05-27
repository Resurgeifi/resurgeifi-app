from flask import Blueprint, render_template, session, redirect, url_for, flash
from models import SessionLocal, User, JournalEntry
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import os
import qrcode
import io
import base64

profile_bp = Blueprint("profile", __name__)

@profile_bp.route("/profile")
def profile():
    user_id = session.get("user_id")
    db = SessionLocal()

    try:
        user = db.query(User).filter_by(id=user_id).first()

        if not user.resurgitag:
            from main import generate_resurgitag
            user.resurgitag = generate_resurgitag(user.display_name or "User")
            db.commit()

        clean_tag = user.resurgitag.lstrip("@")
        base_url = os.getenv("BASE_URL", "") or "http://localhost:5050"
        qr_data = f"{base_url}/profile/public/{clean_tag}"

        qr_img = qrcode.make(qr_data)
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        days_on_journey = (datetime.utcnow() - (user.journey_start_date or datetime.utcnow())).days

        return render_template(
            "profile.html", 
            user=user,
            resurgitag=user.resurgitag,
            points=user.points or 0,
            days_on_journey=days_on_journey,
            qr_code_base64=qr_code_base64
        )

    except SQLAlchemyError:
        db.rollback()
        flash("Something went wrong loading your profile. Please try again.")
        return redirect(url_for("auth.login"))
    finally:
        db.close()

@profile_bp.route("/profile/public/<resurgitag>")
def view_public_profile(resurgitag):
    db = SessionLocal()
    try:
        clean_tag = f"@{resurgitag.lstrip('@').lower()}"
        user = db.query(User).filter(User.resurgitag.ilike(clean_tag)).first()

        if not user:
            flash("No user found with that Resurgitag.")
            return render_template("not_found.html", message="This profile doesn't exist."), 404

        return render_template("public_profile.html", friend=user, current_time=datetime.utcnow())

    finally:
        db.close()
