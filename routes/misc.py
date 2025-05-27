from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from flask_mail import Message
from models import User, JournalEntry, CircleMessage
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import os
from db import SessionLocal

misc_bp = Blueprint("misc", __name__)

@misc_bp.route("/")
def root_redirect():
    return redirect(url_for("misc.landing"))

@misc_bp.route("/landing")
def landing():
    return render_template("landing.html")

@misc_bp.route("/about")
def about():
    return render_template("about.html")

@misc_bp.route("/life-ring")
def life_ring():
    return render_template("life_ring.html")

@misc_bp.route("/contact", methods=["POST"])
def contact():
    message = request.form.get("message")
    name = request.form.get("name", "Unknown")
    email_addr = request.form.get("email", "No email provided")

    if message:
        email = Message(
            subject=f"📨 Contact Form from {name}",
            recipients=[os.getenv("MAIL_FEEDBACK_RECIPIENT")],
            body=f"Name: {name}\nEmail: {email_addr}\n\nMessage:\n{message}"
        )
        from main import mail
        mail.send(email)
        response = make_response("Thanks, you're in.")
        response.headers['Access-Control-Allow-Origin'] = 'https://resurgelabs.com'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    return "No message provided", 400

@misc_bp.route("/contact", methods=["OPTIONS"])
def contact_options():
    response = make_response()
    response.headers['Access-Control-Allow-Origin'] = 'https://resurgelabs.com'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@misc_bp.route("/set-timezone", methods=["POST"])
def set_timezone():
    data = request.get_json()
    offset = data.get("offset", 0)
    session["tz_offset_min"] = offset
    return jsonify({"status": "ok", "offset": offset})

@misc_bp.route("/reset-test-user")
def reset_test_user():
    db = SessionLocal()
    user = db.query(User).filter_by(id=session.get('user_id')).first()

    if not user:
        user = User(
            username="test_user",
            email="test@resurgifi.com",
            password_hash="dev-mode",
            display_name="Testy",
            consent="yes",
            theme_choice="default",
            timezone="America/New_York"
        )
        db.add(user)
        db.commit()
        flash("TestUser created successfully.", "info")

    db.query(JournalEntry).filter_by(user_id=user.id).delete()
    db.query(CircleMessage).filter_by(user_id=user.id).delete()

    user.nickname = None
    user.journey_start_date = None
    user.journal_count = 0
    user.circle_message_count = 0
    user.last_journal_entry = None
    user.last_circle_msg = None
    db.commit()

    session.clear()
    session["user_id"] = user.id
    flash("TestUser created/reset. Starting onboarding.", "success")
    db.close()
    return redirect(url_for("onboarding.onboarding"))
