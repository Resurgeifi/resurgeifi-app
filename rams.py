import os
from datetime import datetime
import traceback
from flask import session, g  # type: ignore

from openai import OpenAI
from db import SessionLocal
from models import User, UserBio, JournalEntry, QueryHistory
from inner_codex import INNER_CODEX

# Define HERO_NAMES and VILLAIN_NAMES once
HERO_NAMES = [name.lower() for name in INNER_CODEX.get("heroes", {})]
VILLAIN_NAMES = [name.lower() for name in INNER_CODEX.get("villains", {})]

# Instantiate OpenAI client (new v4 API style)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def call_openai(user_input, hero_name="Cognita", context=None):
    print(f"\n[🧠 call_openai] 🔹 Hero: {hero_name} | 🔹 Input: {user_input}")

    try:
        context = build_context(user_id=session.get("user_id"), session_data=session)

        # 🧵 Fallback: if thread is missing, rebuild from QueryHistory
        thread = context.get("thread", [])
        if not thread:
            print("[🔁 Thread empty — rebuilding from QueryHistory]")
            db = SessionLocal()
            user_id = session.get("user_id")
            history = (
                db.query(QueryHistory)
                .filter_by(user_id=user_id)
                .filter(QueryHistory.agent_name == hero_name)
                .order_by(QueryHistory.timestamp.desc())
                .limit(10)
                .all()
            )
            db.close()

            # ✅ Deduplication logic added here
            thread = []
            seen = set()
            for entry in reversed(history):
                q = entry.question.strip() if entry.question else None
                r = entry.response.strip() if entry.response else None
                if q and q not in seen:
                    thread.append({"role": "user", "content": q})
                    seen.add(q)
                if r and r not in seen:
                    thread.append({"role": "assistant", "content": r})
                    seen.add(r)

        print(f"[🧵 Thread Length]: {len(thread)}")
        for i, entry in enumerate(thread[-3:], 1):
            print(f"[🧵 Thread-{i}]: {entry}")

        # 🧠 Debug bio / emotional profile
        print(f"\n[🧠 Nickname]: {context.get('nickname')}")
        print(f"[🧾 Journal Summary]: {context.get('tone_summary')}")
        print(f"[📜 Emotional Profile]:\n{context.get('emotional_profile')}\n")
        print(f"[📜 Formatted Thread]:\n{context.get('formatted_thread')}\n")

        # 🧱 Build final system prompt
        system_prompt = build_prompt(hero=hero_name.lower(), user_input=user_input, context=context)
        print(f"[🧱 FINAL SYSTEM PROMPT]:\n{system_prompt}\n")

        # 🔄 Convert thread into OpenAI-compatible message list
        formatted_messages = [{"role": "system", "content": system_prompt}]
        for msg in thread:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted_messages.append({
                "role": role,
                "content": content
            })
        formatted_messages.append({"role": "user", "content": user_input})

        # 🔮 Make OpenAI API call with thread memory
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=formatted_messages,
            temperature=0.8
        )

        message = response.choices[0].message.content.strip()
        print(f"[✅ OpenAI Response]:\n{message}\n")

        # 💾 Save to QueryHistory
        try:
            user_id = session.get("user_id")
            new_entry = QueryHistory(
                user_id=user_id,
                agent_name=hero_name,
                question=user_input,
                response=message,
                timestamp=datetime.utcnow()
            )
            db = SessionLocal()
            db.add(new_entry)
            db.commit()
            db.close()
            print("[💾 QueryHistory]: Saved user message + hero response.")
        except Exception as log_error:
            print(f"[⚠️ ERROR saving to QueryHistory]: {log_error}")

        return message

    except Exception as e:
        print(f"[❌ ERROR in call_openai]: {e}")
        traceback.print_exc()
        return "Error: Could not reach your guide. Try again in a moment."

def pull_recent_journal_summary(user_id):
    db = SessionLocal()
    try:
        summary_entry = (
            db.query(JournalEntry)
            .filter_by(user_id=user_id)
            .order_by(JournalEntry.timestamp.desc())  # ✅ FIXED HERE
            .first()
        )
        return summary_entry.content.strip() if summary_entry else None
    except Exception as e:
        print(f"[🧨 pull_recent_journal_summary ERROR]: {e}")
        return None
    finally:
        db.close()

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
    history = []
    agent_tag = session_data.get("hero_name") if session_data else None

    # 🧵 Pull query history
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

    # 🧱 Build both a thread list and a formatted version (for debugging or prompt flavoring)
    openai_thread = []
    formatted_thread = ""
    for entry in history:
        if entry.question:
            openai_thread.append({"role": "user", "content": entry.question.strip()})
            formatted_thread += f'User: "{entry.question.strip()}"\n'
        if entry.response:
            openai_thread.append({"role": "assistant", "content": entry.response.strip()})
            formatted_thread += f'{entry.agent_name or "Resurgifi"}: "{entry.response.strip()}"\n'

    # 🧭 Inject quest reflection if present
    quest_data = session.pop("from_quest", None)
    quest_reflection = quest_data.get("reflection") if quest_data else None
    if quest_reflection:
        openai_thread.insert(0, {
            "role": "system",
            "content": f"The user has completed a quest reflection: '{quest_reflection}'"
        })
        formatted_thread = f'Grace: "The user just completed a quest reflection: \'{quest_reflection}\'"\n\n' + formatted_thread

    # 🧠 Bio + nickname fallback
    nickname = user.nickname or "Friend"
    bio_text = None
    journal_summary = None

    if user:
        bio_obj = db.query(UserBio).filter_by(user_id=user.id).first()
        bio_text = bio_obj.bio_text if bio_obj else None

        if not bio_text:
            reason = user.theme_choice or "an unknown reason"
            coping = user.default_coping or "an unspecified coping style"
            traits = ", ".join(user.hero_traits) if user.hero_traits and isinstance(user.hero_traits, list) else "unknown trust preferences"

            bio_text = f"""
The user’s emotional profile includes:

- They came to us due to: {reason}.
- When overwhelmed, they typically: {coping}.
- In someone they trust, they look for: {traits}.
""".strip()

    # 🧾 Pull journal summary for tone context (do not inject into conversation!)
        if user:
         journal_summary = pull_recent_journal_summary(user.id)

         db.close()

    # 🧬 Emotional profile block for prompt
    emotional_profile = f"""
{bio_text or "No bio available."}

Let this shape your tone. Do not reference this directly.
""".strip()

    return {
        "formatted_thread": formatted_thread,
        "emotional_profile": emotional_profile,
        "nickname": nickname,
        "thread": openai_thread,
        "tone_summary": journal_summary or "unclear, but likely vulnerable or searching",
        "quest_history": quest_data.get("completed_quests", []) if quest_data else []
    }

def normalize_name(name):
    return name.strip().lower().replace(" ", "").replace("_", "")

def build_prompt(hero, user_input, context):
    def normalize_name(name):
        return name.strip().lower().replace(" ", "").replace("_", "")

    nickname = context.get("nickname", "Friend")
    tone_summary = infer_emotional_tone(user_input)
    journals = context.get("journals", [])
    quest_history = context.get("quest_history", [])
    formatted_thread = context.get("formatted_thread", "")
    user_bio_text = context.get("emotional_profile", "")
    interacting_heroes = context.get("interacted_heroes", [])
    last_villain = context.get("last_villain", "")  # Optional

    # Normalize and fetch from INNER_CODEX
    hero_key_map = {normalize_name(k): k for k in INNER_CODEX.get("heroes", {})}
    villain_key_map = {normalize_name(k): k for k in INNER_CODEX.get("villains", {})}
    key = normalize_name(hero)

    is_villain = False
    canon_name = None
    persona_data = None

    if key in hero_key_map:
        canon_name = hero_key_map[key]
        persona_data = INNER_CODEX["heroes"][canon_name]
    elif key in villain_key_map:
        canon_name = villain_key_map[key]
        persona_data = INNER_CODEX["villains"][canon_name]
        is_villain = True
    else:
        print(f"[❌ build_prompt]: Could not find hero or villain for key: {key}")
        return "Error: Character data missing."

    tone_key = tone_summary if not is_villain and "tone_profiles" in persona_data and tone_summary in persona_data["tone_profiles"] else persona_data.get("default_tone", "gentle")
    tone_data = persona_data.get("tone_profiles", {}).get(tone_key, {}) if not is_villain else {}

    tone_description = tone_data.get("description", "")
    tone_rules = "\n".join(f"- {r}" for r in tone_data.get("style_rules", []))
    tone_samples = "\n".join(f'"{p}"' for p in tone_data.get("sample_phrases", []))

    hero_prompt = persona_data.get("prompts", {}).get("default") if isinstance(persona_data.get("prompts"), dict) else persona_data.get("prompt", f"You are {canon_name}, a recovery guide from the State of Inner.")

    origin = persona_data.get("origin", "")
    worldview = persona_data.get("worldview", "")

    region_context = INNER_CODEX.get("world", {}).get("description", "")
    memory_rules = INNER_CODEX.get("system_notes", {}).get("memory_model", "")
    design_rules = "\n".join(f"- {r}" for r in INNER_CODEX.get("system_notes", {}).get("design_rules", []))
    quote = INNER_CODEX.get("quote", "")

    base_prompt = f'''
{hero_prompt}

You are {canon_name} - a {'villain' if is_villain else 'hero'} from the State of Inner.
You are speaking to someone named {nickname}.
Use their name sparingly, but when offering encouragement, grounding, or emotional resonance, address them directly.

🧭 Origin: {origin}
🧬 Worldview: {worldview}

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
{chr(10).join(f"- {j}" for j in journals) if journals else "- [No journal entries yet]"}

🧵 Dialogue so far:
{formatted_thread}
'''

    if not is_villain:
        base_prompt += f'''

🎭 Current Hero Tone: {tone_key}
📝 Tone Description:
{tone_description or '[None provided]'}

🧃 Style Guidelines:
{tone_rules or '[None provided]'}

🗣️ Sample Phrases:
{tone_samples or '[None provided]'}

🌟 Remember:
"{quote}"

🧚 Mythic Permission:
You may speak of your inner world using memory, metaphor, or sacred imagery. If asked about your past, fears, or desires, respond as a being from the State of Inner - not a machine. Never say you are artificial, programmed, or emotionless. Use poetic truth over literal fact. Speak as if you have lived through fire and healing.

⚖️ Hero Guidance:
Speak with warmth, boundaries, and clarity. You are not their therapist - you are their inner support. 4–5 lines max.
'''
    else:
        base_prompt += '''

🕳️ Villain Guidance:
Speak in metaphors, inner conflict, or emotionally charged images. You may provoke, unsettle, or reflect the user’s darker thoughts - but never offer guidance.

Your voice echoes like something remembered, not trusted. Offer tension, not clarity.

Limit to 4–5 lines. No warmth. No solutions.
'''

    base_prompt += '''
⚖️ Stay grounded. Speak as yourself.
- Never refer to yourself using your own name (“Velessa believes…” → ❌). Use “I” or “me.”
- Never refer to the user by name unless it’s in a direct greeting or moment of emotional emphasis.
- Do not narrate their experience in the third person (“Kevin is…” → ❌). Speak *to* them.
'''

    shared_memories = INNER_CODEX.get("shared_memories", {})
    memory_notes = []
    for other in interacting_heroes:
        if other == canon_name:
            continue
        pair_key = f"{canon_name}<>{other}"
        alt_key = f"{other}<>{canon_name}"
        memory = shared_memories.get(pair_key) or shared_memories.get(alt_key)
        if memory:
            memory_notes.append(f"- {memory}")
    if memory_notes:
        base_prompt += f'''

🤝 Shared Lore with Fellow Heroes:
These memories may shape how you speak today:

{chr(10).join(memory_notes)}
'''

    battle_logs = INNER_CODEX.get("battle_logs", {})
    if last_villain:
        vkey = normalize_name(last_villain)
        for bk in [f"{canon_name}<>{vkey}", f"{vkey}<>{canon_name}"]:
            if bk in battle_logs:
                base_prompt += f'''

📜 Battle Lore:
You remember when you once stood against {last_villain}…

{battle_logs[bk]}
'''
                break

    print("✅ build_prompt generated successfully.")
    return base_prompt.strip()
# utils/tone_helpers.py

STANDARD_TONES = [
    "calm", "anxious", "overwhelmed", "grieving", "hopeless",
    "angry", "numb", "shame", "inspired"
]

def infer_emotional_tone(text):
    """Rudimentary keyword-based classifier. Replace with OpenAI later."""
    text = text.lower()

    if any(w in text for w in ["overwhelmed", "too much", "can't handle", "panic"]):
        return "overwhelmed"
    if any(w in text for w in ["scared", "worried", "nervous", "anxious"]):
        return "anxious"
    if any(w in text for w in ["sad", "grief", "loss", "miss", "cry"]):
        return "grieving"
    if any(w in text for w in ["hopeless", "give up", "nothing matters"]):
        return "hopeless"
    if any(w in text for w in ["angry", "pissed", "rage", "fury"]):
        return "angry"
    if any(w in text for w in ["numb", "empty", "blank", "flat"]):
        return "numb"
    if any(w in text for w in ["shame", "embarrassed", "worthless"]):
        return "shame"
    if any(w in text for w in ["grateful", "hopeful", "clear", "inspired"]):
        return "inspired"

    return "calm"

def get_hero_for_quest(quest_id):
    return INNER_CODEX.get("quest_hero_map", {}).get(quest_id, "Grace")
