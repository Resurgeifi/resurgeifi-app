from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from flask_mail import Message
from werkzeug.utils import secure_filename
import os
from db import SessionLocal

feedback_bp = Blueprint("feedback", __name__)
UPLOAD_FOLDER = "/tmp"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@feedback_bp.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        message = request.form.get("message")
        file = request.files.get("screenshot")
        user = session.get("nickname", f"User ID {session.get('user_id', 'Unknown')}")

        file_path = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

        email_body = f"Feedback from {user}:\n\n{message}\n\nAttachment: {'Yes' if file_path else 'No'}"

        email = Message(
            subject=f"📝 Feedback from {user}",
            recipients=[os.getenv("MAIL_FEEDBACK_RECIPIENT")],
            body=email_body
        )

        if file_path:
            with open(file_path, "rb") as f:
                email.attach(filename, file.content_type, f.read())

        from main import mail  # pulled from global app
        mail.send(email)

        flash("Thanks for your feedback!")
        return redirect(url_for("feedback.feedback"))

    return render_template("feedback.html")
