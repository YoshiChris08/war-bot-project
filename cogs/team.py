import interactions
from interactions import (
    Extension,
    SlashContext,
    slash_command,
    slash_option,
    OptionType,
    SlashCommandChoice,
)

from classes.team import Team
from utils.config import SCOPES
from utils.embeds import build_setup_embed
from utils.guild_config import get_guild_config
from utils.team_store import get_team_by_guild, upsert_team


class TeamRegister(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @slash_command(
        name="team",
        description="Register or view your MKWii team for this server.",
        scopes=SCOPES,
    )
    @slash_option(
        name="action",
        description="Team action.",
        required=True,
        opt_type=OptionType.STRING,
        choices=[
            SlashCommandChoice(name="Register team", value="register"),
            SlashCommandChoice(name="View team info", value="info"),
        ],
    )
    @slash_option(
        name="team_name",
        description="Display name for your team (register only).",
        required=False,
        opt_type=OptionType.STRING,
    )
    async def team(self, ctx: SlashContext, action: str, team_name: str = None):
        if not ctx.guild:
            await ctx.send("Register your team from your team's Discord server.", ephemeral=True)
            return

        if action == "info":
            team = get_team_by_guild(ctx.guild.id)
            if not team:
                await ctx.send(
                    "This server has no registered team. An admin can run `/team` → **Register team**.",
                    ephemeral=True,
                )
                return

            config = get_guild_config(ctx.guild.id)
            embed = interactions.Embed(
                title=team["name"],
                description=f"**Team ID:** `{team['team_id']}`",
                color=0x3498DB,
            )
            if config and config.get("queue_channel_id"):
                embed.add_field(name="Queue channel", value=f"<#{config['queue_channel_id']}>", inline=False)
            await ctx.send(embeds=embed, ephemeral=True)
            return

        member = ctx.author
        if not member.guild_permissions.administrator:
            await ctx.send("You need **Administrator** to register a team.", ephemeral=True)
            return

        name = team_name or ctx.guild.name
        team = Team(guild_id=ctx.guild.id, name=name)
        upsert_team(team.to_dict())

        embed = build_setup_embed(
            ctx.guild.name,
            get_guild_config(ctx.guild.id),
            title="Team registered",
            description=(
                f"**{name}** is registered.\n\n"
                "Next: `/setup` → link a **team queue** channel, then captains use `/queue start`."
            ),
        )
        await ctx.send(embeds=embed, ephemeral=True)


def setup(bot: interactions.Client):
    TeamRegister(bot)
