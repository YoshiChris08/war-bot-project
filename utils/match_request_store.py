import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.config import DATA_DIR

MATCH_REQUESTS_PATH = os.path.join(DATA_DIR, "match-requests.json")


def _load_all() -> Dict[str, Any]:
    if not os.path.exists(MATCH_REQUESTS_PATH):
        return {"requests": {}}
    try:
        with open(MATCH_REQUESTS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if "requests" in data else {"requests": {}}
    except json.JSONDecodeError:
        return {"requests": {}}


def _save_all(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(MATCH_REQUESTS_PATH), exist_ok=True)
    with open(MATCH_REQUESTS_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def get_request(request_id: str) -> Optional[Dict[str, Any]]:
    return _load_all()["requests"].get(request_id)


def upsert_request(request: Dict[str, Any]) -> Dict[str, Any]:
    data = _load_all()
    data["requests"][request["request_id"]] = request
    _save_all(data)
    return request


def delete_request(request_id: str) -> bool:
    data = _load_all()
    if request_id not in data["requests"]:
        return False
    del data["requests"][request_id]
    _save_all(data)
    return True


def pending_for_target_war(target_war_id: str) -> Optional[Dict[str, Any]]:
    for request in _load_all()["requests"].values():
        if request.get("target_war_id") == target_war_id and request.get("status") == "pending":
            return request
    return None


def create_request(
    board: str,
    target_war_id: str,
    requester_war_id: str,
) -> Dict[str, Any]:
    request = {
        "request_id": str(uuid.uuid4()),
        "board": board,
        "target_war_id": target_war_id,
        "requester_war_id": requester_war_id,
        "status": "pending",
        "notification_channel_id": None,
        "notification_message_id": None,
        "created_at": datetime.utcnow().isoformat(),
    }
    return upsert_request(request)
