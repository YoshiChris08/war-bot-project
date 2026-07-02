import json
import os
from typing import Any, Dict, List, Optional

from utils.config import DATA_DIR

BILLBOARD_DIR = os.path.join(DATA_DIR, "billboard-data")


def billboard_path(war_type: str) -> str:
    return os.path.join(BILLBOARD_DIR, f"{war_type.lower()}-billboard.json")


def load_wars(war_type: str) -> List[Dict[str, Any]]:
    path = billboard_path(war_type)
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        print(f"⚠️ {war_type.upper()} billboard JSON is corrupted.")
        return []
    except Exception as exc:
        print(f"❌ Failed to load {war_type} billboard: {exc}")
        return []


def save_wars(war_type: str, wars: List[Dict[str, Any]]) -> None:
    path = billboard_path(war_type)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(wars, handle, indent=2, ensure_ascii=False)


def find_war(war_type: str, war_id: str) -> Optional[Dict[str, Any]]:
    for war in load_wars(war_type):
        if war.get("war_id") == war_id:
            return war
    return None


def find_war_by_author(war_type: str, author_discord_id: int) -> Optional[Dict[str, Any]]:
    for war in load_wars(war_type):
        if war.get("author_discord_id") == author_discord_id and war.get("status", "open") == "open":
            return war
    return None


def upsert_war(war_type: str, war: Dict[str, Any]) -> None:
    wars = load_wars(war_type)
    war_id = war.get("war_id")
    updated = False
    for index, existing in enumerate(wars):
        if existing.get("war_id") == war_id:
            wars[index] = war
            updated = True
            break
    if not updated:
        wars.append(war)
    save_wars(war_type, wars)


def delete_war(war_type: str, war_id: str) -> bool:
    wars = load_wars(war_type)
    new_wars = [war for war in wars if war.get("war_id") != war_id]
    if len(new_wars) == len(wars):
        return False
    save_wars(war_type, new_wars)
    return True


def find_post_by_party_id(party_id: str) -> Optional[tuple[str, Dict[str, Any]]]:
    for war_type in ("rt", "ct"):
        for war in load_wars(war_type):
            if war.get("party_id") == party_id:
                return war_type, war
    return None


def find_war_across_boards(war_id: str) -> Optional[tuple[str, Dict[str, Any]]]:
    for war_type in ("rt", "ct"):
        war = find_war(war_type, war_id)
        if war:
            return war_type, war
    return None
