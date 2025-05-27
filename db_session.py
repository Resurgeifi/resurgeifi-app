from sqlalchemy.orm import scoped_session, sessionmaker
from models import db

SessionLocal = None

def init_session(app):
    global SessionLocal
    with app.app_context():
        engine = db.get_engine()  # ✅ pass app correctly
        SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
