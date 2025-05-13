import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from rams import build_context, build_prompt  # ✅ This goes right here

# Optional: Hardcode a test user
test_user_id = 1
test_question = "Why do I still feel guilty after all this time?"
hero = "Grace"

context = build_context(test_user_id)
print("🔍 CONTEXT:")
print(context)

prompt = build_prompt(hero, test_question, context)
print("\n🧠 FINAL PROMPT:")
print(prompt)

