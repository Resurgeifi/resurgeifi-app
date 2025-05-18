import random
from datetime import datetime
from collections import Counter
from db import SessionLocal
from models import User, JournalEntry, QueryHistory

# Global hero pool
HERO_NAMES = [
    "Grace", "Cognita", "Velessa", "Lucentis", "Sir Renity"
]

# Optional future integration
def pull_recent_journal_summary(user_id):
    # Placeholder for journal integration
    # Example: return last summary or tone keyword
    return None

# Detect crisis tone based on last few messages
def detect_crisis_tone(thread):
    crisis_keywords = [
        "don’t want to live", "give up", "relapse", "hopeless", "done",
        "overdose", "die", "can't do this", "not worth it"
    ]
    user_messages = [msg["text"].lower() for msg in thread[-4:] if msg["speaker"] == "User"]
    return any(any(kw in msg for kw in crisis_keywords) for msg in user_messages)

# Detect relapse-oriented language (fantasizing, not just use)
def detect_relapse_fantasy(thread):
    relapse_phrases = [
        "i miss drinking", "i need a drink", "just one", "cold beer",
        "high again", "i want to use", "what my life is missing",
        "i'm done being sober", "tired of being sober", "need to escape"
    ]
    user_messages = [msg["text"].lower() for msg in thread[-3:] if msg["speaker"] == "User"]
    return any(any(p in msg for p in relapse_phrases) for msg in user_messages)

# Detect tone: playful, dry, sarcastic, emotionally avoidant
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

# Detect metaphor loops (e.g. sock, laundry)
def detect_repetitive_phrases(thread):
    words_to_track = ["sock", "laundry", "fold", "cold beer", "pill", "monster", "ghost", "fog", "reset"]
    all_text = " ".join(msg["text"].lower() for msg in thread[-6:])
    counts = {word: all_text.count(word) for word in words_to_track if all_text.count(word) > 1}
    return counts  # returns { "sock": 3, "laundry": 2 }

# Hero selector based on tone and flags
def select_heroes(tone, thread):
    is_crisis = detect_crisis_tone(thread)
    is_relapse = detect_relapse_fantasy(thread)
    user_message = thread[-1]["text"] if thread else ""
    mentioned = [h for h in HERO_NAMES if h.lower() in user_message.lower()]
    safe_heroes = ["Grace", "Cognita", "Velessa"]
    base_pool = safe_heroes if is_relapse else HERO_NAMES

    # Summoned heroes go first
    forced = [{"name": h, "mode": "speak"} for h in mentioned if h in base_pool]
    available = [h for h in base_pool if h not in mentioned]

    max_heroes = 3 if is_crisis else random.choice([1, 2])
    selected = random.sample(available, k=max(0, max_heroes - len(forced)))
    normal = [{"name": h, "mode": "speak"} for h in selected]

    hero_plans = forced + normal
    print(f"[RAMS] Tone: {tone} | Crisis: {is_crisis} | Relapse: {is_relapse} | Mentioned: {mentioned}")
    return hero_plans

# Thread + onboarding formatter
def build_context(user_id=None, session_data=None, journal_data=None, onboarding=None):
    formatted_thread = ""
    if session_data and isinstance(session_data, list):
        for msg in session_data[-10:]:
            speaker = msg.get("speaker", "Unknown")
            text = msg.get("text", "").strip()
            if speaker and text:
                formatted_thread += f"{speaker}: \"{text}\"\n"
    else:
        formatted_thread = "The Circle has just begun. This may be the user’s first interaction.\n"

    if onboarding:
        reason = onboarding.get("emotional_reason", "an unknown reason")
        coping = onboarding.get("coping_style", "unspecified coping style")
        traits = onboarding.get("trusted_traits", [])
        trait_text = ", ".join(traits) if traits else "unknown trust preferences"

        emotional_profile = f"""
The user’s emotional profile includes:

- They came to us due to: {reason}.
- When overwhelmed, they typically: {coping}.
- In someone they trust, they look for: {trait_text}.

Let this shape your tone. Do not reference this directly.
"""
    else:
        emotional_profile = """
The user’s emotional profile is not fully known.
Speak gently, with emotional awareness, as if meeting someone for the first time.
"""

    return {
        "formatted_thread": formatted_thread.strip(),
        "emotional_profile": emotional_profile.strip()
    }

# Prompt builder for each hero
def build_prompt(hero, user_input, context, nickname="Friend", next_hero=None, previous_hero=None, onboarding=None):
    is_playful = detect_playful_or_dry(context)
    is_relapse = detect_relapse_fantasy(context)
    repeated_concepts = detect_repetitive_phrases(context)

    tone_modifiers = {
        "Grace": "You are warm, honest, and grounded. Never preach. You notice pain under jokes.",
        "Cognita": "You are clever and insightful. Logic + dry wit welcome, but stay connected.",
        "Velessa": "You speak slowly and simply. You gently notice emotional truth.",
        "Lucentis": "You are spiritual clarity grounded in human experience.",
        "Sir Renity": "You are blunt, real, and grounded. You don’t sugarcoat, but you're loyal."
    }

    loop_note = ""
    if repeated_concepts:
        looped = ", ".join(repeated_concepts.keys())
        loop_note = f"🧠 The following metaphors or phrases have been repeated too much: {looped}. Gently steer away from them without calling attention directly."

    relapse_note = ""
    if is_relapse:
        relapse_note = """
⚠️ The user may be romanticizing relapse (e.g., imagining using). Do not validate or explore that.  
Instead, speak to the emotional need underneath: freedom, release, escape, connection.  
Be honest. Stay with them. Do not shame. Do not suggest alternatives unless they ask.
"""

    prompt = f"""
You are {hero}, a recovery mentor in an emotionally alive group chat called The Circle.

The user, {nickname}, didn’t ask a question. They said something — you're replying as yourself.

This is not a chatbot thread. This is not therapy. This is emotional presence in a group.

Here’s what’s been said:
{context}

{tone_modifiers.get(hero, "")}

{"The user seems dry or sarcastic — match that lightly. Don't overanalyze." if is_playful else ""}
{relapse_note}
{loop_note}

Keep your message short — one or two sentences. A single line is okay. Don’t try to be wise. Be real.

You are not a bot. You are a voice in the Circle.
""".strip()

    return prompt

