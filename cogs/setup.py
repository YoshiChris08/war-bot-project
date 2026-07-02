import interactions
from interactions import (
    Extension,
    SlashContext,
    slash_command,
    slash_option,
    OptionType,
    SlashCommandChoice,
    ChannelType,
)

from utils.colors import COLORS
from utils.config import SCOPES
from utils.embeds import build_setup_embed
from utils.guild_config import delete_guild_config, get_guild_config, upsert_guild_config


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
            SlashCommandChoice(name="Link this channel as RT wars", value="link_rt"),
            SlashCommandChoice(name="Link this channel as CT wars", value="link_ct"),
            SlashCommandChoice(name="Link this channel as team queue", value="link_queue"),
            SlashCommandChoice(name="Create category (RT, CT, queue, how-to-use)", value="create_category"),
            SlashCommandChoice(name="Unlink setup", value="unlink"),
        ],
    )
    async def setup(self, ctx: SlashContext, action: str):
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.", ephemeral=True)
            return

        member = ctx.author
        if not member or not getattr(member, "guild_permissions", None) or not member.guild_permissions.administrator:
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

        if action in ("link_rt", "link_ct", "link_queue"):
            if action == "link_rt":
                field, label = "rt_channel_id", "RT wars"
            elif action == "link_ct":
                field, label = "ct_channel_id", "CT wars"
            else:
                field, label = "queue_channel_id", "Team queue"
            upsert_guild_config(
                guild_id,
                guild_name,
                **{field: ctx.channel_id},
            )
            config = get_guild_config(guild_id)
            embed = build_setup_embed(
                guild_name,
                config,
                title="Channel linked",
                description=f"{label} will use {ctx.channel.mention}.",
            )
            await ctx.send(embeds=embed, ephemeral=True)
            return

        if action == "create_category":
            overwrites = {
                ctx.guild.default_role: interactions.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                ),
                ctx.guild.me: interactions.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    embed_links=True,
                    manage_messages=True,
                ),
            }

            try:
                category = await ctx.guild.create_category(
                    name="War Bot",
                    overwrites=overwrites,
                    reason="War Bot setup",
                )
                how_to = await ctx.guild.create_text_channel(
                    name="how-to-use",
                    category=category,
                    topic="War Bot · guides and announcements",
                    overwrites=overwrites,
                    reason="War Bot setup",
                )
                rt_channel = await ctx.guild.create_text_channel(
                    name="rt-wars",
                    category=category,
                    topic="War Bot · RT war billboard",
                    overwrites=overwrites,
                    reason="War Bot setup",
                )
                ct_channel = await ctx.guild.create_text_channel(
                    name="ct-wars",
                    category=category,
                    topic="War Bot · CT war billboard",
                    overwrites=overwrites,
                    reason="War Bot setup",
                )
                queue_channel = await ctx.guild.create_text_channel(
                    name="team-queue",
                    category=category,
                    topic="War Bot · team queue lobby",
                    overwrites=overwrites,
                    reason="War Bot setup",
                )
            except interactions.Forbidden:
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
                rt_channel_id=rt_channel.id,
                ct_channel_id=ct_channel.id,
                queue_channel_id=queue_channel.id,
            )
            config = get_guild_config(guild_id)
            embed = build_setup_embed(
                guild_name,
                config,
                title="Setup complete",
                description=(
                    f"Created **War Bot** category with {how_to.mention}, "
                    f"{queue_channel.mention}, {rt_channel.mention}, and {ct_channel.mention}."
                ),
            )
            await ctx.send(embeds=embed, ephemeral=True)


def setup(bot: interactions.Client):
    ServerSetup(bot)
