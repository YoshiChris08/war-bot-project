import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from utils.config import DATA_DIR

CANCEL_REQUESTS_PATH = os.path.join(DATA_DIR, "war-cancel-requests.json")


def _load_all() -> Dict[str, Any]:
    if not os.path.exists(CANCEL_REQUESTS_PATH):
        return {"requests": {}}
    try:
        with open(CANCEL_REQUESTS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if "requests" in data else {"requests": {}}
    except json.JSONDecodeError:
        return {"requests": {}}


def _save_all(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(CANCEL_REQUESTS_PATH), exist_ok=True)
    with open(CANCEL_REQUESTS_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def create_cancel_request(
    board: str,
    requester_war: Dict[str, Any],
    opponent_war: Dict[str, Any],
    requester_discord_id: int,
) -> Dict[str, Any]:
    request_id = str(uuid.uuid4())
    request = {
        "request_id": request_id,
        "board": board,
        "requester_war_id": requester_war.get("war_id"),
        "opponent_war_id": opponent_war.get("war_id"),
        "requester_discord_id": requester_discord_id,
        "requester_team_name": requester_war.get("team_name"),
        "opponent_team_name": opponent_war.get("team_name"),
        "opponent_captain_id": opponent_war.get("author_discord_id"),
        "requester_guild_id": requester_war.get("origin_guild_id"),
        "opponent_guild_id": opponent_war.get("origin_guild_id"),
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }
    data = _load_all()
    data["requests"][request_id] = request
    _save_all(data)
    return request


def get_cancel_request(request_id: str) -> Optional[Dict[str, Any]]:
    return _load_all()["requests"].get(request_id)


def find_cancel_for_war(war_id: str) -> Optional[Dict[str, Any]]:
    for request in _load_all()["requests"].values():
        if request.get("status") != "pending":
            continue
        if war_id in (request.get("requester_war_id"), request.get("opponent_war_id")):
            return request
    return None


def delete_cancel_request(request_id: str) -> bool:
    data = _load_all()
    if request_id not in data["requests"]:
        return False
    del data["requests"][request_id]
    _save_all(data)
    return True
