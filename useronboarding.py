# useronboarding.py

# ========== Q1: What brings you here today? ==========
ONBOARDING_Q1_STORIES = {
    "Major loss or grieving": (
        "I lost someone I didn’t think I could live without. "
        "Grief doesn't follow rules — some days I feel numb, other days I collapse from nowhere. "
        "I try to hold it together, but it always finds me. That’s why I’m here."
    ),
    "Anxiety or fear": (
        "My mind never stops. I’m constantly overthinking, planning for worst-case scenarios, even when nothing’s wrong. "
        "It’s like my body is wired for a threat that isn’t coming. I’m just… tired of being afraid."
    ),
    "Addiction": (
        "I’ve done things I swore I never would, just to feed the craving. "
        "Addiction took pieces of me — friends, trust, even my self-respect. "
        "I’m here because I want to believe there’s still something worth saving."
    ),
    "Depression or emptiness": (
        "Most days I feel like I’m underwater. Everyone thinks I’m fine, but inside there’s just this dull ache, like nothing matters. "
        "I smile, I show up, but I don’t feel *here*. That’s why I came."
    ),
    "Low self-worth": (
        "I don’t know how to like myself, let alone love myself. "
        "I always feel like I’m too much or not enough. "
        "I keep waiting for someone to see value in me — maybe I need to learn how to see it first."
    ),
    "Trauma or PTSD": (
        "There are moments I can’t move past. They show up in my dreams, in loud sounds, in silence. "
        "I thought I’d buried it, but it still lives in my body. I’m here because I want to stop running from it."
    ),
    "Emotional growth": (
        "I’m not in crisis — but I don’t feel whole, either. "
        "I want to understand myself better, figure out why I react the way I do. "
        "I’m not here to escape something… I’m here to grow into someone."
    )
}

# ========== Q2: When emotions overwhelm you, what do you tend to do? ==========
ONBOARDING_Q2_STORIES = {
    "Crash under the covers": (
        "When everything hits at once, I shut down. The world feels too loud, too heavy. "
        "So I disappear under blankets and hope no one needs me until I can breathe again."
    ),
    "Stay busy": (
        "If I slow down, the feelings catch up. So I keep moving — cleaning, working, helping others — anything to avoid sitting in the pain."
    ),
    "Talk to someone (or wish I could)": (
        "Sometimes I reach out. Sometimes I just wish someone would ask. I carry a lot inside, hoping someone will help carry it with me."
    ),
    "Exercise": (
        "I need to move it out of me. The tension, the chaos, the fog — when I sweat, I feel like I exist again."
    ),
    "Scroll on my phone": (
        "I distract myself in a sea of strangers’ lives. It’s not healing, but it numbs the edge just long enough to survive the wave."
    ),
    "Meditate / Pray / Listen to music": (
        "I try to find something still and sacred. Whether it’s prayer, music, or breath — I need something deeper to hold onto."
    ),
    "Seek solitude": (
        "When I’m overwhelmed, I disappear. Not because I don’t care — but because I need space to feel safely."
    )
}

# ========== Q3: What qualities do you admire in someone you trust? ==========
ONBOARDING_Q3_TRAITS = {
    "Makes me feel safe": "I admire people who make me feel protected — not judged, not pushed, just safe to be who I am.",
    "Calms things down": "I trust people who don’t add fuel to the fire. They bring clarity and calm when everything else feels chaotic.",
    "Says what I need to hear": "I value honesty, even when it’s hard. I’d rather someone tell me the truth than sugarcoat things.",
    "Makes me laugh": "Humor breaks the tension for me. I feel close to people who can make me laugh when I least expect it.",
    "Doesn’t judge me": "Being around someone who truly sees me — flaws and all — and doesn’t shame me? That’s everything.",
    "Reminds me who I am": "I love people who hold a mirror up to the good in me — especially when I forget it myself."
}

# Final structure to generate a fake user backstory from their onboarding
# Example function to compose story:
def build_user_backstory(q1, q2, q3_traits):
    story = []
    if q1 in ONBOARDING_Q1_STORIES:
        story.append(ONBOARDING_Q1_STORIES[q1])
    if q2 in ONBOARDING_Q2_STORIES:
        story.append(ONBOARDING_Q2_STORIES[q2])
    for trait in q3_traits:
        if trait in ONBOARDING_Q3_TRAITS:
            story.append(ONBOARDING_Q3_TRAITS[trait])
    return " " + " ".join(story)

# Example usage:
# fake_story = build_user_backstory(
#     "Addiction",
#     "Stay busy",
#     ["Makes me feel safe", "Says what I need to hear"]
# )

