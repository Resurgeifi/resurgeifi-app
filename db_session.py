from sqlalchemy.orm import scoped_session, sessionmaker
from models import db

SessionLocal = None

def init_session(app):
    global SessionLocal
    with app.app_context():  # 🔒 Ensures Flask context is available when initializing
        engine = db.get_engine(app)
        SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
