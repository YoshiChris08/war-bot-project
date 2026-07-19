"""MMR helpers — track+role ratings, team averages, ranked war adjustments."""

from typing import Any, Dict, List, Tuple

from utils.player_store import DEFAULT_PLAYER_MMR, apply_player_delta, get_player, get_rating

DEFAULT_MMR = DEFAULT_PLAYER_MMR
MMR_K = 32


def _is_bagger(player: Dict[str, Any]) -> bool:
    return bool(player.get("bagger") or player.get("role") == "Bagger")


def player_mmr(
    player: Dict[str, Any],
    *,
    war_type: str = "RT",
    use_role: bool = True,
) -> int:
    """
    Rating for matchmaking/display.
    When use_role is True, uses the player's role rating for that track.
    """
    discord_id = player.get("discord_id")
    if not discord_id:
        return int(player.get("mmr", DEFAULT_MMR))
    if use_role:
        return get_rating(
            int(discord_id),
            war_type,
            bagger=_is_bagger(player),
            role=player.get("role"),
        )
    return int(get_player(int(discord_id)).get("mmr", DEFAULT_MMR))


def team_roster_players(lineup: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Core team members only — excludes hub allies (for team MMR / matchmaking avg)."""
    return [player for player in lineup or [] if not player.get("ally")]


def scoring_players(lineup: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Everyone who should receive personal MMR — core roster + allies."""
    return [player for player in lineup or [] if player.get("discord_id")]


def average_team_mmr(lineup: List[Dict[str, Any]], war_type: str = "RT") -> int:
    roster = team_roster_players(lineup)
    if not roster:
        return DEFAULT_MMR
    total = sum(player_mmr(player, war_type=war_type) for player in roster)
    return round(total / len(roster))


def format_average_rank(lineup: List[Dict[str, Any]], war_type: str = "RT") -> str:
    return f"`{average_team_mmr(lineup, war_type):,}` MMR (team avg)"


def _margin_multiplier(point_margin: int) -> float:
    margin = max(1, int(point_margin))
    return min(1.5, 1.0 + (margin / 100.0))


def calculate_team_mmr_delta(
    winner_lineup: List[Dict[str, Any]],
    loser_lineup: List[Dict[str, Any]],
    point_margin: int,
    war_type: str = "RT",
) -> int:
    winner_avg = average_team_mmr(winner_lineup, war_type)
    loser_avg = average_team_mmr(loser_lineup, war_type)
    expected = 1.0 / (1.0 + 10 ** ((loser_avg - winner_avg) / 400.0))
    delta = round(MMR_K * (1.0 - expected) * _margin_multiplier(point_margin))
    return max(1, delta)


def apply_ranked_war_mmr(
    winner_lineup: List[Dict[str, Any]],
    loser_lineup: List[Dict[str, Any]],
    point_margin: int,
    war_type: str = "RT",
) -> Tuple[int, Dict[str, int]]:
    """
    Apply MMR to every player on both lineups (including allies).
    Team average / expected score still uses core roster only (no allies).
    """
    team_delta = calculate_team_mmr_delta(
        winner_lineup, loser_lineup, point_margin, war_type=war_type
    )
    per_player: Dict[str, int] = {}

    for player in scoring_players(winner_lineup):
        discord_id = int(player["discord_id"])
        apply_player_delta(
            discord_id,
            team_delta,
            won=True,
            war_type=war_type,
            bagger=_is_bagger(player),
            role=player.get("role"),
        )
        per_player[str(discord_id)] = team_delta

    for player in scoring_players(loser_lineup):
        discord_id = int(player["discord_id"])
        apply_player_delta(
            discord_id,
            -team_delta,
            won=False,
            war_type=war_type,
            bagger=_is_bagger(player),
            role=player.get("role"),
        )
        per_player[str(discord_id)] = -team_delta

    return team_delta, per_player
