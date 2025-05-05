from flask import Flask, render_template, request, redirect, url_for, session
from markupsafe import Markup
import os
from datetime import datetime
from uuid import uuid4
from openai import OpenAI
from dotenv import load_dotenv
from models import JournalEntry, QueryHistory, User  # ✅ Moved here
from db import SessionLocal, engine
from models import Base  # You already import User etc.

# Load OpenAI API key from .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
admin_password = os.getenv("ADMIN_PASSWORD", "resurgifi123")
client = OpenAI(api_key=api_key)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "resurgifi-dev-key")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route('/')
def landing():
    return render_template('landing.html')


@app.route("/menu")
def menu():
    if 'username' not in session:
        return redirect(url_for('register'))
    cards = [
        {"title": "Inner Circle", "description": "Ask the AI Circle for insight and support", "link": "/form", "button_text": "Enter"},
        {"title": "Burnthrough", "description": "Process anger, betrayal, or emotional overload", "link": "/burnthrough", "button_text": "Begin"},
        {"title": "Dev Date", "description": "Code gently with Eileen", "link": "/eileen", "button_text": "Let’s Go"},
        {"title": "Journal", "description": "Write freely, reflect deeply", "link": "/journal", "button_text": "Open Journal"},
        {"title": "Dashboard", "description": "View your progress", "link": "/dashboard", "button_text": "Check Stats"}
    ]
    return render_template("carousel.html", cards=cards)


@app.route("/onboarding")
def onboarding():
    return render_template("onboarding.html")


@app.route('/form', methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        question = request.form['question']
        return redirect(url_for('ask'), code=307)
    return render_template('form.html')


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
        username = request.form['username'].strip()
        password = request.form['password']
        display_name = request.form.get('display_name', '').strip()
        theme_choice = request.form['theme_choice']

        if db.query(User).filter_by(username=username).first():
            db.close()
            return render_template('register.html', error="Username already taken.")

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            display_name=display_name or None,
            theme_choice=theme_choice
        )
        db.add(user)
        db.commit()
        db.close()

        session['username'] = username
        session['theme_choice'] = theme_choice
        session['session_id'] = str(uuid4())  # ✅ Ensures dashboard and /ask won't break

        return redirect(url_for('menu'))

    return render_template('register.html')


@app.route('/user/logout')
def user_logout():
    session.clear()
    return redirect(url_for('register'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get("password")
        if password == admin_password:
            session['admin'] = True
            return redirect(url_for('admin_logs'))
        return render_template('login.html', error="Incorrect password")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))


@app.route('/admin/logs')
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


@app.route("/history")
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
