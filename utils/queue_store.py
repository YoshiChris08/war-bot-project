import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.config import DATA_DIR

QUEUE_STORE_PATH = os.path.join(DATA_DIR, "queue-parties.json")


def _load_all() -> Dict[str, Any]:
    if not os.path.exists(QUEUE_STORE_PATH):
        return {"parties": {}}
    try:
        with open(QUEUE_STORE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if "parties" in data else {"parties": {}}
    except json.JSONDecodeError:
        return {"parties": {}}


def _save_all(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(QUEUE_STORE_PATH), exist_ok=True)
    with open(QUEUE_STORE_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def list_parties() -> List[Dict[str, Any]]:
    return list(_load_all()["parties"].values())


def get_party(party_id: str) -> Optional[Dict[str, Any]]:
    return _load_all()["parties"].get(party_id)


def get_party_by_invite(invite_code: str) -> Optional[Dict[str, Any]]:
    for party in list_parties():
        if party.get("invite_code") == invite_code and party.get("status") == "preparing":
            return party
    return None


def get_active_party_for_user(discord_id: int) -> Optional[Dict[str, Any]]:
    for party in list_parties():
        if party.get("status") not in ("preparing", "posted", "matched"):
            continue
        if party.get("captain_discord_id") == discord_id:
            return party
        for player in party.get("lineup", []):
            if player.get("discord_id") == discord_id:
                return party
    return None


def get_active_party_for_guild(guild_id: int) -> Optional[Dict[str, Any]]:
    for party in list_parties():
        if party.get("guild_id") == guild_id and party.get("status") in ("preparing", "posted", "matched"):
            return party
    return None


def upsert_party(party: Dict[str, Any]) -> Dict[str, Any]:
    data = _load_all()
    party["last_updated"] = datetime.utcnow().isoformat()
    data["parties"][party["party_id"]] = party
    _save_all(data)
    return party


def delete_party(party_id: str) -> bool:
    data = _load_all()
    if party_id not in data["parties"]:
        return False
    del data["parties"][party_id]
    _save_all(data)
    return True
