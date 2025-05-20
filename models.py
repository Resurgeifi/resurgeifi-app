from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(150), nullable=True)
    theme_choice = Column(String(100), nullable=True)
    consent = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    nickname = Column(String(50), nullable=True)
    timezone = Column(String(50), default="UTC")

    # ✅ NEW tracking fields
    journey_start_date = Column(DateTime, nullable=True)
    journal_count = Column(Integer, default=0)
    circle_message_count = Column(Integer, default=0)
    last_journal_entry = Column(Text, nullable=True)
    last_circle_msg = Column(Text, nullable=True)

class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="journal_entries")

class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    agent_name = Column(String(100))

    user = relationship("User", backref="query_history")

class CircleMessage(Base):
    __tablename__ = "circle_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    speaker = Column(String(100), nullable=False)
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="circle_messages")
