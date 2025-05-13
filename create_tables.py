from db import engine, Base
from models import User

# This will create all tables from Base metadata — including "users"
Base.metadata.create_all(bind=engine)
print("✅ Tables created successfully.")
