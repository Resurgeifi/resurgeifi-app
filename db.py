# db.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# ✅ Load .env and get DB URL
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# ✅ Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = scoped_session(sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
))

# ✅ Declare base for models
Base = declarative_base()

# ✅ Optional: test connection
if __name__ == "__main__":
    try:
        with engine.connect() as connection:
            print("✅ Connected to Postgres successfully via SQLAlchemy!")
    except Exception as e:
        print("❌ Failed to connect to the database:")
        print(e)

