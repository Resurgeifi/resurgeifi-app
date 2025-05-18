# 🧱 Standard Library
import os
import random
from datetime import datetime
from uuid import uuid4

# 🌐 Timezone Handling
import pytz
from pytz import timezone as tz, all_timezones
from pytz import utc  # ✅ Utility to handle timestamp localization

def localize_time(utc_time, user_timezone):
    if not user_timezone:
        user_timezone = "America/New_York"  # fallback timezone
    return utc_time.replace(tzinfo=utc).astimezone(tz(user_timezone))

# 🔒 Auth + Security
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# 🌍 Flask Core
from flask import Flask, abort, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mail import Mail, Message
from flask_cors import CORS  # ✅ Add this to support cross-origin POSTs
from datetime import datetime, timedelta  # Required for idle logic

# 🧪 Environment Config
from dotenv import load_dotenv

# 🤖 AI Integration
from openai import OpenAI

# 🧩 Resurgifi Internal
from db import SessionLocal, engine
from models import Base, User, JournalEntry, QueryHistory
from rams import HERO_NAMES, build_context, select_heroes, build_prompt
from markupsafe import Markup

# ✅ Load environment variables
load_dotenv()

# ✅ Initialize Flask app
app = Flask(__name__)
CORS(app, supports_credentials=True, resources={
    r"/contact": {
        "origins": ["https://resurgelabs.com"],
        "methods": ["POST", "OPTIONS"]
    }
})

app.secret_key = os.getenv("FLASK_SECRET_KEY", "resurgifi-dev-key")

# ✅ Configure Flask-Mail
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT"))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS") == "True"
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")

mail = Mail(app)

# ✅ Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# ✅ Load OpenAI credentials
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)
admin_password = os.getenv("ADMIN_PASSWORD", "resurgifi123")
def get_mock_conversation(absence_minutes):
    # Skip if gone for less than an hour
    if absence_minutes < 60:
        return []

    # Cap total injected messages (e.g. 12 max)
    messages = []

    if absence_minutes < 180:  # 1–3 hours
        messages += [
            {"speaker": "Grace", "text": "You ever just... sit in the quiet and let your heart catch up?"},
            {"speaker": "Lucentis", "text": "This stillness has weight. But not the heavy kind."},
            {"speaker": "Cognita", "text": "Silence is just unprocessed data."}
        ]

    elif absence_minutes < 360:  # 3–6 hours
        messages += [
            {"speaker": "Sir Renity", "text": "Remember that time at Stepville when we tried a group ice bath? Never again."},
            {"speaker": "Velessa", "text": "The laughter was worth the freeze though."},
            {"speaker": "Grace", "text": "Still got chills thinking about it."}
        ]

    elif absence_minutes < 720:  # 6–12 hours
        messages += [
            {"speaker": "Lucentis", "text": "If the wind could speak, I think it would sound like Grace when she’s thoughtful."},
            {"speaker": "Cognita", "text": "Don’t give her ideas. She’ll start rhyming again."},
            {"speaker": "Velessa", "text": "I’m just waiting for someone to bring snacks."}
        ]

    elif absence_minutes < 4320:  # up to 3 days
        messages += [
            {"speaker": "Sir Renity", "text": "Three sunrises and no word. He’s got to be climbing his own mountain."},
            {"speaker": "Grace", "text": "Or maybe just sleeping in. That counts too."},
            {"speaker": "Cognita", "text": "We don’t disappear. We just pause the thread."}
        ]

    # Cap it to max 12 lines
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
@app.route("/circle")
@login_required
def circle():
    from models import CircleMessage  # Make sure this import is at the top

    user_id = session.get("user_id")
    db = SessionLocal()

    # 🧠 NEW: Check how long they've been gone
    last_seen_str = session.get("last_seen_circle")
    now = datetime.utcnow()
    session["last_seen_circle"] = now.isoformat()

    absence_minutes = 0
    if last_seen_str:
        try:
            last_seen = datetime.fromisoformat(last_seen_str)
            absence_minutes = (now - last_seen).total_seconds() / 60
        except Exception as e:
            print("⚠️ Failed to parse last_seen_circle:", e)

    # ✨ Inject mock banter if enough time has passed
    from models import CircleMessage
    from main import get_mock_conversation  # Ensure this function is added above

    mock_msgs = get_mock_conversation(absence_minutes)
    for msg in mock_msgs:
        db.add(CircleMessage(user_id=user_id, speaker=msg["speaker"], text=msg["text"]))
    db.commit()

    # 🔁 Get latest 50 messages (includes any new mock ones)
    messages = (
        db.query(CircleMessage)
        .filter_by(user_id=user_id)
        .order_by(CircleMessage.timestamp.asc())
        .limit(50)
        .all()
    )

    # 🧠 Save to session thread memory
    thread = [{"speaker": msg.speaker, "text": msg.text} for msg in messages]
    session["circle_thread"] = thread

    # 🕓 Set "start of day" based on user timezone offset
    offset_min = session.get("tz_offset_min", 0)
    local_now = now - timedelta(minutes=offset_min)
    start_of_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    session["start_of_day"] = start_of_day.isoformat()

    db.close()
    return render_template("circle.html")
@app.route("/summarize-journal", methods=["GET"])
@login_required
def summarize_journal():
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    user_id = session.get("user_id")
    thread = session.get("circle_thread", [])

    if not thread or not user_id:
        flash("No Circle data available for today.", "warning")
        return redirect(url_for("journal"))

    # 🔒 Only summarize user messages
    user_only = [msg for msg in thread if msg["speaker"] == "User"]

    if not user_only:
        flash("Say something in the Circle before summarizing. Your journal should reflect your own voice.", "warning")
        return redirect(url_for("journal"))

    # Format user-only content
    formatted = "\n".join([f'User: "{msg["text"]}"' for msg in user_only])

    # ✍️ Prompt
    prompt = f"""
You are a compassionate and emotionally intelligent summarizer.

Your job is to write a short first-person journal entry based ONLY on what the user shared today.

Use the user's tone. Reflect their emotional state honestly — even if it's scattered, sarcastic, or numb. Do not lecture. Do not over-explain. Do not write like a therapist or give advice.

NEVER summarize what other characters said. Focus ONLY on the user’s own words.

Do NOT mention "the Circle," "heroes," or anything the user didn’t say. You are writing AS the user, TO themselves.

Length: 1–3 short paragraphs max. Tone: authentic, imperfect, emotionally raw or chill.

Here is the full record of what the user said today:
---
{formatted}
---
Now write a realistic journal entry that sounds like the user wrote it in their own words.
    """.strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.65
        )
        journal_text = response.choices[0].message.content.strip()
    except Exception as e:
        print("🔥 Journal summarization error:", str(e))
        flash("Something went wrong while generating your summary.", "error")
        return redirect(url_for("journal"))

    # Redirect with draft text preloaded
    return redirect(url_for("journal", auto_summarize="true", summary_text=journal_text))

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
    if 'username' not in session:
        return redirect(url_for('register'))

    db = SessionLocal()
    user = db.query(User).filter_by(username=session['username']).first()
    db.close()

    # ✅ Calculate days on journey
    journey_start_date = session.get('journey_start_date')
    days_on_journey = 0
    if journey_start_date:
        try:
            start_date = datetime.strptime(journey_start_date, '%Y-%m-%d')
            days_on_journey = (datetime.now().date() - start_date.date()).days
        except Exception as e:
            print("Journey date error:", e)

    quotes = [
        "You’re not behind — you’re becoming.",
        "Even now, you are enough.",
        "Healing isn’t linear. Keep going.",
        "You don’t have to do this alone.",
        "Small steps are still progress.",
        "Your presence here is a win."
    ]

    return render_template(
        "menu.html",
        daily_quote=random.choice(quotes),
        journey=user.theme_choice or "Not Selected",
        streak=session.get('streak', 0),
        last_entry=session.get('last_entry', None),
        days_on_journey=days_on_journey
    )


@app.route("/home1")
@login_required
def home1():
    return render_template("home1.html")

@app.route('/form', methods=['GET', 'POST'])
@login_required
def form():
    if request.method == 'POST':
        question = request.form['question']
        return redirect(url_for('ask'), code=307)
    return render_template('form.html')

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    db = SessionLocal()
    user = db.query(User).filter_by(username=session['username']).first()

    if not user:
        db.close()
        flash("User not found.")
        return redirect(url_for('login'))

    # ✅ Short list of common U.S. timezones
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
        # ✅ Journey selection
        if 'journey' in request.form:
            journey = request.form.get("journey")
            if journey:
                user.theme_choice = journey
                session['journey'] = journey
                db.commit()
                flash("Journey updated to: " + journey.replace("_", " ").title(), "success")
                return redirect(url_for('settings'))

        # ✅ Timezone selection
        if 'timezone' in request.form:
            selected_tz = request.form.get("timezone")
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
        if 'nickname' in request.form:
            nickname = request.form.get("nickname")
            if nickname:
                user.nickname = nickname
                user.display_name = nickname
                db.commit()
                flash("Nickname updated.", "success")
                return redirect(url_for('settings'))

        # ✅ Journey start date input
        if 'journey_start_date' in request.form:
            date_str = request.form.get("journey_start_date")
            if date_str:
                session['journey_start_date'] = date_str
                flash("Journey start date saved.", "success")
                return redirect(url_for('settings'))

    current_journey = user.theme_choice or "Not Selected"
    timezone = user.timezone or ""
    nickname = user.nickname or ""
    journey_start_date = session.get("journey_start_date", "")

    db.close()

    return render_template(
        "settings.html",
        current_ring=current_journey,
        timezone=timezone,
        timezones=common_timezones,
        nickname=nickname,
        journey_start_date=journey_start_date
    )


@app.route("/delete-entry/<int:id>", methods=["GET", "POST"])
@login_required
def delete_entry(id):
    db = SessionLocal()
    user = db.query(User).filter_by(username=session['username']).first()

    entry = db.query(JournalEntry).filter_by(id=id, user_id=user.id).first()
    if entry:
        db.delete(entry)
        db.commit()

    db.close()
    return redirect(url_for('journal'))


@app.route("/edit_entry/<int:id>", methods=["GET", "POST"])
@login_required
def edit_entry(id):
    db = SessionLocal()
    entry = db.query(JournalEntry).get(id)

    if not entry:
        db.close()
        return redirect(url_for("journal"))

    if request.method == "POST":
        entry.content = request.form["content"]
        db.commit()
        entry_id = entry.id  # Grab ID before closing session
        db.close()
        return redirect(url_for("edit_entry", id=entry_id, saved="true"))

    db.close()
    return render_template("edit_entry.html", entry=entry)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        nickname = request.form.get("nickname")  # ✅ Optional nickname

        if not username or not email or not password or not nickname:
            flash("Please fill in all fields.", "warning")
            return redirect(url_for("register"))

        db = SessionLocal()
        existing_user = db.query(User).filter_by(email=email).first()
        if existing_user:
            db.close()
            flash("Account with that email already exists. Please log in.", "error")
            return redirect(url_for("login"))

        hashed_pw = generate_password_hash(password)

        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_pw,
            display_name=nickname,
            nickname=nickname,
            theme_choice=None,
            timezone=None
        )

        db.add(new_user)
        db.commit()

        # ✅ Initialize session and set defaults
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        session['journey'] = "Not Selected"
        session['timezone'] = "America/New_York"

        db.close()

        flash("Registration successful. Let’s begin your journey.", "success")
        return redirect(url_for("settings"))  # Go to settings right after register

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password")

        db = SessionLocal()
        user = db.query(User).filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['journey'] = user.theme_choice or "Not Selected"
            session['timezone'] = user.timezone or "America/New_York"
            db.close()
            flash("Login successful. Welcome back.", "success")
            return redirect(url_for("menu"))

        db.close()
        flash("Incorrect username or password.", "error")
        return render_template("login.html")

    return render_template("login.html")

@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    message = ""
    if request.method == "POST":
        email = request.form.get("email")
        db = SessionLocal()
        user = db.query(User).filter_by(email=email).first()
        if user:
            reset_code = str(random.randint(100000, 999999))
            session["reset_code"] = reset_code
            session["reset_email"] = email

            # Send the email
            msg = Message("Your Resurgifi Password Reset Code", recipients=[email])
            msg.body = f"Hi there,\n\nUse this code to reset your password: {reset_code}\n\n- The Resurgifi Team"
            mail.send(msg)

            db.close()
            return redirect(url_for("reset_confirm"))
        else:
            message = "No account found with that email."
            db.close()

    return render_template("reset_password.html", message=message)
@app.route("/reset-confirm", methods=["GET", "POST"])
def reset_confirm():
    message = ""
    if request.method == "POST":
        code_entered = request.form.get("reset_code")
        new_password = request.form.get("new_password")

        if code_entered == session.get("reset_code"):
            db = SessionLocal()
            user = db.query(User).filter_by(email=session.get("reset_email")).first()
            if user:
                user.password_hash = generate_password_hash(new_password)
                db.commit()
                db.close()

                session.pop("reset_code", None)
                session.pop("reset_email", None)

                flash("Your password has been reset. Please log in.")
                return redirect(url_for("login"))
            else:
                message = "User not found."
        else:
            message = "Invalid code. Please try again."

    return render_template("reset_confirm.html", message=message)


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
    user = db.query(User).filter_by(username=session['username']).first()
    if not user:
        db.close()
        return redirect(url_for('register'))

    user_timezone = user.timezone if user.timezone in all_timezones else "America/New_York"

    # ✅ Handle new journal submission
    if request.method == 'POST':
        entry = request.form['entry']
        new_entry = JournalEntry(user_id=user.id, content=entry)
        db.add(new_entry)
        db.commit()

    # ✅ Get past entries
    raw_entries = (
        db.query(JournalEntry)
        .filter_by(user_id=user.id)
        .order_by(JournalEntry.timestamp.desc())
        .all()
    )

    # ✅ Localize timestamps
    localized_entries = []
    for entry in raw_entries:
        try:
            local_time = localize_time(entry.timestamp, user_timezone)
            localized_entries.append({
                "id": entry.id,
                "content": entry.content,
                "timestamp": local_time.strftime("%b %d, %I:%M %p")
            })
        except Exception as e:
            localized_entries.append({
                "id": entry.id,
                "content": entry.content,
                "timestamp": "Unknown"
            })

    # ✅ Auto-summarize content from today's Circle (if requested)
    summary_text = request.args.get("summary_text", "")

    db.close()
    current_ring = "The Spark"
    return render_template(
        'journal.html',
        entries=localized_entries,
        current_ring=current_ring,
        summary_text=summary_text
    )

@app.route('/ask', methods=['POST'])
@login_required
def ask():
    try:
        from models import CircleMessage  # ✅ Add this import near the top if not already

        data = request.get_json()
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        if 'session_id' not in session:
            session['session_id'] = str(uuid4())

        user_id = session.get("user_id")

        db = SessionLocal()
        user = db.query(User).filter_by(id=user_id).first()
        nickname = user.nickname if user and user.nickname else user.username

        # 🧠 Pull thread from session (still used for context)
        thread = session.get("circle_thread", [])
        thread.append({"speaker": "User", "text": user_message})
        thread = thread[-20:]  # trim session memory

        # 🧠 Persist user message to DB
        db.add(CircleMessage(user_id=user_id, speaker="User", text=user_message))

        # Store last input time for idle check
        session["last_input_ts"] = datetime.utcnow().isoformat()

        tone = session.get("tone", "neutral")
        onboarding = session.get("onboarding_data", {})
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
                        context=thread,
                        nickname=nickname,
                        onboarding=onboarding
                    )

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": prompt}],
                        temperature=0.6
                    )

                    reply = response.choices[0].message.content.strip()

                    if reply.lower().startswith(f"{hero.lower()}:"):
                        reply = reply[len(hero) + 1:].strip()

                    pause = random.randint(2500, 4000)
                    typing_time = len(reply.split()) * random.randint(65, 80)
                    delay = min(8000, pause + typing_time + i * 900)

                elif mode == "brb":
                    reply = hero_plan.get("text", f"{hero} has stepped away briefly.")
                    delay = 1200 + i * 900

                else:
                    continue

                # ✅ Save hero reply to DB
                db.add(CircleMessage(user_id=user_id, speaker=hero, text=reply))

                results.append({
                    "hero": hero,
                    "text": reply,
                    "delay_ms": delay
                })

                thread.append({"speaker": hero, "text": reply})

                if user and mode == "speak":
                    db.add(QueryHistory(
                        user_id=user.id,
                        question=user_message,
                        agent_name=hero,
                        response=reply
                    ))

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                thread.append({"speaker": hero, "text": error_msg})
                results.append({
                    "hero": hero,
                    "text": error_msg,
                    "delay_ms": 1500 + i * 700
                })

        # ✅ Update session memory
        session["circle_thread"] = thread[-20:]
        db.commit()
        db.close()

        return jsonify({"messages": results})

    except Exception as e:
        import traceback
        print("🔥 /ask route error:", traceback.format_exc())
        return jsonify({"error": "Server error", "details": str(e)}), 500


@app.route('/idle-check', methods=['GET'])
@login_required
def idle_check():
    from models import CircleMessage  # ensure this is imported
    last_ts = session.get("last_input_ts")
    if not last_ts:
        return jsonify({"idle": False})

    try:
        last_time = datetime.fromisoformat(last_ts)
    except:
        return jsonify({"idle": False})

    elapsed = datetime.utcnow() - last_time
    if elapsed < timedelta(seconds=60):
        return jsonify({"idle": False})

    # Pull recent thread
    thread = session.get("circle_thread", [])
    thread_text = " ".join(msg["text"] for msg in thread[-6:] if msg["speaker"] != "System")

    # Banter lines
    banter_lines = {
        "Grace": "I’m still here, Kevin. Just letting the moment breathe.",
        "Sir Renity": "Sometimes silence is strategy. Or snacks. You back?",
        "Lucentis": "If the wind shifts, I’ll know you’re nearby again.",
        "Cognita": "Thinking time is still part of the process.",
        "Velessa": "Even the breath between words has meaning."
    }

    # Avoid repeating last hero
    last_hero = next((msg["speaker"] for msg in reversed(thread) if msg["speaker"] in banter_lines), None)
    options = [h for h in banter_lines if h != last_hero]
    chosen = random.choice(options)

    new_entry = {"speaker": chosen, "text": banter_lines[chosen]}

    # ✅ Save to DB
    db = SessionLocal()
    db.add(CircleMessage(
        user_id=session.get("user_id"),
        speaker=chosen,
        text=banter_lines[chosen]
    ))
    db.commit()
    db.close()

    # ✅ Save to session
    thread.append(new_entry)
    session["circle_thread"] = thread[-20:]

    return jsonify({"idle": True, "message": new_entry})

@app.route("/feedback", methods=["GET", "POST"])
@login_required
def feedback():
    if request.method == "POST":
        message = request.form.get("message")
        user = session.get("username", "Unknown User")

        if message:
            email = Message(
                subject=f"📝 Feedback from {user}",
                recipients=[os.getenv("MAIL_FEEDBACK_RECIPIENT")],
                body=message
            )
            mail.send(email)
            flash("Thanks for your feedback!")
            return redirect(url_for("feedback"))

        flash("Please enter a message.")

    return render_template("feedback.html")
@app.route("/history")
@login_required
def history():
    if 'username' not in session:
        return redirect(url_for('register'))

    db = SessionLocal()
    user = db.query(User).filter_by(username=session['username']).first()

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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)

