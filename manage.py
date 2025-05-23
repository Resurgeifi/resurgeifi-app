from flask.cli import FlaskGroup
from main import app
from models import db

cli = FlaskGroup(app)

if __name__ == "__main__":
    cli()

