from flask import Blueprint, render_template, session, redirect, url_for, flash, jsonify
from models import User, CircleMessage, QueryHistory
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta, date
from rams import build_prompt, select_heroes, build_context
from uuid import uuid4
from openai import OpenAI
import random
import os
from db import SessionLocal

circle_bp = Blueprint("circle", __name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_mock_conversation(absence_minutes):
    if absence_minutes < 60:
        return []

    messages = []

    if absence_minutes < 180:
        messages += [
            {"speaker": "Grace", "text": "You ever just... sit in the quiet and let your heart catch up?"},
            {"speaker": "Lucentis", "text": "This stillness has weight. But not the heavy kind."},
            {"speaker": "Cognita", "text": "Silence is just unprocessed data."}
        ]
    elif absence_minutes < 360:
        messages += [
            {"speaker": "Sir Renity", "text": "Remember that time at Stepville when we tried a group ice bath? Never again."},
            {"speaker": "Velessa", "text": "The laughter was worth the freeze though."},
            {"speaker": "Grace", "text": "Still got chills thinking about it."}
        ]
    elif absence_minutes < 720:
        messages += [
            {"speaker": "Lucentis", "text": "If the wind could speak, I think it would sound like Grace when she’s thoughtful."},
            {"speaker": "Cognita", "text": "Don’t give her ideas. She’ll start rhyming again."},
            {"speaker": "Velessa", "text": "I’m just waiting for someone to bring snacks."}
        ]
    elif absence_minutes < 4320:
        messages += [
            {"speaker": "Sir Renity", "text": "Three sunrises and no word. He’s got to be climbing his own mountain."},
            {"speaker": "Grace", "text": "Or maybe just sleeping in. That counts too."},
            {"speaker": "Cognita", "text": "We don’t disappear. We just pause the thread."}
        ]

    return messages[:12]

@circle_bp.route("/circle")
def circle():
    db = SessionLocal()
    now = datetime.utcnow()
    user_id = session.get("user_id")
    session["last_seen_circle"] = now.isoformat()

    last_seen_str = session.get("last_seen_circle")
    absence_minutes = 0
    if last_seen_str:
        try:
            last_seen = datetime.fromisoformat(last_seen_str)
            absence_minutes = (now - last_seen).total_seconds() / 60
        except Exception as e:
            print("⚠️ Failed to parse last_seen_circle:", e)

    try:
        mock_msgs = get_mock_conversation(absence_minutes)
        for msg in mock_msgs:
            db.add(CircleMessage(sender_id=user_id, receiver_id=user_id, text=msg["text"]))
        db.commit()

        messages = (
            db.query(CircleMessage)
            .filter_by(user_id=user_id)
            .order_by(CircleMessage.timestamp.asc())
            .limit(50)
            .all()
        )

        thread = [{"speaker": msg.speaker, "text": msg.text} for msg in messages]
        session["circle_thread"] = thread

        offset_min = session.get("tz_offset_min", 0)
        local_now = now - timedelta(minutes=offset_min)
        start_of_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        session["start_of_day"] = start_of_day.isoformat()

        return render_template("circle.html")

    except SQLAlchemyError as e:
        db.rollback()
        flash("Trouble loading your Circle. Please try again in a moment.")
        return redirect(url_for("profile.profile"))
    finally:
        db.close()

@circle_bp.route("/ask", methods=["POST"])
def ask():
    data = session.get("user_id")
    if not data:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        db = SessionLocal()
        user_id = session.get("user_id")
        user = db.query(User).get(user_id)

        from flask import request
        user_message = request.get_json().get("message", "").strip()
        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        if "session_id" not in session:
            session["session_id"] = str(uuid4())

        thread = session.get("circle_thread", [])
        thread.append({"speaker": "User", "text": user_message})
        thread = thread[-20:]

        db.add(CircleMessage(sender_id=user_id, receiver_id=user_id, text=user_message))
        session["last_input_ts"] = datetime.utcnow().isoformat()

        tone = session.get("tone", "neutral")
        onboarding = session.get("onboarding_data", {})

        recent_quest = session.pop("from_quest", None)
        context_data = build_context(user_id=user.id, session_data=thread, onboarding=onboarding)
        context_data["thread"] = thread
        if recent_quest:
            context_data["recent_quest"] = recent_quest

        previous_hero = next((msg["speaker"] for msg in reversed(thread[:-1]) if msg["speaker"] != "User"), None)
        selected_heroes = select_heroes(tone, thread)
        results = []

        for i, hero_plan in enumerate(selected_heroes):
            hero = hero_plan["name"]
            mode = hero_plan.get("mode", "speak")

            try:
                if mode == "speak":
                    prompt = build_prompt(
                        hero=hero,
                        user_input=user_message,
                        context=context_data,
                        onboarding=onboarding,
                        previous_hero=previous_hero
                    )

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": prompt}],
                        temperature=0.6
                    )

                    reply = response.choices[0].message.content.strip()
                    if reply.lower().startswith(f"{hero.lower()}:"):
                        reply = reply[len(hero)+1:].strip()

                    pause = random.randint(2500, 4000)
                    typing_time = len(reply.split()) * random.randint(65, 80)
                    delay = min(8000, pause + typing_time + i * 900)

                elif mode == "brb":
                    reply = hero_plan.get("text", f"{hero} has stepped away briefly.")
                    delay = 1200 + i * 900
                else:
                    continue

                hero_user = db.query(User).filter_by(resurgitag=f"@{hero}", resurgitag_locked=True).first()
                db.add(CircleMessage(sender_id=hero_user.id, receiver_id=user_id, text=reply))
                thread.append({"speaker": hero, "text": reply})

                db.add(QueryHistory(
                    user_id=user.id,
                    question=user_message,
                    agent_name=hero,
                    response=reply
                ))

                results.append({
                    "hero": hero,
                    "text": reply,
                    "delay_ms": delay
                })

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                thread.append({"speaker": hero, "text": error_msg})
                results.append({
                    "hero": hero,
                    "text": error_msg,
                    "delay_ms": 1500 + i * 700
                })

        today_key = f"circle_points_awarded_{date.today().isoformat()}"
        user_messages = [m for m in thread if m["speaker"] == "User"]

        if len(user_messages) >= 3 and not session.get(today_key):
            user.points = (user.points or 0) + 3
            session[today_key] = True
            session["points_just_added"] = 3

        session["circle_thread"] = thread[-20:]
        db.commit()
        return jsonify({"messages": results})

    except Exception as e:
        import traceback
        print("🔥 /ask route error:", traceback.format_exc())
        return jsonify({"error": "Server error", "details": str(e)}), 500
