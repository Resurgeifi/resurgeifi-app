import yaml
import os

def load_quest(quest_id):
    """Loads quest data from YAML file based on quest_id."""
    filename = f"quest_{quest_id:02}.yaml"
    quest_path = os.path.join("quests", filename)

    if not os.path.exists(quest_path):
        raise FileNotFoundError(f"Quest config not found: {quest_path}")

    with open(quest_path, "r") as file:
        return yaml.safe_load(file)

