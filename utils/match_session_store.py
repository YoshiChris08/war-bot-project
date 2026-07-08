import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.config import DATA_DIR

MATCH_SESSIONS_PATH = os.path.join(DATA_DIR, "match-sessions.json")


def _load_all() -> Dict[str, Any]:
    if not os.path.exists(MATCH_SESSIONS_PATH):
        return {"sessions": {}}
    try:
        with open(MATCH_SESSIONS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if "sessions" in data else {"sessions": {}}
    except json.JSONDecodeError:
        return {"sessions": {}}


def _save_all(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(MATCH_SESSIONS_PATH), exist_ok=True)
    with open(MATCH_SESSIONS_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    return _load_all()["sessions"].get(session_id)


def get_session_by_channel(channel_id: int) -> Optional[Dict[str, Any]]:
    for session in _load_all()["sessions"].values():
        if channel_id in (
            session.get("channel_a_id"),
            session.get("channel_b_id"),
        ):
            return session
    return None


def get_session_by_war_id(war_id: str) -> Optional[Dict[str, Any]]:
    for session in _load_all()["sessions"].values():
        if war_id in (session.get("war_a_id"), session.get("war_b_id")):
            return session
    return None


def delete_session(session_id: str) -> bool:
    data = _load_all()
    if session_id not in data["sessions"]:
        return False
    del data["sessions"][session_id]
    _save_all(data)
    return True


def upsert_session(session: Dict[str, Any]) -> Dict[str, Any]:
    data = _load_all()
    data["sessions"][session["session_id"]] = session
    _save_all(data)
    return session


def create_session(
    board: str,
    war_a: Dict[str, Any],
    war_b: Dict[str, Any],
    channel_a_id: int,
    channel_b_id: int,
    roster_a_ids: List[int],
    roster_b_ids: List[int],
) -> Dict[str, Any]:
    session = {
        "session_id": str(uuid.uuid4()),
        "board": board,
        "war_a_id": war_a.get("war_id"),
        "war_b_id": war_b.get("war_id"),
        "guild_a_id": war_a.get("origin_guild_id"),
        "guild_b_id": war_b.get("origin_guild_id"),
        "team_a_name": war_a.get("team_name"),
        "team_b_name": war_b.get("team_name"),
        "channel_a_id": channel_a_id,
        "channel_b_id": channel_b_id,
        "roster_a_ids": roster_a_ids,
        "roster_b_ids": roster_b_ids,
        "created_at": datetime.utcnow().isoformat(),
    }
    return upsert_session(session)
