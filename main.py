# 🧱 Standard Library
import os
import random
from datetime import datetime, timedelta
from uuid import uuid4

# 🌐 Timezone Handling
import pytz
from pytz import timezone as tz, all_timezones
from pytz import utc

def localize_time(utc_time, user_timezone):
    if not user_timezone:
        user_timezone = "America/New_York"
    return utc_time.replace(tzinfo=utc).astimezone(tz(user_timezone))
def generate_resurgitag(base_name):
    """Generate a Resurgifi handle like @Jonas_23"""
    base = ''.join(c for c in base_name if c.isalnum())[:10].capitalize()
    suffix = ''.join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ123456789", k=2))
    return f"@{base}_{suffix}"

# 🔒 Auth + Security
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# 🌍 Flask Core
from flask import Flask, abort, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mail import Mail, Message
from flask_cors import CORS

# 🧪 Environment Config
from dotenv import load_dotenv

# 🤖 AI Integration
from openai import OpenAI

# 🧩 Resurgifi Internal
from models import db, User, JournalEntry, QueryHistory
from flask_migrate import Migrate
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError  # ✅ NEW: Handle rollback issues
from rams import HERO_NAMES, build_context, select_heroes, build_prompt
from markupsafe import Markup
import qrcode
import io
import base64

# ✅ Load environment variables
load_dotenv()

# ✅ Initialize Flask App
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "resurgifi-dev-key")

# ✅ CORS for cross-origin POSTs
CORS(app, supports_credentials=True, resources={
    r"/contact": {
        "origins": ["https://resurgelabs.com"],
        "methods": ["POST", "OPTIONS"]
    }
})

# ✅ Email Config
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT"))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS") == "True"
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")
mail = Mail(app)

# ✅ Database Config
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
migrate = Migrate(app, db)

# ✅ SessionLocal for manual queries (inside app context)
with app.app_context():
    engine = db.get_engine()
    SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# ✅ OpenAI Setup
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# ✅ Admin password fallback
admin_password = os.getenv("ADMIN_PASSWORD", "resurgifi123")

from flask import g
from models import User

@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        db = SessionLocal()
        try:
            g.user = db.query(User).filter_by(id=user_id).first()
        finally:
            db.close()

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

# ✅ Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access Resurgifi.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/profile")
@login_required
def profile():
    user_id = session.get("user_id")
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(id=user_id).first()

        if not user.resurgitag:
            user.resurgitag = generate_resurgitag(user.display_name or "User")
            db.commit()

        qr_data = f"https://resurgifi-app.onrender.com/friends/{user.resurgitag}"
        qr_img = qrcode.make(qr_data)
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        days_on_journey = (datetime.utcnow() - (user.journey_start_date or datetime.utcnow())).days
        return render_template("profile.html", user=user,
                               resurgitag=user.resurgitag,
                               points=user.points or 0,
                               days_on_journey=days_on_journey,
                               qr_code_base64=qr_code_base64)
    
    except SQLAlchemyError as e:
        db.rollback()
        flash("Something went wrong loading your profile. Please try again.")
        return redirect(url_for('login'))
    
    finally:
        db.close()



@app.route("/circle")
@login_required
def circle():
    from models import CircleMessage
    from main import get_mock_conversation

    user_id = session.get("user_id")
    db = SessionLocal()
    now = datetime.utcnow()
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
            db.add(CircleMessage(user_id=user_id, speaker=msg["speaker"], text=msg["text"]))
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
        return redirect(url_for('profile'))
    finally:
        db.close()

@app.route("/summarize-journal", methods=["GET"])
@login_required
def summarize_journal():
    from openai import OpenAI
    from datetime import datetime, timedelta
    from models import User, DailyReflection, CircleMessage
    from db import SessionLocal

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    user_id = session.get("user_id")

    if not user_id:
        flash("User not logged in.", "error")
        return redirect(url_for("journal"))

    db = SessionLocal()

    # ⏳ Last 24 hours of Circle messages from the user
    since = datetime.utcnow() - timedelta(hours=24)
    messages = db.query(CircleMessage).filter(
        CircleMessage.user_id == user_id,
        CircleMessage.speaker.ilike("user"),
        CircleMessage.timestamp >= since
    ).order_by(CircleMessage.timestamp).all()

    if not messages:
        flash("Say something in the Circle before summarizing. Your journal should reflect your own voice.", "warning")
        db.close()
        return redirect(url_for("journal"))

    formatted = "\n".join([f'User: "{msg.text}"' for msg in messages])

    # 🧠 Pull onboarding context
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
Focus on their real emotions, not casual questions or playful comments.
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
    return redirect(url_for("journal", auto_summarize="true", summary_text=journal_text))

@app.route("/test-db")
def test_db():
    try:
        db = SessionLocal()
        entries = db.query(JournalEntry).order_by(JournalEntry.timestamp.desc()).limit(5).all()
        result = [
            {
                "id": entry.id,
                "content": entry.content,
                "timestamp": entry.timestamp.strftime("%Y-%m-%d %H:%M")
            }
            for entry in entries
        ]
        db.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/about")
@login_required
def about():
    return render_template("about.html")

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route("/menu")
@login_required
def menu():
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()

        if not user:
            flash("User not found.")
            return redirect(url_for('login'))

        days_on_journey = 0
        if user.journey_start_date:
            try:
                days_on_journey = (datetime.now().date() - user.journey_start_date.date()).days
            except Exception as e:
                print("🔥 Error calculating journey days:", e)

        journal_entries = db.query(JournalEntry).filter_by(user_id=user.id).order_by(JournalEntry.timestamp.desc()).all()
        journal_count = len(journal_entries)
        last_journal = journal_entries[0].timestamp.strftime("%b %d, %Y") if journal_entries else None

        from models import CircleMessage
        now = datetime.utcnow()
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        circle_msgs = (
            db.query(CircleMessage)
            .filter(CircleMessage.user_id == user.id)
            .filter(CircleMessage.timestamp >= start_today)
            .filter(CircleMessage.speaker != "User")
            .order_by(CircleMessage.timestamp.desc())
            .all()
        )
        last_circle_msg = circle_msgs[0].text if circle_msgs else None

        return render_template(
            "menu.html",
            current_ring=user.theme_choice or "Unranked",
            days_on_journey=days_on_journey,
            journal_count=journal_count,
            last_journal=last_journal,
            last_circle_msg=last_circle_msg,
            streak=session.get('streak', 0)
        )

    except SQLAlchemyError:
        db.rollback()
        flash("Could not load your menu. Try again soon.", "error")
        return redirect(url_for("login"))
    finally:
        db.close()

@app.route("/home1")
@login_required
def home1():
    return render_template("home1.html")

@app.route('/form', methods=['GET', 'POST'])
@login_required
def form():
    db = SessionLocal()
    try:
        if request.method == 'POST':
            question = request.form['question']
            db.close()  # No DB write here, but session was opened — so close cleanly
            return redirect(url_for('ask'), code=307)

        return render_template('form.html')

    except SQLAlchemyError:
        db.rollback()
        flash("Something went wrong loading the form.", "error")
        return redirect(url_for("menu"))
    finally:
        db.close()

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()

        if not user:
            flash("User not found.")
            return redirect(url_for('login'))

        common_timezones = [
            "America/New_York",
            "America/Chicago",
            "America/Denver",
            "America/Los_Angeles",
            "America/Phoenix",
            "America/Anchorage",
            "America/Honolulu"
        ]

        if request.method == "POST":
            form = request.form

            # ✅ Journey selection
            if 'journey' in form:
                journey = form.get("journey")
                if journey:
                    user.theme_choice = journey
                    session['journey'] = journey
                    db.commit()
                    flash("Journey updated to: " + journey.replace("_", " ").title(), "success")
                    return redirect(url_for('settings'))

            # ✅ Timezone selection
            if 'timezone' in form:
                selected_tz = form.get("timezone")
                if selected_tz in common_timezones:
                    user.timezone = selected_tz
                    session['timezone'] = selected_tz
                    db.commit()
                    flash("Time zone updated successfully.", "success")
                    return redirect(url_for('settings'))
                else:
                    flash("Invalid time zone selected.", "error")
                    return redirect(url_for('settings'))

            # ✅ Nickname update
            if 'nickname' in form:
                nickname = form.get("nickname")
                if nickname:
                    user.nickname = nickname
                    user.display_name = nickname
                    session['nickname'] = nickname
                    db.commit()
                    flash("Nickname updated.", "success")
                    return redirect(url_for('settings'))

            # ✅ Journey start date input
            if 'journey_start_date' in form:
                date_str = form.get("journey_start_date")
                if date_str:
                    try:
                        parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
                        user.journey_start_date = parsed_date
                        db.commit()
                        flash("Journey start date saved.", "success")
                    except ValueError:
                        flash("Invalid date format.", "error")
                    return redirect(url_for('settings'))

        # 🧠 Pull saved values
        current_journey = user.theme_choice or "Not Selected"
        timezone = user.timezone or ""
        nickname = user.nickname or ""
        journey_start_date = user.journey_start_date.strftime('%Y-%m-%d') if user.journey_start_date else ""

        return render_template(
            "settings.html",
            current_ring=current_journey,
            timezone=timezone,
            timezones=common_timezones,
            nickname=nickname,
            journey_start_date=journey_start_date
        )

    except SQLAlchemyError:
        db.rollback()
        flash("Error saving or loading settings. Try again.", "error")
        return redirect(url_for("menu"))
    finally:
        db.close()

@app.route("/delete-entry/<int:id>", methods=["GET", "POST"])
@login_required
def delete_entry(id):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()
        if not user:
            flash("User not found.")
            return redirect(url_for('journal'))

        entry = db.query(JournalEntry).filter_by(id=id, user_id=user.id).first()
        if entry:
            db.delete(entry)
            db.commit()
            flash("Entry deleted.", "success")
        else:
            flash("Entry not found.", "error")

        return redirect(url_for('journal'))

    except SQLAlchemyError:
        db.rollback()
        flash("Error deleting entry. Please try again.", "error")
        return redirect(url_for('journal'))
    finally:
        db.close()

@app.route("/edit_entry/<int:id>", methods=["GET", "POST"])
@login_required
def edit_entry(id):
    db = SessionLocal()
    try:
        entry = db.query(JournalEntry).get(id)

        if not entry:
            flash("Entry not found.", "error")
            return redirect(url_for("journal"))

        if request.method == "POST":
            entry.content = request.form["content"]
            db.commit()
            entry_id = entry.id
            flash("Entry updated.", "success")
            return redirect(url_for("edit_entry", id=entry_id, saved="true"))

        return render_template("edit_entry.html", entry=entry)

    except SQLAlchemyError:
        db.rollback()
        flash("Error editing entry. Please try again.", "error")
        return redirect(url_for("journal"))
    finally:
        db.close()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not email or not password or not confirm_password:
            flash("Please fill in all fields.", "warning")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        db = SessionLocal()
        try:
            existing_user = db.query(User).filter_by(email=email).first()
            if existing_user:
                flash("Account with that email already exists. Please log in.", "error")
                return redirect(url_for("login"))

            hashed_pw = generate_password_hash(password)

            new_user = User(
                email=email,
                password_hash=hashed_pw,
                nickname=None,
                display_name=None,
                theme_choice=None,
                consent=None,
                journey_start_date=None,
                timezone=None
            )

            db.add(new_user)
            db.commit()

            session['user_id'] = new_user.id
            session['journey'] = "Not Selected"
            session['timezone'] = "America/New_York"

            flash("Registration successful. Let’s begin your journey.", "success")
            return redirect(url_for("onboarding"))
        except SQLAlchemyError as e:
            db.rollback()
            flash("Something went wrong while creating your account.", "error")
            return redirect(url_for("register"))
        finally:
            db.close()

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
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

                if not user.nickname or not user.theme_choice:
                    return redirect(url_for("onboarding"))

                flash("Login successful. Welcome back.", "success")
                return redirect(url_for("menu"))

            flash("Incorrect email or password.", "error")
            return render_template("login.html")
        except SQLAlchemyError as e:
            db.rollback()
            flash("Database error during login. Please try again.", "error")
            return render_template("login.html")
        finally:
            db.close()

    return render_template("login.html")


@app.route("/reset-password", methods=["GET", "POST"])
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
                mail.send(msg)

                return redirect(url_for("reset_confirm"))
            else:
                message = "No account found with that email."

        return render_template("reset_password.html", message=message)
    except SQLAlchemyError:
        db.rollback()
        flash("Something went wrong. Try again.", "error")
        return redirect(url_for("reset_password"))
    finally:
        db.close()

@app.route("/reset-confirm", methods=["GET", "POST"])
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
                    return redirect(url_for("login"))
                else:
                    message = "User not found."
            else:
                message = "Invalid code. Please try again."

        return render_template("reset_confirm.html", message=message)
    except SQLAlchemyError:
        db.rollback()
        flash("Something went wrong during password reset.", "error")
        return redirect(url_for("reset_password"))
    finally:
        db.close()

@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You’ve been logged out.")
    return redirect(url_for("login"))

@app.route('/admin/logs')
@login_required
def admin_logs():
    if not session.get('admin'):
        return redirect(url_for('login'))
    try:
        with open("logs/conversations.log", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = "No logs available."
    return render_template('admin_logs.html', logs=content)

@app.route('/dashboard')
@login_required
def dashboard():
    if 'session_id' not in session:
        return redirect(url_for('register'))

    session_id = session.get('session_id')
    journal_path = f"logs/journals/{session_id}.txt"
    entry_count = 0
    streak_days = set()

    if os.path.exists(journal_path):
        with open(journal_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('['):
                    entry_count += 1
                    date_str = line[1:11]
                    streak_days.add(date_str)

    streak = len(streak_days)
    return render_template('dashboard.html', entry_count=entry_count, streak=streak)

from rams import build_context, select_heroes, build_prompt

@app.route("/journal", methods=["GET", "POST"])
@login_required
def journal():
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()
        if not user:
            return redirect(url_for('register'))

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

    except SQLAlchemyError as e:
        db.rollback()
        flash("Problem accessing journal. Try again soon.", "error")
        return redirect(url_for("menu"))
    finally:
        db.close()

@app.route('/ask', methods=['POST'])
@login_required
def ask():
    try:
        from models import User, CircleMessage, QueryHistory, db
        from rams import build_prompt, select_heroes, build_context
        from datetime import datetime, date
        import random

        data = request.get_json()
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        if 'session_id' not in session:
            session['session_id'] = str(uuid4())

        user_id = session.get("user_id")
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # 🧠 Circle memory
        thread = session.get("circle_thread", [])
        thread.append({"speaker": "User", "text": user_message})
        thread = thread[-20:]  # Keep it lean

        # ✅ Save user message to DB
        db.session.add(CircleMessage(user_id=user_id, speaker="User", text=user_message))
        session["last_input_ts"] = datetime.utcnow().isoformat()

        tone = session.get("tone", "neutral")
        onboarding = session.get("onboarding_data", {})

        # 🧠 Quest reflection link
        recent_quest = session.pop("from_quest", None)

        # 🧠 Prompt context
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

                db.session.add(CircleMessage(user_id=user_id, speaker=hero, text=reply))
                thread.append({"speaker": hero, "text": reply})

                db.session.add(QueryHistory(
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

        # ✅ Reward points for Circle use — once per day
        user_messages = [m for m in thread if m["speaker"] == "User"]
        today_key = f"circle_points_awarded_{date.today().isoformat()}"

        if len(user_messages) >= 3 and not session.get(today_key):
            user.points = (user.points or 0) + 3
            session[today_key] = True
            session["points_just_added"] = 3  # Optional: used for UI flash

        session["circle_thread"] = thread[-20:]
        db.session.commit()
        return jsonify({"messages": results})

    except Exception as e:
        import traceback
        print("🔥 /ask route error:", traceback.format_exc())
        return jsonify({"error": "Server error", "details": str(e)}), 500

import os
import io
import base64
from flask import request, render_template, flash, redirect, url_for, session
from flask_mail import Message
from werkzeug.utils import secure_filename
from sqlalchemy.exc import SQLAlchemyError

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = '/tmp'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/feedback", methods=["GET", "POST"])
@login_required
def feedback():
    if request.method == "POST":
        message = request.form.get("message")
        file = request.files.get("screenshot")
        user = session.get("nickname", f"User ID {session.get('user_id', 'Unknown')}")

        file_path = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

        email_body = f"Feedback from {user}:\n\n{message}\n\nAttachment: {'Yes' if file_path else 'No'}"

        email = Message(
            subject=f"📝 Feedback from {user}",
            recipients=[os.getenv("MAIL_FEEDBACK_RECIPIENT")],
            body=email_body
        )

        if file_path:
            with open(file_path, "rb") as f:
                email.attach(filename, file.content_type, f.read())

        mail.send(email)
        flash("Thanks for your feedback!")
        return redirect(url_for("feedback"))

    return render_template("feedback.html")

@app.route("/history")
@login_required
def history():
    if 'username' not in session:
        return redirect(url_for('register'))

    db = SessionLocal()
    user = db.query(User).filter_by(id=session['user_id']).first()

    if not user:
        db.close()
        return redirect(url_for('register'))

    history_items = (
        db.query(QueryHistory)
        .filter_by(user_id=user.id)
        .order_by(QueryHistory.timestamp.desc())
        .all()
    )
    db.close()
    return render_template("history.html", history=history_items)

@app.route("/contact", methods=["POST"])
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
        mail.send(email)
        response = make_response("Thanks, you're in.")
        response.headers['Access-Control-Allow-Origin'] = 'https://resurgelabs.com'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    return "No message provided", 400
@app.route("/contact", methods=["OPTIONS"])
def contact_options():
    response = make_response()
    response.headers['Access-Control-Allow-Origin'] = 'https://resurgelabs.com'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route("/set-timezone", methods=["POST"])
def set_timezone():
    data = request.get_json()
    offset = data.get("offset", 0)  # Offset in minutes (e.g. -300 for EST)
    session["tz_offset_min"] = offset
    return jsonify({"status": "ok", "offset": offset})
@app.route("/life-ring")
def life_ring():
    return render_template("life_ring.html")

@app.route("/reset-test-user")
def reset_test_user():
    from models import User, JournalEntry, CircleMessage
    db = SessionLocal()

    # Try to find the test user
    user = db.query(User).filter_by(id=session['user_id']).first()

    if not user:
        # ✅ Auto-create TestUser
        user = User(
            username="test_user",
            email="test@resurgifi.com",
            password_hash="dev-mode",  # Bypass login logic
            display_name="Testy",
            consent="yes",
            theme_choice="default",
            timezone="America/New_York"
        )
        db.add(user)
        db.commit()
        flash("TestUser created successfully.", "info")

    # Now wipe any existing data
    db.query(JournalEntry).filter_by(user_id=user.id).delete()
    db.query(CircleMessage).filter_by(user_id=user.id).delete()

    # Reset flags
    user.nickname = None
    user.journey_start_date = None
    user.journal_count = 0
    user.circle_message_count = 0
    user.last_journal_entry = None
    user.last_circle_msg = None
    db.commit()

    # ✅ Pull values BEFORE closing session
    user_id = user.id
    username = user.username
    db.close()

    # Log them in
    session.clear()

    session["user_id"] = user_id

    flash("TestUser created/reset. Starting onboarding.", "success")
    return redirect(url_for("onboarding"))
@app.route("/submit-onboarding", methods=["POST"])
@login_required
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

        db.commit()
        return "Success", 200

    except Exception as e:
        print("🔥 Onboarding submission error:", str(e))
        db.rollback()
        return "Error processing onboarding", 500
    finally:
        db.close()

@app.route("/onboarding", methods=["GET"])
@login_required
def onboarding():
    return render_template("onboarding.html")
@app.route("/quest", methods=["GET", "POST"])
@login_required
def quest():
    from models import User, UserQuestEntry, db
    from datetime import datetime, timedelta
    import openai

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
                return redirect(url_for("circle"))

            if todays_quests:
                last_time = max(q.timestamp for q in todays_quests)
                if (now - last_time) < timedelta(hours=4):
                    flash("You can only complete one quest every 4 hours. Try again later.", "warning")
                    return redirect(url_for("circle"))

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

            return redirect(url_for("circle"))

        return render_template("quest.html")

    except SQLAlchemyError:
        db_session.rollback()
        flash("Quest processing failed. Please try again.", "error")
        return redirect(url_for("circle"))
    finally:
        db_session.close()
@app.route("/change-tag", methods=["GET", "POST"])
@login_required
def change_resurgitag():
    user_id = session.get("user_id")
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()

        if user.resurgitag_locked:
            flash("You can only change your Resurgitag once.")
            return redirect(url_for("profile"))

        if request.method == "POST":
            new_tag = request.form.get("new_tag", "").strip()
            if new_tag and new_tag.startswith("@") and len(new_tag) <= 32:
                existing = db.query(User).filter_by(resurgitag=new_tag).first()
                if existing:
                    flash("That tag is already taken. Try another.")
                else:
                    user.resurgitag = new_tag
                    user.resurgitag_locked = True
                    db.commit()
                    flash("Your Resurgitag has been updated!")
                    return redirect(url_for("profile"))
            else:
                flash("Tag must start with @ and be less than 32 characters.")
        return render_template("change_tag.html", current_tag=user.resurgitag)
    finally:
        db.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)

