"""`/war` slash commands — use in `war-vs-*` match channels only."""

import interactions
from interactions import (
    Extension,
    SlashContext,
    slash_command,
    slash_option,
    OptionType,
    SlashCommandChoice,
)

from utils.config import SCOPES
from utils.match_queue_handlers import (
    handle_approve_cancel,
    handle_complete,
    handle_confirm,
    handle_decline_cancel,
    handle_dispute,
    handle_match_cancel,
    handle_submit_scores,
)
from utils.match_session_store import get_session_by_channel


class WarCommands(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    async def _require_war_channel(self, ctx: SlashContext) -> bool:
        if not get_session_by_channel(ctx.channel_id):
            await ctx.send("Use this in your **`war-vs-*`** match channel.", ephemeral=True)
            return False
        return True

    @slash_command(
        name="war",
        description="Match channel",
        sub_cmd_name="complete",
        sub_cmd_description="Captain reports the match result.",
        scopes=SCOPES,
    )
    @slash_option(
        name="outcome",
        description="Did your team win?",
        required=True,
        opt_type=OptionType.STRING,
        choices=[
            SlashCommandChoice(name="We won", value="won"),
            SlashCommandChoice(name="We lost", value="lost"),
        ],
    )
    async def war_complete(self, ctx: SlashContext, outcome: str):
        if not await self._require_war_channel(ctx):
            return
        await handle_complete(self.bot, ctx, reporter_won=(outcome == "won"))

    @slash_command(
        name="war",
        description="Match channel",
        sub_cmd_name="scores",
        sub_cmd_description="Captain submits scores (RXX fallback only).",
        scopes=SCOPES,
    )
    async def war_scores(self, ctx: SlashContext):
        if not await self._require_war_channel(ctx):
            return
        await handle_submit_scores(self.bot, ctx)

    @slash_command(
        name="war",
        description="Match channel",
        sub_cmd_name="confirm",
        sub_cmd_description="Captain confirms the reported result.",
        scopes=SCOPES,
    )
    async def war_confirm(self, ctx: SlashContext):
        if not await self._require_war_channel(ctx):
            return
        await handle_confirm(self.bot, ctx)

    @slash_command(
        name="war",
        description="Match channel",
        sub_cmd_name="dispute",
        sub_cmd_description="Captain disputes the reported result.",
        scopes=SCOPES,
    )
    async def war_dispute(self, ctx: SlashContext):
        if not await self._require_war_channel(ctx):
            return
        await handle_dispute(self.bot, ctx)

    @slash_command(
        name="war",
        description="Match channel",
        sub_cmd_name="cancel",
        sub_cmd_description="Captain requests to abort the match.",
        scopes=SCOPES,
    )
    async def war_cancel(self, ctx: SlashContext):
        if not await self._require_war_channel(ctx):
            return
        await handle_match_cancel(self.bot, ctx)

    @slash_command(
        name="war",
        description="Match channel",
        sub_cmd_name="approve-cancel",
        sub_cmd_description="Opponent approves a cancel request.",
        scopes=SCOPES,
    )
    async def war_approve_cancel(self, ctx: SlashContext):
        if not await self._require_war_channel(ctx):
            return
        await handle_approve_cancel(self.bot, ctx)

    @slash_command(
        name="war",
        description="Match channel",
        sub_cmd_name="decline-cancel",
        sub_cmd_description="Opponent declines a cancel request.",
        scopes=SCOPES,
    )
    async def war_decline_cancel(self, ctx: SlashContext):
        if not await self._require_war_channel(ctx):
            return
        await handle_decline_cancel(self.bot, ctx)


def setup(bot: interactions.Client):
    WarCommands(bot)
