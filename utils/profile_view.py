"""Helpers for /profile view — team affiliation + recent form."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from utils.player_store import DEFAULT_PLAYER_MMR, get_player
from utils.team_store import get_team_by_guild
from utils.war_results_store import list_results, list_results_for_player


def estimate_guild_team_mmr(guild_id: int) -> Optional[int]:
    """
    Rough team MMR: average overall rating of players who appeared as
    non-ally core on that guild's completed wars (allies excluded from team avg).
    """
    ids: Set[int] = set()
    for result in list_results():
        for guild_key, lineup_key in (
            ("winner_guild_id", "winner_lineup"),
            ("loser_guild_id", "loser_lineup"),
        ):
            if result.get(guild_key) != guild_id:
                continue
            for player in result.get(lineup_key) or []:
                if player.get("ally"):
                    continue
                discord_id = player.get("discord_id")
                if discord_id:
                    ids.add(int(discord_id))
    if not ids:
        return None
    total = sum(int(get_player(i).get("mmr", DEFAULT_PLAYER_MMR)) for i in ids)
    return round(total / len(ids))


def resolve_profile_team(guild_id: Optional[int]) -> tuple[Optional[Dict[str, Any]], Optional[int]]:
    if not guild_id:
        return None, None
    team = get_team_by_guild(guild_id)
    if not team:
        return None, None
    return team, estimate_guild_team_mmr(guild_id)


def recent_wars_for_profile(discord_id: int, *, limit: int = 5) -> List[Dict[str, Any]]:
    return list_results_for_player(discord_id, limit=limit)
