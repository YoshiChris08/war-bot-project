"""MMR helpers — team averages for display and ranked war adjustments."""

from typing import Any, Dict, List, Tuple

from utils.player_store import DEFAULT_PLAYER_MMR, apply_player_delta, get_player

DEFAULT_MMR = DEFAULT_PLAYER_MMR
MMR_K = 32


def player_mmr(player: Dict[str, Any]) -> int:
    discord_id = player.get("discord_id")
    if discord_id:
        return int(get_player(int(discord_id)).get("mmr", DEFAULT_MMR))
    return int(player.get("mmr", DEFAULT_MMR))


def team_roster_players(lineup: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Core team members only — excludes hub allies."""
    return [player for player in lineup or [] if not player.get("ally")]


def average_team_mmr(lineup: List[Dict[str, Any]]) -> int:
    roster = team_roster_players(lineup)
    if not roster:
        return DEFAULT_MMR
    total = sum(player_mmr(player) for player in roster)
    return round(total / len(roster))


def format_average_rank(lineup: List[Dict[str, Any]]) -> str:
    return f"`{average_team_mmr(lineup):,}` MMR (team avg)"


def _margin_multiplier(point_margin: int) -> float:
    margin = max(1, int(point_margin))
    return min(1.5, 1.0 + (margin / 100.0))


def calculate_team_mmr_delta(
    winner_lineup: List[Dict[str, Any]],
    loser_lineup: List[Dict[str, Any]],
    point_margin: int,
) -> int:
    winner_avg = average_team_mmr(winner_lineup)
    loser_avg = average_team_mmr(loser_lineup)
    expected = 1.0 / (1.0 + 10 ** ((loser_avg - winner_avg) / 400.0))
    delta = round(MMR_K * (1.0 - expected) * _margin_multiplier(point_margin))
    return max(1, delta)


def apply_ranked_war_mmr(
    winner_lineup: List[Dict[str, Any]],
    loser_lineup: List[Dict[str, Any]],
    point_margin: int,
) -> Tuple[int, Dict[str, int]]:
    """Apply MMR changes to stored player records. Returns team delta and per-player map."""
    team_delta = calculate_team_mmr_delta(winner_lineup, loser_lineup, point_margin)
    per_player: Dict[str, int] = {}

    winner_roster = team_roster_players(winner_lineup)
    loser_roster = team_roster_players(loser_lineup)

    for player in winner_roster:
        discord_id = player.get("discord_id")
        if not discord_id:
            continue
        apply_player_delta(int(discord_id), team_delta, won=True)
        per_player[str(discord_id)] = team_delta

    for player in loser_roster:
        discord_id = player.get("discord_id")
        if not discord_id:
            continue
        apply_player_delta(int(discord_id), -team_delta, won=False)
        per_player[str(discord_id)] = -team_delta

    return team_delta, per_player
