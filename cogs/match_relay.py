import interactions
from interactions import Extension, listen
from interactions.api.events import MessageCreate

from utils.match_session_store import get_session_by_channel


class MatchRelay(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @listen(MessageCreate)
    async def relay_war_message(self, event: MessageCreate):
        message = event.message
        if not message or message.author.bot:
            return

        channel = message.channel
        if not channel:
            return
        channel_id = channel.id

        session = get_session_by_channel(channel_id)
        if not session:
            return

        if channel_id == session.get("channel_a_id"):
            peer_channel_id = session.get("channel_b_id")
            allowed_ids = set(int(x) for x in session.get("roster_a_ids", []))
        elif channel_id == session.get("channel_b_id"):
            peer_channel_id = session.get("channel_a_id")
            allowed_ids = set(int(x) for x in session.get("roster_b_ids", []))
        else:
            return

        if message.author.id not in allowed_ids:
            return

        if not peer_channel_id:
            return

        content = (message.content or "").strip()
        if not content and not message.attachments:
            return

        author_name = message.author.display_name or message.author.username
        embed = interactions.Embed(description=content or "*(attachment)*")
        embed.set_footer(text=author_name)

        try:
            peer = await self.bot.fetch_channel(peer_channel_id)
            await peer.send(embeds=embed)
        except Exception as exc:
            print(f"❌ Failed to relay war message: {exc}")


def setup(bot: interactions.Client):
    MatchRelay(bot)
