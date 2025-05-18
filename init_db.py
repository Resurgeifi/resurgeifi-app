from db import engine
from models import Base

if __name__ == "__main__":
    print("📦 Creating missing tables if needed...")
    Base.metadata.create_all(bind=engine)
    print("✅ Done.")
