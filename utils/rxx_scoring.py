"""Build and validate war scores from Lounge API RXX room data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from utils.lounge_api import LoungeAPIError, fetch_room_by_rxx
from utils.player_links import resolve_friend_code, verify_cached_fcs_against_wiimmfi
from utils.wiimmfi import (
    build_table_reference_from_scores,
    build_team_score_entry,
    friend_code_key,
    normalize_friend_code,
    score_implied_margin,
    sort_lineup_for_scores,
    team_point_total,
    validate_reported_margin,
)


def _room_players(room: Dict[str, Any]) -> List[Dict[str, Any]]:
    players = room.get("players") or room.get("room_players") or []
    if isinstance(players, dict):
        return list(players.values())
    return list(players)


def _room_player_fc(player: Dict[str, Any]) -> Optional[str]:
    for key in ("fc", "friend_code", "friendcode"):
        fc = normalize_friend_code(str(player.get(key, "")))
        if fc:
            return fc
    return None


def _room_player_score(player: Dict[str, Any]) -> Optional[int]:
    for key in ("score", "total_score", "war_score", "points"):
        raw = player.get(key)
        if raw is None:
            continue
        if isinstance(raw, (int, float)):
            return int(raw)
        text = str(raw).strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return None


async def build_expected_fc_map(
    winner_war: Dict[str, Any],
    loser_war: Dict[str, Any],
) -> Tuple[Dict[int, str], List[str]]:
    """Map discord_id -> FC and list of players missing a link."""
    fc_by_discord: Dict[int, str] = {}
    missing: List[str] = []

    for war in (winner_war, loser_war):
        guild_id = war.get("origin_guild_id")
        for player in war.get("lineup", []):
            discord_id = player.get("discord_id")
            if not discord_id:
                missing.append(player.get("player", "Unknown player"))
                continue
            fc = await resolve_friend_code(int(discord_id), guild_id=guild_id)
            if not fc:
                missing.append(player.get("player", str(discord_id)))
                continue
            fc_by_discord[int(discord_id)] = fc
    return fc_by_discord, missing


def _match_lineup_scores(
    war: Dict[str, Any],
    fc_by_discord: Dict[int, str],
    room_by_fc: Dict[str, Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    ordered = sort_lineup_for_scores(war.get("lineup", []))
    players_out: List[Dict[str, Any]] = []
    penalties = 0

    for player in ordered:
        discord_id = player.get("discord_id")
        if not discord_id:
            return None, f"**{player.get('player', '?')}** has no Discord link on the roster."
        fc = fc_by_discord.get(int(discord_id))
        if not fc:
            return None, f"**{player.get('player', '?')}** has no linked friend code."
        fc_key = friend_code_key(fc)
        room_player = room_by_fc.get(fc_key or "")
        if not room_player:
            return None, (
                f"**{player.get('player', '?')}** (`{fc}`) was not found in the WiimmFI room."
            )
        score = _room_player_score(room_player)
        if score is None:
            return None, f"No score in room data for **{player.get('player', '?')}** (`{fc}`)."
        players_out.append(
            {
                "player": player.get("player"),
                "role": player.get("role"),
                "bagger": bool(player.get("bagger") or player.get("role") == "Bagger"),
                "discord_id": discord_id,
                "ally": bool(player.get("ally")),
                "score": score,
                "friend_code": fc,
            }
        )

    parsed = {"players": players_out, "penalties": penalties}
    return build_team_score_entry(war, parsed), None


async def build_scores_from_rxx(
    rxx: str,
    winner_war: Dict[str, Any],
    loser_war: Dict[str, Any],
    reported_margin: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Fetch room via Lounge API, match FCs to rosters, validate margin.
    Returns (table_reference, error_message).
    """
    try:
        room = await fetch_room_by_rxx(rxx)
    except LoungeAPIError as exc:
        return None, str(exc)

    room_players = _room_players(room)
    room_by_fc: Dict[str, Dict[str, Any]] = {}
    for row in room_players:
        fc = _room_player_fc(row)
        if not fc:
            continue
        key = friend_code_key(fc)
        if key:
            room_by_fc[key] = row

    if not room_by_fc:
        return None, f"Room `{rxx}` has no player friend codes."

    fc_by_discord, missing = await build_expected_fc_map(winner_war, loser_war)
    if missing:
        names = ", ".join(missing[:8])
        extra = f" (+{len(missing) - 8} more)" if len(missing) > 8 else ""
        return None, (
            f"Missing friend code links for: **{names}**{extra}. "
            "Players must run `/profile link` before completing."
        )

    mismatches, _verified = await verify_cached_fcs_against_wiimmfi(list(fc_by_discord.keys()))
    if mismatches:
        # Prefer lineup display names when available.
        name_by_id: Dict[int, str] = {}
        for war in (winner_war, loser_war):
            for player in war.get("lineup", []):
                if player.get("discord_id"):
                    name_by_id[int(player["discord_id"])] = player.get("player") or str(
                        player["discord_id"]
                    )
        parts = []
        for row in mismatches[:6]:
            name = name_by_id.get(row["discord_id"], row.get("player") or str(row["discord_id"]))
            parts.append(
                f"**{name}**: linked `{row['cached_fc']}` ≠ WiimmFI `{row['live_fc']}`"
            )
        extra = f" (+{len(mismatches) - 6} more)" if len(mismatches) > 6 else ""
        return None, (
            "Friend code mismatch — linked profiles don't match WiimmFI for this room:\n"
            + "\n".join(parts)
            + extra
            + "\nPlayers should re-run `/profile link` with the correct FC, then retry "
            "`/war complete` (or use manual `/war scores` fallback)."
        )

    winner_entry, winner_error = _match_lineup_scores(winner_war, fc_by_discord, room_by_fc)
    if winner_error:
        return None, winner_error
    loser_entry, loser_error = _match_lineup_scores(loser_war, fc_by_discord, room_by_fc)
    if loser_error:
        return None, loser_error

    ok, margin_error = validate_reported_margin(winner_entry, loser_entry, reported_margin)
    if not ok:
        return None, margin_error

    table_ref = build_table_reference_from_scores(winner_entry, loser_entry)
    table_ref["rxx"] = rxx
    table_ref["sync_method"] = "rxx"
    return table_ref, None


async def validate_rxx_margin(
    rxx: str,
    reported_margin: int,
    winner_war: Dict[str, Any],
    loser_war: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    table_ref, error = await build_scores_from_rxx(rxx, winner_war, loser_war, reported_margin)
    if error:
        return False, error
    if not table_ref:
        return False, "Could not validate RXX room scores."
    implied = score_implied_margin(
        table_ref["team_scores"]["winner"],
        table_ref["team_scores"]["loser"],
    )
    if implied != reported_margin:
        return False, (
            f"RXX room scores imply **{implied}** points, not **{reported_margin}**."
        )
    return True, None
