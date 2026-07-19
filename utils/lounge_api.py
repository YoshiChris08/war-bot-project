"""HTTP client for MKW Lounge API (https://github.com/255MP/mkw-api-docs)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp

LOUNGE_API_BASE = os.getenv("LOUNGE_API_BASE", "https://www.mkwlounge.gg/api").rstrip("/")
PLAYER_ENDPOINT = f"{LOUNGE_API_BASE}/player.php"
WIIMMFI_ENDPOINT = f"{LOUNGE_API_BASE}/wiimmfi.php"
HOSTFC_ENDPOINT = f"{LOUNGE_API_BASE}/hostfc.php"

_api_key: Optional[str] = None
_session: Optional[aiohttp.ClientSession] = None
_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)


def set_lounge_api_key(key: Optional[str]) -> None:
    global _api_key
    _api_key = (key or "").strip() or None


def get_lounge_api_key() -> Optional[str]:
    return _api_key or os.getenv("LOUNGE_API_KEY", "").strip() or None


def _require_api_key() -> str:
    key = get_lounge_api_key()
    if not key:
        raise LoungeAPIError("Lounge API key is not configured (set LOUNGE_API_KEY or GCP secret lounge_api_key).")
    return key


class LoungeAPIError(Exception):
    pass


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=_DEFAULT_TIMEOUT)
    return _session


async def close_lounge_api() -> None:
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
    _session = None


async def _get_json(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    query = {k: v for k, v in params.items() if v is not None}
    url = f"{endpoint}?{urlencode(query)}"
    session = _get_session()
    try:
        async with session.get(url) as response:
            text = await response.text()
            if response.status != 200:
                raise LoungeAPIError(f"Lounge API HTTP {response.status}: {text[:200]}")
            try:
                data = await response.json(content_type=None)
            except Exception as exc:
                raise LoungeAPIError(f"Invalid Lounge API JSON: {exc}") from exc
    except aiohttp.ClientError as exc:
        raise LoungeAPIError(f"Lounge API request failed: {exc}") from exc

    if not isinstance(data, dict):
        raise LoungeAPIError("Lounge API returned unexpected payload.")
    if data.get("status") != "success":
        reason = data.get("reason") or data.get("message") or "unknown error"
        raise LoungeAPIError(f"Lounge API error: {reason}")
    return data


def _comma_join(values: List[Any]) -> str:
    return ",".join(str(v) for v in values if v is not None)


def _extract_fc(row: Dict[str, Any]) -> Optional[str]:
    for key in ("fc", "friend_code", "friendcode", "wiimmfi_fc"):
        raw = row.get(key)
        if raw:
            return str(raw)
    return None


async def lookup_lounge_player_by_discord(discord_id: int) -> Optional[Dict[str, Any]]:
    """
    Resolve Lounge identity via player.php (discord_user_id).
    Returns player_id / player_name / discord_user_id — typically no FC.
    """
    data = await _get_json(
        PLAYER_ENDPOINT,
        {
            "code": _require_api_key(),
            "discord_user_id": str(discord_id),
        },
    )
    results = data.get("results") or []
    return results[0] if results else None


async def lookup_players_by_discord_ids(
    discord_ids: List[int],
    *,
    lounge_verified_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    WiimmFI FC lookup via wiimmfi.php (discord_user_ids).
    Often empty even when player.php finds a Lounge account.
    """
    if not discord_ids:
        return []
    data = await _get_json(
        WIIMMFI_ENDPOINT,
        {
            "code": _require_api_key(),
            "discord_user_ids": _comma_join(discord_ids),
        },
    )
    results = data.get("results") or []
    if not lounge_verified_only:
        return results
    return [row for row in results if row.get("lounge_verified") or row.get("verified")]


async def lookup_players_by_friend_codes(fcs: List[str]) -> List[Dict[str, Any]]:
    if not fcs:
        return []
    data = await _get_json(
        WIIMMFI_ENDPOINT,
        {
            "code": _require_api_key(),
            "fcs": _comma_join(fcs),
        },
    )
    return data.get("results") or []


async def fetch_host_friend_codes(guild_id: int, discord_ids: List[int]) -> List[Dict[str, Any]]:
    """GET hostfc.php — no API key required per docs."""
    if not discord_ids:
        return []
    data = await _get_json(
        HOSTFC_ENDPOINT,
        {
            "discord_guild_id": guild_id,
            "discord_user_id": _comma_join(discord_ids),
        },
    )
    return data.get("results") or []


async def fetch_room_by_rxx(rxx: str) -> Dict[str, Any]:
    """
    Fetch WiimmFI room data for an RXX code via Lounge API.
    Expected: results with player rows containing at least `fc` and `score`.
    """
    data = await _get_json(
        WIIMMFI_ENDPOINT,
        {
            "code": _require_api_key(),
            "rxx": rxx,
        },
    )
    results = data.get("results")
    if isinstance(results, list) and results:
        if len(results) == 1 and isinstance(results[0], dict) and results[0].get("players"):
            return results[0]
        if all(isinstance(row, dict) and (_extract_fc(row) or row.get("fc")) for row in results):
            return {"rxx": rxx, "players": results}
    if isinstance(results, dict):
        return results
    raise LoungeAPIError(f"No room data returned for `{rxx}`.")
