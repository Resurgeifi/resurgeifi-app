# utils/user_utils.py

from database import SessionLocal
from models import UserBlock

def is_blocked(sender_id, recipient_id):
    """
    Check if the recipient has blocked the sender.
    Returns True if blocked, else False.
    """
    db = SessionLocal()
    try:
        return db.query(UserBlock).filter_by(
            blocker_id=recipient_id,
            blocked_id=sender_id
        ).first() is not None
    finally:
        db.close()
