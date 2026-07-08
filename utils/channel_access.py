from typing import Any, Optional

import interactions


async def can_access_guild(bot: interactions.Client, guild_id: int) -> bool:
    if bot.get_guild(guild_id):
        return True
    try:
        await bot.fetch_guild(guild_id)
        return True
    except Exception:
        return False


async def fetch_accessible_channel(
    bot: interactions.Client,
    channel_id: int,
) -> Optional[Any]:
    try:
        channel = await bot.fetch_channel(channel_id)
    except Exception:
        return None
    if channel is None:
        return None
    return channel
