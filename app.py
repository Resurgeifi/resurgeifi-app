import os
from flask import Flask, render_template
from flask_mail import Mail
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv

from models import db

# Blueprints
from routes.admin import admin_bp
from routes.circle import circle_bp
from routes.journal import journal_bp
from routes.profile import profile_bp
from routes.settings import settings_bp
from routes.hero import hero_bp
from routes.villain import villain_bp
from routes.feedback import feedback_bp
from routes.onboarding import onboarding_bp
from routes.quest import quest_bp
from routes.misc import misc_bp

# ✅ Load environment variables
load_dotenv()

# ✅ Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "resurgifi-dev-key")

# ✅ Core Configs
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT"))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS") == "True"
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")

# ✅ Init extensions
db.init_app(app)
mail = Mail(app)
migrate = Migrate(app, db)
CORS(app, supports_credentials=True)

# ✅ Register Blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(circle_bp)
app.register_blueprint(journal_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(hero_bp)
app.register_blueprint(villain_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(quest_bp)
app.register_blueprint(misc_bp)

# ✅ Root route renders landing.html
@app.route('/')
def landing():
    return render_template("landing.html")

# ✅ Optional alias (if needed)
@app.route('/landing')
def landing_alias():
    return render_template("landing.html")

