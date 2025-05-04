from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
# Test connection
if __name__ == "__main__":
    try:
        with engine.connect() as connection:
            print("✅ Connected to Postgres successfully via SQLAlchemy!")
    except Exception as e:
        print("❌ Failed to connect to the database:")
        print(e)
