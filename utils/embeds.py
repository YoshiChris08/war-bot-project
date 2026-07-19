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
            value=format_average_rank(lineup, war_type),
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
        description="MKWii 5v5 war matchmaking.",
        color=COLORS["default"],
    )
    embed.add_field(
        name="Quick start",
        value=(
            "1. Admin: `/team` then `/setup`\n"
            "2. Everyone: `/profile link` (Lounge auto-links or enter FC)\n"
            "3. Captain: `/queue start` → teammates join lobby → `/queue post`\n"
            "4. Hub: allies join or teams request a match\n"
            "5. Matched: talk in `war-vs-*`, finish with `/war complete` + RXX"
        ),
        inline=False,
    )
    embed.add_field(
        name="More detail",
        value="`/help queue` · `/help war` · `/help billboard` · `/help setup`",
        inline=False,
    )
    embed.set_footer(text="War Bot")
    return embed


def build_profile_embed(
    *,
    display_name: str,
    discord_id: int,
    avatar_url: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
    player: Optional[Dict[str, Any]] = None,
    team: Optional[Dict[str, Any]] = None,
    team_mmr: Optional[int] = None,
    recent: Optional[List[Dict[str, Any]]] = None,
) -> interactions.Embed:
    from utils.player_store import DEFAULT_PLAYER_MMR, get_player

    profile = profile or {}
    player = player or get_player(discord_id)
    ratings = player.get("ratings") or {}
    record = player.get("record") or {}

    lounge_name = profile.get("lounge_name")
    title_name = "Profile — " + (lounge_name if lounge_name else display_name)
    embed = interactions.Embed(
        title=f"{title_name}",
        description=(
            f"<@{discord_id}>"
            + (f" · Lounge **{lounge_name}**" if lounge_name else " · Not linked to Lounge")
        ),
        color=COLORS["default"],
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    fc = profile.get("friend_code") or "Not linked"
    source = profile.get("link_source")
    fc_line = f"`{fc}`"
    embed.add_field(name="Friend code", value=fc_line, inline=False)

    def _cell(track: str, role: str) -> str:
        mmr = int((ratings.get(track) or {}).get(role, DEFAULT_PLAYER_MMR))
        rec = (record.get(track) or {}).get(role) or {}
        w = int(rec.get("wins", 0))
        l = int(rec.get("losses", 0))
        return f"`{mmr:,}` · {w}W–{l}L"

    embed.add_field(
        name="RT ratings",
        value=(
            f"**Runner** {_cell('rt', 'runner')}\n"
            f"**Bagger** {_cell('rt', 'bagger')}"
        ),
        inline=True,
    )
    embed.add_field(
        name="CT ratings",
        value=(
            f"**Runner** {_cell('ct', 'runner')}\n"
            f"**Bagger** {_cell('ct', 'bagger')}"
        ),
        inline=True,
    )

    overall_w = int(player.get("wins", 0))
    overall_l = int(player.get("losses", 0))
    embed.add_field(
        name="Overall",
        value=f"**{overall_w}W – {overall_l}L**",
        inline=True,
    )

    if team:
        team_line = f"**{team.get('name', 'Unknown')}**"
        if team_mmr is not None:
            team_line += f"\nTeam MMR avg `~{team_mmr:,}`"
        embed.add_field(name="Team", value=team_line, inline=False)
    else:
        embed.add_field(
            name="Team",
            value="_No team registered in this server_",
            inline=False,
        )

    recent = recent or []
    if recent:
        lines = []
        for row in recent:
            outcome = row.get("player_outcome", "?")
            war_type = str(row.get("war_type", "RT")).upper()
            mode = str(row.get("mode", "ranked")).title()
            if outcome == "W":
                opponent = row.get("loser_team_name", "Unknown")
                sign = "+"
            else:
                opponent = row.get("winner_team_name", "Unknown")
                sign = "−"
            margin = row.get("point_margin", "?")
            entry = row.get("player_entry") or {}
            role = "Bag" if (entry.get("bagger") or entry.get("role") == "Bagger") else "Run"
            ally = " · ally" if entry.get("ally") else ""
            delta = (row.get("player_mmr_deltas") or {}).get(str(discord_id))
            delta_txt = f" · MMR `{delta:+d}`" if isinstance(delta, int) else ""
            lines.append(
                f"**{outcome}** {war_type} {mode} vs **{opponent}** "
                f"({sign}{margin}) · {role}{ally}{delta_txt}"
            )
        embed.add_field(name="Recent wars", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Recent wars", value="_No completed wars yet_", inline=False)

    embed.set_footer(text="War Bot · /profile link to update FC")
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
        embed.add_field(
            name="📊 Their team rank",
            value=format_average_rank(lineup, requester_war.get("war_type", "RT")),
            inline=False,
        )
    embed.set_footer(text="War Bot · Accept or decline below")
    return embed
