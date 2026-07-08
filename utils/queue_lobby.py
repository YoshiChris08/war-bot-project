"""Refresh the team-server queue lobby Discord message."""

from utils.embeds import build_queue_party_embed
from utils.queue_buttons import build_queue_party_buttons


async def refresh_queue_lobby_message(bot, party: dict) -> None:
    channel_id = party.get("lobby_channel_id")
    message_id = party.get("lobby_message_id")
    if not channel_id or not message_id:
        return

    try:
        channel = await bot.fetch_channel(channel_id)
        message = await channel.fetch_message(message_id)
        await message.edit(
            embeds=build_queue_party_embed(party),
            components=build_queue_party_buttons(party),
        )
    except Exception as exc:
        print(f"❌ Failed to refresh queue lobby: {exc}")
