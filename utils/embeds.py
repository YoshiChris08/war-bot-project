from typing import Any, Dict, List, Optional

import interactions

from utils.colors import COLORS
from utils.mmr import format_average_rank
from classes.queue_party import MODE_CASUAL
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
    mode = war.get("mode", "ranked")
    label = status_label(search_mode, status, lineup)

    embed = interactions.Embed(
        title=f"{war.get('team_name', 'Unknown Team')} — {war_type} · {mode.title()}",
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

    if mode == MODE_CASUAL:
        embed.add_field(
            name=f"👥 Lineup ({len(lineup)}/5)",
            value=format_lineup(lineup),
            inline=False,
        )
    else:
        embed.add_field(
            name="📊 Team rank",
            value=format_average_rank(lineup),
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
            f"**Track:** {war_type} · **Mode:** {party.get('mode', 'ranked').title()}\n"
            f"**Party ID:** `{party.get('party_id')}`"
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
            value=(
                f"Billboard post `{party.get('match_post_id')}` is live. "
                "Teammates can still join here while you look for allies on the hub."
            ),
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
            name="RT Ranked",
            value=f"<#{config['rt_ranked_channel_id']}>" if config.get("rt_ranked_channel_id") else "Not linked",
            inline=True,
        )
        embed.add_field(
            name="RT Casual",
            value=f"<#{config['rt_casual_channel_id']}>" if config.get("rt_casual_channel_id") else "Not linked",
            inline=True,
        )
        embed.add_field(
            name="CT Ranked",
            value=f"<#{config['ct_ranked_channel_id']}>" if config.get("ct_ranked_channel_id") else "Not linked",
            inline=True,
        )
        embed.add_field(
            name="CT Casual",
            value=f"<#{config['ct_casual_channel_id']}>" if config.get("ct_casual_channel_id") else "Not linked",
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


def build_how_to_use_embed() -> interactions.Embed:
    embed = interactions.Embed(
        title="How to use War Bot",
        description="MKWii 5v5 war matchmaking — team queue → hub billboard.",
        color=COLORS["default"],
    )
    embed.add_field(
        name="1 · One-time server setup (admin)",
        value=(
            "• `/team` → **Register team** — links this Discord to your team\n"
            "• `/setup` → **Create category** — makes RT/CT billboards + team queue channels\n"
            "• Or use `/setup` → **Link …** to point at existing channels"
        ),
        inline=False,
    )
    embed.add_field(
        name="2 · Start a war search (captain)",
        value=(
            "• `/queue` → **Start queue** — pick RT or CT; **ranked by default**, choose casual if needed\n"
            "• A lobby posts in **team-queue** — teammates click **Join as Runner** / **Join as Bagger**\n"
            "• Need **at least 1 bagger** before posting to the hub"
        ),
        inline=False,
    )
    embed.add_field(
        name="3 · Hub billboard",
        value=(
            "• Captain uses **Post to Billboard** (or `/queue` → **Post to hub billboard**)\n"
            "• **Looking For Allies** — fill toward 5/5; teammates can still join in team-queue\n"
            "• **Looking For Opponents** — only when **5/5** with a bagger; other teams **Request Match** (you accept)\n"
            "• After accept: use **`/queue` in the `war-vs-*` channel** — `complete`, `submit-scores`, `confirm`, `cancel-match`\n"
            "• Score line: `p1 p2 p3 p4 bagger penalties` (space separated; penalties optional)\n"
            "• **Ranked:** rt-ranked-wars / ct-ranked-wars (default)\n"
            "• **Casual:** rt-casual-wars / ct-casual-wars"
        ),
        inline=False,
    )
    embed.add_field(
        name="4 · Useful commands",
        value=(
            "• `/queue-status` — your lobby + hub post\n"
            "• `/war-view` — your billboard post\n"
            "• `/team` → **View team info**"
        ),
        inline=False,
    )
    embed.set_footer(text="War Bot · Questions? Ask your server admin.")
    return embed


def build_match_request_embed(requester_war: Dict[str, Any]) -> interactions.Embed:
    mode = requester_war.get("mode", "ranked")
    lineup = requester_war.get("lineup", [])
    embed = interactions.Embed(
        title=f"⚔️ Match request — {requester_war.get('team_name', 'Unknown Team')}",
        description=(
            f"**{requester_war.get('team_name')}** wants to war your team.\n"
            f"**Track:** {requester_war.get('war_type', 'RT')} · **Mode:** {mode.title()}\n"
            f"**Search time:** `{requester_war.get('start_time', 'ASAP')}`"
        ),
        color=COLORS["opponents"],
    )
    if mode == MODE_CASUAL:
        embed.add_field(name="👥 Their lineup", value=format_lineup(lineup), inline=False)
    else:
        embed.add_field(name="📊 Their team rank", value=format_average_rank(lineup), inline=False)
    embed.set_footer(text="War Bot · Accept or decline below")
    return embed
