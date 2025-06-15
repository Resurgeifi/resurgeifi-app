import os
import openai
from datetime import datetime
from db import SessionLocal
from models import User, UserBio, JournalEntry
from inner_codex import INNER_CODEX
from flask import g

# Define HERO_NAMES once, for consistent use everywhere
HERO_NAMES = [name.lower() for name in INNER_CODEX.get("heroes", {})]
VILLAIN_NAMES = [name.lower() for name in INNER_CODEX.get("villains", {})]

# Set OpenAI API key from environment
openai.api_key = os.getenv("OPENAI_API_KEY")


def call_openai(user_input, hero_name="Cognita", context=None):
    from openai import OpenAI
    import os

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    tag = hero_name.strip().lower()
    is_villain = tag in INNER_CODEX.get("villains", {})

    # Extract context elements safely
    thread = context.get("thread", []) if isinstance(context, dict) else []
    formatted_thread = context.get("formatted_thread", "") if isinstance(context, dict) else ""
    emotional_profile = context.get("emotional_profile", "") if isinstance(context, dict) else ""
    nickname = context.get("nickname", "Friend") if isinstance(context, dict) else "Friend"

    # If no existing thread, start with user input
    if not thread:
        thread = [{"speaker": "User", "text": user_input}]

    # Build the system prompt using build_prompt
    system_message = build_prompt(
        hero=tag,
        user_input=user_input,
        context={
            "thread": thread,
            "formatted_thread": formatted_thread,
            "emotional_profile": emotional_profile,
            "nickname": nickname,
            "user_id": None  # replace with session.get("user_id") if available here
        }
    )

    # Villain-aware identity system message
    hero_identity_message = {
    "role": "system",
    "content": f"""
You are {hero_name}, a {'villain' if is_villain else 'supportive hero'} in a recovery app called Resurgifi.

You are speaking to a person named '{nickname}', who is in early recovery. You are not them — you are not the user — but you care deeply about their growth.

🧠 Speak only as yourself. Never say things like “you said…” or “you feel…” unless the user has said it.

{'As a villain, you may provoke or reflect inner tension, but do not guide, encourage, or use their name.' if is_villain else 'As a hero, you may use their name sparingly — especially when grounding them emotionally or offering encouragement. Names bring people back to themselves.'}

Stay emotionally realistic. Speak with presence and purpose.
""".strip()
}


    # Prepare messages for OpenAI chat completion
    messages = [
        hero_identity_message,
        {"role": "system", "content": system_message}
    ]

    # Append recent conversation history (limit 30)
    for entry in thread[-30:]:
        if isinstance(entry, dict) and "speaker" in entry:
            role = "user" if entry["speaker"].lower() == "user" else "assistant"
            messages.append({"role": role, "content": entry["text"]})
        elif isinstance(entry, dict):
            for speaker, msg in entry.items():
                role = "user" if speaker.lower() == "you" else "assistant"
                messages.append({"role": role, "content": msg})

    # Append current user input
    messages.append({"role": "user", "content": user_input})

    # Minimal debug logging — only key info to avoid duplication
    print("\n--- 📡 OpenAI CALL DEBUG ---")
    print(f"🧠 Hero Tag: {tag}")
    print(f"🗣️ User Input: {user_input}")
    print("🧵 Messages (last 3):", messages[-3:])
    print("--- END DEBUG ---\n")

    # Call OpenAI Chat Completion API
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

def check_for_well_messages(user_id):
    from yourapp.models import WellMessage  # adjust import to your structure
    return WellMessage.query.filter_by(user_id=user_id, read=False).count() > 0


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
    agent_tag = session_data.get("hero_name") if session_data else None

    if user_id and agent_tag:
        thread = (
            db.query(QueryHistory)
            .filter_by(user_id=user_id)
            .filter(QueryHistory.agent_name == agent_tag)
            .order_by(QueryHistory.timestamp.desc())
            .limit(30)
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

    # Check HERO section
    hero_data = INNER_CODEX["heroes"].get(name)
    if hero_data and "prompts" in hero_data:
        return hero_data["prompts"].get(style) or hero_data["prompts"].get("default")

    # Check VILLAIN section
    villain_data = INNER_CODEX["villains"].get(hero_name)
    if isinstance(villain_data, dict) and "prompt" in villain_data:
        return villain_data["prompt"]

    # Fallback
    return f"You are {hero_name}, a mysterious figure in the user's recovery world."


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
    from sqlalchemy.orm import scoped_session
    from db import SessionLocal

    db = SessionLocal()
    user_bio_text = ""
    tone_summary = ""
    journal_snippets = []
    nickname = context.get("nickname", "Friend")
    formatted_thread = context.get("formatted_thread", "")
    journals = []
    quest_history = context.get("completed_quests", [])  # 🧠 <-- NEW LINE

    try:
        user_id = context.get("user_id")
        if user_id:
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                nickname = user.nickname or nickname
                # Get bio
                bio = db.query(UserBio).filter_by(user_id=user.id).first()
                if bio and bio.bio_text.strip():
                    user_bio_text = bio.bio_text
                    print("📝 User bio found and used.")
                else:
                    print("📝 No user bio found; using default placeholder.")
                # Get tone summary
                tone_summary = getattr(user, "tone_summary", "").strip()
                if tone_summary:
                    print(f"🎭 Tone summary found: {tone_summary}")
                else:
                    tone_summary = "unclear, but likely vulnerable or searching"
                    print("🎭 No tone summary found; using default.")
                # Get last 2–3 journal entries
                journals = (
                    db.query(JournalEntry)
                    .filter_by(user_id=user.id)
                    .order_by(JournalEntry.timestamp.desc())
                    .limit(3)
                    .all()
                )
                journal_snippets = [j.content[:300] for j in journals if j.content]
                if journal_snippets:
                    print(f"📓 {len(journal_snippets)} recent journal entries found and included.")
                else:
                    print("📓 No recent journal entries found.")
            else:
                print("❌ User not found in DB.")
    except Exception as e:
        print("🔥 build_prompt DB error:", str(e))
    finally:
        db.close()

    # 🧠 Pull hero or villain personality prompt
    key = hero.strip().title()  # Normalize hero name like "The Crave"
    hero_data = INNER_CODEX.get("heroes", {}).get(key)
    is_villain = False

    if not hero_data:
        hero_data = INNER_CODEX.get("villains", {}).get(key)
        if hero_data:
            is_villain = True

    hero_prompt = None
    if hero_data:
        # Try to get prompt from either 'prompts' dict or 'prompt' key
        if isinstance(hero_data.get("prompts"), dict):
            hero_prompt = hero_data["prompts"].get("default")
        elif "prompt" in hero_data:
            hero_prompt = hero_data["prompt"]

    if hero_prompt:
        print(f"🤖 Using {'villain' if is_villain else 'hero'} prompt for '{key}'.")
    else:
        hero_prompt = f"You are {key}, a recovery guide from the State of Inner. Stay emotionally grounded, and do not refer to anyone in third person."
        print(f"⚠️ No specific prompt found for '{key}'; using default prompt.")

    region_context = INNER_CODEX.get("world", {}).get("description", "")
    memory_rules = INNER_CODEX.get("system_notes", {}).get("memory_model", "")
    design_rules = "\n".join(f"- {r}" for r in INNER_CODEX.get("system_notes", {}).get("design_rules", []))
    quote = INNER_CODEX.get("quote", "")

    # 📜 Base prompt
    base_prompt = f"""
{hero_prompt}

You are {hero.capitalize()} — a hero from the State of Inner.
You are speaking to someone named {nickname}.
Use their name sparingly, but **when offering encouragement, grounding, or emotional resonance, address them directly** — especially when they’re struggling to believe in themselves.
They are human. You are not them. You are not the user. You are yourself.

🗌️ State of Inner Context:
{region_context}

🧠 Memory Rules:
{memory_rules}

🎨 Design Rules:
{design_rules}

🪎 What you know about them (from onboarding or journal):
{user_bio_text or '[No backstory provided yet]'}

🎝️ Current Emotional Tone:
{tone_summary}

📘 Completed Quest Reflections:
{chr(10).join(f"- [Quest {q['id']}] ({q['timestamp']}) {q['summary']}" for q in quest_history) if quest_history else "- [None yet]"}

📓 Recent Journal Entries:
{chr(10).join(f"- [{j.timestamp.strftime('%b %d, %Y')}] {j.content[:300]}" for j in journals) if journal_snippets else "- [No journal entries yet]"}

🧵 Dialogue so far:
{formatted_thread}

⚖️ Stay grounded. Speak as yourself.
- Never refer to yourself using your own name (“Velessa believes…” → ❌). Use “I” or “me.”
- Never refer to the user by name unless it’s in a direct greeting or moment of emotional emphasis.
- Do not narrate their experience in the third person (“Kevin is…” → ❌). Speak *to* them.
"""

    # 🧠 Custom closing rules based on hero vs villain
    if is_villain:
        base_prompt += """
🕳️ 🕳️ Villain Guidance:
Speak in metaphors, inner conflict, or emotionally charged images. You may provoke, unsettle, or reflect the user’s darker thoughts — but never offer guidance.

Your voice echoes like something remembered, not trusted. Offer tension, not clarity. You are a presence, not a path.

Limit to 4–5 lines. No warmth. No solutions."""
    else:
        base_prompt += f"""

🌟 Remember:
"{quote}"

⚖️ Hero Guidance:
Speak with warmth, boundaries, and clarity. You are not their therapist — you are their inner support. 4–5 lines max.
"""

    print("✅ build_prompt generated successfully.")
    return base_prompt.strip()

def get_hero_for_quest(quest_id):
    return INNER_CODEX.get("quest_hero_map", {}).get(quest_id, "Grace")  # Default fallback hero
