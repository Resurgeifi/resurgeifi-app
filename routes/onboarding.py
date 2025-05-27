from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from models import SessionLocal, User
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

onboarding_bp = Blueprint("onboarding", __name__)

@onboarding_bp.route("/onboarding", methods=["GET"])
def onboarding():
    return render_template("onboarding.html")

@onboarding_bp.route("/submit-onboarding", methods=["POST"])
def submit_onboarding():
    db = SessionLocal()
    try:
        user_id = session.get("user_id")
        if not user_id:
            return "Unauthorized", 401

        data = request.get_json()
        user = db.query(User).filter_by(id=user_id).first()

        if not user:
            return "User not found", 404

        user.core_trigger = data.get("q1")
        user.default_coping = data.get("q2")
        user.hero_traits = data.get("q3", [])
        user.nickname = data.get("nickname")
        user.journey_start_date = datetime.utcnow()
        user.theme_choice = data.get("journey")
        user.has_completed_onboarding = True

        db.commit()
        return "Success", 200

    except Exception as e:
        print("🔥 Onboarding submission error:", str(e))
        db.rollback()
        return "Error processing onboarding", 500
    finally:
        db.close()
