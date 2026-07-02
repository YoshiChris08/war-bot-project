import interactions
from typing import Optional
from interactions import (
    Extension,
    SlashContext,
    slash_command,
    slash_option,
    OptionType,
    SlashCommandChoice,
)

from classes.player import Player
from classes.queue_party import MODE_CASUAL, PARTY_PREPARING, QueueParty
from utils.billboard_store import find_post_by_party_id
from utils.config import SCOPES
from utils.embeds import build_queue_party_embed, build_queue_status_embed
from utils.guild_config import get_queue_channel_id
from utils.queue_service import post_party_to_billboard
from utils.queue_buttons import build_queue_party_buttons
from utils.queue_store import (
    delete_party,
    get_active_party_for_guild,
    get_active_party_for_user,
    get_party,
    upsert_party,
)
from utils.search_time import parse_search_time
from utils.team_store import get_team_by_guild


class QueueCommands(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    async def _refresh_lobby_message(self, party: dict) -> None:
        channel_id = party.get("lobby_channel_id")
        message_id = party.get("lobby_message_id")
        if not channel_id or not message_id:
            return
        try:
            channel = await self.bot.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
            await message.edit(
                embeds=build_queue_party_embed(party),
                components=build_queue_party_buttons(party),
            )
        except Exception as exc:
            print(f"❌ Failed to refresh queue lobby: {exc}")

    @slash_command(
        name="queue",
        description="Form a team queue in this server, then post to the hub billboard.",
        scopes=SCOPES,
    )
    @slash_option(
        name="action",
        description="Queue action.",
        required=True,
        opt_type=OptionType.STRING,
        choices=[
            SlashCommandChoice(name="Start queue (captain)", value="start"),
            SlashCommandChoice(name="Post to hub billboard", value="post"),
            SlashCommandChoice(name="View queue status", value="status"),
            SlashCommandChoice(name="Cancel queue", value="cancel"),
        ],
    )
    @slash_option(
        name="track_type",
        description="RT or CT (start/post).",
        required=False,
        opt_type=OptionType.STRING,
        choices=[
            SlashCommandChoice(name="RT", value="RT"),
            SlashCommandChoice(name="CT", value="CT"),
        ],
    )
    @slash_option(
        name="search_time",
        description="Search time in ET (start). Defaults to ASAP.",
        required=False,
        opt_type=OptionType.STRING,
    )
    @slash_option(
        name="is_bagger",
        description="Whether you are a bagger (start).",
        required=False,
        opt_type=OptionType.BOOLEAN,
    )
    @slash_option(
        name="looking_for",
        description="Hub post mode (post). Opponents requires 5/5 + bagger.",
        required=False,
        opt_type=OptionType.STRING,
        choices=[
            SlashCommandChoice(name="Looking For Allies", value="allies"),
            SlashCommandChoice(name="Looking For Opponents", value="opponents"),
        ],
    )
    async def queue(
        self,
        ctx: SlashContext,
        action: str,
        track_type: Optional[str] = None,
        search_time: Optional[str] = None,
        is_bagger: Optional[bool] = None,
        looking_for: Optional[str] = None,
    ):
        if not ctx.guild:
            await ctx.send("Queue commands must be used in your team's Discord server.", ephemeral=True)
            return

        team = get_team_by_guild(ctx.guild.id)
        if not team:
            await ctx.send("Register this server with `/team` → **Register team** first.", ephemeral=True)
            return

        if action == "status":
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
            return

        if action == "cancel":
            party = get_active_party_for_user(ctx.author.id)
            if not party:
                await ctx.send("No active queue to cancel.", ephemeral=True)
                return
            if party.get("captain_discord_id") != ctx.author.id:
                await ctx.send("Only the queue captain can cancel.", ephemeral=True)
                return
            delete_party(party["party_id"])
            if party.get("lobby_message_id") and party.get("lobby_channel_id"):
                try:
                    channel = await self.bot.fetch_channel(party["lobby_channel_id"])
                    message = await channel.fetch_message(party["lobby_message_id"])
                    await message.delete()
                except Exception:
                    pass
            await ctx.send("Queue cancelled.", ephemeral=True)
            return

        if action == "post":
            party = get_active_party_for_user(ctx.author.id)
            if not party or party.get("status") != PARTY_PREPARING:
                await ctx.send("Start a queue with `/queue` → **Start queue** first.", ephemeral=True)
                return
            if party.get("captain_discord_id") != ctx.author.id:
                await ctx.send("Only the captain can post to the billboard.", ephemeral=True)
                return

            post, message = post_party_to_billboard(party, looking_for)
            if not post:
                await ctx.send(message, ephemeral=True)
                return

            party = get_party(party["party_id"])
            await self._refresh_lobby_message(party)
            await ctx.send(f"{message}\n**Post ID:** `{post['war_id']}`", ephemeral=True)
            return

        if action == "start":
            if get_active_party_for_guild(ctx.guild.id):
                await ctx.send("This server already has an active queue. Use `/queue` → **View queue status**.", ephemeral=True)
                return
            if get_active_party_for_user(ctx.author.id):
                await ctx.send("You are already in a queue party.", ephemeral=True)
                return

            queue_channel_id = get_queue_channel_id(ctx.guild.id) or ctx.channel_id
            search_time_value, error = parse_search_time(search_time)
            if error:
                await ctx.send(error, ephemeral=True)
                return

            captain = Player(
                player=ctx.author.display_name,
                role="Bagger" if is_bagger else "Runner",
                ally=False,
                bagger=bool(is_bagger),
                discord_id=ctx.author.id,
            )

            party = QueueParty(
                team_id=team["team_id"],
                guild_id=ctx.guild.id,
                team_name=team["name"],
                war_type=(track_type or "RT").upper(),
                captain_discord_id=ctx.author.id,
                search_time=search_time_value,
                mode=MODE_CASUAL,
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

            await ctx.send(
                f"Queue lobby created in <#{queue_channel_id}>.\n"
                f"**Invite code:** `{party_dict['invite_code']}`\n"
                f"Teammates can join via the lobby buttons (1–5 players, same server).",
                ephemeral=True,
            )


def setup(bot: interactions.Client):
    QueueCommands(bot)
