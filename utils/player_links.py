"""Resolve Discord users to Wii friend codes via Lounge API + local profiles."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from utils.lounge_api import (
    LoungeAPIError,
    fetch_host_friend_codes,
    lookup_lounge_player_by_discord,
    lookup_players_by_discord_ids,
)
from utils.player_profile_store import get_profile, has_linked_fc, upsert_profile
from utils.wiimmfi import friend_code_key, normalize_friend_code


def _fc_from_row(row: Dict[str, Any]) -> Optional[str]:
    for key in ("fc", "friend_code", "friendcode", "wiimmfi_fc"):
        fc = normalize_friend_code(str(row.get(key, "")))
        if fc:
            return fc
    return None


async def verify_cached_fcs_against_wiimmfi(
    discord_ids: List[int],
) -> Tuple[List[Dict[str, Any]], List[int]]:
    """
    Compare cached profile FCs to live WiimmFI/Lounge FCs (when available).

    Returns (mismatches, verified_ids).
    - mismatches: players whose live FC differs from the cached link
    - verified_ids: players whose live FC matched cache (eligible for upgrade)
    Non-Lounge / offline players with no live FC are skipped (not an error).
    """
    unique_ids = sorted({int(d) for d in discord_ids if d})
    if not unique_ids:
        return [], []

    try:
        rows = await lookup_players_by_discord_ids(unique_ids, lounge_verified_only=False)
    except LoungeAPIError:
        return [], []

    live_by_discord: Dict[int, str] = {}
    for row in rows:
        raw_id = row.get("discord_user_id") or row.get("discord_id")
        if raw_id is None:
            continue
        try:
            discord_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        fc = _fc_from_row(row)
        if fc:
            live_by_discord[discord_id] = fc

    mismatches: List[Dict[str, Any]] = []
    verified_ids: List[int] = []
    for discord_id in unique_ids:
        live_fc = live_by_discord.get(discord_id)
        if not live_fc:
            continue
        profile = get_profile(discord_id)
        cached = normalize_friend_code((profile or {}).get("friend_code", ""))
        if not cached:
            continue
        if friend_code_key(cached) != friend_code_key(live_fc):
            mismatches.append(
                {
                    "discord_id": discord_id,
                    "player": (profile or {}).get("lounge_name") or str(discord_id),
                    "cached_fc": cached,
                    "live_fc": live_fc,
                }
            )
            continue

        verified_ids.append(discord_id)
        fields: Dict[str, Any] = {
            "lounge_verified": True,
            "last_fc_verified_at": datetime.utcnow().isoformat(),
        }
        if (profile or {}).get("link_source") in ("manual", "lounge+manual", "hostfc"):
            fields["link_source"] = "lounge"
        upsert_profile(discord_id, **fields)

    return mismatches, verified_ids


async def try_lounge_link(discord_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    """
    Attempt automatic Lounge link by Discord ID.

    Returns (profile, lounge_player, error_message).
    - profile: fully linked when an FC was available from wiimmfi.php
    - lounge_player: player.php identity when Lounge account exists but FC still needed
    """
    lounge_player: Optional[Dict[str, Any]] = None
    wiimmfi_row: Optional[Dict[str, Any]] = None
    fc: Optional[str] = None

    player_result, wiimmfi_result = await asyncio.gather(
        lookup_lounge_player_by_discord(discord_id),
        lookup_players_by_discord_ids([discord_id], lounge_verified_only=False),
        return_exceptions=True,
    )

    if isinstance(player_result, LoungeAPIError):
        return None, None, str(player_result)
    if isinstance(player_result, Exception):
        return None, None, f"Lounge lookup failed: {player_result}"
    lounge_player = player_result

    if isinstance(wiimmfi_result, LoungeAPIError):
        pass
    elif isinstance(wiimmfi_result, Exception):
        pass
    elif wiimmfi_result:
        wiimmfi_row = wiimmfi_result[0]
        fc = _fc_from_row(wiimmfi_row)

    if not fc and not lounge_player:
        return None, None, None

    lounge_name = None
    lounge_player_id = None
    if lounge_player:
        lounge_name = lounge_player.get("player_name") or lounge_player.get("name")
        lounge_player_id = lounge_player.get("player_id")
    elif wiimmfi_row:
        lounge_name = wiimmfi_row.get("name") or wiimmfi_row.get("player_name")
        lounge_player_id = wiimmfi_row.get("player_id")

    if fc:
        profile = upsert_profile(
            discord_id,
            friend_code=fc,
            lounge_name=lounge_name,
            lounge_player_id=lounge_player_id,
            link_source="lounge",
            lounge_verified=bool(
                (wiimmfi_row or {}).get("lounge_verified")
                or (wiimmfi_row or {}).get("verified")
                or lounge_player
            ),
        )
        return profile, lounge_player, None

    return None, lounge_player, None


async def link_manual_friend_code(
    discord_id: int,
    raw_fc: str,
    *,
    lounge_player: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    fc = normalize_friend_code(raw_fc)
    if not fc:
        return None, "Invalid friend code. Use `XXXX-XXXX-XXXX`."

    fields: Dict[str, Any] = {
        "friend_code": fc,
        "link_source": "lounge+manual" if lounge_player else "manual",
        "lounge_verified": bool(lounge_player),
    }
    if lounge_player:
        fields["lounge_name"] = lounge_player.get("player_name") or lounge_player.get("name")
        fields["lounge_player_id"] = lounge_player.get("player_id")

    profile = upsert_profile(discord_id, **fields)
    return profile, None


async def resolve_friend_code(
    discord_id: int,
    *,
    guild_id: Optional[int] = None,
) -> Optional[str]:
    profile = get_profile(discord_id)
    if profile and profile.get("friend_code"):
        return profile["friend_code"]

    try:
        rows = await lookup_players_by_discord_ids([discord_id], lounge_verified_only=False)
        if rows:
            fc = _fc_from_row(rows[0])
            if fc:
                lounge_player = None
                try:
                    lounge_player = await lookup_lounge_player_by_discord(discord_id)
                except LoungeAPIError:
                    pass
                upsert_profile(
                    discord_id,
                    friend_code=fc,
                    lounge_name=(lounge_player or rows[0]).get("player_name")
                    or rows[0].get("name"),
                    lounge_player_id=(lounge_player or rows[0]).get("player_id"),
                    link_source="lounge",
                    lounge_verified=True,
                )
                return fc
    except LoungeAPIError:
        pass

    if guild_id:
        try:
            host_rows = await fetch_host_friend_codes(guild_id, [discord_id])
            if host_rows:
                fc = normalize_friend_code(host_rows[0].get("fc", ""))
                if fc:
                    upsert_profile(discord_id, friend_code=fc, link_source="hostfc")
                    return fc
        except LoungeAPIError:
            pass

    return None


async def lineup_missing_links(
    lineup: List[Dict[str, Any]],
    *,
    guild_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    missing = []
    for player in lineup or []:
        discord_id = player.get("discord_id")
        if not discord_id:
            continue
        fc = await resolve_friend_code(int(discord_id), guild_id=guild_id)
        if not fc:
            missing.append(player)
    return missing


async def require_linked_fc(ctx, guild_id: int | None = None) -> bool:
    """Return True if the user has a resolvable friend code."""
    if has_linked_fc(ctx.author.id):
        return True
    fc = await resolve_friend_code(ctx.author.id, guild_id=guild_id)
    if fc:
        return True
    await ctx.send(
        "Link your Wii friend code first with `/profile link` "
        "(Lounge accounts are detected automatically).",
        ephemeral=True,
    )
    return False
