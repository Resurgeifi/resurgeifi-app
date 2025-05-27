from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from models import SessionLocal, User, JournalEntry, DailyReflection, CircleMessage
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from openai import OpenAI
from pytz import timezone as tz, utc, all_timezones

journal_bp = Blueprint("journal", __name__)

def localize_time(utc_time, user_timezone):
    if not user_timezone:
        user_timezone = "America/New_York"
    return utc_time.replace(tzinfo=utc).astimezone(tz(user_timezone))

@journal_bp.route("/journal", methods=["GET", "POST"])
def journal():
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()
        if not user:
            return redirect(url_for('auth.register'))

        user_timezone = user.timezone if user.timezone in all_timezones else "America/New_York"

        if request.method == 'POST':
            entry = request.form['entry']
            new_entry = JournalEntry(user_id=user.id, content=entry)
            db.add(new_entry)

            today = datetime.utcnow().date()
            entries_today = db.query(JournalEntry).filter(
                JournalEntry.user_id == user.id,
                JournalEntry.timestamp >= datetime.combine(today, datetime.min.time())
            ).count()

            if entries_today <= 3:
                user.points = (user.points or 0) + 1
                session["points_just_added"] = 1

            db.commit()

        raw_entries = db.query(JournalEntry).filter_by(user_id=user.id).order_by(JournalEntry.timestamp.desc()).all()

        localized_entries = []
        for entry in raw_entries:
            try:
                local_time = localize_time(entry.timestamp, user_timezone)
                localized_entries.append({
                    "id": entry.id,
                    "content": entry.content,
                    "timestamp": local_time.strftime("%b %d, %I:%M %p")
                })
            except Exception:
                localized_entries.append({
                    "id": entry.id,
                    "content": entry.content,
                    "timestamp": "Unknown"
                })

        summary_text = request.args.get("summary_text", "")
        return render_template('journal.html', entries=localized_entries, current_ring="The Spark", summary_text=summary_text)

    except SQLAlchemyError:
        db.rollback()
        flash("Problem accessing journal. Try again soon.", "error")
        return redirect(url_for("menu"))
    finally:
        db.close()

@journal_bp.route("/edit_entry/<int:id>", methods=["GET", "POST"])
def edit_entry(id):
    db = SessionLocal()
    try:
        entry = db.query(JournalEntry).get(id)

        if not entry:
            flash("Entry not found.", "error")
            return redirect(url_for("journal.journal"))

        if request.method == "POST":
            entry.content = request.form["content"]
            db.commit()
            entry_id = entry.id
            flash("Entry updated.", "success")
            return redirect(url_for("journal.edit_entry", id=entry_id, saved="true"))

        return render_template("edit_entry.html", entry=entry)

    except SQLAlchemyError:
        db.rollback()
        flash("Error editing entry. Please try again.", "error")
        return redirect(url_for("journal.journal"))
    finally:
        db.close()

@journal_bp.route("/delete-entry/<int:id>", methods=["GET", "POST"])
def delete_entry(id):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()
        if not user:
            flash("User not found.")
            return redirect(url_for("journal.journal"))

        entry = db.query(JournalEntry).filter_by(id=id, user_id=user.id).first()
        if entry:
            db.delete(entry)
            db.commit()
            flash("Entry deleted.", "success")
        else:
            flash("Entry not found.", "error")

        return redirect(url_for("journal.journal"))

    except SQLAlchemyError:
        db.rollback()
        flash("Error deleting entry. Please try again.", "error")
        return redirect(url_for("journal.journal"))
    finally:
        db.close()

@journal_bp.route("/summarize-journal", methods=["GET"])
def summarize_journal():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    user_id = session.get("user_id")

    if not user_id:
        flash("User not logged in.", "error")
        return redirect(url_for("journal.journal"))

    db = SessionLocal()
    since = datetime.utcnow() - timedelta(hours=24)
    messages = db.query(CircleMessage).filter(
        CircleMessage.sender_id == user_id,
        CircleMessage.speaker.ilike("user"),
        CircleMessage.timestamp >= since
    ).order_by(CircleMessage.timestamp).all()

    if not messages:
        flash("Say something in the Circle before summarizing.", "warning")
        db.close()
        return redirect(url_for("journal.journal"))

    formatted = "\n".join([f'User: "{msg.text}"' for msg in messages])

    user = db.query(User).filter_by(id=user_id).first()
    nickname = user.nickname or "Friend"
    theme = user.theme_choice or "self-discovery"
    display_name = user.display_name or "compassionate people"

    prompt = f"""
You are Resurgifi, a recovery-focused journaling assistant.

The user goes by the nickname: {nickname}
Their theme for joining Resurgifi is: {theme}
They admire people who are: {display_name}

Here’s what they said in today’s Circle:
---
{formatted}
---

Write a short, first-person journal entry that reflects their emotional state and current inner experience. 
Keep it to a single paragraph (about 4–5 sentences). 
Do not mention or reference any heroes by name — this is a personal reflection, not a game recap.
Be emotionally honest but brief. Avoid advice or therapy-speak.
""".strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.65
        )
        journal_text = response.choices[0].message.content.strip()

        reflection = DailyReflection(
            user_id=user_id,
            date=datetime.utcnow(),
            summary_text=journal_text
        )
        db.add(reflection)
        db.commit()
        flash("Journal summary saved successfully.", "success")

    except Exception as e:
        print("🔥 Journal summarization error:", str(e))
        flash("Something went wrong while generating your summary.", "error")
        db.rollback()

    db.close()
    return redirect(url_for("journal.journal", auto_summarize="true", summary_text=journal_text))
