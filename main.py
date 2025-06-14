# 🧱 Standard Library
import os
import random
import re
from datetime import datetime, timedelta
from datetime import time

from uuid import uuid4
from utils.quest_loader import load_quest
from utils.timezone_utils import get_user_local_bounds

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

def clean_text_for_voice(raw_text, speaker_name=None):
    """Clean up text to improve voice performance."""
    text = raw_text.replace("...", "…")  # replace with ellipsis character
    text = re.sub(r'\.(\w)', r'. \1', text)  # ensure pause after periods

    if speaker_name and speaker_name.lower() == "grace":
        text = text.replace("dot", ".")  # special rule for Grace if needed

    return text.strip()


# 🔒 Auth + Security
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# 🌍 Flask Core
from flask import Flask, abort, render_template, request, redirect, url_for, session, flash, jsonify, g, Response
from flask_mail import Mail, Message
from flask_cors import CORS

# 🧪 Environment Config
from dotenv import load_dotenv

# 🤖 AI Integration
from openai import OpenAI
import requests  # ✅ For ElevenLabs streaming

# 🧩 Resurgifi Internal
from models import (
    db,
    User,
    UserConnection,
    JournalEntry,
    QueryHistory,
    HeroProfile,
    VillainProfile,
    CircleMessage,
    DailyReflection,
    UserQuestEntry,
    WishingWellMessage
)
from useronboarding import generate_and_store_bio  
from flask_migrate import Migrate
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from rams import get_hero_for_quest, HERO_NAMES, build_context, select_heroes, build_prompt, call_openai
from markupsafe import Markup
import qrcode
import io
import base64
from sqlalchemy import and_


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

# ✅ ElevenLabs Setup
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
GRACE_VOICE_ID = "hIeqtoW1V7vxkxl7mya3"

@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    text = clean_text_for_voice(request.json.get("text", ""))
    if not text:
        return {"error": "No text provided."}, 400

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.7,
            "similarity_boost": 0.75
        }
    }

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{GRACE_VOICE_ID}/stream",
        headers=headers,
        json=payload,
        stream=True
    )

    if response.status_code != 200:
        return {"error": "TTS failed", "details": response.text}, 500

    return Response(response.iter_content(chunk_size=4096),
                    content_type="audio/mpeg")


# ✅ Admin password fallback
admin_password = os.getenv("ADMIN_PASSWORD", "resurgifi123")

# ✅ Admin and user context loading
@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        db_session = SessionLocal()
        try:
            g.user = db_session.query(User).filter_by(id=user_id).first()
            if g.user:
                # ✅ Check for Wishing Well messages
                from models import WellMessage  # adjust path if needed
                unread_count = db_session.query(WellMessage).filter_by(user_id=user_id, read=False).count()
                g.user.has_well_messages = unread_count > 0
        finally:
            db_session.close()
# ✅ Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access Resurgifi.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ✅ Admin access check
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user or not getattr(g.user, "is_admin", False):
            flash("Admin access required.")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function
@app.route("/admin/send-message", methods=["GET", "POST"])
@admin_required
def admin_send_message():
    db = SessionLocal()
    if request.method == "POST":
        user_id = request.form.get("user_id")
        tag = request.form.get("resurgitag")
        content = request.form.get("content")
        sender = request.form.get("sender") or "System"
        msg_type = request.form.get("type") or "system"

        # 🔎 Resolve user
        user = None
        if user_id:
            user = db.query(User).filter_by(id=user_id).first()
        elif tag:
            user = db.query(User).filter_by(resurgitag=tag).first()

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("admin_send_message"))

        # 💌 Create message
        new_msg = WishingWellMessage(
            user_id=user.id,
            sender=sender,
            message_type=msg_type,
            content=content,
            is_public=False,
            is_read=False
        )
        db.add(new_msg)
        db.commit()
        flash("Message sent to user!", "success")
        return redirect(url_for("admin_send_message"))

    return render_template("admin_send_message.html")
@app.route("/connect/<int:user_id>", methods=["GET", "POST"])
@login_required
def connect_user(user_id):
    db = SessionLocal()
    try:
        current_user_id = session.get("user_id")

        # Prevent self-follow
        if current_user_id == user_id:
            flash("You can't follow yourself.", "warning")
            return redirect(url_for("circle"))

        # Check for existing connection
        existing = db.query(UserConnection).filter_by(
            follower_id=current_user_id, followed_id=user_id
        ).first()

        if existing:
            flash("You already follow this user.", "info")
        else:
            new_conn = UserConnection(
                follower_id=current_user_id,
                followed_id=user_id
            )
            db.add(new_conn)
            db.commit()
            flash("🎉 Connection created successfully!", "success")

        # Safe redirect
        user = db.query(User).filter_by(id=user_id).first()
        if user and user.resurgitag:
            return redirect(url_for('view_public_profile', resurgitag=user.resurgitag))
        else:
            return redirect(url_for('circle'))

    finally:
        db.close()

@app.route("/admin/users/<int:user_id>")
@admin_required
def view_user(user_id):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            flash("User not found.", "warning")
            return redirect(url_for("admin_users"))
        return render_template("admin_view_user.html", user=user)
    finally:
        db.close()
@app.route("/admin/users", methods=["GET"])
@admin_required
def admin_users():
    if not g.user or not g.user.is_admin:
        flash("Access denied.")
        return redirect(url_for("menu"))

    db = SessionLocal()
    try:
        search_term = request.args.get("search", "").strip()

        base_query = db.query(User)

        if search_term:
            base_query = base_query.filter(
                (User.email.ilike(f"%{search_term}%")) |
                (User.resurgitag.ilike(f"%{search_term}%")) |
                (User.nickname.ilike(f"%{search_term}%"))
            )

        users = base_query.order_by(User.created_at.desc()).all()

        ghosts = db.query(User).filter(
            User.has_completed_onboarding == False,
            (User.resurgitag == None) | (User.resurgitag == "")
        ).order_by(User.created_at.desc()).all()

    finally:
        db.close()

    return render_template("admin_users.html", users=users, ghosts=ghosts, search_term=search_term)
@app.route("/admin/user/<int:user_id>")
@admin_required
def admin_user_profile(user_id):
    db = SessionLocal()
    user = db.query(User).get(user_id)

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('admin_users'))

    journals = db.query(JournalEntry).filter_by(user_id=user.id).order_by(JournalEntry.timestamp.desc()).limit(20).all()
    messages = db.query(CircleMessage).filter_by(sender=user.resurgitag).order_by(CircleMessage.timestamp.desc()).limit(20).all()

    return render_template("admin_user_profile.html", user=user, journals=journals, messages=messages)

@app.route('/landing')
def landing_alias():
    # If logged in → skip cinematic completely
    if "user_id" in session:
        return redirect(url_for("menu"))

    # If already seen this session → skip to login
    if session.get("seen_intro"):
        return redirect(url_for("login"))

    # First-time visitor (this session)
    session["seen_intro"] = True
    return render_template("landing.html")

# ✅ Grant admin to user
@app.route("/admin/grant_admin", methods=["POST"])
@login_required
@admin_required
def grant_admin():
    tag = request.form.get("resurgitag", "").strip().lstrip("@")
    full_tag = f"@{tag}"
    user = User.query.filter(User.resurgitag.ilike(full_tag)).first()

    if user:
        user.is_admin = True
        db.session.commit()
        flash(f"👑 {user.resurgitag} is now an admin.")
    else:
        flash("⚠️ User not found.")
    
    return redirect(url_for("admin_dashboard"))

# ✅ Admin dashboard view
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    try:
        total_users = db.session.query(User).count()
        start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        active_today = db.session.query(User).filter(User.last_login >= start_of_day).count()
        recent_users = db.session.query(User).order_by(User.created_at.desc()).limit(5).all()
        recent_circle = db.session.query(CircleMessage).order_by(CircleMessage.timestamp.desc()).limit(10).all()
        recent_journals = db.session.query(JournalEntry).order_by(JournalEntry.timestamp.desc()).limit(10).all()

        return render_template("admin_dashboard.html", 
            stats={
                "total_users": total_users,
                "active_today": active_today,
                "recent_users": recent_users
            },
            logs={
                "circle_messages": recent_circle,
                "journal_entries": recent_journals
            }
        )
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Error loading dashboard.")
        return redirect(url_for("index"))

# ✅ Delete ghost users
@app.route("/admin/delete_ghosts", methods=["POST"])
@login_required
@admin_required
def delete_ghosts():
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    ghosts = User.query.filter(
        ((User.email == None) | (User.email == "")),
        (User.resurgitag == None),
        (User.journal_count == 0),
        (User.circle_message_count == 0),
        (User.created_at != None),
        (User.created_at < cutoff)
    ).all()

    count = len(ghosts)
    for ghost in ghosts:
        db.session.delete(ghost)

    db.session.commit()
    flash(f"🕊️ {count} ghost user(s) released into the mist.")
    return redirect(url_for("admin_dashboard"))
@app.route('/admin/grant_points', methods=['POST'])
@login_required
@admin_required
def grant_points():
    db = SessionLocal()
    try:
        resurgitag = request.form.get('resurgitag', '').lstrip('@')
        points = int(request.form.get('points', 0))

        user = db.query(User).filter_by(resurgitag=resurgitag).first()
        if not user:
            flash("User not found.", "error")
            return redirect(url_for('admin_dashboard'))

        user.points = (user.points or 0) + points
        db.commit()

        flash(f"Gave {points} points to @{resurgitag}!", "success")
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        db.rollback()
        flash("Failed to grant points. Error logged.", "error")
        return redirect(url_for('admin_dashboard'))
    finally:
        db.close()

# ✅ Profile view
@app.route("/profile")
@login_required
def profile():
    user_id = session.get("user_id")
    db = SessionLocal()

    try:
        user = db.query(User).filter_by(id=user_id).first()

        if not user:
            flash("User not found.", "error")
            return redirect(url_for('login'))

        clean_tag = user.resurgitag.lstrip("@") if user.resurgitag else "unknown"
        base_url = os.getenv("BASE_URL", request.host_url.rstrip("/"))
        qr_data = f"{base_url}/profile/public/{clean_tag}"

        # ✅ Generate QR code as base64
        qr_img = qrcode.make(qr_data)
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        days_on_journey = (datetime.utcnow() - (user.journey_start_date or datetime.utcnow())).days
        edit_identity = request.args.get("edit_identity") == "true"

        return render_template("profile.html", 
                               user=user,
                               resurgitag=user.resurgitag,
                               points=user.points or 0,
                               days_on_journey=days_on_journey,
                               qr_code_base64=qr_code_base64,
                               public_profile_url=qr_data,  # ✅ ADDED LINE
                               first_name=user.first_name,
                               last_name=user.last_name,
                               city=user.city,
                               state=user.state,
                               show_real_name=user.show_real_name,
                               show_location=user.show_location,
                               edit_identity=edit_identity)

    except SQLAlchemyError:
        db.rollback()
        flash("Something went wrong loading your profile. Please try again.")
        return redirect(url_for('login'))

    finally:
        db.close()
@app.route("/circle/chat/<resurgitag>", methods=["POST"])
@login_required
def circle_chat(resurgitag):
    from inner_codex import INNER_CODEX
    db = SessionLocal()

    user_id = session.get("user_id")
    user_input = request.json.get("message")
    if not user_input:
        return jsonify({"error": "Message missing"}), 400

    tag = resurgitag.strip().lower().lstrip("@")

    # 🧵 Pull last 7 days of conversation
    week_ago = datetime.utcnow() - timedelta(days=7)
    thread_query = db.query(QueryHistory).filter_by(
        user_id=user_id,
        contact_tag=tag
    ).filter(QueryHistory.timestamp >= week_ago).order_by(QueryHistory.timestamp).all()

    context = [
        {"question": entry.question, "response": entry.response}
        for entry in thread_query
    ]

    # 🧠 Check if it's a known hero
    is_hero = tag in [h.lower().replace(" ", "") for h in INNER_CODEX["heroes"].keys()]
    is_villain = tag in [v.lower().replace(" ", "") for v in INNER_CODEX["villains"].keys()]

    if is_hero:
        canon_name = [h for h in INNER_CODEX["heroes"].keys() if h.lower().replace(" ", "") == tag][0]
        response = call_openai(user_input=user_input, hero_name=canon_name, context={
            "thread": context,
            "user_id": user_id,
        })

        # 📝 Save USER message
        db.add(QueryHistory(
            user_id=user_id,
            contact_tag=tag,
            agent_name=canon_name,
            question=user_input,
            response="",
            sender_role="user",
            hero_name=canon_name
        ))

        # 💬 Save HERO response
        db.add(QueryHistory(
            user_id=user_id,
            contact_tag=tag,
            agent_name=canon_name,
            question="",
            response=response,
            sender_role="assistant",
            hero_name=canon_name
        ))

        db.commit()
        return jsonify({"response": response})

    elif is_villain:
        canon_name = [v for v in INNER_CODEX["villains"].keys() if v.lower().replace(" ", "") == tag][0]

        # ❗ Villains get NO journal context
        response = call_openai(user_input=user_input, hero_name=canon_name, context={
            "thread": context,
            "user_id": user_id,
            "suppress_journal": True
        })

        db.add(QueryHistory(
            user_id=user_id,
            contact_tag=tag,
            agent_name=canon_name,
            question=user_input,
            response=response,
            sender_role="user",  # optional: could leave null for villains
            hero_name=canon_name
        ))
        db.commit()
        return jsonify({"response": response})

    else:
        return jsonify({"error": "No matching hero or villain found."}), 404

@app.route("/circle/chat/<resurgitag>", methods=["GET"])
@login_required
def show_hero_chat(resurgitag):
    from inner_codex import INNER_CODEX
    db = SessionLocal()

    user_id = session.get("user_id")
    tag = resurgitag.strip().lower().lstrip("@")

    user = db.query(User).filter_by(id=user_id).first()
    contact_name = None

    # 🔍 Check User table (real people)
    contact = db.query(User).filter_by(resurgitag=tag).first()
    if contact and getattr(contact, "is_hero", False):
        contact_name = contact.nickname or contact.display_name or tag

    # 🦸 Check HeroProfile if not found
    if not contact_name:
        hero = db.query(HeroProfile).filter_by(resurgitag=tag).first()
        if hero:
            contact_name = hero.display_name or tag

    # 🧟‍♂️ Check Villains
    if not contact_name:
        villain_map = {
            k.lower().replace(" ", "").replace("@", ""): k
            for k in INNER_CODEX["villains"].keys()
        }
        if tag in villain_map:
            contact_name = villain_map[tag]
            messages = [{"speaker": contact_name, "text": f"{contact_name} waits in the shadows…"}]
            return render_template("chat.html", resurgitag=tag, messages=messages, display_name=contact_name, quest_flash=False)

        flash("Hero not found.")
        return redirect(url_for("circle"))

    # 💬 Pull 7-day message history
    week_ago = datetime.utcnow() - timedelta(days=7)
    thread = db.query(QueryHistory).filter_by(
        user_id=user.id,
        contact_tag=tag
    ).filter(QueryHistory.timestamp >= week_ago).order_by(QueryHistory.timestamp).all()

    messages = []
    for entry in thread:
        messages.append({"speaker": "You", "text": entry.question})
        messages.append({"speaker": contact_name, "text": entry.response})

    # 🧙 Handle quest reflection if present
    quest_reflection = session.pop("from_quest", None)
    quest_flash = False
    reflection_text = ""

    if quest_reflection:
        reflection_text = quest_reflection.get("reflection", "")
        messages.insert(0, {"speaker": "You", "text": reflection_text})
        quest_flash = True

        # 🧠 Trigger AI reflection response
        canon_name = contact_name
        context = {"thread": [], "user_id": user_id}

        try:
            ai_response = call_openai(
                user_input=reflection_text,
                hero_name=canon_name,
                context=context
            )
            messages.insert(1, {"speaker": canon_name, "text": ai_response})

            # ✅ Save to DB
            db.add(QueryHistory(
                user_id=user_id,
                contact_tag=tag,
                agent_name=canon_name,
                question=reflection_text,
                response=ai_response
            ))
            db.commit()
        except Exception as e:
            print(f"⚠️ AI quest reflection failed: {e}")

    return render_template("chat.html", resurgitag=tag, messages=messages, display_name=contact_name, quest_flash=quest_flash)

@app.route("/codex")
def inner_codex():
    return render_template("codex.html")
@app.route("/summarize-journal", methods=["GET"])
@login_required
def summarize_journal():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    user_id = session.get("user_id")
    db = SessionLocal()

    user = db.query(User).filter_by(id=user_id).first()
    start_of_day, end_of_day = get_user_local_bounds(user)

    # 🕒 Time zone debug
    print("🕒 [DEBUG] Time Zone Summary Check")
    print("User time zone:", user.timezone)
    print("Start of day UTC:", start_of_day)
    print("End of day UTC:", end_of_day)

    # 🎯 Query valid hero-tagged messages
    messages = db.query(QueryHistory).filter(
        and_(
            QueryHistory.user_id == user_id,
            QueryHistory.sender_role == "user",
            QueryHistory.hero_name.isnot(None),
            QueryHistory.timestamp.between(start_of_day, end_of_day)
        )
    ).order_by(QueryHistory.timestamp).all()

    if not messages:
        print("🚫 No qualifying hero messages found today. Dumping all messages between bounds:")
        all_today = db.query(QueryHistory).filter(
            QueryHistory.user_id == user_id,
            QueryHistory.timestamp.between(start_of_day, end_of_day)
        ).order_by(QueryHistory.timestamp).all()

        for msg in all_today:
            preview = (msg.question or "")[:50]
            print(f"[{msg.timestamp}] role={msg.sender_role}, hero={msg.hero_name}, input={preview}...")

        flash("Talk to at least one hero today before summarizing.", "warning")
        db.close()
        return redirect(url_for("journal"))

    # ✅ Format chat for GPT
    formatted = "\n".join([f'User: "{msg.question}"' for msg in messages])

    nickname = user.nickname or "Friend"
    theme = user.theme_choice or "self-discovery"
    display_name = user.display_name or "compassionate people"

    prompt = f"""
You are Resurgifi, a recovery-focused journaling assistant.

The user goes by the nickname: {nickname}
Their theme for joining Resurgifi is: {theme}
They admire people who are: {display_name}

Here’s what they said in today’s chats with Resurgifi heroes:
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
        flash("Journal summary generated successfully.", "success")

    except Exception as e:
        print("🔥 Journal summarization error:", str(e))
        flash("Something went wrong while generating your summary.", "error")
        db.rollback()

    db.close()
    return redirect(url_for("journal", auto_summarize="true", summary_text=journal_text))

@app.route("/about", methods=["GET", "POST"])
@login_required
def about():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        # Optional: Log it or send email — already working

        flash("Message sent! We'll be in touch soon. 💌", "success")
        return redirect(url_for("about"))  # Safely redirect to avoid resubmission

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
            .filter(CircleMessage.sender_id == user.id)
            .filter(CircleMessage.timestamp >= start_today)
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

@app.route('/form')
@login_required
def form():
    db = SessionLocal()
    try:
        user_id = session.get("user_id")

        # Pull users this user is following
        connections = db.query(User).join(UserConnection, User.id == UserConnection.followed_id)\
            .filter(UserConnection.follower_id == user_id)\
            .order_by(User.nickname.asc()).all()

        return render_template('form.html', connected_users=connections, current_time=datetime.utcnow())
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

        if request.method == "POST":
            form = request.form

            # 🌀 Journey selection
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

            # 📅 Start date
            date_str = form.get("journey_start_date")
            if date_str:
                try:
                    user.journey_start_date = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    flash("Invalid date format for journey start.", "error")

            # 📝 Nickname
            nickname = form.get("nickname", "").strip()
            if nickname:
                user.nickname = nickname
                user.display_name = nickname
                session['nickname'] = nickname

            # 🕒 Time zone selection
            tz = form.get("timezone")
            if tz:
                user.timezone = tz

            # 👁️ Visibility toggle (still available in user.profile)
            user.show_journey_publicly = 'show_journey_publicly' in form

            db.commit()
            flash("Settings updated successfully.", "success")
            return redirect(url_for('settings'))

        # 🧠 Pull saved values for GET
        try:
            journey_start_date = (
                user.journey_start_date.strftime('%Y-%m-%d')
                if isinstance(user.journey_start_date, datetime)
                else ""
            )
        except Exception:
            journey_start_date = ""

        return render_template(
            "settings.html",
            theme_choice=user.theme_choice,
            journey_start_date=journey_start_date,
            nickname=user.nickname or "",
            timezone=user.timezone or "America/New_York",  # Defaults to EST if none set
            show_journey_publicly=user.show_journey_publicly,
            datetime=datetime
        )

    except SQLAlchemyError:
        db.rollback()
        flash("Error loading or saving settings. Please try again.", "error")
        return redirect(url_for("menu"))
    finally:
        db.close()


@app.route("/profile/update-visibility", methods=["POST"])
@login_required
def update_visibility():
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=session['user_id']).first()
        if not user:
            flash("User not found.", "error")
            return redirect(url_for('profile'))

        form = request.form

        # ✅ Personal info
        user.first_name = form.get("first_name", "").strip() or None
        user.last_name = form.get("last_name", "").strip() or None
        user.city = form.get("city", "").strip() or None
        user.state = form.get("state", "").strip() or None

        # ✅ Visibility toggles
        user.show_real_name = 'show_real_name' in form
        user.show_location = 'show_location' in form

        db.commit()
        flash("Visibility preferences updated!", "success")
        return redirect(url_for("profile"))

    except SQLAlchemyError:
        db.rollback()
        flash("Something went wrong while saving preferences.", "error")
        return redirect(url_for("profile"))
    finally:
        db.close()


@app.route("/profile/public/<resurgitag>")
def view_public_profile(resurgitag):
    db = SessionLocal()
    try:
        # Normalize tag: remove leading @ if present, and lowercase it
        clean_tag = f"@{resurgitag.lstrip('@').lower()}"

        user = db.query(User).filter(User.resurgitag.ilike(clean_tag)).first()

        if not user:
            flash("No user found with that Resurgitag.")
            return render_template("not_found.html", message="This profile doesn't exist."), 404

        # Used to calculate days on journey
        return render_template("public_profile.html", friend=user, current_time=datetime.utcnow())

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

            # 🧠 Generate unique resurgitag using global function
            fallback_nickname = "traveler"
            existing_tags = {u.resurgitag for u in db.query(User).filter(User.resurgitag.isnot(None)).all()}
            resurgitag = generate_resurgitag(fallback_nickname)
            while resurgitag in existing_tags:
                resurgitag = generate_resurgitag(fallback_nickname)

            # ✅ Create new user with resurgitag
            new_user = User(
                email=email,
                password_hash=hashed_pw,
                nickname=None,
                display_name=None,
                theme_choice=None,
                consent=None,
                journey_start_date=None,
                timezone=None,
                resurgitag=resurgitag,
                resurgitag_locked=False
            )

            db.add(new_user)
            db.commit()

            session['user_id'] = new_user.id
            session['journey'] = "Not Selected"
            session['timezone'] = "America/New_York"

            flash("Registration successful. Let’s begin your journey.", "success")
            return redirect(url_for("onboarding"))

        except SQLAlchemyError:
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

                # ✅ Only redirect to onboarding if it hasn't been completed
                if not user.has_completed_onboarding:
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
        thread = thread[-20:]

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

                hero_user = db.query(User).filter_by(resurgitag=f"@{hero}", resurgitag_locked=True).first()

                db.session.add(CircleMessage(sender_id=user_id, receiver_id=hero_user.id, text=user_message))
                db.session.add(CircleMessage(sender_id=hero_user.id, receiver_id=user_id, text=reply))

                db.session.add(QueryHistory(
                    user_id=user.id,
                    question=user_message,
                    agent_name=hero,
                    response=reply
                ))

                thread.append({"speaker": hero, "text": reply})

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
            session["points_just_added"] = 3

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
@app.route("/wishing_well", methods=["GET", "POST"])
@login_required
def wishing_well():
    db = SessionLocal()
    user_id = session["user_id"]

    try:
        if request.method == "POST":
            message = request.form.get("wish_message", "").strip()
            is_public = request.form.get("is_public") == "on"

            if not message:
                flash("Your wish cannot be empty.", "warning")
                return redirect(url_for("wishing_well"))

            new_wish = WishingWellMessage(
                user_id=user_id,
                sender="user",
                message_type="wish",
                content=message,
                is_public=is_public
            )
            db.add(new_wish)
            db.commit()
            flash("🌠 Your wish has been cast into the Well.", "success")
            return redirect(url_for("wishing_well"))

        # ✅ Get last 5 unread *non-wish* messages
        unread_scrolls = (
            db.query(WishingWellMessage)
            .filter(
                WishingWellMessage.user_id == user_id,
                WishingWellMessage.is_read == False,
                WishingWellMessage.message_type != "wish"
            )
            .order_by(WishingWellMessage.timestamp.asc())
            .limit(5)
            .all()
        )

        # 🎁 Package scrolls for display
        scroll_payload = [
            {
                "content": scroll.content,
                "signed_by": scroll.sender or "The Well"
            }
            for scroll in unread_scrolls
        ]

        # 🌍 Optional: get recent public user wishes
        recent_wishes = (
            db.query(WishingWellMessage)
            .filter_by(message_type="wish", is_public=True)
            .order_by(WishingWellMessage.timestamp.desc())
            .limit(15)
            .all()
        )

        return render_template(
            "wishing_well.html",
            unread_scrolls=scroll_payload,
            wishes=recent_wishes
        )

    except Exception as e:
        db.rollback()
        print("🧨 Wishing Well Error:", e)
        flash("Something went wrong. Try again soon.", "error")
        return redirect(url_for("menu"))

    finally:
        db.close()
@app.route("/api/mark_scroll_read", methods=["POST"])
@login_required
def mark_scroll_read():
    from flask import jsonify
    db = SessionLocal()

    try:
        data = request.get_json()
        scroll_id = data.get("scroll_id")

        if not scroll_id:
            return jsonify({"error": "Missing scroll_id"}), 400

        scroll = db.query(WishingWellMessage).filter_by(id=scroll_id, user_id=session["user_id"]).first()
        if not scroll:
            return jsonify({"error": "Scroll not found"}), 404

        scroll.is_read = True
        db.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        db.rollback()
        print("🧨 Scroll Read Error:", e)
        return jsonify({"error": "Server error"}), 500

    finally:
        db.close()

@app.route('/wishing_well_archive')
@login_required
def wishing_well_archive():
    from db import SessionLocal
    db_session = SessionLocal()
    user_id = session.get("user_id")

    messages = db_session.query(WishingWellMessage)\
        .filter_by(user_id=user_id)\
        .order_by(WishingWellMessage.timestamp.desc())\
        .all()

    # Mark messages as read
    for msg in messages:
        if not msg.is_read:
            msg.is_read = True
    db_session.commit()

    return render_template("wishing_well_archive.html", messages=messages)

@app.context_processor
def inject_global_well_status():
    from models import WishingWellMessage
    if "user_id" in session:
        db = SessionLocal()
        try:
            has_unread = db.query(WishingWellMessage).filter_by(
                user_id=session["user_id"],
                message_type="wish",
                is_read=False
            ).count() > 0
            return {"has_wish_messages": has_unread}
        finally:
            db.close()
    return {"has_wish_messages": False}

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
    db = SessionLocal()
    user = db.query(User).filter_by(id=session['user_id']).first()
    if not user:
        flash("User not found.")
        return redirect(url_for('onboarding'))

    form = request.form

    # ⛏️ Extract form data
    q1 = form.get("q1")  # Core trigger
    q2 = form.get("q2")  # Default coping strategy
    q3 = form.getlist("q3")  # Hero trait preferences (checkboxes)

    # 🧠 Save to user object
    user.core_trigger = q1
    user.default_coping = q2
    user.hero_traits = q3
    user.onboarding_complete = True

    db.commit()  # 💾 Save changes before using data

    # ✅ Generate and store bio from raw form values
    generate_and_store_bio(
        user_id=user.id,
        q1=q1,
        q2=q2,
        q3_traits=q3
    )

    db.close()
    flash("Onboarding complete. Welcome aboard. 🛟")
    return redirect(url_for('menu'))


@app.route("/onboarding", methods=["GET"])
@login_required
def onboarding():
    return render_template("onboarding.html")

@app.route("/quest/<int:quest_id>", methods=["GET", "POST"])
@login_required
def run_quest(quest_id):
    db_session = SessionLocal()
    try:
        user_id = session.get("user_id")
        user = db_session.query(User).get(user_id)
        now = datetime.utcnow()

        # 🔁 Load quest YAML
        quest = load_quest(quest_id)

        if request.method == "POST":
            reflection = request.form.get("reflection", "").strip()
            if not reflection:
                flash("Please enter a reflection to submit.", "warning")
                return redirect(url_for("run_quest", quest_id=quest_id))

            four_hours_ago = now - timedelta(hours=4)
            recent_quests = db_session.query(UserQuestEntry)\
                .filter_by(user_id=user_id)\
                .filter(UserQuestEntry.timestamp >= four_hours_ago).all()

            if len(recent_quests) >= 3:
                flash("You’ve already completed 3 quests in the last 4 hours. Take a break and come back soon!", "info")
                return redirect(url_for("circle"))

            # ✨ GPT Summary
            summary_text = ""
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Summarize this quest reflection in one short, emotional sentence. Do not sound robotic."},
                        {"role": "user", "content": reflection}
                    ],
                    temperature=0.7
                )
                summary_text = response.choices[0].message.content.strip()
            except Exception as e:
                print("⚠️ GPT summarization failed:", e)
                summary_text = ""

            new_entry = UserQuestEntry(
                user_id=user_id,
                quest_id=quest_id,
                completed=True,
                timestamp=now,
                summary_text=summary_text or reflection
            )
            db_session.add(new_entry)
            user.points = (user.points or 0) + 5
            session["points_just_added"] = 5
            db_session.commit()

            hero_tag = quest["hero"]
            session["from_quest"] = {
                "quest_id": quest_id,
                "reflection": summary_text or reflection
            }

            return redirect(url_for("show_hero_chat", resurgitag=hero_tag.lower()))

        return render_template("quest_engine.html", quest=quest, quest_id=quest_id)

    except Exception as e:
        db_session.rollback()
        flash("Quest processing failed. Please try again.", "error")
        print(f"❌ Quest route error: {e}")
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

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("login"))

        if user.resurgitag_locked:
            flash("You can only change your Resurgitag once.", "warning")
            return redirect(url_for("profile"))

        if request.method == "POST":
            new_tag = request.form.get("new_tag", "").strip().lower()

            if not new_tag.startswith("@"):
                new_tag = "@" + new_tag

            if len(new_tag) > 32:
                flash("Tag must be 32 characters or less.", "error")
                return render_template("change_tag.html", current_tag=user.resurgitag)

            existing = db.query(User).filter_by(resurgitag=new_tag).first()
            if existing:
                flash("That tag is already taken. Try another.", "error")
            else:
                # Optional: Notify friends or log tag change
                user.resurgitag = new_tag
                user.resurgitag_locked = True
                db.commit()
                flash("Your Resurgitag has been updated!", "success")
                return redirect(url_for("profile"))

        return render_template("change_tag.html", current_tag=user.resurgitag)

    finally:
        db.close()
@app.route("/circle")
@login_required
def circle():
    return redirect(url_for("form"))  # or wherever the new Circle interface lives

@app.route('/hero/<resurgitag>')
def hero_profile(resurgitag):
    resurgitag_clean = resurgitag.lower().strip('@')
    hero = HeroProfile.query.filter_by(resurgitag=resurgitag_clean, type='hero').first()
    if not hero:
        return abort(404)

    # 👇 Dynamically assign image path if it's missing
    if not hero.image_path:
        hero.image_path = f"/static/images/heroes/{resurgitag_clean}/{resurgitag_clean}_profile.png"

    # 🔗 Static hero links
    hero_links = {
        'lucentis': ['grace', 'velessa'],
        'grace': ['lucentis', 'sirrenity'],
        'velessa': ['grace', 'cognita'],
        'sirrenity': ['cognita', 'lucentis'],
        'cognita': ['sirrenity', 'velessa']
    }
    linked_allies = hero_links.get(resurgitag_clean, [])

    return render_template(
        'hero_profile.html',
        hero=hero,
        allies=linked_allies
    )


@app.route('/villain/<resurgitag>')
def villain_profile(resurgitag):
    from models import VillainProfile
    db = SessionLocal()
    try:
        villain = db.query(VillainProfile).filter_by(resurgitag=resurgitag.lower().strip('@')).first()
        if not villain:
            return abort(404)

        # Static relationship map for now (expand later as canon grows)
        villain_links = {
            'thecrave': ['highnesshollow', 'wardenfall'],
            'highnesshollow': ['thecrave', 'theundermind'],
            'wardenfall': ['theundermind', 'charnobyl'],
            'theundermind': ['highnesshollow', 'themurk'],
            'charnobyl': ['wardenfall', 'anxia'],
            'anxia': ['charnobyl', 'littlelack'],
            'littlelack': ['anxia', 'theexs'],
            'theexs': ['littlelack', 'captainfine'],
            'captainfine': ['theexs', 'themurk'],
            'themurk': ['theundermind', 'anxia']
        }
        linked_villains = villain_links.get(villain.resurgitag, [])

        return render_template(
            'villain_profile.html',
            villain=villain,
            linked_villains=linked_villains
        )
    finally:
        db.close()
@app.route("/<path:any_path>")
def universal_fallback(any_path):
    # Prevent catching static files, favicon, or admin/backend routes
    if any_path.startswith(("static/", "admin", "favicon")):
        abort(404)
    return render_template("coming_soon.html")

@app.errorhandler(404)
def fallback_404(error):
    return render_template("coming_soon.html"), 404
@app.route("/dev/seed_scrolls")
@login_required
def dev_seed_scrolls():
    db = SessionLocal()
    user_id = session["user_id"]

    try:
        # Create 5 fake scroll messages
        messages = [
            ("You came back. That’s everything.", "System"),
            ("A friend joined your Circle.", "Sarah"),
            ("The water remembers you.", "Lucentis"),
            ("You're still here. That counts.", "Velessa"),
            ("You made it through today.", "Grace")
        ]

        for content, sender in messages:
            msg = WishingWellMessage(
                user_id=user_id,
                sender=sender,
                message_type="scroll",
                content=content,
                is_public=False,
                is_read=False  # <-- make sure this exists in your model!
            )
            db.add(msg)

        db.commit()
        flash("✅ Dev scrolls seeded into your wishing well.", "success")
        return redirect(url_for("wishing_well"))

    except Exception as e:
        db.rollback()
        flash("🧨 Could not seed scrolls.", "error")
        print("Seeding error:", e)
        return redirect(url_for("menu"))

    finally:
        db.close()
# Optional but useful for local testing
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
