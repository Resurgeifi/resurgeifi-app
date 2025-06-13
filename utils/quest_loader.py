import yaml
import os

def load_quest(quest_id):
    """Loads quest data from YAML file based on quest_id."""
    base_path = os.path.join("resurgeifi-app-main", "quests")
    filename = f"quest_{quest_id:02}.yaml"
    filepath = os.path.join(base_path, filename)

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Quest config not found: {filepath}")

    with open(filepath, "r") as file:
        return yaml.safe_load(file)
