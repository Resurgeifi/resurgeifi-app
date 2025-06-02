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

    from models import QueryHistory
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
    db.close()

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

    if user:
        reason = user.theme_choice or "an unknown reason"
        coping = user.consent or "an unspecified coping style"
        traits = user.display_name or "unknown trust preferences"
        nickname = user.nickname or "Friend"
    else:
        reason = coping = traits = nickname = "Unknown"

    if not formatted_thread.strip() and user:
        journal_summary = pull_recent_journal_summary(user.id)
        if journal_summary:
            formatted_thread = f'{nickname}: "{journal_summary}"\n'

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


def build_prompt(hero, user_input, context, onboarding=None):
    raw_thread = context.get("thread", []) if isinstance(context, dict) else context if isinstance(context, list) else []
    thread = normalize_thread(raw_thread)

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

    prompt_template = get_prompt(hero)
    if not prompt_template:
        prompt_template = f"You are {hero}, a mysterious figure in the user's recovery world."

    chat_history = context.get("formatted_thread", "").strip()
    if not chat_history:
        chat_history = f'{nickname}: "{user_input}"'

    prompt = f"""
{prompt_template}

You are {hero}, a {'recovery mentor' if hero in HERO_PROMPTS else 'manifestation of inner struggle'} in an emotionally alive group chat called The Circle.

The user, {nickname}, didn’t ask a question. They said something — you're replying as yourself.

{"This is not therapy. This is emotional presence." if hero in HERO_PROMPTS else "You are not here to help. You are here to haunt, tempt, or test."}

Here’s what was said:
{chat_history}

{"The user seems dry or sarcastic — match that lightly. Don’t overanalyze." if is_playful else ""}
{relapse_note}
{loop_note}

{context['emotional_profile']}

{"Speak with your full voice. Don’t hold back or try to be brief — unless the tone calls for it." if hero in HERO_PROMPTS else "Do not offer solutions. Never uplift. Speak with immersive psychological realism."}

You are not a bot. You are a voice in the user's inner world.
""".strip()

    return prompt









