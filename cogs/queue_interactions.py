import re
from typing import Optional

import interactions
from interactions import ComponentContext, Extension, component_callback

from classes.player import Player
from utils.billboard_refresh import refresh_war_billboard_posts
from utils.lineup_lock import find_blocking_lineup, lineup_lock_message
from utils.player_links import require_linked_fc
from utils.match_posting import sync_billboard_post_from_party
from utils.match_service import board_for_party
from utils.queue_lobby import refresh_queue_lobby_message
from utils.queue_service import cancel_party, post_party_to_billboard
from utils.queue_store import get_party, upsert_party
from utils.roster import PARTY_PREPARING, is_roster_full, team_queue_lobby_active


def _player_in_lineup(lineup: list, discord_id: int) -> bool:
    return any(entry.get("discord_id") == discord_id for entry in lineup)


class QueueInteractions(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    async def _refresh_lobby(self, party: dict) -> None:
        await refresh_queue_lobby_message(self.bot, party)

    @component_callback(re.compile(r"^queue_join_(runner|bagger):(.+)$"))
    async def queue_join(self, ctx: ComponentContext):
        match = re.match(r"^queue_join_(runner|bagger):(.+)$", ctx.custom_id)
        role_key = match.group(1)
        party_id = match.group(2)

        party = get_party(party_id)
        if not party or not team_queue_lobby_active(party):
            await ctx.send("This queue lobby is no longer open.", ephemeral=True)
            return

        if ctx.guild_id != party.get("guild_id"):
            await ctx.send("Only members of **this team's server** can join the queue lobby.", ephemeral=True)
            return

        if not await require_linked_fc(ctx, party.get("guild_id")):
            return

        lineup = party.get("lineup", [])
        if is_roster_full(lineup):
            await ctx.send("This queue is already full (5/5).", ephemeral=True)
            return

        if _player_in_lineup(lineup, ctx.author.id):
            await ctx.send("You are already in this queue.", ephemeral=True)
            return

        block = find_blocking_lineup(ctx.author.id, exclude_party_id=party_id)
        if block:
            await ctx.send(lineup_lock_message(block), ephemeral=True)
            return

        is_bagger = role_key == "bagger"
        role_name = "Bagger" if is_bagger else "Runner"
        lineup.append(
            Player(
                player=ctx.author.display_name,
                role=role_name,
                ally=False,
                bagger=is_bagger,
                discord_id=ctx.author.id,
            ).to_dict()
        )
        party["lineup"] = lineup
        upsert_party(party)
        if party.get("status") != PARTY_PREPARING:
            synced = sync_billboard_post_from_party(party)
            if synced:
                board, war = synced
                upsert_party(party)
                await refresh_war_billboard_posts(self.bot, board, war)
        await self._refresh_lobby(party)
        await ctx.send(f"You joined the queue as **{role_name}**.", ephemeral=True)

    @component_callback(re.compile(r"^queue_leave:(.+)$"))
    async def queue_leave(self, ctx: ComponentContext):
        party_id = ctx.custom_id.split(":", 1)[1]
        party = get_party(party_id)
        if not party or not team_queue_lobby_active(party):
            await ctx.send("This queue lobby is no longer open.", ephemeral=True)
            return

        if party.get("captain_discord_id") == ctx.author.id:
            await ctx.send("Captains must use **Cancel Queue** instead of leave.", ephemeral=True)
            return

        lineup = [p for p in party.get("lineup", []) if p.get("discord_id") != ctx.author.id]
        if len(lineup) == len(party.get("lineup", [])):
            await ctx.send("You are not in this queue.", ephemeral=True)
            return

        party["lineup"] = lineup
        upsert_party(party)
        if party.get("status") != PARTY_PREPARING:
            synced = sync_billboard_post_from_party(party)
            if synced:
                board, war = synced
                upsert_party(party)
                await refresh_war_billboard_posts(self.bot, board, war)
        await self._refresh_lobby(party)
        await ctx.send("You left the queue.", ephemeral=True)

    @component_callback(re.compile(r"^queue_post:(.+)$"))
    async def queue_post(self, ctx: ComponentContext):
        party_id = ctx.custom_id.split(":", 1)[1]
        party = get_party(party_id)
        if not party or party.get("status") != PARTY_PREPARING:
            await ctx.send("This queue is not ready to post.", ephemeral=True)
            return

        if ctx.author.id != party.get("captain_discord_id"):
            await ctx.send("Only the captain can post to the billboard.", ephemeral=True)
            return

        post, message = post_party_to_billboard(party)
        if not post:
            await ctx.send(message, ephemeral=True)
            return

        party = get_party(party_id)
        await refresh_war_billboard_posts(self.bot, board_for_party(party), post)
        await self._refresh_lobby(party)
        await ctx.send(f"{message}\n**Post ID:** `{post['war_id']}`", ephemeral=True)

    @component_callback(re.compile(r"^queue_cancel:(.+)$"))
    async def queue_cancel(self, ctx: ComponentContext):
        party_id = ctx.custom_id.split(":", 1)[1]
        party = get_party(party_id)
        if not party:
            await ctx.send("Queue not found.", ephemeral=True)
            return

        if ctx.author.id != party.get("captain_discord_id"):
            await ctx.send("Only the captain can cancel the queue.", ephemeral=True)
            return

        cancel_party(party_id)
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await ctx.send("Queue cancelled.", ephemeral=True)


def setup(bot: interactions.Client):
    QueueInteractions(bot)
