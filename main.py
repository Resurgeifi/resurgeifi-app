import os
import random
from datetime import datetime
from uuid import uuid4

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mail import Mail, Message
from markupsafe import Markup
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from openai import OpenAI
from models import JournalEntry, QueryHistory, User
from db import SessionLocal, engine
from models import Base

# ✅ Load environment variables
load_dotenv()

# ✅ Initialize Flask app
app = Flask(__name__)
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
        journey=session.get('journey'),
        streak=session.get('streak', 0),
        last_entry=session.get('last_entry', None)
    )


@app.route("/onboarding", methods=['GET', 'POST'])
@login_required
def onboarding():
    if request.method == 'POST':
        journey = request.form.get('journey')
        if journey:
            session['journey'] = journey  # Save in session (or DB if needed later)
            return redirect(url_for('menu'))
    return render_template("onboarding.html")


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
    if request.method == "POST":
        journey = request.form.get("journey")
        if journey:
            session['journey'] = journey
            flash("Journey updated to: " + journey.replace("_", " ").title())
            return redirect(url_for('settings'))
    return render_template("settings.html")


@app.route('/burnthrough', methods=['GET', 'POST'])
def burnthrough():
    if request.method == 'POST':
        question = request.form['question']
        return redirect(url_for('ask'), code=307)
    return render_template('burnthrough.html')


@app.route('/eileen')
def eileen():
    return render_template('eileen.html')


@app.route('/journal', methods=['GET', 'POST'])
def journal():
    if 'username' not in session:
        return redirect(url_for('register'))

    db = SessionLocal()
    user = db.query(User).filter_by(username=session['username']).first()
    if not user:
        db.close()
        return redirect(url_for('register'))

    if request.method == 'POST':
        entry = request.form['entry']
        new_entry = JournalEntry(user_id=user.id, content=entry)
        db.add(new_entry)
        db.commit()

    entries = (
        db.query(JournalEntry)
        .filter_by(user_id=user.id)
        .order_by(JournalEntry.timestamp.desc())
        .all()
    )
    db.close()

    return render_template('journal.html', entries=entries)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db = SessionLocal()
        try:
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            consent = request.form.get('consent')

            # Validate form fields
            if not username or not email or not password or not confirm_password or not consent:
                return render_template('register.html', error="Please fill out all fields and check the box.")

            if password != confirm_password:
                return render_template('register.html', error="Passwords do not match.")

            # Check if user already exists by username or email
            existing_user = db.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()

            if existing_user:
                return render_template('register.html', error="Username or email already in use.")

            # Create new user
            hashed_pw = generate_password_hash(password)
            new_user = User(
                username=username,
                email=email,
                password_hash=hashed_pw,
                consent=consent
            )
            db.add(new_user)
            db.commit()

            # Set session
            session['username'] = username
            session['session_id'] = str(uuid4())
            session['user_id'] = new_user.id

            return redirect(url_for('onboarding'))

        except Exception as e:
            db.rollback()
            print("[REGISTRATION ERROR]", e)
            return render_template('register.html', error="Something went wrong. Please try again.")

        finally:
            db.close()

    return render_template('register.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password")

        db = SessionLocal()
        user = db.query(User).filter_by(username=username).first()
        db.close()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for("menu"))

        flash("Incorrect username or password.")
        return render_template("login.html")

    return render_template("login.html")


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


@app.route('/ask', methods=['POST'])
@login_required
def ask():
    question = request.form.get("question")
    if not question:
        return redirect(url_for("menu"))

    if 'session_id' not in session:
        session['session_id'] = str(uuid4())
    user_id = session['session_id']

    db = SessionLocal()
    user = db.query(User).filter_by(username=session.get('username')).first()

    agents = [
        {"name": "Cognita – The Mindshift Operative", "prompt": "You are Cognita, master of cognitive reframing..."},
        {"name": "Velessa – Goddess of the Present Moment", "prompt": "You are Velessa. Bring mindfulness..."},
        {"name": "Grace – The Light Within", "prompt": "You are Grace, the spiritual guide..."},
        {"name": "Serenity – The Healer of Peace", "prompt": "You are Serenity. Help the user regulate..."},
        {"name": "Lucentis – Guardian of Clarity", "prompt": "You are Lucentis, the spiritual guardian..."}
    ]

    previous_responses = {}
    log_entries = []

    for agent in agents:
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": agent["prompt"]},
                    {"role": "user", "content": question}
                ],
                temperature=0.7
            )
            reply = response.choices[0].message.content
            previous_responses[agent["name"]] = Markup(reply)
            log_entries.append(f"{agent['name']}\n{reply}\n")

            if user:
                db.add(QueryHistory(
                    user_id=user.id,
                    question=question,
                    agent_name=agent["name"],
                    response=reply
                ))

        except Exception as e:
            error_msg = f"<em>Error: {e}</em>"
            previous_responses[agent["name"]] = Markup(error_msg)
            log_entries.append(f"{agent['name']}\n{error_msg}\n")

    if user:
        db.commit()
    db.close()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs("logs", exist_ok=True)
    with open("logs/conversations.log", "a", encoding="utf-8") as f:
        f.write(f"\n---\nTime: {timestamp}\nUser ID: {user_id}\nQuestion: {question}\n")
        for entry in log_entries:
            f.write(f"{entry}\n")

    referer = request.headers.get("Referer", "")
    if "/form" in referer:
        return render_template("form.html", results=previous_responses)
    else:
        return render_template("burnthrough.html", results=previous_responses)
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


if __name__ == '__main__':
    app.run(debug=True, port=5050)
