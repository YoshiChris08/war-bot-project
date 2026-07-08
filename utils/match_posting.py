from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from classes.player import Player
from classes.queue_party import MODE_CASUAL
from classes.war import War
from utils.billboard_store import find_post_by_party_id, upsert_war
from utils.boards import board_for_war
from utils.roster import SEARCH_ALLIES, SEARCH_OPPONENTS, reconcile_search_mode


def lineup_from_dicts(lineup: List[Dict[str, Any]]) -> List[Player]:
    return [Player.from_dict(player) for player in lineup]


def create_match_post_from_party(party: Dict[str, Any], search_mode: str) -> Dict[str, Any]:
    """Create a hub billboard MatchPost from a team-server QueueParty."""
    lineup = lineup_from_dicts(party.get("lineup", []))
    mode = party.get("mode", "ranked")
    war = War(
        war_type=party.get("war_type", "RT"),
        team_name=party.get("team_name", "Unknown Team"),
        start_time=party.get("search_time", "ASAP"),
        search_in_advance=party.get("search_time", "ASAP") != "ASAP",
        lineup=lineup,
        search_mode=search_mode,
        status="open",
        author_discord_id=party.get("captain_discord_id"),
        origin_guild_id=party.get("guild_id"),
        party_id=party.get("party_id"),
        mode=mode,
    )
    war.last_updated = datetime.utcnow().isoformat()
    war.ally_count = sum(1 for player in lineup if player.ally)
    return war.to_dict()


def sync_party_lineup_from_post(party: Dict[str, Any], post: Dict[str, Any]) -> Dict[str, Any]:
    party["lineup"] = post.get("lineup", [])
    party["search_mode"] = post.get("search_mode", party.get("search_mode", "allies"))
    party["mode"] = post.get("mode", party.get("mode", "ranked"))
    if post.get("status") == "matched":
        party["status"] = "matched"
    return party


def sync_billboard_post_from_party(party: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Push team-queue roster changes to the linked hub billboard post."""
    found = find_post_by_party_id(party.get("party_id"))
    if not found:
        return None

    board, war = found
    war["lineup"] = list(party.get("lineup", []))
    war["ally_count"] = sum(1 for player in war["lineup"] if player.get("ally"))
    war["last_updated"] = datetime.utcnow().isoformat()
    war["search_mode"] = reconcile_search_mode(war.get("search_mode", SEARCH_ALLIES), war["lineup"])
    party["search_mode"] = war["search_mode"]

    upsert_war(board, war)
    return board, war
