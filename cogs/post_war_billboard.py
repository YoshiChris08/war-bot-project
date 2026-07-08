import interactions
from dotenv import load_dotenv
from interactions import Extension, Client, listen, Task, IntervalTrigger

from utils.billboard_store import load_wars
from utils.boards import ALL_BOARD_KEYS
from utils.channel_access import can_access_guild, fetch_accessible_channel
from utils.embeds import build_war_embed
from utils.guild_config import list_billboard_channel_targets
from utils.war_buttons import build_war_buttons

load_dotenv(".env.local")


class PostWarBillboard(Extension):
    def __init__(self, bot: Client):
        self.bot = bot
        self.board_caches: dict[str, dict] = {}
        self.ready = False
        self._skipped_guilds: set[int] = set()

    def _cache_for(self, board: str) -> dict:
        if board not in self.board_caches:
            self.board_caches[board] = {}
        return self.board_caches[board]

    def load_json(self, board: str):
        return [
            war for war in load_wars(board)
            if war.get("status") in ("open", "matched")
        ]

    @listen()
    async def on_startup(self):
        print("✅ Billboard system starting...")

        for board in ALL_BOARD_KEYS:
            cache = self._cache_for(board)
            async for channel_id, channel in self._iter_accessible_channels(board):
                await self.initial_sync(board, channel_id, channel, cache)

        self.ready = True

        if not self.sync_billboards.running:
            self.sync_billboards.start()
            print("✅ Billboard diff-sync task running")

    async def _can_reach_guild(self, guild_id: int, guild_name: str = "") -> bool:
        if await can_access_guild(self.bot, guild_id):
            return True
        if guild_id not in self._skipped_guilds:
            self._skipped_guilds.add(guild_id)
            label = guild_name or str(guild_id)
            print(f"⏭️ Skipping billboard sync for **{label}** — bot is not in that server.")
        return False

    async def _iter_accessible_channels(self, board: str):
        for target in list_billboard_channel_targets(board):
            guild_id = target["guild_id"]
            channel_id = target["channel_id"]
            if not await self._can_reach_guild(guild_id, target.get("guild_name", "")):
                continue
            channel = await fetch_accessible_channel(self.bot, channel_id)
            if not channel:
                print(f"⏭️ Skipping billboard channel {channel_id} — bot cannot access it.")
                continue
            yield channel_id, channel

    async def initial_sync(self, board: str, channel_id: int, channel, cache: dict):

        wars = self.load_json(board)

        for war in wars:
            war_id = war["war_id"]
            embed = build_war_embed(war)
            components = build_war_buttons(war)
            try:
                msg = await channel.send(embeds=embed, components=components)
            except Exception as exc:
                print(f"❌ Cannot post {board} war {war_id} to channel {channel_id}: {exc}")
                continue

            if war_id not in cache:
                cache[war_id] = {"data": war, "messages": {}}
            cache[war_id]["data"] = war
            cache[war_id]["messages"][channel_id] = msg.id

        print(f"✅ Initial {board} billboard synced for channel {channel_id}")

    async def refresh_war(self, board: str, war: dict) -> None:
        """Immediately update this war's billboard messages across all hub channels."""
        war_id = war.get("war_id")
        if not war_id:
            return

        cache = self._cache_for(board)
        embed = build_war_embed(war)
        components = build_war_buttons(war)

        async for channel_id, channel in self._iter_accessible_channels(board):
            message_id = cache.get(war_id, {}).get("messages", {}).get(channel_id)
            if not message_id:
                message_id = await self._find_war_message(channel, war_id)

            if not message_id:
                try:
                    msg = await channel.send(embeds=embed, components=components)
                except Exception as exc:
                    print(f"❌ Cannot post {board} war {war_id} to channel {channel_id}: {exc}")
                    continue
                message_id = msg.id
                print(f"🆕 Posted {board} war {war_id} to channel {channel_id}")

            try:
                message = await channel.fetch_message(message_id)
                if message is None:
                    print(f"⚠️ Missing {board} war {war_id} message in channel {channel_id}; will repost")
                    cache.get(war_id, {}).get("messages", {}).pop(channel_id, None)
                    try:
                        msg = await channel.send(embeds=embed, components=components)
                    except Exception as exc:
                        print(f"❌ Cannot post {board} war {war_id} to channel {channel_id}: {exc}")
                        continue
                    if war_id not in cache:
                        cache[war_id] = {"data": war, "messages": {}}
                    cache[war_id]["data"] = war
                    cache[war_id]["messages"][channel_id] = msg.id
                    print(f"🆕 Reposted {board} war {war_id} in channel {channel_id}")
                    continue
                await message.edit(embeds=embed, components=components)
                if war_id not in cache:
                    cache[war_id] = {"data": war, "messages": {}}
                cache[war_id]["data"] = war
                cache[war_id]["messages"][channel_id] = message_id
                print(f"🔁 Refreshed {board} war {war_id} in channel {channel_id}")
            except Exception as exc:
                print(f"❌ Failed to refresh war {war_id} in channel {channel_id}: {exc}")

    async def remove_war(self, board: str, war_id: str) -> None:
        """Delete this war's billboard messages across all hub channels."""
        cache = self._cache_for(board)
        async for channel_id, channel in self._iter_accessible_channels(board):
            message_id = cache.get(war_id, {}).get("messages", {}).get(channel_id)
            if not message_id:
                message_id = await self._find_war_message(channel, war_id)
            if not message_id:
                continue
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
                print(f"🗑️ Removed {board} war {war_id} from channel {channel_id}")
            except Exception as exc:
                print(f"❌ Failed to remove war {war_id} from channel {channel_id}: {exc}")

        if war_id in cache:
            del cache[war_id]

    async def _find_war_message(self, channel, war_id: str) -> int | None:
        try:
            messages = await channel.fetch_messages(limit=50)
            for message in messages:
                for row in message.components or []:
                    for component in row.children:
                        custom_id = getattr(component, "custom_id", None) or ""
                        if custom_id.endswith(f":{war_id}"):
                            return message.id
        except Exception:
            pass
        return None

    @Task.create(IntervalTrigger(seconds=30))
    async def sync_billboards(self):
        for board in ALL_BOARD_KEYS:
            cache = self._cache_for(board)
            async for channel_id, channel in self._iter_accessible_channels(board):
                await self.sync_one(board, channel_id, channel, cache)

    async def sync_one(self, board: str, channel_id: int, channel, cache: dict):
        latest_wars = self.load_json(board)
        latest_by_id = {w["war_id"]: w for w in latest_wars}

        for war_id, war in latest_by_id.items():
            entry = cache.get(war_id)
            message_id = entry["messages"].get(channel_id) if entry else None

            if not message_id:
                try:
                    msg = await channel.send(
                        embeds=build_war_embed(war),
                        components=build_war_buttons(war),
                    )
                except Exception as exc:
                    print(f"❌ Cannot post {board} war {war_id} to channel {channel_id}: {exc}")
                    continue

                if war_id not in cache:
                    cache[war_id] = {"data": war, "messages": {}}
                cache[war_id]["data"] = war
                cache[war_id]["messages"][channel_id] = msg.id
                print(f"🆕 New {board} war {war_id} in channel {channel_id}")
                continue

            if entry and war != entry["data"]:
                try:
                    msg = await channel.fetch_message(message_id)
                    if msg is None:
                        cache[war_id]["messages"].pop(channel_id, None)
                        print(f"⚠️ Missing {board} war {war_id} message in channel {channel_id}; will repost")
                        continue
                    await msg.edit(
                        embeds=build_war_embed(war),
                        components=build_war_buttons(war),
                    )
                    cache[war_id]["data"] = war
                    print(f"🔁 Updated {board} war {war_id} in channel {channel_id}")
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
                            print(f"❌ Deleted {board} war {war_id} from channel {channel_id}")
                        except Exception:
                            pass
                    cache[war_id]["messages"].pop(channel_id, None)
                    if not cache[war_id]["messages"]:
                        del cache[war_id]


def setup(bot: Client):
    PostWarBillboard(bot)
