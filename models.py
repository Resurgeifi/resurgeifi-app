from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(150), nullable=True)
    theme_choice = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Optional: Relationships for future use
    # journal_entries = relationship("JournalEntry", back_populates="user")
    # questions = relationship("QuestionLog", back_populates="user")
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import relationship

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
    agent_name = Column(String(100))  # ✅ FIXED
    user = relationship("User", backref="query_history")
