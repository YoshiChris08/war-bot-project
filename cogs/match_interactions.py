import re

import interactions
from interactions import ComponentContext, Extension, component_callback

from utils.billboard_store import find_war
from utils.billboard_refresh import refresh_war_billboard_posts
from utils.guild_config import get_queue_channel_id
from utils.match_request_store import delete_request, get_request, upsert_request
from utils.match_service import create_war_comm_channels, finalize_match
from utils.queue_lobby import refresh_queue_lobby_message
from utils.queue_store import get_party


class MatchInteractions(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    async def _disable_notification(self, request: dict, note: str) -> None:
        channel_id = request.get("notification_channel_id")
        message_id = request.get("notification_message_id")
        if not channel_id or not message_id:
            return
        try:
            channel = await self.bot.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
            embed = message.embeds[0] if message.embeds else interactions.Embed(title="Match request")
            embed.description = f"{embed.description or ''}\n\n**{note}**"
            await message.edit(embeds=embed, components=[])
        except Exception:
            pass

    @component_callback(re.compile(r"^match_accept:(.+)$"))
    async def match_accept(self, ctx: ComponentContext):
        request_id = ctx.custom_id.split(":", 1)[1]
        request = get_request(request_id)
        if not request or request.get("status") != "pending":
            await ctx.send("This match request is no longer active.", ephemeral=True)
            return

        board = request["board"]
        target_war = find_war(board, request["target_war_id"])
        requester_war = find_war(board, request["requester_war_id"])
        if not target_war or not requester_war:
            await ctx.send("One of the war posts no longer exists.", ephemeral=True)
            delete_request(request_id)
            return

        if ctx.author.id != target_war.get("author_discord_id"):
            await ctx.send("Only the defending team's **captain** can accept this match.", ephemeral=True)
            return

        target_war, requester_war = finalize_match(board, target_war, requester_war)
        await refresh_war_billboard_posts(self.bot, board, target_war)
        await refresh_war_billboard_posts(self.bot, board, requester_war)

        session = await create_war_comm_channels(self.bot, board, target_war, requester_war)
        if not session:
            await ctx.send("Match accepted but failed to create war comm channels.", ephemeral=True)
            return

        request["status"] = "accepted"
        upsert_request(request)
        await self._disable_notification(request, f"Accepted by {ctx.author.display_name}.")

        for war in (target_war, requester_war):
            party_id = war.get("party_id")
            if party_id:
                party = get_party(party_id)
                if party:
                    await refresh_queue_lobby_message(self.bot, party)

        requester_channel = get_queue_channel_id(requester_war["origin_guild_id"])
        if requester_channel:
            try:
                ch = await self.bot.fetch_channel(requester_channel)
                await ch.send(
                    f"<@{requester_war['author_discord_id']}> — **{target_war.get('team_name')}** accepted your match! "
                    f"Use <#{session['channel_b_id']}> to coordinate."
                )
            except Exception:
                pass

        await ctx.send(
            f"Match confirmed vs **{requester_war.get('team_name')}**! "
            f"Your team channel: <#{session['channel_a_id']}>",
            ephemeral=True,
        )

    @component_callback(re.compile(r"^match_deny:(.+)$"))
    async def match_deny(self, ctx: ComponentContext):
        request_id = ctx.custom_id.split(":", 1)[1]
        request = get_request(request_id)
        if not request or request.get("status") != "pending":
            await ctx.send("This match request is no longer active.", ephemeral=True)
            return

        board = request["board"]
        target_war = find_war(board, request["target_war_id"])
        requester_war = find_war(board, request["requester_war_id"])
        if not target_war:
            await ctx.send("War post not found.", ephemeral=True)
            delete_request(request_id)
            return

        if ctx.author.id != target_war.get("author_discord_id"):
            await ctx.send("Only the defending team's **captain** can decline.", ephemeral=True)
            return

        request["status"] = "denied"
        upsert_request(request)
        delete_request(request_id)
        await self._disable_notification(request, f"Declined by {ctx.author.display_name}.")

        if requester_war:
            requester_channel = get_queue_channel_id(requester_war["origin_guild_id"])
            if requester_channel:
                try:
                    ch = await self.bot.fetch_channel(requester_channel)
                    await ch.send(
                        f"<@{requester_war['author_discord_id']}> — **{target_war.get('team_name')}** declined your match request."
                    )
                except Exception:
                    pass

        await ctx.send("Match request declined.", ephemeral=True)


def setup(bot: interactions.Client):
    MatchInteractions(bot)
