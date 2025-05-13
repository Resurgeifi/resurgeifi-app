from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)  # ✅ Added
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(150), nullable=True)
    theme_choice = Column(String(100), nullable=True)
    consent = Column(String(10), nullable=True)  # ✅ Added
    created_at = Column(DateTime, default=datetime.utcnow)
    nickname = Column(String(50), nullable=True)
    timezone = Column(String(50), default="UTC")

    # Optional: Relationships for future use
    # journal_entries = relationship("JournalEntry", back_populates="user")
    # questions = relationship("QuestionLog", back_populates="user")

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
