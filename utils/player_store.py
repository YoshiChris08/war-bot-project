import json
import os
from typing import Any, Dict, Optional

from utils.config import DATA_DIR

DEFAULT_PLAYER_MMR = 10_000
PLAYER_STORE_PATH = os.path.join(DATA_DIR, "player-mmr.json")


def _load_all() -> Dict[str, Any]:
    if not os.path.exists(PLAYER_STORE_PATH):
        return {"players": {}}
    try:
        with open(PLAYER_STORE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if "players" in data else {"players": {}}
    except json.JSONDecodeError:
        return {"players": {}}


def _save_all(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(PLAYER_STORE_PATH), exist_ok=True)
    with open(PLAYER_STORE_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def get_player(discord_id: int) -> Dict[str, Any]:
    data = _load_all()
    key = str(discord_id)
    if key not in data["players"]:
        return {
            "discord_id": discord_id,
            "mmr": DEFAULT_PLAYER_MMR,
            "wins": 0,
            "losses": 0,
        }
    return data["players"][key]


def apply_player_delta(discord_id: int, mmr_delta: int, won: bool) -> Dict[str, Any]:
    data = _load_all()
    key = str(discord_id)
    current = data["players"].get(key, get_player(discord_id))
    current["mmr"] = max(0, int(current.get("mmr", DEFAULT_PLAYER_MMR)) + mmr_delta)
    if won:
        current["wins"] = int(current.get("wins", 0)) + 1
    else:
        current["losses"] = int(current.get("losses", 0)) + 1
    data["players"][key] = current
    _save_all(data)
    return current


def set_player_mmr(discord_id: int, mmr: int) -> Dict[str, Any]:
    data = _load_all()
    key = str(discord_id)
    current = data["players"].get(key, get_player(discord_id))
    current["mmr"] = max(0, int(mmr))
    data["players"][key] = current
    _save_all(data)
    return current
