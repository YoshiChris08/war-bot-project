from datetime import datetime
from typing import Any, Dict, List

from classes.player import Player
from classes.war import War


def lineup_from_dicts(lineup: List[Dict[str, Any]]) -> List[Player]:
    return [Player.from_dict(player) for player in lineup]


def create_match_post_from_party(party: Dict[str, Any], search_mode: str) -> Dict[str, Any]:
    """Create a hub billboard MatchPost from a team-server QueueParty."""
    lineup = lineup_from_dicts(party.get("lineup", []))
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
    )
    war.last_updated = datetime.utcnow().isoformat()
    war.ally_count = sum(1 for player in lineup if player.ally)
    return war.to_dict()


def sync_party_lineup_from_post(party: Dict[str, Any], post: Dict[str, Any]) -> Dict[str, Any]:
    party["lineup"] = post.get("lineup", [])
    party["search_mode"] = post.get("search_mode", party.get("search_mode", "allies"))
    if post.get("status") == "matched":
        party["status"] = "matched"
    return party
