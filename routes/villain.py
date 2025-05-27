from flask import Blueprint, render_template, abort
from models import SessionLocal, VillainProfile

villain_bp = Blueprint("villain", __name__)

@villain_bp.route('/villain/<resurgitag>')
def villain_profile(resurgitag):
    db = SessionLocal()
    try:
        clean_tag = resurgitag.lower().strip('@')
        villain = db.query(VillainProfile).filter_by(resurgitag=clean_tag).first()

        if not villain:
            return abort(404)

        villain_links = {
            'thecrave': ['highnesshollow', 'wardenfall'],
            'highnesshollow': ['thecrave', 'theundermind'],
            'wardenfall': ['theundermind', 'charnobyl'],
            'theundermind': ['highnesshollow', 'themurk'],
            'charnobyl': ['wardenfall', 'anxia'],
            'anxia': ['charnobyl', 'littlelack'],
            'littlelack': ['anxia', 'theexs'],
            'theexs': ['littlelack', 'captainfine'],
            'captainfine': ['theexs', 'themurk'],
            'themurk': ['theundermind', 'anxia']
        }
        linked_villains = villain_links.get(clean_tag, [])

        return render_template(
            'villain_profile.html',
            villain=villain,
            linked_villains=linked_villains
        )
    finally:
        db.close()
