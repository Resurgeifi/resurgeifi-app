# db_sessions.py
from models import db
from sqlalchemy.orm import scoped_session, sessionmaker

SessionLocal = None

def init_session(app):
    global SessionLocal
    engine = db.get_engine(app)
    SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
