import interactions
from dotenv import load_dotenv
from interactions import Extension, Client, listen, Task, IntervalTrigger

from utils.billboard_store import load_wars
from utils.config import CT_CHANNEL_ID, RT_CHANNEL_ID
from utils.embeds import build_war_embed
from utils.guild_config import list_configured_billboard_channels
from utils.war_buttons import build_war_buttons

load_dotenv(".env.local")


def _collect_channel_ids(war_type: str) -> list[int]:
    """Hub env channels plus any per-guild configured billboard channels."""
    channel_ids = []
    hub_id = CT_CHANNEL_ID if war_type == "ct" else RT_CHANNEL_ID
    if hub_id:
        channel_ids.append(hub_id)

    for channel_id in list_configured_billboard_channels(war_type):
        if channel_id not in channel_ids:
            channel_ids.append(channel_id)

    return channel_ids


class PostWarBillboard(Extension):
    def __init__(self, bot: Client):
        self.bot = bot
        # war_id -> { "data": war_dict, "messages": { channel_id: message_id } }
        self.rt_wars = {}
        self.ct_wars = {}
        self.ready = False

    def _cache_for(self, war_type: str) -> dict:
        return self.ct_wars if war_type == "ct" else self.rt_wars

    def load_json(self, war_type: str):
        return [
            war for war in load_wars(war_type)
            if war.get("status") in ("open", "matched")
        ]

    @listen()
    async def on_startup(self):
        print("✅ Billboard system starting...")

        for war_type in ("rt", "ct"):
            cache = self._cache_for(war_type)
            for channel_id in _collect_channel_ids(war_type):
                await self.initial_sync(war_type, channel_id, cache)

        self.ready = True

        if not self.sync_billboards.running:
            self.sync_billboards.start()
            print("✅ Billboard diff-sync task running")

    async def initial_sync(self, war_type: str, channel_id: int, cache: dict):
        try:
            channel = await self.bot.fetch_channel(channel_id)
        except Exception as exc:
            print(f"❌ Cannot access channel {channel_id}: {exc}")
            return

        wars = self.load_json(war_type)

        for war in wars:
            war_id = war["war_id"]
            embed = build_war_embed(war)
            components = build_war_buttons(war)
            msg = await channel.send(embeds=embed, components=components)

            if war_id not in cache:
                cache[war_id] = {"data": war, "messages": {}}
            cache[war_id]["data"] = war
            cache[war_id]["messages"][channel_id] = msg.id

        print(f"✅ Initial {war_type.upper()} billboard synced for channel {channel_id}")

    @Task.create(IntervalTrigger(seconds=30))
    async def sync_billboards(self):
        for war_type in ("rt", "ct"):
            cache = self._cache_for(war_type)
            for channel_id in _collect_channel_ids(war_type):
                await self.sync_one(war_type, channel_id, cache)

    async def sync_one(self, war_type: str, channel_id: int, cache: dict):
        if not channel_id:
            return

        try:
            channel = await self.bot.fetch_channel(channel_id)
        except Exception as exc:
            print(f"❌ Cannot access channel {channel_id}: {exc}")
            return

        latest_wars = self.load_json(war_type)
        latest_by_id = {w["war_id"]: w for w in latest_wars}

        for war_id, war in latest_by_id.items():
            if war_id not in cache:
                embed = build_war_embed(war)
                components = build_war_buttons(war)
                msg = await channel.send(embeds=embed, components=components)
                cache[war_id] = {
                    "data": war,
                    "messages": {channel_id: msg.id},
                }
                print(f"🆕 New {war_type.upper()} war {war_id} in channel {channel_id}")
                continue

            old_data = cache[war_id]["data"]
            if war != old_data:
                try:
                    message_id = cache[war_id]["messages"].get(channel_id)
                    if message_id:
                        msg = await channel.fetch_message(message_id)
                        embed = build_war_embed(war)
                        components = build_war_buttons(war)
                        await msg.edit(embeds=embed, components=components)
                    else:
                        msg = await channel.send(
                            embeds=build_war_embed(war),
                            components=build_war_buttons(war),
                        )
                        cache[war_id]["messages"][channel_id] = msg.id

                    cache[war_id]["data"] = war
                    print(f"🔁 Updated {war_type.upper()} war {war_id} in channel {channel_id}")
                except Exception as exc:
                    print(f"❌ Failed to edit war {war_id}: {exc}")

        if self.ready:
            for war_id in list(cache.keys()):
                if war_id not in latest_by_id:
                    message_id = cache[war_id]["messages"].get(channel_id)
                    if message_id:
                        try:
                            msg = await channel.fetch_message(message_id)
                            await msg.delete()
                            print(f"❌ Deleted {war_type.upper()} war {war_id} from channel {channel_id}")
                        except Exception:
                            pass
                    cache[war_id]["messages"].pop(channel_id, None)
                    if not cache[war_id]["messages"]:
                        del cache[war_id]


def setup(bot: Client):
    PostWarBillboard(bot)
