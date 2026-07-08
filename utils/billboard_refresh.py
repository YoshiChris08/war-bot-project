from typing import Any, Dict

import interactions


def _billboard_cog(bot: interactions.Client):
    from cogs.post_war_billboard import PostWarBillboard

    for ext in bot.ext.values():
        if isinstance(ext, PostWarBillboard):
            return ext
    return None


async def refresh_war_billboard_posts(
    bot: interactions.Client,
    board: str,
    war: Dict[str, Any],
) -> None:
    cog = _billboard_cog(bot)
    if cog:
        await cog.refresh_war(board, war)


async def remove_war_from_billboards(
    bot: interactions.Client,
    board: str,
    war_id: str,
) -> None:
    cog = _billboard_cog(bot)
    if cog:
        await cog.remove_war(board, war_id)
