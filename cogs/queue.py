import interactions
from typing import Optional
from interactions import (
    Extension,
    Modal,
    ShortText,
    SlashContext,
    slash_command,
    slash_option,
    OptionType,
    SlashCommandChoice,
)

from classes.player import Player
from classes.queue_party import MODE_CASUAL, MODE_RANKED, PARTY_PREPARING, QueueParty
from utils.billboard_store import find_post_by_party_id
from utils.billboard_refresh import refresh_war_billboard_posts
from utils.config import SCOPES
from utils.embeds import build_queue_party_embed, build_queue_status_embed
from utils.guild_config import get_queue_channel_id
from utils.lineup_lock import find_blocking_lineup, lineup_lock_message
from utils.match_service import board_for_party
from utils.queue_lobby import refresh_queue_lobby_message
from utils.queue_service import cancel_party, post_party_to_billboard
from utils.queue_buttons import build_queue_party_buttons
from utils.queue_store import (
    get_active_party_for_guild,
    get_active_party_for_user,
    get_party,
    upsert_party,
)
from utils.search_time import parse_search_time
from utils.team_store import get_team_by_guild


def _parse_start_modal(kwargs: dict) -> tuple[Optional[dict], Optional[str]]:
    track = (kwargs.get("track") or "RT").strip().upper()
    if track not in ("RT", "CT"):
        return None, "Track must be **RT** or **CT**."

    role = (kwargs.get("role") or "runner").strip().lower()
    if role in ("bagger", "bag", "b"):
        is_bagger = True
    elif role in ("runner", "run", "r"):
        is_bagger = False
    else:
        return None, "Role must be **runner** or **bagger**."

    mode_raw = (kwargs.get("mode") or "ranked").strip().lower()
    if mode_raw in ("casual", "c"):
        mode = MODE_CASUAL
    elif mode_raw in ("ranked", "rank", "r", ""):
        mode = MODE_RANKED
    else:
        return None, "Mode must be **ranked** or **casual**."

    search_time_value, time_error = parse_search_time(kwargs.get("search_time"))
    if time_error:
        return None, time_error

    return {
        "track": track,
        "is_bagger": is_bagger,
        "mode": mode,
        "search_time": search_time_value,
    }, None


class QueueCommands(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    async def _refresh_lobby_message(self, party: dict) -> None:
        await refresh_queue_lobby_message(self.bot, party)

    def _require_team_server(self, ctx: SlashContext) -> tuple[dict, str] | tuple[None, None]:
        if not ctx.guild:
            return None, "Use this in your team's Discord server."
        team = get_team_by_guild(ctx.guild.id)
        if not team:
            return None, "Register this server with `/team` first."
        return team, ""

    @slash_command(
        name="queue",
        description="Team queue",
        sub_cmd_name="start",
        sub_cmd_description="Captain starts a lobby in #team-queue.",
        scopes=SCOPES,
    )
    async def queue_start(self, ctx: SlashContext):
        team, error = self._require_team_server(ctx)
        if error:
            await ctx.send(error, ephemeral=True)
            return

        if get_active_party_for_guild(ctx.guild.id):
            await ctx.send("This server already has an active queue. Use `/queue status`.", ephemeral=True)
            return

        block = find_blocking_lineup(ctx.author.id)
        if block:
            await ctx.send(lineup_lock_message(block), ephemeral=True)
            return

        modal = Modal(
            ShortText(
                label="Track (RT or CT)",
                custom_id="track",
                placeholder="RT",
                required=True,
                max_length=2,
            ),
            ShortText(
                label="Your role",
                custom_id="role",
                placeholder="runner or bagger",
                required=True,
                max_length=12,
            ),
            ShortText(
                label="Search time (ET)",
                custom_id="search_time",
                placeholder="ASAP",
                required=False,
                max_length=32,
            ),
            ShortText(
                label="Mode",
                custom_id="mode",
                placeholder="ranked or casual",
                required=False,
                max_length=8,
            ),
            title="Start queue",
        )
        await ctx.send_modal(modal)
        m_ctx = await self.bot.wait_for_modal(modal, ctx.author)

        parsed, parse_error = _parse_start_modal(m_ctx.kwargs)
        if parse_error:
            await m_ctx.send(parse_error, ephemeral=True)
            return

        if get_active_party_for_user(ctx.author.id):
            await m_ctx.send("You are already in a queue party.", ephemeral=True)
            return

        queue_channel_id = get_queue_channel_id(ctx.guild.id) or ctx.channel_id
        captain = Player(
            player=ctx.author.display_name,
            role="Bagger" if parsed["is_bagger"] else "Runner",
            ally=False,
            bagger=parsed["is_bagger"],
            discord_id=ctx.author.id,
        )

        party = QueueParty(
            team_id=team["team_id"],
            guild_id=ctx.guild.id,
            team_name=team["name"],
            war_type=parsed["track"],
            captain_discord_id=ctx.author.id,
            search_time=parsed["search_time"],
            mode=parsed["mode"],
            status=PARTY_PREPARING,
            lineup=[captain],
            lobby_channel_id=queue_channel_id,
        )
        party_dict = party.to_dict()

        channel = await self.bot.fetch_channel(queue_channel_id)
        message = await channel.send(
            embeds=build_queue_party_embed(party_dict),
            components=build_queue_party_buttons(party_dict),
        )
        party_dict["lobby_message_id"] = message.id
        upsert_party(party_dict)

        await m_ctx.send(
            f"Queue lobby created in <#{queue_channel_id}>.\n"
            "Teammates join via the lobby buttons.",
            ephemeral=True,
        )

    @slash_command(
        name="queue",
        description="Team queue",
        sub_cmd_name="post",
        sub_cmd_description="Captain posts the lobby to the hub billboard.",
        scopes=SCOPES,
    )
    @slash_option(
        name="looking_for",
        description="Allies (default) or opponents (5/5 + bagger)",
        required=False,
        opt_type=OptionType.STRING,
        choices=[
            SlashCommandChoice(name="Allies", value="allies"),
            SlashCommandChoice(name="Opponents", value="opponents"),
        ],
    )
    async def queue_post(self, ctx: SlashContext, looking_for: Optional[str] = None):
        _, error = self._require_team_server(ctx)
        if error:
            await ctx.send(error, ephemeral=True)
            return

        party = get_active_party_for_user(ctx.author.id)
        if not party or party.get("status") != PARTY_PREPARING:
            await ctx.send("Start a queue with `/queue start` first.", ephemeral=True)
            return
        if party.get("captain_discord_id") != ctx.author.id:
            await ctx.send("Only the captain can post.", ephemeral=True)
            return

        post, message = post_party_to_billboard(party, looking_for)
        if not post:
            await ctx.send(message, ephemeral=True)
            return

        party = get_party(party["party_id"])
        await refresh_war_billboard_posts(self.bot, board_for_party(party), post)
        await self._refresh_lobby_message(party)
        await ctx.send(f"{message}\n**Post ID:** `{post['war_id']}`", ephemeral=True)

    @slash_command(
        name="queue",
        description="Team queue",
        sub_cmd_name="status",
        sub_cmd_description="View your lobby and hub post.",
        scopes=SCOPES,
    )
    async def queue_status(self, ctx: SlashContext):
        party = get_active_party_for_user(ctx.author.id)
        if not party:
            await ctx.send("You are not in an active queue party.", ephemeral=True)
            return

        post = None
        if party.get("match_post_id"):
            found = find_post_by_party_id(party["party_id"])
            if found:
                _, post = found
        await ctx.send(embeds=build_queue_status_embed(party, post), ephemeral=True)

    @slash_command(
        name="queue",
        description="Team queue",
        sub_cmd_name="cancel",
        sub_cmd_description="Captain cancels the team queue.",
        scopes=SCOPES,
    )
    async def queue_cancel(self, ctx: SlashContext):
        party = get_active_party_for_user(ctx.author.id)
        if not party:
            await ctx.send("No active queue to cancel.", ephemeral=True)
            return
        if party.get("captain_discord_id") != ctx.author.id:
            await ctx.send("Only the captain can cancel.", ephemeral=True)
            return

        cancel_party(party["party_id"])
        if party.get("lobby_message_id") and party.get("lobby_channel_id"):
            try:
                channel = await self.bot.fetch_channel(party["lobby_channel_id"])
                message = await channel.fetch_message(party["lobby_message_id"])
                await message.delete()
            except Exception:
                pass
        await ctx.send("Queue cancelled.", ephemeral=True)


def setup(bot: interactions.Client):
    QueueCommands(bot)
