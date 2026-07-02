import json
import os
from typing import Any, Dict, Optional

from utils.config import DATA_DIR

TEAM_STORE_PATH = os.path.join(DATA_DIR, "teams.json")


def _load_all() -> Dict[str, Any]:
    if not os.path.exists(TEAM_STORE_PATH):
        return {"teams": {}}
    try:
        with open(TEAM_STORE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if "teams" in data else {"teams": {}}
    except json.JSONDecodeError:
        return {"teams": {}}


def _save_all(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(TEAM_STORE_PATH), exist_ok=True)
    with open(TEAM_STORE_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def get_team_by_guild(guild_id: int) -> Optional[Dict[str, Any]]:
    return _load_all()["teams"].get(str(guild_id))


def upsert_team(team: Dict[str, Any]) -> Dict[str, Any]:
    data = _load_all()
    key = str(team["guild_id"])
    data["teams"][key] = team
    _save_all(data)
    return team
