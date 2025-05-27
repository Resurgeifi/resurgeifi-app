from flask import Blueprint, render_template, abort
from models import HeroProfile

hero_bp = Blueprint("hero", __name__)

@hero_bp.route('/hero/<resurgitag>')
def hero_profile(resurgitag):
    resurgitag_clean = resurgitag.lower().strip('@')
    hero = HeroProfile.query.filter_by(resurgitag=resurgitag_clean, type='hero').first()
    if not hero:
        return abort(404)

    if not hero.image_path:
        hero.image_path = f"/static/images/heroes/{resurgitag_clean}/{resurgitag_clean}_profile.png"

    hero_links = {
        'lucentis': ['grace2', 'velessa'],
        'grace2': ['lucentis', 'sirrenity'],
        'velessa': ['grace2', 'cognita'],
        'sirrenity': ['cognita', 'lucentis'],
        'cognita': ['sirrenity', 'velessa']
    }
    linked_allies = hero_links.get(resurgitag_clean, [])

    return render_template(
        'hero_profile.html',
        hero=hero,
        allies=linked_allies
    )
