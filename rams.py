import random
from datetime import datetime
from collections import Counter
from db import SessionLocal
from models import User, JournalEntry, QueryHistory
from prompts import HERO_PROMPTS  # ✅ imported directly

# ✅ Hero pool
HERO_NAMES = ["Grace", "Cognita", "Velessa", "Lucentis", "Sir Renity"]

# 🧠 Optional future journal integration
def pull_recent_journal_summary(user_id):
    return None

# 🚨 Detect active crisis tone
def detect_crisis_tone(thread):
    crisis_keywords = [
        "don’t want to live", "give up", "relapse", "hopeless", "done",
        "overdose", "die", "can't do this", "not worth it"
    ]
    user_messages = [msg["text"].lower() for msg in thread[-4:] if msg["speaker"] == "User"]
    return any(any(kw in msg for kw in crisis_keywords) for msg in user_messages)

# 🍺 Detect romanticizing relapse
def detect_relapse_fantasy(thread):
    relapse_phrases = [
        "i miss drinking", "i need a drink", "just one", "cold beer",
        "high again", "i want to use", "what my life is missing",
        "i'm done being sober", "tired of being sober", "need to escape"
    ]
    user_messages = [msg["text"].lower() for msg in thread[-3:] if msg["speaker"] == "User"]
    return any(any(p in msg for p in relapse_phrases) for msg in user_messages)

# 😒 Dry or deflective tone
def detect_playful_or_dry(thread):
    if not thread:
        return False
    last_user = next((msg for msg in reversed(thread) if msg["speaker"] == "User"), None)
    if not last_user:
        return False
    text = last_user["text"].lower().strip()
    dry_triggers = [
        "i need to shave", "lol", "whatever", "who knows", "i guess", "meh", "k",
        "sure", "haha", "just kidding", "lmao", "what’s for dinner", "ugh"
    ]
    return len(text) <= 12 or any(trigger in text for trigger in dry_triggers)

# 🔁 Metaphor loops
def detect_repetitive_phrases(thread):
    words = ["sock", "laundry", "fold", "cold beer", "pill", "monster", "ghost", "fog", "reset"]
    all_text = " ".join(msg["text"].lower() for msg in thread[-6:])
    return {w: all_text.count(w) for w in words if all_text.count(w) > 1}

# 🎯 Hero selector
def select_heroes(tone, thread):
    is_crisis = detect_crisis_tone(thread)
    is_relapse = detect_relapse_fantasy(thread)
    user_message = thread[-1]["text"] if thread else ""
    mentioned = [h for h in HERO_NAMES if h.lower() in user_message.lower()]
    safe_heroes = ["Grace", "Cognita", "Velessa"]
    base_pool = safe_heroes if is_relapse else HERO_NAMES

    if is_relapse:
        forced = [{"name": "Grace", "mode": "speak"}]
        available = [h for h in HERO_NAMES if h not in ["Lucentis", "Sir Renity", "Grace"]]
    else:
        forced = [{"name": h, "mode": "speak"} for h in mentioned if h in base_pool]
        available = [h for h in base_pool if h not in mentioned]

    max_heroes = 3 if is_crisis else random.choice([1, 2])
    selected = random.sample(available, k=max(0, max_heroes - len(forced)))
    normal = [{"name": h, "mode": "speak"} for h in selected]

    print(f"[RAMS] Tone: {tone} | Crisis: {is_crisis} | Relapse: {is_relapse} | Mentioned: {mentioned}")
    return forced + normal

# 🧠 Context + onboarding builder
def build_context(user_id=None, session_data=None, journal_data=None, onboarding=None):
    db = SessionLocal()
    user = db.query(User).filter_by(id=user_id).first() if user_id else None
    db.close()

    formatted_thread = ""
    if session_data and isinstance(session_data, list):
        for msg in session_data[-10:]:
            speaker = msg.get("speaker", "Unknown")
            text = msg.get("text", "").strip()
            if speaker and text:
                formatted_thread += f"{speaker}: \"{text}\"\n"
    else:
        formatted_thread = "The Circle has just begun. This may be the user’s first interaction.\n"

    if user:
        reason = user.theme_choice or "an unknown reason"
        coping = user.consent or "an unspecified coping style"
        traits = user.display_name or "unknown trust preferences"
        nickname = user.nickname or "Friend"
    else:
        reason = coping = traits = nickname = "Unknown"

    emotional_profile = f"""
The user’s emotional profile includes:

- They came to us due to: {reason}.
- When overwhelmed, they typically: {coping}.
- In someone they trust, they look for: {traits}.

Let this shape your tone. Do not reference this directly.
"""

    return {
        "formatted_thread": formatted_thread.strip(),
        "emotional_profile": emotional_profile.strip(),
        "nickname": nickname
    }

def build_prompt(hero, user_input, context, next_hero=None, previous_hero=None, onboarding=None):
    thread = context.get("thread", []) if isinstance(context, dict) else []
    is_playful = detect_playful_or_dry(thread)
    is_relapse = detect_relapse_fantasy(thread)
    repeated = detect_repetitive_phrases(thread)
    nickname = context.get("nickname", "Friend")

    loop_note = ""
    if repeated:
        looped = ", ".join(repeated.keys())
        loop_note = f"🧠 These metaphors have come up a lot: {looped}. Gently steer away without naming them."

    relapse_note = ""
    if is_relapse:
        relapse_note = """
⚠️ The user may be romanticizing relapse. Do not explore details. Stay with the emotional need. No shame.
"""

    prompt = f"""
{HERO_PROMPTS.get(hero, "")}

You are {hero}, a recovery mentor in an emotionally alive group chat called The Circle.

The user, {nickname}, didn’t ask a question. They said something — you're replying as yourself.

This is not therapy. This is emotional presence.

Here's what was said:
{context['formatted_thread']}

{"The user seems dry or sarcastic — match that lightly. Don't overanalyze." if is_playful else ""}
{relapse_note}
{loop_note}

{context['emotional_profile']}

Keep it short — 1–2 lines. Don’t try to be wise. Be real.

You are not a bot. You are a voice in the Circle.
""".strip()

    return prompt


