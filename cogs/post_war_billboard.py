import os
import json
import interactions
from dotenv import load_dotenv
from interactions import Task, IntervalTrigger, Extension, Client, listen, Button, ButtonStyle, ActionRow

load_dotenv(".env.local")

# ---------------------------
# Channel IDs
# ---------------------------
RT_CHANNEL_ID = int(os.getenv("RT_WAR_ID")) if os.getenv("RT_WAR_ID") else None
CT_CHANNEL_ID = int(os.getenv("CT_WAR_ID")) if os.getenv("CT_WAR_ID") else None

# ---------------------------
# Paths
# ---------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BILLBOARD_DIR = os.path.join(BASE_DIR, "temp", "billboard-data")


class PostWarBillboard(Extension):
    def __init__(self, bot: Client):
        self.bot = bot

        # ✅ In-memory cache:
        # war_id -> { "data": war_dict, "message_id": int }
        self.rt_wars = {}
        self.ct_wars = {}

        # ✅ Prevents startup race-condition deletes
        self.ready = False

    # ---------------------------
    # JSON Loader
    # ---------------------------
    def load_json(self, war_type: str):
        path = os.path.join(BILLBOARD_DIR, f"{war_type}-billboard.json")

        if not os.path.exists(path):
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            print(f"⚠️ {war_type.upper()} billboard JSON is corrupted.")
            return []
        except Exception as e:
            print(f"❌ Failed to load {war_type} billboard: {e}")
            return []

    # ---------------------------
    # Embed Formatter
    # ---------------------------
    def format_war(self, war: dict) -> interactions.Embed:
        lineup = war.get("lineup", [])

        # Build lineup text
        if lineup:
            lineup_text = "\n".join(
                f"- **{p.get('player', 'Unknown')}** ({p.get('role', 'Unknown')})"
                for p in lineup
            )
        else:
            lineup_text = "No players yet."

        # Color by war type
        war_type = war.get("war_type", "RT").upper()
        color = 0x2ECC71 if war_type == "RT" else 0x9B59B6

        embed = interactions.Embed(
            title=f"{war.get('team_name', 'Unknown Team')} searching ({war_type})",
            description=f"**War ID:** `{war.get('war_id')}`",
            color=color
        )

        embed.add_field(
            name="⏰ Time Searching For",
            value=f"`{war.get('start_time', 'Unknown')}`",
            inline=False
        )

        embed.add_field(
            name=f"👥 Lineup ({len(lineup)})",
            value=lineup_text,
            inline=False
        )

        embed.set_footer(text="Auto-updated War Billboard")

        return embed

    # Create buttons used to accept or deny wars. For now just a placeholder.
    def build_war_buttons(self, war_id: str):
        button = Button(
            style=ButtonStyle.SUCCESS,
            label="Accept War (Placeholder)",
            custom_id=f"accept_war:{war_id}",  # unique per war
            disabled=False
        )

        return ActionRow(button)

        

    # ---------------------------
    # Startup Sync
    # ---------------------------
    @listen()
    async def on_startup(self):
        print("✅ Billboard system starting...")

        if RT_CHANNEL_ID:
            await self.initial_sync("rt", RT_CHANNEL_ID, self.rt_wars)

        if CT_CHANNEL_ID:
            await self.initial_sync("ct", CT_CHANNEL_ID, self.ct_wars)

        # ✅ Unlock deletion after initial sync completes
        self.ready = True

        if not self.sync_billboards.running:
            self.sync_billboards.start()
            print("✅ Billboard diff-sync task running")

    async def initial_sync(self, war_type: str, channel_id: int, cache: dict):
        channel = await self.bot.fetch_channel(channel_id)
        wars = self.load_json(war_type)

        for war in wars:
            embed = self.format_war(war)
            components = self.build_war_buttons(war["war_id"])
            msg = await channel.send(embeds=embed, components=components)

            cache[war["war_id"]] = {
                "data": war,
                "message_id": msg.id
            }

        print(f"✅ Initial {war_type.upper()} billboard synced")

    # ---------------------------
    # Diff-Based Live Sync
    # ---------------------------
    @Task.create(IntervalTrigger(seconds=30))
    async def sync_billboards(self):
        await self.sync_one("rt", RT_CHANNEL_ID, self.rt_wars)
        await self.sync_one("ct", CT_CHANNEL_ID, self.ct_wars)

    async def sync_one(self, war_type: str, channel_id: int, cache: dict):
        if not channel_id:
            return

        channel = await self.bot.fetch_channel(channel_id)
        latest_wars = self.load_json(war_type)
        latest_by_id = {w["war_id"]: w for w in latest_wars}

        # ---------------------------
        # NEW or UPDATED wars
        # ---------------------------
        for war_id, war in latest_by_id.items():

            # ✅ NEW WAR → create message
            if war_id not in cache:
                embed = self.format_war(war)
                components = self.build_war_buttons(war["war_id"])
                msg = await channel.send(embeds=embed, components=components)

                cache[war_id] = {
                    "data": war,
                    "message_id": msg.id
                }

                print(f"🆕 New {war_type.upper()} war {war_id}")
                continue

            # 🔁 UPDATED WAR → edit message
            old_data = cache[war_id]["data"]
            if war != old_data:
                try:
                    msg = await channel.fetch_message(cache[war_id]["message_id"])
                    embed = self.format_war(war)
                    components = self.build_war_buttons(war["war_id"])
                    msg = await channel.send(embeds=embed, components=components)

                    cache[war_id]["data"] = war
                    print(f"🔁 Updated {war_type.upper()} war {war_id}")
                except Exception as e:
                    print(f"❌ Failed to edit war {war_id}: {e}")

        # ---------------------------
        # DELETED wars → delete message
        # ---------------------------
        if self.ready and latest_by_id:
            for war_id in list(cache.keys()):
                if war_id not in latest_by_id:
                    try:
                        msg = await channel.fetch_message(cache[war_id]["message_id"])
                        await msg.delete()
                        print(f"❌ Deleted {war_type.upper()} war {war_id}")
                    except Exception:
                        pass

                    del cache[war_id]


# ---------------------------
# Extension Loader
# ---------------------------
def setup(bot: Client):
    PostWarBillboard(bot)