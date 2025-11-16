import json
import os
import interactions
from dotenv import load_dotenv
from interactions import (
    Extension,
    Embed,
    SlashContext,
    slash_command,
    slash_option,
    OptionType,
    SlashCommandChoice,
)


# --- Role / Guild IDs will need to be set to correct values to test / run for prod ---
# --- Current values default to roles / guild in Yoshi's Testing Server and Grand Star Cup

load_dotenv(".env.local")
global_ping_role = [907468726146854973, 1153207371976409109, 888289090695479357, 888289675490504754] # test role in Yoshi's Testing Server, Referee Role in GSC
penchoices = [
    SlashCommandChoice(name="Scrim", value="scrim"),
    SlashCommandChoice(name="Match", value="gsc_match"),
]

class PenSubmit(Extension):
    def __init__(self, bot):
        self.bot = bot


    # ---- COMMANDS BELOW ----

    @interactions.slash_command(
        name="submit_pen",
        description="Pings GSC Referees with a provided possible Penalty",
    )
    @interactions.slash_option(
        name="type",
        description="Match Type",
        required=True,
        opt_type=OptionType.STRING,
        choices=[
            interactions.SlashCommandChoice(name="Scrim", value="scrim"),
            interactions.SlashCommandChoice(name="Match", value="gsc_match"),
        ],
    )
    @interactions.slash_option(
        name="title",
        description="Match Header (e.g., Cy v RS - Pen on RS)",
        required=True,
        opt_type=OptionType.STRING,
    )
    @interactions.slash_option(
        name="link",
        description="GIF/Video link",
        required=True,
        opt_type=OptionType.STRING,
    )
    async def submitpen(self, ctx, type: str, title: str, link: str):

        await ctx.defer(ephemeral=True)

        allowed_guilds = [814572061510729758, 888071905184198736]
        if ctx.guild_id not in allowed_guilds:
            return await ctx.send("You are not allowed to use this command!", ephemeral=True)

        # Guild routing
        if ctx.guild_id == 814572061510729758:
            ping_role = 1153207371976409109
            spec_channel_id = (
                1323062737076621384 if type == "scrim" else 814572061510729761
            )
        else:
            ping_role = 907468726146854973
            spec_channel_id = (
                907079860856455209 if type == "scrim" else 951530514689429544
            )

        channel = await self.bot.fetch_channel(spec_channel_id)
        if not channel:
            return await ctx.send("Unable to locate the referee channel.", ephemeral=True)

        try:
            embed = interactions.Embed(
                title=title,
                description=f"Submitted by: {ctx.author.mention}",
                color=0x00FF00
            )

            # BUG: Discord auto-embeds the link ABOVE the embed, don't see any way around this currently.
            await channel.send(
                content=f"<@&{ping_role}>\n{link}",
                embeds=[embed]
            )

            await ctx.send("Penalty submitted successfully!", ephemeral=True)

        except Exception as e:
            print(e)
            await ctx.send("Something went wrong when submitting your penalty!", ephemeral=True)


def setup(bot: interactions.Client):
    PenSubmit(bot)
