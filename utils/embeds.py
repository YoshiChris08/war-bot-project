from typing import Any, Dict, List, Optional

import interactions

from utils.colors import COLORS
from utils.roster import (
    SEARCH_ALLIES,
    SEARCH_OPPONENTS,
    can_seek_opponents,
    format_lineup,
    party_status_label,
    roster_summary,
    status_label,
)


def _track_color(war_type: str) -> int:
    return COLORS["ct"] if war_type.upper() == "CT" else COLORS["rt"]


def _embed_color(war: Dict[str, Any]) -> int:
    status = war.get("status", "open")
    search_mode = war.get("search_mode", SEARCH_ALLIES)
    lineup = war.get("lineup", [])

    if status == "matched":
        return COLORS["matched"]
    if search_mode == SEARCH_OPPONENTS and can_seek_opponents(lineup):
        return COLORS["opponents"]
    return COLORS["allies"]


def build_war_embed(war: Dict[str, Any]) -> interactions.Embed:
    war_type = war.get("war_type", "RT").upper()
    lineup = war.get("lineup", [])
    search_mode = war.get("search_mode", SEARCH_ALLIES)
    status = war.get("status", "open")
    label = status_label(search_mode, status, lineup)

    embed = interactions.Embed(
        title=f"{war.get('team_name', 'Unknown Team')} — {war_type} War",
        description=(
            f"**Status:** {label}\n"
            f"**Post ID:** `{war.get('war_id')}`"
            + (f"\n**Party ID:** `{war.get('party_id')}`" if war.get("party_id") else "")
        ),
        color=_embed_color(war),
    )

    embed.add_field(
        name="⏰ Search Time (ET)",
        value=f"`{war.get('start_time', 'ASAP')}`",
        inline=False,
    )

    embed.add_field(
        name="📋 Roster",
        value=roster_summary(lineup),
        inline=False,
    )

    embed.add_field(
        name=f"👥 Lineup ({len(lineup)}/5)",
        value=format_lineup(lineup),
        inline=False,
    )

    matched = war.get("matched_opponent")
    if matched and status == "matched":
        embed.add_field(
            name="⚔️ Opponent",
            value=(
                f"**{matched.get('team_name', 'Unknown')}**\n"
                f"Accepted by <@{matched.get('author_discord_id', '0')}>"
            ),
            inline=False,
        )

    if search_mode == SEARCH_ALLIES and not can_seek_opponents(lineup):
        embed.add_field(
            name="ℹ️ Allies needed",
            value=(
                "This post is **Looking For Allies**. Opponent search unlocks at "
                "**5/5** with **at least 1 bagger**."
            ),
            inline=False,
        )

    embed.set_footer(text="War Bot · Hub billboard")
    return embed


def build_queue_party_embed(party: Dict[str, Any]) -> interactions.Embed:
    war_type = party.get("war_type", "RT").upper()
    lineup = party.get("lineup", [])
    status = party.get("status", "preparing")
    label = party_status_label(status)

    embed = interactions.Embed(
        title=f"Queue Lobby — {party.get('team_name', 'Unknown Team')}",
        description=(
            f"**Stage:** {label}\n"
            f"**Track:** {war_type} · **Mode:** {party.get('mode', 'casual').title()}\n"
            f"**Party ID:** `{party.get('party_id')}`\n"
            f"**Invite code:** `{party.get('invite_code')}`"
        ),
        color=COLORS["waiting"] if status == "preparing" else COLORS["opponents"],
    )

    embed.add_field(
        name="⏰ Search Time (ET)",
        value=f"`{party.get('search_time', 'ASAP')}`",
        inline=False,
    )

    embed.add_field(
        name="📋 Roster",
        value=roster_summary(lineup),
        inline=False,
    )

    embed.add_field(
        name=f"👥 Team lineup ({len(lineup)}/5)",
        value=format_lineup(lineup),
        inline=False,
    )

    if status == "preparing":
        embed.add_field(
            name="ℹ️ Next step",
            value=(
                "Teammates from **this server** join here (1–5 players). "
                "Captain posts to the hub billboard when ready — requires **≥1 bagger**. "
                "Opponent search only unlocks at **5/5** with a bagger."
            ),
            inline=False,
        )
    elif status == "posted":
        embed.add_field(
            name="ℹ️ Hub status",
            value=f"Billboard post `{party.get('match_post_id')}` is live. Ally/opponent flow continues on the hub.",
            inline=False,
        )

    embed.set_footer(text="War Bot · Team server queue")
    return embed


def build_queue_status_embed(party: Dict[str, Any], post: Optional[Dict[str, Any]] = None) -> interactions.Embed:
    embed = build_queue_party_embed(party)
    embed.title = f"Your Queue — {party.get('team_name', 'Unknown Team')}"
    if post:
        embed.add_field(
            name="📌 Hub post",
            value=status_label(post.get("search_mode", "allies"), post.get("status", "open"), post.get("lineup", [])),
            inline=False,
        )
    return embed


def build_war_view_embed(war: Dict[str, Any], *, is_owner: bool) -> interactions.Embed:
    embed = build_war_embed(war)
    embed.title = f"Hub Post — {war.get('team_name', 'Unknown Team')}"
    if is_owner:
        embed.description = (
            f"{embed.description}\n\n"
            "Manage this post from the hub billboard buttons."
        )
    return embed


def build_setup_embed(
    guild_name: str,
    config: Optional[Dict[str, Any]],
    *,
    title: str,
    description: str,
    error: bool = False,
) -> interactions.Embed:
    embed = interactions.Embed(
        title=title,
        description=description,
        color=COLORS["error"] if error else COLORS["default"],
    )

    if config:
        embed.add_field(
            name="RT Wars Channel",
            value=f"<#{config['rt_channel_id']}>" if config.get("rt_channel_id") else "Not linked",
            inline=True,
        )
        embed.add_field(
            name="CT Wars Channel",
            value=f"<#{config['ct_channel_id']}>" if config.get("ct_channel_id") else "Not linked",
            inline=True,
        )
        embed.add_field(
            name="Team Queue Channel",
            value=f"<#{config['queue_channel_id']}>" if config.get("queue_channel_id") else "Not linked",
            inline=True,
        )
        if config.get("how_to_use_channel_id"):
            embed.add_field(
                name="How To Use",
                value=f"<#{config['how_to_use_channel_id']}>",
                inline=False,
            )
        if config.get("category_id"):
            embed.add_field(
                name="Category ID",
                value=f"`{config['category_id']}`",
                inline=False,
            )

    embed.set_footer(text=f"War Bot setup · {guild_name}")
    return embed
