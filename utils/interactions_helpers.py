"""Helpers for discord-py-interactions (v5) APIs."""

from interactions import PermissionOverwrite, Permissions


def has_guild_admin(ctx) -> bool:
    """Return True when the interaction author has Administrator in this guild."""
    if not getattr(ctx, "guild", None):
        return False
    return Permissions.ADMINISTRATOR in ctx.author_permissions


def build_war_bot_channel_overwrites(guild) -> list[PermissionOverwrite]:
    """@everyone can read; only the bot can post in War Bot channels."""
    everyone = PermissionOverwrite.for_target(guild.default_role)
    everyone.add_allows(Permissions.VIEW_CHANNEL)
    everyone.add_denies(Permissions.SEND_MESSAGES)

    bot_overwrite = PermissionOverwrite.for_target(guild.me)
    bot_overwrite.add_allows(
        Permissions.VIEW_CHANNEL,
        Permissions.SEND_MESSAGES,
        Permissions.EMBED_LINKS,
        Permissions.MANAGE_MESSAGES,
    )
    return [everyone, bot_overwrite]
