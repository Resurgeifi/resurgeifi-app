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
from flask import Flask, abort, render_template, request, redirect, url_for, session, flash
from flask_mail import Mail, Message
from flask_cors import CORS  # ✅ Add this to support cross-origin POSTs

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
CORS(app)  # ✅ Now placed after app init

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

# ✅ Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access Resurgifi.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
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

    if request.method == 'POST':
        entry = request.form['entry']
        new_entry = JournalEntry(user_id=user.id, content=entry)
        db.add(new_entry)
        db.commit()

    raw_entries = (
        db.query(JournalEntry)
        .filter_by(user_id=user.id)
        .order_by(JournalEntry.timestamp.desc())
        .all()
    )

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

    db.close()
    current_ring = "The Spark"
    return render_template('journal.html', entries=localized_entries, current_ring=current_ring)

@app.route('/ask', methods=['POST'])
@login_required
def ask():
    question = request.form.get("question")
    if not question:
        return redirect(url_for("menu"))

    if 'session_id' not in session:
        session['session_id'] = str(uuid4())
    user_id = session.get("user_id")

    db = SessionLocal()
    user = db.query(User).filter_by(id=user_id).first()
    db.close()

    # 🔍 Step 1: RAMS — Build context and fixed hero order
    context = build_context(user_id)
    heroes = HERO_NAMES  # <-- fixed order: Grace → Cognita → Velessa → Lucentis → Sir Renity
    hero_pairs = list(zip(heroes, heroes[1:] + [None]))

    previous_responses = {}
    log_entries = []

    db = SessionLocal()

    for i, (hero, next_hero) in enumerate(hero_pairs):
        previous_hero = hero_pairs[i - 1][0] if i > 0 else None
        try:
            prompt = build_prompt(hero, question, context, next_hero=next_hero, previous_hero=previous_hero)

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.8
            )
            reply = response.choices[0].message.content.strip()

            previous_responses[hero] = Markup(reply)
            log_entries.append(f"{hero}\n{reply}\n")

            if user:
                db.add(QueryHistory(
                    user_id=user.id,
                    question=question,
                    agent_name=hero,
                    response=reply
                ))

        except Exception as e:
            error_msg = f"<em>Error: {e}</em>"
            previous_responses[hero] = Markup(error_msg)
            log_entries.append(f"{hero}\n{error_msg}\n")

    if user:
        db.commit()
    db.close()

    # 🗂️ Step 4: Log to file
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs("logs", exist_ok=True)
    with open("logs/conversations.log", "a", encoding="utf-8") as f:
        f.write(f"\n---\nTime: {timestamp}\nUser ID: {user_id}\nQuestion: {question}\n")
        for entry in log_entries:
            f.write(f"{entry}\n")

    # ✅ Step 5: Let frontend know this was the last hero
    is_last_hero = True

    return render_template("circle.html", results=previous_responses, is_last_hero=is_last_hero)

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
        return render_template("thankyou.html")

    return "No message provided", 400


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
@app.route('/new_circle')
def new_circle():
    return render_template('new_circle.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)

