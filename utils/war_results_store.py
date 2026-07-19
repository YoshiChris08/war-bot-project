import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

from utils.config import DATA_DIR

WAR_RESULTS_PATH = os.path.join(DATA_DIR, "war-results.json")


def _load_all() -> Dict[str, Any]:
    if not os.path.exists(WAR_RESULTS_PATH):
        return {"results": []}
    try:
        with open(WAR_RESULTS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if "results" in data else {"results": []}
    except json.JSONDecodeError:
        return {"results": []}


def _save_all(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(WAR_RESULTS_PATH), exist_ok=True)
    with open(WAR_RESULTS_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def append_result(result: Dict[str, Any]) -> Dict[str, Any]:
    data = _load_all()
    result.setdefault("result_id", str(uuid.uuid4()))
    result.setdefault("completed_at", datetime.utcnow().isoformat())
    result.setdefault("table_bot_synced", False)
    data["results"].append(result)
    _save_all(data)
    return result


def list_results() -> List[Dict[str, Any]]:
    return _load_all()["results"]


def list_results_for_player(discord_id: int, *, limit: int = 5) -> List[Dict[str, Any]]:
    """Most recent completed wars involving this Discord user (newest first)."""
    matches: List[Dict[str, Any]] = []
    target = int(discord_id)
    for result in reversed(list_results()):
        found_side = None
        found_player = None
        for side, key in (("winner", "winner_lineup"), ("loser", "loser_lineup")):
            for player in result.get(key) or []:
                if player.get("discord_id") == target:
                    found_side = side
                    found_player = player
                    break
            if found_side:
                break
        if not found_side:
            continue
        matches.append(
            {
                **result,
                "player_outcome": "W" if found_side == "winner" else "L",
                "player_entry": found_player,
            }
        )
        if len(matches) >= limit:
            break
    return matches
