from sqlalchemy.orm import scoped_session, sessionmaker
from models import db

SessionLocal = None  # Global session factory

def init_session(app):
    global SessionLocal
    engine = db.get_engine(app)  # ✅ Properly pass the app to get_engine
    SessionLocal = scoped_session(sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    ))
    print("✅ SessionLocal successfully initialized.")
