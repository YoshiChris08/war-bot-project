import interactions
from interactions import (
    Extension,
    SlashContext,
    slash_command,
    slash_option,
    OptionType,
    SlashCommandChoice,
)

from utils.colors import COLORS
from utils.config import SCOPES
from utils.embeds import build_how_to_use_embed, build_setup_embed
from utils.guild_config import delete_guild_config, get_guild_config, upsert_guild_config
from utils.interactions_helpers import build_war_bot_channel_overwrites, has_guild_admin


class ServerSetup(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @slash_command(
        name="setup",
        description="Configure War Bot billboard channels for this server.",
        scopes=SCOPES,
    )
    @slash_option(
        name="action",
        description="Setup action to perform.",
        required=True,
        opt_type=OptionType.STRING,
        choices=[
            SlashCommandChoice(name="Check current setup", value="check"),
            SlashCommandChoice(name="Link this channel as RT ranked", value="link_rt_ranked"),
            SlashCommandChoice(name="Link this channel as RT casual", value="link_rt_casual"),
            SlashCommandChoice(name="Link this channel as CT ranked", value="link_ct_ranked"),
            SlashCommandChoice(name="Link this channel as CT casual", value="link_ct_casual"),
            SlashCommandChoice(name="Link this channel as team queue", value="link_queue"),
            SlashCommandChoice(
                name="Create category (4 boards + queue + how-to-use)",
                value="create_category",
            ),
            SlashCommandChoice(name="Unlink setup", value="unlink"),
        ],
    )
    async def setup(self, ctx: SlashContext, action: str):
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.", ephemeral=True)
            return

        if not has_guild_admin(ctx):
            await ctx.send("You need **Administrator** permission to manage War Bot setup.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        guild_id = ctx.guild.id
        guild_name = ctx.guild.name
        existing = get_guild_config(guild_id)

        if action == "check":
            if not existing:
                embed = build_setup_embed(
                    guild_name,
                    None,
                    title="Setup not found",
                    description="War Bot is not configured in this server yet. Run `/setup` with a link or create option.",
                )
            else:
                embed = build_setup_embed(
                    guild_name,
                    existing,
                    title=f"Setup in {guild_name}",
                    description="These channels receive billboard posts for this server.",
                )
            await ctx.send(embeds=embed, ephemeral=True)
            return

        if action == "unlink":
            if not existing:
                await ctx.send("No setup found for this server.", ephemeral=True)
                return
            delete_guild_config(guild_id)
            embed = build_setup_embed(
                guild_name,
                None,
                title="Setup unlinked",
                description="War Bot will no longer use custom channels in this server. Hub env channels still apply globally.",
            )
            await ctx.send(embeds=embed, ephemeral=True)
            return

        link_actions = {
            "link_rt_ranked": {
                "fields": {"rt_ranked_channel_id": ctx.channel_id, "rt_channel_id": ctx.channel_id},
                "label": "RT ranked",
            },
            "link_rt_casual": {
                "fields": {"rt_casual_channel_id": ctx.channel_id},
                "label": "RT casual",
            },
            "link_ct_ranked": {
                "fields": {"ct_ranked_channel_id": ctx.channel_id, "ct_channel_id": ctx.channel_id},
                "label": "CT ranked",
            },
            "link_ct_casual": {
                "fields": {"ct_casual_channel_id": ctx.channel_id},
                "label": "CT casual",
            },
            "link_queue": {
                "fields": {"queue_channel_id": ctx.channel_id},
                "label": "Team queue",
            },
        }
        if action in link_actions:
            link = link_actions[action]
            upsert_guild_config(guild_id, guild_name, **link["fields"])
            config = get_guild_config(guild_id)
            embed = build_setup_embed(
                guild_name,
                config,
                title="Channel linked",
                description=f"{link['label']} will use {ctx.channel.mention}.",
            )
            await ctx.send(embeds=embed, ephemeral=True)
            return

        if action == "create_category":
            permission_overwrites = build_war_bot_channel_overwrites(ctx.guild)

            try:
                category = await ctx.guild.create_category(
                    name="War Bot",
                    permission_overwrites=permission_overwrites,
                    reason="War Bot setup",
                )
                how_to = await ctx.guild.create_text_channel(
                    name="how-to-use",
                    category=category,
                    topic="War Bot · guides and announcements",
                    permission_overwrites=permission_overwrites,
                    reason="War Bot setup",
                )
                rt_ranked = await ctx.guild.create_text_channel(
                    name="rt-ranked-wars",
                    category=category,
                    topic="War Bot · RT ranked billboard",
                    permission_overwrites=permission_overwrites,
                    reason="War Bot setup",
                )
                rt_casual = await ctx.guild.create_text_channel(
                    name="rt-casual-wars",
                    category=category,
                    topic="War Bot · RT casual billboard",
                    permission_overwrites=permission_overwrites,
                    reason="War Bot setup",
                )
                ct_ranked = await ctx.guild.create_text_channel(
                    name="ct-ranked-wars",
                    category=category,
                    topic="War Bot · CT ranked billboard",
                    permission_overwrites=permission_overwrites,
                    reason="War Bot setup",
                )
                ct_casual = await ctx.guild.create_text_channel(
                    name="ct-casual-wars",
                    category=category,
                    topic="War Bot · CT casual billboard",
                    permission_overwrites=permission_overwrites,
                    reason="War Bot setup",
                )
                queue_channel = await ctx.guild.create_text_channel(
                    name="team-queue",
                    category=category,
                    topic="War Bot · team queue lobby",
                    permission_overwrites=permission_overwrites,
                    reason="War Bot setup",
                )
            except interactions.errors.Forbidden:
                embed = interactions.Embed(
                    title="Setup failed",
                    description="I need **Manage Channels** permission to create the War Bot category.",
                    color=COLORS["error"],
                )
                await ctx.send(embeds=embed, ephemeral=True)
                return

            upsert_guild_config(
                guild_id,
                guild_name,
                category_id=category.id,
                how_to_use_channel_id=how_to.id,
                rt_ranked_channel_id=rt_ranked.id,
                rt_casual_channel_id=rt_casual.id,
                ct_ranked_channel_id=ct_ranked.id,
                ct_casual_channel_id=ct_casual.id,
                rt_channel_id=rt_ranked.id,
                ct_channel_id=ct_ranked.id,
                queue_channel_id=queue_channel.id,
            )

            try:
                await how_to.send(embeds=build_how_to_use_embed())
            except Exception as exc:
                print(f"⚠️ Could not post how-to guide in #{how_to.name}: {exc}")

            config = get_guild_config(guild_id)
            embed = build_setup_embed(
                guild_name,
                config,
                title="Setup complete",
                description=(
                    f"Created **War Bot** category with {how_to.mention}, {queue_channel.mention}, "
                    f"{rt_ranked.mention}, {rt_casual.mention}, {ct_ranked.mention}, and {ct_casual.mention}."
                ),
            )
            await ctx.send(embeds=embed, ephemeral=True)


def setup(bot: interactions.Client):
    ServerSetup(bot)
