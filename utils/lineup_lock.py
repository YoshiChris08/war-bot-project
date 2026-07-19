"""Block players from joining multiple active lineups at once."""

from typing import Any, Dict, Optional

from utils.billboard_store import load_wars
from utils.boards import ALL_BOARD_KEYS
from utils.queue_store import list_parties

ACTIVE_PARTY_STATUSES = ("preparing", "posted", "matched")
ACTIVE_WAR_STATUSES = ("open", "matched")


def _user_in_lineup(lineup: list, discord_id: int) -> bool:
    return any(entry.get("discord_id") == discord_id for entry in lineup or [])


def find_blocking_lineup(
    discord_id: int,
    *,
    exclude_party_id: Optional[str] = None,
    exclude_war_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return another active lineup this user is on, or None if free to join."""
    for party in list_parties():
        if party.get("status") not in ACTIVE_PARTY_STATUSES:
            continue
        if exclude_party_id and party.get("party_id") == exclude_party_id:
            continue
        if _user_in_lineup(party.get("lineup", []), discord_id):
            return {
                "kind": "party",
                "team_name": party.get("team_name", "Unknown"),
                "status": party.get("status", "active"),
            }

    for board in ALL_BOARD_KEYS:
        for war in load_wars(board):
            if war.get("status") not in ACTIVE_WAR_STATUSES:
                continue
            if exclude_war_id and war.get("war_id") == exclude_war_id:
                continue
            if _user_in_lineup(war.get("lineup", []), discord_id):
                return {
                    "kind": "war",
                    "team_name": war.get("team_name", "Unknown"),
                    "status": war.get("status", "open"),
                }
    return None


def lineup_lock_message(block: Dict[str, Any]) -> str:
    team = block.get("team_name", "another team")
    status = block.get("status", "")
    if block.get("kind") == "party":
        if status == "matched":
            return (
                f"You are already on **{team}**'s matched roster. "
                "Finish or cancel that match before joining elsewhere."
            )
        if status == "posted":
            return (
                f"You are already on **{team}**'s queue (posted to the hub). "
                "Leave that lineup or wait for the match to finish before joining elsewhere."
            )
        return (
            f"You are already in **{team}**'s team queue. "
            "Leave that lobby before joining another lineup."
        )

    if status == "matched":
        return (
            f"You are already on **{team}**'s matched war roster. "
            "Complete or cancel that match before joining elsewhere."
        )
    return (
        f"You are already on **{team}**'s hub roster. "
        "Leave that post or wait until the match ends before joining as an ally elsewhere."
    )
