import os
import qrcode
import io
import base64
from datetime import datetime
from flask import Blueprint, render_template, session, redirect, url_for, flash
from models import User
from sqlalchemy.exc import SQLAlchemyError
from db_session import SessionLocal

# ✅ Fix: Declare the Blueprint
profile_bp = Blueprint("profile", __name__)

@profile_bp.route("/profile")
def profile():
    user_id = session.get("user_id")
    db = SessionLocal()

    try:
        user = db.query(User).filter_by(id=user_id).first()
        
        if not user or not user.resurgitag:
            flash("Resurgitag missing — please contact support.", "error")
            return redirect(url_for("menu"))

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


