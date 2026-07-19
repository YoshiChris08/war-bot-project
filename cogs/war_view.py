import interactions
from interactions import Extension, SlashContext, slash_command

from utils.billboard_store import find_post_by_party_id, load_wars
from utils.boards import ALL_BOARD_KEYS
from utils.config import SCOPES
from utils.embeds import build_queue_status_embed, build_war_view_embed
from utils.queue_store import get_active_party_for_user
from utils.war_buttons import build_war_buttons


def _find_author_post(author_id: int):
    for board in ALL_BOARD_KEYS:
        for war in load_wars(board):
            if war.get("author_discord_id") == author_id and war.get("status") in ("open", "matched"):
                return board, war
    return None


class WarView(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @slash_command(
        name="queue-status",
        description="View your team queue lobby and hub billboard post.",
        scopes=SCOPES,
    )
    async def queue_status(self, ctx: SlashContext):
        party = get_active_party_for_user(ctx.author.id)
        if not party:
            await ctx.send(
                "You are not in a queue. Use `/queue start` in your team server.",
                ephemeral=True,
            )
            return

        post = None
        if party.get("match_post_id"):
            found = find_post_by_party_id(party["party_id"])
            if found:
                _, post = found

        await ctx.send(embeds=build_queue_status_embed(party, post), ephemeral=True)

    @slash_command(
        name="war-view",
        description="View your hub billboard post (after posting from queue).",
        scopes=SCOPES,
    )
    async def war_view(self, ctx: SlashContext):
        found = _find_author_post(ctx.author.id)
        if not found:
            await ctx.send(
                "No hub post found. Form a queue with `/queue start`, then post to the billboard.",
                ephemeral=True,
            )
            return

        war_type, war = found
        embed = build_war_view_embed(war, is_owner=True)
        components = build_war_buttons(war)
        await ctx.send(embeds=embed, components=components, ephemeral=True)


def setup(bot: interactions.Client):
    WarView(bot)
