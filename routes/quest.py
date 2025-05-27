from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from models import User, UserQuestEntry
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from openai import OpenAI
import os
from db import SessionLocal

quest_bp = Blueprint("quest", __name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@quest_bp.route("/quest", methods=["GET", "POST"])
def quest():
    db_session = SessionLocal()
    try:
        user_id = session.get("user_id")
        user = db_session.query(User).get(user_id)
        now = datetime.utcnow()

        if request.method == "POST":
            reflection = request.form.get("reflection", "").strip()
            summary_text = ""

            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            todays_quests = db_session.query(UserQuestEntry).filter_by(user_id=user_id).filter(UserQuestEntry.timestamp >= today_start).all()

            if len(todays_quests) >= 3:
                flash("You’ve already completed the maximum of 3 quests today.", "info")
                return redirect(url_for("circle.circle"))

            if todays_quests:
                last_time = max(q.timestamp for q in todays_quests)
                if (now - last_time) < timedelta(hours=4):
                    flash("You can only complete one quest every 4 hours. Try again later.", "warning")
                    return redirect(url_for("circle.circle"))

            if reflection:
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "system",
                                "content": "Summarize this quest reflection in one short, emotional sentence. Do not sound robotic."
                            },
                            {
                                "role": "user",
                                "content": reflection
                            }
                        ],
                        temperature=0.7
                    )
                    summary_text = response.choices[0].message.content.strip()
                except Exception as e:
                    print("⚠️ GPT summarization failed:", e)
                    summary_text = ""

                new_entry = UserQuestEntry(
                    user_id=user_id,
                    quest_id=1,
                    completed=True,
                    timestamp=now,
                    summary_text=summary_text
                )
                db_session.add(new_entry)

                if len(todays_quests) < 3:
                    user.points = (user.points or 0) + 5
                    session["points_just_added"] = 5

                db_session.commit()

                session["from_quest"] = {
                    "quest_id": 1,
                    "reflection": summary_text or reflection
                }

            return redirect(url_for("circle.circle"))

        return render_template("quest.html")

    except SQLAlchemyError:
        db_session.rollback()
        flash("Quest processing failed. Please try again.", "error")
        return redirect(url_for("circle.circle"))
    finally:
        db_session.close()
