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
    theme_choice = db.Column(db.String(100), nullable=True)
    consent = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    nickname = db.Column(db.String(50), nullable=True)
    timezone = db.Column(db.String(50), default="UTC")
    resurgitag = db.Column(db.String(32), unique=True, nullable=True)

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

    # ✅ Friends relationship
    friends = db.relationship(
        "User",
        secondary=friend_association,
        primaryjoin=id == friend_association.c.user_id,
        secondaryjoin=id == friend_association.c.friend_id,
        backref="friend_of"
    )

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

class CircleMessage(db.Model):
    __tablename__ = "circle_messages"

    id = db.Column(db.Integer, primary_key=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    speaker = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="circle_messages")

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


