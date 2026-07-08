import re
from typing import Any, Dict, List, Optional

import interactions
from interactions import PermissionOverwrite, Permissions

from utils.billboard_store import upsert_war
from utils.boards import board_key as board_for_war
from utils.guild_config import get_guild_config
from utils.match_request_store import create_request, pending_for_target_war
from utils.match_session_store import create_session
from utils.mmr import team_roster_players
from utils.match_posting import sync_party_lineup_from_post
from utils.queue_store import get_party, upsert_party
from datetime import datetime


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:20] or "team"


def roster_member_ids(war: Dict[str, Any]) -> List[int]:
    ids = []
    for player in team_roster_players(war.get("lineup", [])):
        discord_id = player.get("discord_id")
        if discord_id and int(discord_id) not in ids:
            ids.append(int(discord_id))
    return ids


def _touch_war(war: Dict[str, Any]) -> Dict[str, Any]:
    war["last_updated"] = datetime.utcnow().isoformat()
    war["ally_count"] = sum(1 for player in war.get("lineup", []) if player.get("ally"))
    return war


def _sync_parties(board: str, war_a: Dict[str, Any], war_b: Dict[str, Any]) -> None:
    for war in (war_a, war_b):
        party_id = war.get("party_id")
        if not party_id:
            continue
        party = get_party(party_id)
        if party:
            upsert_party(sync_party_lineup_from_post(party, war))


def finalize_match(board: str, target_war: Dict[str, Any], requester_war: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    target_war["status"] = "matched"
    target_war["matched_opponent"] = {
        "war_id": requester_war.get("war_id"),
        "team_name": requester_war.get("team_name"),
        "author_discord_id": requester_war.get("author_discord_id"),
    }
    requester_war["status"] = "matched"
    requester_war["matched_opponent"] = {
        "war_id": target_war.get("war_id"),
        "team_name": target_war.get("team_name"),
        "author_discord_id": target_war.get("author_discord_id"),
    }
    target_war = _touch_war(target_war)
    requester_war = _touch_war(requester_war)
    upsert_war(board, target_war)
    upsert_war(board, requester_war)
    _sync_parties(board, target_war, requester_war)
    return target_war, requester_war


async def _channel_overwrites(guild, member_ids: List[int]) -> List[PermissionOverwrite]:
    everyone = PermissionOverwrite.for_target(guild.default_role)
    everyone.add_denies(Permissions.VIEW_CHANNEL)

    bot = PermissionOverwrite.for_target(guild.me)
    bot.add_allows(
        Permissions.VIEW_CHANNEL,
        Permissions.SEND_MESSAGES,
        Permissions.EMBED_LINKS,
        Permissions.READ_MESSAGE_HISTORY,
        Permissions.MANAGE_CHANNELS,
    )

    overwrites = [everyone, bot]
    for member_id in member_ids:
        try:
            member = guild.get_member(member_id) or await guild.fetch_member(member_id)
        except Exception:
            continue
        overwrite = PermissionOverwrite.for_target(member)
        overwrite.add_allows(
            Permissions.VIEW_CHANNEL,
            Permissions.SEND_MESSAGES,
            Permissions.READ_MESSAGE_HISTORY,
        )
        overwrites.append(overwrite)
    return overwrites


async def create_war_comm_channels(
    bot: interactions.Client,
    board: str,
    target_war: Dict[str, Any],
    requester_war: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    roster_a = roster_member_ids(target_war)
    roster_b = roster_member_ids(requester_war)
    if not roster_a or not roster_b:
        return None

    guild_a = await bot.fetch_guild(int(target_war["origin_guild_id"]))
    guild_b = await bot.fetch_guild(int(requester_war["origin_guild_id"]))
    config_a = get_guild_config(guild_a.id) or {}
    config_b = get_guild_config(guild_b.id) or {}
    category_a = config_a.get("category_id")
    category_b = config_b.get("category_id")

    short = target_war.get("war_id", "")[:6]
    channel_a = await guild_a.create_text_channel(
        name=f"war-vs-{_slug(requester_war.get('team_name', 'team'))}-{short}",
        category=category_a,
        permission_overwrites=await _channel_overwrites(guild_a, roster_a),
        topic=f"War comms vs {requester_war.get('team_name')} — messages relay to their server",
    )
    channel_b = await guild_b.create_text_channel(
        name=f"war-vs-{_slug(target_war.get('team_name', 'team'))}-{short}",
        category=category_b,
        permission_overwrites=await _channel_overwrites(guild_b, roster_b),
        topic=f"War comms vs {target_war.get('team_name')} — messages relay to their server",
    )

    intro_a = (
        f"**Match confirmed** vs **{requester_war.get('team_name')}**.\n"
        "Chat here — messages relay to the other team's war channel.\n\n"
        "**Captain commands (this channel only):**\n"
        "• `/queue complete` + `outcome:won` or `lost` — finish the match\n"
        "• `/queue submit-scores` — submit your team's score line (if no RXX)\n"
        "• `/queue confirm` / `/queue dispute` — both captains confirm the result\n"
        "• `/queue cancel-match` — request to abort (other captain approves)"
    )
    intro_b = (
        f"**Match confirmed** vs **{target_war.get('team_name')}**.\n"
        "Chat here — messages relay to the other team's war channel.\n\n"
        "**Captain commands (this channel only):**\n"
        "• `/queue complete` + `outcome:won` or `lost` — finish the match\n"
        "• `/queue submit-scores` — submit your team's score line (if no RXX)\n"
        "• `/queue confirm` / `/queue dispute` — both captains confirm the result\n"
        "• `/queue cancel-match` — request to abort (other captain approves)"
    )
    await channel_a.send(intro_a)
    await channel_b.send(intro_b)

    return create_session(
        board,
        target_war,
        requester_war,
        channel_a.id,
        channel_b.id,
        roster_a,
        roster_b,
    )


def start_match_request(board: str, target_war_id: str, requester_war_id: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    if pending_for_target_war(target_war_id):
        return None, "This team already has a pending match request."
    request = create_request(board, target_war_id, requester_war_id)
    return request, None


def board_for_party(party: Dict[str, Any]) -> str:
    return board_for_war(party.get("war_type", "RT"), party.get("mode", "ranked"))
