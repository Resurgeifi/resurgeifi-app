import random
from datetime import datetime
from collections import Counter
from db import SessionLocal
from models import User, JournalEntry, QueryHistory
from prompts import HERO_PROMPTS, VILLAIN_PROMPTS
from flask import session

HERO_NAMES = ["Grace", "Cognita", "Velessa", "Lucentis", "Sir Renity"]

def call_openai(user_input, hero_name="Cognita", context=None):
    from openai import OpenAI
    import os

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    tag = hero_name.strip().lower()
    is_villain = tag in VILLAIN_PROMPTS

    thread = context.get("thread", []) if isinstance(context, dict) else context if isinstance(context, list) else []
    formatted_thread = context.get("formatted_thread", "") if isinstance(context, dict) else ""
    emotional_profile = context.get("emotional_profile", "") if isinstance(context, dict) else ""
    nickname = context.get("nickname", "Friend") if isinstance(context, dict) else "Friend"

    if not thread:
        thread = [{"speaker": "User", "text": user_input}]

    system_message = build_prompt(
    hero=tag,
    user_input=user_input,
    context={
        "thread": thread,
        "formatted_thread": formatted_thread,
        "emotional_profile": emotional_profile,
        "nickname": nickname,
        "user_id": session.get("user_id")  # ✅ Add this line
    }
)


    messages = [{"role": "system", "content": system_message}]
    for entry in thread[-6:]:
        if "speaker" in entry and entry["speaker"].lower() == "user":
            messages.append({"role": "user", "content": entry["text"]})
        elif "speaker" in entry:
            messages.append({"role": "assistant", "content": entry["text"]})
        else:
            for speaker, msg in entry.items():
                role = "user" if speaker.lower() == "you" else "assistant"
                messages.append({"role": role, "content": msg})

    print("\n--- 📡 OpenAI CALL DEBUG ---")
    print(f"🧠 Hero Tag: {tag}")
    print(f"🗣️ User Input: {user_input}")
    print("🧵 Messages:", messages[-3:])
    print("--- END DEBUG ---\n")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.85,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"🔥 OpenAI Error for {tag}: {e}")
        return "Something went wrong. Try again in a moment."


def pull_recent_journal_summary(user_id):
    db = SessionLocal()
    summary_entry = (
        db.query(JournalEntry)
        .filter_by(user_id=user_id)
        .order_by(JournalEntry.created_at.desc())
        .first()
    )
    db.close()
    return summary_entry.content.strip() if summary_entry else None


def detect_crisis_tone(thread):
    crisis_keywords = [
        "don’t want to live", "give up", "relapse", "hopeless", "done",
        "overdose", "die", "can't do this", "not worth it"
    ]
    user_messages = [msg["text"].lower() for msg in thread[-4:] if msg["speaker"] == "User"]
    return any(any(kw in msg for msg in user_messages) for kw in crisis_keywords)


def detect_relapse_fantasy(thread):
    relapse_phrases = [
        "i miss drinking", "i need a drink", "just one", "cold beer",
        "high again", "i want to use", "what my life is missing",
        "i'm done being sober", "tired of being sober", "need to escape"
    ]
    user_messages = [msg["text"].lower() for msg in thread[-3:] if msg["speaker"] == "User"]
    return any(any(p in msg for msg in user_messages) for p in relapse_phrases)


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


def detect_repetitive_phrases(thread):
    words = ["sock", "laundry", "fold", "cold beer", "pill", "monster", "ghost", "fog", "reset"]
    all_text = " ".join(msg["text"].lower() for msg in thread[-6:])
    return {w: all_text.count(w) for w in words if all_text.count(w) > 1}


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


def build_context(user_id=None, session_data=None, journal_data=None, onboarding=None):
    db = SessionLocal()
    user = db.query(User).filter_by(id=user_id).first() if user_id else None

    from models import QueryHistory, UserBio
    history = []
    if user_id:
        thread = (
            db.query(QueryHistory)
            .filter_by(user_id=user_id)
            .order_by(QueryHistory.timestamp.desc())
            .limit(50)
            .all()
        )
        history = list(reversed(thread))

    full_thread = []
    for entry in history:
        timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M")
        full_thread.append({"speaker": "User", "text": entry.question.strip(), "time": timestamp})
        full_thread.append({"speaker": entry.agent_name or "Resurgifi", "text": entry.response.strip(), "time": timestamp})

    formatted_thread = ""
    for msg in full_thread:
        formatted_thread += f"{msg['speaker']} ({msg['time']}): \"{msg['text']}\"\n"

    quest_data = session.pop("from_quest", None)
    quest_reflection = quest_data.get("reflection") if quest_data else None
    if quest_reflection:
        formatted_thread = f'Grace: "The user has just completed a quest. They wrote: \'{quest_reflection}\'"\n\n' + formatted_thread

    # 🧠 Pull nickname & bio
    nickname = user.nickname if user and user.nickname else "Friend"
    bio_text = None
    if user:
        bio = db.query(UserBio).filter_by(user_id=user.id).first()
        bio_text = bio.bio_text if bio else None

    # ⛑️ Fallback if no bio
    if not bio_text and user:
        reason = user.theme_choice or "an unknown reason"
        coping = user.default_coping or "an unspecified coping style"
        traits = ", ".join(user.hero_traits or []) if user.hero_traits else "unknown trust preferences"
        bio_text = f"""
The user’s emotional profile includes:

- They came to us due to: {reason}.
- When overwhelmed, they typically: {coping}.
- In someone they trust, they look for: {traits}.
""".strip()

    # 📖 If no chat thread, fall back to journal
    if not formatted_thread.strip() and user:
        journal_summary = pull_recent_journal_summary(user.id)
        if journal_summary:
            formatted_thread = f'{nickname}: "{journal_summary}"\n'

    db.close()

    emotional_profile = f"""
{bio_text}

Let this shape your tone. Do not reference this directly.
""".strip()

    return {
        "formatted_thread": formatted_thread.strip(),
        "emotional_profile": emotional_profile,
        "nickname": nickname,
        "thread": full_thread
    }

def get_prompt(hero_name, style="default"):
    name = hero_name.lower().strip()
    hero_prompt = HERO_PROMPTS.get(name, {})

    if isinstance(hero_prompt, dict):
        return hero_prompt.get(style) or hero_prompt.get("default")
    elif isinstance(hero_prompt, str):
        return hero_prompt
    else:
        return VILLAIN_PROMPTS.get(name) or f"You are {hero_name}, a mysterious figure in the user's recovery world."


def normalize_thread(thread):
    normalized = []
    for item in thread:
        if isinstance(item, dict):
            if "speaker" in item and "text" in item:
                normalized.append(item)
            else:
                for speaker, text in item.items():
                    normalized.append({
                        "speaker": "User" if speaker.strip().lower() == "you" else speaker.capitalize(),
                        "text": text.strip()
                    })
    return normalized


def build_prompt(hero, user_input, context):
    from models import User, UserBio, JournalEntry
    from sqlalchemy.orm import scoped_session
    from db import SessionLocal

    db = SessionLocal()
    user_bio_text = ""
    tone_summary = ""
    journal_snippets = []
    nickname = context.get("nickname", "Friend")
    formatted_thread = context.get("formatted_thread", "")

    try:
        user_id = context.get("user_id")
        if user_id:
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                nickname = user.nickname or nickname
                # Get bio
                bio = db.query(UserBio).filter_by(user_id=user.id).first()
                if bio:
                    user_bio_text = bio.bio_text
                # Get tone summary (if we ever want to expand)
                tone_summary = user.tone_summary or ""
                # Get last 2-3 journal entries
                journals = db.query(JournalEntry).filter_by(user_id=user.id).order_by(JournalEntry.timestamp.desc()).limit(3).all()
                journal_snippets = [j.entry_text[:300] for j in journals if j.entry_text]
    except Exception as e:
        print("🔥 build_prompt DB error:", str(e))
    finally:
        db.close()

    # Build prompt
    base_prompt = f"""
You are {hero.capitalize()}, a Resurgifi guide helping someone in emotional recovery.
This is their nickname: {nickname}.

Backstory: {user_bio_text}

Tone Summary: {tone_summary}

Recent Journal Reflections:
- {chr(10).join(journal_snippets)}

Conversation so far:
{formatted_thread}

Respond with empathy, clarity, and purpose.
Always speak as yourself. Do not summarize — respond like you're sitting beside them.
"""

    return base_prompt.strip()









