import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, Text, Boolean, DateTime, ForeignKey
from openai import OpenAI  # ✅ This is what was missing
from flask_login import UserMixin
db = SQLAlchemy()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class WellMessage(db.Model):
    __tablename__ = "well_messages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Receiver
    sender = Column(Text, nullable=False, default="System")            # Hero, system, or user
    message = Column(Text, nullable=False)
    message_type = Column(Text, nullable=False, default="system")      # 'system', 'hero', 'user'
    read = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<WellMessage from {self.sender} to user {self.user_id}: {'read' if self.read else 'unread'}>"

# ✅ Association table for friends
friend_association = db.Table(
    'friend_association',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('friend_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(150), nullable=True)
    theme_choice = db.Column(db.JSON, nullable=True)
    consent = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    nickname = db.Column(db.String(50), nullable=True)
    timezone = db.Column(db.String(50), default="UTC")
    resurgitag = db.Column(db.String(32), unique=True, nullable=True)
    resurgitag_locked = db.Column(db.Boolean, default=False)
    has_completed_onboarding = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    show_real_name = db.Column(db.Boolean, default=False)
    show_location = db.Column(db.Boolean, default=False)
    show_journey_publicly = db.Column(db.Boolean, default=False)
    show_journey_to_friends = db.Column(db.Boolean, default=True)

    # Onboarding fields
    core_trigger = db.Column(db.String(100), nullable=True)
    default_coping = db.Column(db.String(100), nullable=True)
    hero_traits = db.Column(db.JSON, nullable=True)
    first_quest_complete = Column(Boolean, default=False)

    # Tracking fields
    journey_start_date = db.Column(db.DateTime, nullable=True)
    journal_count = db.Column(db.Integer, default=0)
    circle_message_count = db.Column(db.Integer, default=0)
    last_journal_entry = db.Column(db.Text, nullable=True)
    last_circle_msg = db.Column(db.Text, nullable=True)
    points = db.Column(db.Integer, default=0)
    last_login = db.Column(db.DateTime, nullable=True)

    # Friend system
    friends = db.relationship(
        "User",
        secondary=friend_association,
        primaryjoin=id == friend_association.c.user_id,
        secondaryjoin=id == friend_association.c.friend_id,
        backref="friend_of"
    )

    # Circle status
    mood_status = db.Column(db.String(50), default="🫥")
    last_active = db.Column(db.DateTime, default=datetime.utcnow)

class DirectMessage(db.Model):
    __tablename__ = "direct_messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    deleted_by_sender = db.Column(db.Boolean, default=False)
    deleted_by_recipient = db.Column(db.Boolean, default=False)

    sender = db.relationship("User", foreign_keys=[sender_id], backref="messages_sent")
    recipient = db.relationship("User", foreign_keys=[recipient_id], backref="messages_received")
class UserBlock(db.Model):
    __tablename__ = "user_blocks"

    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    blocked_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    blocker = db.relationship("User", foreign_keys=[blocker_id], backref="blocks_initiated")
    blocked = db.relationship("User", foreign_keys=[blocked_id], backref="blocks_received")

    __table_args__ = (db.UniqueConstraint("blocker_id", "blocked_id", name="_block_uc"),)

class UserBio(db.Model):
    __tablename__ = "user_bio"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    bio_text = db.Column(db.Text)

    user = db.relationship("User", backref="bio")

class JournalEntry(db.Model):
    __tablename__ = "journal_entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="journal_entries")


class QueryHistory(db.Model):
    __tablename__ = "query_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    agent_name = db.Column(db.String(100))
    contact_tag = db.Column(db.String(32), nullable=True)
    sender_role = db.Column(db.String(50), nullable=True)  # 'user' or 'assistant'
    hero_name = db.Column(db.String(50), nullable=True)
    user = db.relationship("User", backref="query_history")


class CircleMember(db.Model):
    __tablename__ = "circle_members"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_hero = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id], backref="circle")
    contact = db.relationship("User", foreign_keys=[contact_id])


class CircleMessage(db.Model):
    __tablename__ = "circle_messages"

    id = db.Column(db.Integer, primary_key=True, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    sender = db.relationship("User", foreign_keys=[sender_id], backref="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], backref="received_messages")


class UserQuestEntry(db.Model):
    __tablename__ = "user_quest_entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    quest_id = db.Column(db.Integer, nullable=False)
    completed = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    summary_text = db.Column(db.Text, nullable=True)

    user = db.relationship("User", backref="quest_entries")


class DailyReflection(db.Model):
    __tablename__ = "daily_reflections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    summary_text = db.Column(db.Text, nullable=False)

    user = db.relationship("User", backref="daily_reflections")


class HeroProfile(db.Model):
    __tablename__ = "hero_profiles"

    id = db.Column(db.Integer, primary_key=True)
    resurgitag = db.Column(db.String(32), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(150), nullable=True)
    represents = db.Column(db.String(150), nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    catchphrase = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    type = db.Column(db.String(20), default="hero")
    image_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class VillainProfile(db.Model):
    __tablename__ = "villain_profiles"

    id = db.Column(db.Integer, primary_key=True)
    resurgitag = db.Column(db.String(64), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    represents = db.Column(db.String(150), nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    catchphrase = db.Column(db.String(255))
    bio = db.Column(db.Text)
    image_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class VillainFlashEncounter(db.Model):
    __tablename__ = "villain_encounters"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    villain_tag = db.Column(db.String(32), nullable=False)
    encounter_type = db.Column(db.String(50))
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="villain_encounters")


class FlashMomentLog(db.Model):
    __tablename__ = "flash_moment_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    source = db.Column(db.String(100))
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="flash_moments")


class SupportGestureLog(db.Model):
    __tablename__ = "support_gestures"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    gesture_type = db.Column(db.String(50), default="balloon")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship("User", foreign_keys=[sender_id], backref="sent_support")
    receiver = db.relationship("User", foreign_keys=[receiver_id], backref="received_support")


class UserSettings(db.Model):
    __tablename__ = "user_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    visibility_mode = db.Column(db.String(50), default="fade")
    receive_check_ins = db.Column(db.Boolean, default=True)
    receive_support = db.Column(db.Boolean, default=True)

    user = db.relationship("User", backref="settings")

# ✅ login_required
 decorator
from functools import wraps
from flask import session, redirect, url_for, flash

def login_required
(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


# ✅ User-to-User Connections
class UserConnection(db.Model):
    __tablename__ = 'user_connections'
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    follower = db.relationship('User', foreign_keys=[follower_id], backref='following_assocs')
    followed = db.relationship('User', foreign_keys=[followed_id], backref='followers_assocs')

