import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from utils.config import DATA_DIR

PROFILE_STORE_PATH = os.path.join(DATA_DIR, "player-profiles.json")


def _load_all() -> Dict[str, Any]:
    if not os.path.exists(PROFILE_STORE_PATH):
        return {"profiles": {}}
    try:
        with open(PROFILE_STORE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if "profiles" in data else {"profiles": {}}
    except json.JSONDecodeError:
        return {"profiles": {}}


def _save_all(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(PROFILE_STORE_PATH), exist_ok=True)
    with open(PROFILE_STORE_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def get_profile(discord_id: int) -> Optional[Dict[str, Any]]:
    return _load_all()["profiles"].get(str(discord_id))


def upsert_profile(discord_id: int, **fields: Any) -> Dict[str, Any]:
    data = _load_all()
    key = str(discord_id)
    current = data["profiles"].get(key, {"discord_id": discord_id})
    current.update(fields)
    current["discord_id"] = discord_id
    current["updated_at"] = datetime.utcnow().isoformat()
    data["profiles"][key] = current
    _save_all(data)
    return current


def has_linked_fc(discord_id: int) -> bool:
    profile = get_profile(discord_id)
    return bool(profile and profile.get("friend_code"))
