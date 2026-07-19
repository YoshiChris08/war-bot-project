import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from utils.config import DATA_DIR

COMPLETIONS_PATH = os.path.join(DATA_DIR, "war-completions-pending.json")

ACTIVE_STATUSES = ("collecting_scores", "pending_confirmation")


def _load_all() -> Dict[str, Any]:
    if not os.path.exists(COMPLETIONS_PATH):
        return {"pending": {}}
    try:
        with open(COMPLETIONS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if "pending" in data else {"pending": {}}
    except json.JSONDecodeError:
        return {"pending": {}}


def _save_all(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(COMPLETIONS_PATH), exist_ok=True)
    with open(COMPLETIONS_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def _base_pending(
    board: str,
    reporter_war: Dict[str, Any],
    opponent_war: Dict[str, Any],
    winner_war_id: str,
    point_margin: int,
    reporter_discord_id: int,
    session_id: Optional[str],
) -> Dict[str, Any]:
    return {
        "completion_id": str(uuid.uuid4()),
        "session_id": session_id,
        "board": board,
        "reporter_war_id": reporter_war.get("war_id"),
        "opponent_war_id": opponent_war.get("war_id"),
        "winner_war_id": winner_war_id,
        "point_margin": point_margin,
        "reporter_discord_id": reporter_discord_id,
        "reporter_team_name": reporter_war.get("team_name"),
        "opponent_team_name": opponent_war.get("team_name"),
        "opponent_captain_id": opponent_war.get("author_discord_id"),
        "reporter_captain_id": reporter_war.get("author_discord_id"),
        "reporter_guild_id": reporter_war.get("origin_guild_id"),
        "opponent_guild_id": opponent_war.get("origin_guild_id"),
        "mode": reporter_war.get("mode", "ranked"),
        "created_at": datetime.utcnow().isoformat(),
    }


def create_pending_with_rxx(
    board: str,
    reporter_war: Dict[str, Any],
    opponent_war: Dict[str, Any],
    winner_war_id: str,
    point_margin: int,
    reporter_discord_id: int,
    rxx: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    pending = _base_pending(
        board, reporter_war, opponent_war, winner_war_id, point_margin, reporter_discord_id, session_id
    )
    pending.update(
        {
            "status": "pending_confirmation",
            "sync_method": "rxx",
            "rxx": rxx,
            "team_scores": None,
            "confirmed_by": [],
        }
    )
    data = _load_all()
    data["pending"][pending["completion_id"]] = pending
    _save_all(data)
    return pending


def create_pending_collecting_scores(
    board: str,
    reporter_war: Dict[str, Any],
    opponent_war: Dict[str, Any],
    winner_war_id: str,
    point_margin: int,
    reporter_discord_id: int,
    session_id: Optional[str] = None,
    *,
    rxx: Optional[str] = None,
    manual_fallback: bool = False,
    fallback_reason: Optional[str] = None,
) -> Dict[str, Any]:
    pending = _base_pending(
        board, reporter_war, opponent_war, winner_war_id, point_margin, reporter_discord_id, session_id
    )
    pending.update(
        {
            "status": "collecting_scores",
            "sync_method": "player_scores",
            "rxx": rxx,
            "team_scores": {},
            "manual_fallback": manual_fallback,
            "fallback_reason": fallback_reason,
        }
    )
    data = _load_all()
    data["pending"][pending["completion_id"]] = pending
    _save_all(data)
    return pending


def upsert_team_scores(completion_id: str, war_id: str, team_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = _load_all()
    pending = data["pending"].get(completion_id)
    if not pending or pending.get("status") != "collecting_scores":
        return None
    scores = pending.setdefault("team_scores", {})
    scores[war_id] = team_entry
    data["pending"][completion_id] = pending
    _save_all(data)
    return pending


def clear_team_scores(completion_id: str) -> Optional[Dict[str, Any]]:
    data = _load_all()
    pending = data["pending"].get(completion_id)
    if not pending or pending.get("status") != "collecting_scores":
        return None
    pending["team_scores"] = {}
    data["pending"][completion_id] = pending
    _save_all(data)
    return pending


def mark_pending_confirmation(completion_id: str, table_reference: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = _load_all()
    pending = data["pending"].get(completion_id)
    if not pending:
        return None
    pending["status"] = "pending_confirmation"
    pending["sync_method"] = table_reference.get("sync_method")
    pending["rxx"] = table_reference.get("rxx")
    pending["team_scores"] = table_reference.get("team_scores")
    pending["confirmed_by"] = []
    data["pending"][completion_id] = pending
    _save_all(data)
    return pending


def record_captain_confirmation(completion_id: str, captain_id: int) -> Optional[Dict[str, Any]]:
    data = _load_all()
    pending = data["pending"].get(completion_id)
    if not pending or pending.get("status") != "pending_confirmation":
        return None
    confirmed = pending.setdefault("confirmed_by", [])
    if captain_id not in confirmed:
        confirmed.append(captain_id)
    data["pending"][completion_id] = pending
    _save_all(data)
    return pending


def both_captains_confirmed(pending: Dict[str, Any]) -> bool:
    needed = {pending.get("reporter_captain_id"), pending.get("opponent_captain_id")}
    needed.discard(None)
    confirmed = set(pending.get("confirmed_by") or [])
    return needed.issubset(confirmed)


def get_pending(completion_id: str) -> Optional[Dict[str, Any]]:
    return _load_all()["pending"].get(completion_id)


def find_pending_for_war(war_id: str) -> Optional[Dict[str, Any]]:
    for pending in _load_all()["pending"].values():
        if pending.get("status") not in ACTIVE_STATUSES:
            continue
        if war_id in (pending.get("reporter_war_id"), pending.get("opponent_war_id")):
            return pending
    return None


def delete_pending(completion_id: str) -> bool:
    data = _load_all()
    if completion_id not in data["pending"]:
        return False
    del data["pending"][completion_id]
    _save_all(data)
    return True
