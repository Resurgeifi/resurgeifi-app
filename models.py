from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ✅ Association table for friends
friend_association = db.Table(
    'friend_association',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('friend_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)

class User(db.Model):
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

    # 🔐 Privacy toggle for public profile
    show_journey_publicly = db.Column(db.Boolean, default=False)

    # Onboarding fields
    core_trigger = db.Column(db.String(100), nullable=True)
    default_coping = db.Column(db.String(100), nullable=True)
    hero_traits = db.Column(db.JSON, nullable=True)

    # Tracking fields
    journey_start_date = db.Column(db.DateTime, nullable=True)
    journal_count = db.Column(db.Integer, default=0)
    circle_message_count = db.Column(db.Integer, default=0)
    last_journal_entry = db.Column(db.Text, nullable=True)
    last_circle_msg = db.Column(db.Text, nullable=True)
    points = db.Column(db.Integer, default=0)
    last_login = db.Column(db.DateTime, nullable=True)  # ✅ NEW: for dashboard stats

    # ✅ Friends relationship
    friends = db.relationship(
        "User",
        secondary=friend_association,
        primaryjoin=id == friend_association.c.user_id,
        secondaryjoin=id == friend_association.c.friend_id,
        backref="friend_of"
    )

    # ✅ Mood and activity for Circle visuals
    mood_status = db.Column(db.String(50), default="🫥")  # Emoji or mood tag
    last_active = db.Column(db.DateTime, default=datetime.utcnow)


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


class FlashMomentLog(db.Model):
    __tablename__ = "flash_moment_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    source = db.Column(db.String(100))  # e.g., "journal", "quest"
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="flash_moments")


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
    encounter_type = db.Column(db.String(50))  # e.g., "journal", "dream", "panic"
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="villain_encounters")


class SupportGestureLog(db.Model):
    __tablename__ = "support_gestures"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    gesture_type = db.Column(db.String(50), default="balloon")  # or emoji
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
