import random
import string

def generate_resurgitag(base_name="user"):
    tag = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"@{base_name.lower()}{tag}"
