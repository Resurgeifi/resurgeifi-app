from flask import Blueprint, request, session, flash
from models import User
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from routes.resurgitag import generate_resurgitag
from db import SessionLocal


onboarding_bp = Blueprint("onboarding", __name__)

@onboarding_bp.route("/submit-onboarding", methods=["POST"])
def submit_onboarding():
    import json
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

        # ✅ Generate Resurgitag based on nickname
        if not user.resurgitag:
            base = user.nickname or "User"
            user.resurgitag = generate_resurgitag(base)

        db.commit()
        return "Success", 200

    except Exception as e:
        print("🔥 Onboarding submission error:", str(e))
        db.rollback()
        return "Error processing onboarding", 500
    finally:
        db.close()

