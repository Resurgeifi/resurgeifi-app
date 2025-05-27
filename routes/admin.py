from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import SessionLocal, User, CircleMessage, JournalEntry
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from functools import wraps
from models import login_required


admin_bp = Blueprint("admin", __name__)

# ✅ Admin access check
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(id=session.get("user_id")).first()
            if not user or not getattr(user, "is_admin", False):
                flash("Admin access required.")
                return redirect(url_for("menu"))
        finally:
            db.close()
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        active_today = db.query(User).filter(User.last_login >= start_of_day).count()
        recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()
        recent_circle = db.query(CircleMessage).order_by(CircleMessage.timestamp.desc()).limit(10).all()
        recent_journals = db.query(JournalEntry).order_by(JournalEntry.timestamp.desc()).limit(10).all()

        return render_template("admin_dashboard.html", 
            stats={
                "total_users": total_users,
                "active_today": active_today,
                "recent_users": recent_users
            },
            logs={
                "circle_messages": recent_circle,
                "journal_entries": recent_journals
            }
        )
    except SQLAlchemyError:
        db.rollback()
        flash("Error loading dashboard.")
        return redirect(url_for("menu"))
    finally:
        db.close()

# routes/admin.py

@admin_bp.route('/admin/grant_points', methods=["POST"])
@login_required
@admin_required
def grant_points():
    db = SessionLocal()
    try:
        raw_tag = request.form.get('resurgitag', '').strip()
        resurgitag = raw_tag.lstrip('@')
        raw_points = request.form.get('points', '').strip()

        try:
            points = int(raw_points)
        except ValueError:
            flash("⚠️ Invalid number of points.", "error")
            return redirect(url_for('admin.dashboard'))

        user = db.query(User).filter(User.resurgitag.ilike(f"@{resurgitag}")).first()

        if not user:
            flash(f"⚠️ User '@{resurgitag}' not found.", "error")
            return redirect(url_for('admin.dashboard'))

        user.points = (user.points or 0) + points
        db.commit()

        flash(f"✅ Gave {points} points to {user.resurgitag}!", "success")
        return redirect(url_for('admin.dashboard'))

    except Exception as e:
        db.rollback()
        flash("🔥 Failed to grant points. Error logged.", "error")
        print("Grant Points Error:", e)
        return redirect(url_for('admin.dashboard'))
    finally:
        db.close()

@admin_bp.route("/admin/delete_ghosts", methods=["POST"])
@admin_required
def delete_ghosts():
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        ghosts = db.query(User).filter(
            ((User.email == None) | (User.email == "")),
            (User.resurgitag == None),
            (User.journal_count == 0),
            (User.circle_message_count == 0),
            (User.created_at != None),
            (User.created_at < cutoff)
        ).all()

        count = len(ghosts)
        for ghost in ghosts:
            db.delete(ghost)

        db.commit()
        flash(f"🕊️ {count} ghost user(s) released into the mist.")
        return redirect(url_for("admin.admin_dashboard"))
    finally:
        db.close()

@admin_bp.route("/admin/grant_admin", methods=["POST"])
@admin_required
def grant_admin():
    db = SessionLocal()
    try:
        tag = request.form.get("resurgitag", "").strip().lstrip("@")
        full_tag = f"@{tag}"
        user = db.query(User).filter(User.resurgitag.ilike(full_tag)).first()

        if user:
            user.is_admin = True
            db.commit()
            flash(f"👑 {user.resurgitag} is now an admin.")
        else:
            flash("⚠️ User not found.")
        
        return redirect(url_for("admin.admin_dashboard"))
    finally:
        db.close()
