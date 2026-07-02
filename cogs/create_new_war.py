import json
import os
import re
import interactions
from typing import Optional
from classes.player import Player
from classes.war import War
from interactions import (
    Extension,
    SlashContext,
    slash_command,
    slash_option,
    OptionType,
    SlashCommandChoice,
)
from dotenv import load_dotenv

load_dotenv(".env.local")

PROJECT_ENV = os.getenv("PROJECT_ENVIRONMENT", "local").lower()
DEV = PROJECT_ENV == "local"

GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else 1436538029316636705
SCOPES = [GUILD_ID] if DEV else None

RT_CHANNEL_ID = os.getenv("RT_WAR_ID")
CT_CHANNEL_ID = os.getenv("CT_WAR_ID")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class CreateNewWar(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @slash_command(
        name="create-new-war",
        description="Starts a new war and posts it on the billboard. Default is RT.",
        scopes=SCOPES
    )
    @slash_option(
        name="track_type",
        description="Track type (RT or CT). If omitted, defaults to RT.",
        required=False,
        opt_type=OptionType.STRING,
        choices=[
            SlashCommandChoice(name="RT", value="RT"),
            SlashCommandChoice(name="CT", value="CT"),
        ],
    )
    @slash_option(
        name="team_name",
        description="Name of the team you're searching as.",
        required=False,
        opt_type=OptionType.STRING
    )
    @slash_option(
        name="search_time",
        description="Time in ET (GMT-5). Defaults to ASAP.",
        required=False,
        opt_type=OptionType.STRING
    )
    @slash_option(
        name="is_bagger",
        description="Determine whether the person searching for the war is a bagger.",
        required=False,
        opt_type=OptionType.BOOLEAN
    )
    async def create_new_war(
        self,
        ctx: SlashContext,
        track_type: Optional[str] = None,
        team_name: Optional[str] = None,
        search_time: Optional[str] = None,
        is_bagger: Optional[bool] = None,
    ):

        # Track type
        is_ct = (track_type or "RT").upper() == "CT"
        target_channel_id = CT_CHANNEL_ID if is_ct else RT_CHANNEL_ID
        track_label = "CT" if is_ct else "RT"

        # Team name
        if not team_name:
            team_name = ctx.guild.name if ctx.guild else "Unknown Server"

        # Search time
        if not search_time:
            search_time = "ASAP"
        else:
            raw_input = search_time.strip().upper()

            if raw_input.isdigit():
                hour = int(raw_input)
                if hour < 0 or hour > 23:
                    await ctx.send(
                        "Invalid time. Please enter **0–23**, or **7PM / 11AM**.",
                        ephemeral=True
                    )
                    return
                else:
                    search_time = raw_input

            elif re.fullmatch(r"(1[0-2]|[1-9])(AM|PM)", raw_input):
                search_time = raw_input

            else:
                await ctx.send(
                    "Invalid time format.\n\n Valid examples:\n"
                    "- `0` → `23`\n"
                    "- `7PM`\n"
                    "- `11AM`\n\nAll times are ET (GMT-5).",
                    ephemeral=True
                )
                return

        # Bagger flag
        if is_bagger is None:
            is_bagger = False

        user_id = ctx.author.id

        await ctx.send(
            f"Command received in **{team_name}**.\n"
            f"Track type: **{track_label}**\n"
            f"Bagger: **{is_bagger}**\n"
            f"Search time: **{search_time}**\n"
            f"Your user ID is `{user_id}`.",
            ephemeral=True
        )


        print(search_time)

        # Using display name for now, will likely link with lounge in the future
        creation_player = Player(ctx.author.display_name, role="Bagger" if is_bagger else "Runner", ally=False)
        creation_war = War(war_type=track_label, team_name=team_name, start_time=search_time, search_in_advance=False if search_time=="ASAP" else True)
        creation_war.lineup.append(creation_player)
        billboard_path = (os.path.join(BASE_DIR, 'temp', 'billboard-data','ct-billboard.json') if is_ct else os.path.join(BASE_DIR, 'temp', 'billboard-data', 'rt-billboard.json'))


        # Load existing data (if any)
        if os.path.exists(billboard_path):
            with open(billboard_path, "r", encoding="utf-8") as f:
                try:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = []
                except json.JSONDecodeError:
                    existing_data = []
        else:
            existing_data = []

        # Append the new war dict
        existing_data.append(creation_war.to_dict())

        # Write back to JSON file
        os.makedirs(os.path.dirname(billboard_path), exist_ok=True)
        with open(billboard_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)

        print(f"Added war to {billboard_path}")

        # Post to the appropriate billboard channel
        try:
            channel = await self.bot.fetch_channel(target_channel_id)
        except Exception as e:
            print(f"Error sending to target channel {target_channel_id}: {e}")

def setup(bot: interactions.Client):
    CreateNewWar(bot)

