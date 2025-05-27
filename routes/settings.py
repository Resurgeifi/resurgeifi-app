from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from models import User
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime  # ✅ FIXED: Now importing the class, not the module
from db import SessionLocal

settings_bp = Blueprint("settings", __name__)

@settings_bp.route("/settings", methods=["GET", "POST"])
def settings():
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()

        if not user:
            flash("User not found.")
            return redirect(url_for('auth.login'))

        if request.method == "POST":
            form = request.form

            # 🌀 Journey Theme
            journey = form.get("theme_choice")
            valid_journeys = [
                "Major loss or grieving",
                "Anxiety or fear",
                "Addiction",
                "Depression or emptiness",
                "Low self-worth",
                "Trauma or PTSD",
                "Emotional growth"
            ]
            if journey in valid_journeys:
                user.theme_choice = journey
                session['journey'] = journey

            # 📅 Journey Start Date (relapse reset)
            date_str = form.get("journey_start_date")
            if date_str:
                try:
                    user.journey_start_date = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    flash("Invalid date format for journey start.", "error")

            # 📝 Nickname update
            nickname = form.get("nickname", "").strip()
            if nickname:
                user.nickname = nickname
                user.display_name = nickname
                session['nickname'] = nickname

            # 👁️ Visibility toggle
            user.show_journey_publicly = 'show_journey_publicly' in form

            db.commit()
            flash("Settings updated successfully.", "success")
            return redirect(url_for('settings.settings'))

        # Format journey date for form
        try:
            journey_start_date = user.journey_start_date.strftime('%Y-%m-%d') if user.journey_start_date else ""
        except Exception:
            journey_start_date = ""

        return render_template(
            "settings.html",
            theme_choice=user.theme_choice or "",
            journey_start_date=journey_start_date,
            nickname=user.nickname or "",
            show_journey_publicly=bool(getattr(user, "show_journey_publicly", False)),
            datetime=datetime  # ✅ This will now work correctly in Jinja
        )

    except SQLAlchemyError:
        db.rollback()
        flash("Error loading or saving settings. Please try again.", "error")
        return redirect(url_for("menu"))
    finally:
        db.close()
