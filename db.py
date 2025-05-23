from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

# ✅ Optional: Flask-aware base if used
try:
    from main import db
    Base = db.Model
except:
    Base = declarative_base()

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ✅ Test connection
if __name__ == "__main__":
    try:
        with engine.connect() as connection:
            print("✅ Connected to Postgres successfully via SQLAlchemy!")
    except Exception as e:
        print("❌ Failed to connect to the database:")
        print(e)
