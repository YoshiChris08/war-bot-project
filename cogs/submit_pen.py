import os
import re
import aiohttp
import interactions
from io import BytesIO  # ✅ NEW
from dotenv import load_dotenv
from interactions import (
    Extension,
    SlashContext,
    slash_command,
    slash_option,
    OptionType,
    SlashCommandChoice,
    Attachment,
    Embed,
    File,
    Button, 
    ButtonStyle, 
    Modal, 
    ComponentContext, 
    component_callback
)
from interactions.api.events import Component

load_dotenv(".env.local")

# 25 MB default upload limit
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

# Allowed video/image extensions for penalties
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".gif"}


def slugify_filename(title: str, fallback: str) -> str:
    """Create a safe-ish filename from the title, falling back to original name. Removing spaces and any other chars that may
    break the application"""
    _, ext = os.path.splitext(fallback or "")
    ext = ext.lower()

    safe_title = title.strip().lower()
    safe_title = re.sub(r"[^a-z0-9]+", "_", safe_title).strip("_")

    if not safe_title:
        safe_title = "penalty"

    return f"{safe_title}{ext or ''}"

reacted_users = []
vote_data = {}
def get_vote_for_user(user_id):
    
    for user, vote in reacted_users:
        if user == user_id:  # Check if user ID matches
            return vote  # Return the vote value
    return None  # Return None if the user has not voted
def create_vote_embed(title, description, author, votes):
    """Creates an embed with vote counts."""
    embed = interactions.Embed(title=title, color=0x00FF00)
    embed.description= description
    embed.add_field(name="Submitted by", value=str(author), inline=False)
    for vote_title, count in votes.items():
        embed.add_field(name=f"{vote_title} Votes", value=str(count), inline=True)
    return embed
# Surely there is a better way to do this efficently, but this is the code I used during the public betatest for YoshiBot
class PenSubmit(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @slash_command(
        name="submit_pen",
        description="Pings Referees with a provided possible Penalty",
    )
    @slash_option(
        name="type",
        description="Match Type",
        required=True,
        opt_type=OptionType.STRING,
        choices=[
            SlashCommandChoice(name="Scrim", value="scrim"),
            SlashCommandChoice(name="Match", value="gsc_match"),
        ],
    )
    @slash_option(
        name="title",
        description="Match Header (e.g., Cy v RS - Pen on RS)",
        required=True,
        opt_type=OptionType.STRING,
    )
    @slash_option(
        name="attachment",
        description="Attach the GIF/Video link here (ie. cdn.discordapp / imgur / giphy)",
        required=True,
        opt_type=OptionType.STRING,
    )
    async def submitpen(
        self,
        ctx: SlashContext,
        type: str,
        title: str,
        video: Attachment,
    ):
        await ctx.defer(ephemeral=True)

        # Channel / role IDs from env
        spec_channel_id = (
            int(os.getenv("SCRIM_PEN_CHANNEL"))
            if type == "scrim"
            else int(os.getenv("GSC_PEN_CHANNEL"))
        )
        ref_role_id = os.getenv("REF_ID")

        if not spec_channel_id:
            return await ctx.send(
                "Config error: SCRIM_PEN_CHANNEL / GSC_PEN_CHANNEL is not set.",
                ephemeral=True,
            )

        if not ref_role_id:
            return await ctx.send(
                "Config error: REF_ID (referee role ID) is not set.",
                ephemeral=True,
            )

        channel = await self.bot.fetch_channel(spec_channel_id)
        if not channel:
            return await ctx.send(
                "Unable to locate the referee channel.", ephemeral=True
            )
        auto_name = slugify_filename(title, filename)
        try:
                    vote_counts = {"0": 0, "5": 0, "10": 0, "20": 0} # need to add spot correct functionality in future
                    description = f"Download: {attachment}"
                    embed = create_vote_embed(auto_name, description, ctx.author.mention, vote_counts)
                    buttons = [
                            interactions.Button(
                            style=interactions.ButtonStyle.PRIMARY,
                            label=label,
                            custom_id=f"vote_button_{label}",
                        )
                        for label in vote_counts.keys()
                    ] + [
                        interactions.Button(
                            style=interactions.ButtonStyle.RED,
                            label="Remove Vote",
                            custom_id="remove_button",
                        )
                    ]
                    
                    message = await channel.send(embeds=[embed], content=f"<@&{ping_role}>", components=buttons)
                    await channel.send(attachment)
                    vote_data[message.id] = vote_counts  # Store vote counts keyed by message ID
                    await ctx.send("Penalty submitted successfully!", ephemeral=True)
                    reacted_users.clear() # since i dont have an object-oriented focus atm, i currently use a dictionary with keys/penalty that attributes to a singular penalty at a time.

                except Exception as e:
                    print("SubmitPen Error:", repr(e))
                    #current_time = datetime.now()
                    # print("Current Time:", current_time.strftime("%H:%M:%S"))
                    await ctx.send("Something went wrong when submitting your penalty!", ephemeral=True)

            @component_callback("vote_button_0")
async def vote_0(ctx: interactions.ComponentContext):
  
         if any(role.id in global_ping_role for role in ctx.author.roles):
            if not any(ctx.author.id == user[0] for user in reacted_users):
                await handle_vote(ctx, "0")
                reacted_users.append([ctx.author.id, "0"])
            else:
                await ctx.send("You have already ruled this penalty! In order to change your vote, please hit 'Remove Vote' first", ephemeral=True)
         else:
            await ctx.send("You do not have permission to vote on this penalty!", ephemeral=True)

@component_callback("vote_button_5")
async def vote_5(ctx: interactions.ComponentContext):
            if any(role.id in global_ping_role for role in ctx.author.roles):
                if not any(ctx.author.id == user[0] for user in reacted_users):
                    await handle_vote(ctx, "5")
                    reacted_users.append([ctx.author.id, "5"])
                else:
                    await ctx.send("You have already ruled this penalty! In order to change your vote, please hit 'Remove Vote' first", ephemeral=True)
            else:
                await ctx.send("You do not have permission to vote on this penalty!", ephemeral=True)

@component_callback("vote_button_10")
async def vote_10(ctx: interactions.ComponentContext):
            if any(role.id in global_ping_role for role in ctx.author.roles):
                if not any(ctx.author.id == user[0] for user in reacted_users):
                    await handle_vote(ctx, "10")
                    reacted_users.append([ctx.author.id, "10"])
                else:
                    await ctx.send("You have already ruled this penalty! In order to change your vote, please hit 'Remove Vote' first", ephemeral=True)
            else:
                    await ctx.send("You do not have permission to vote on this penalty!", ephemeral=True)

@component_callback("vote_button_20")
async def vote_20(ctx: interactions.ComponentContext):
            if any(role.id in global_ping_role for role in ctx.author.roles):
                if not any(ctx.author.id == user[0] for user in reacted_users):
                    await handle_vote(ctx, "20")
                    reacted_users.append([ctx.author.id,"20"])
                else:
                    await ctx.send("You have already ruled this penalty! In order to change your vote, please hit 'Remove Vote' first", ephemeral=True)
            else:
                await ctx.send("You do not have permission to vote on this penalty!", ephemeral=True)

@component_callback("remove_button")
async def vote_remove(ctx: interactions.ComponentContext):
    try:
        await handle_vote(ctx, "remove")
        index = next(i for i, user in enumerate(reacted_users) if user[0] == ctx.author.id)
        
        reacted_users.pop(index)
        
        await ctx.send("Your vote has been removed!", ephemeral=True)
    except StopIteration:
        if any(role.id in global_ping_role for role in ctx.author.roles):
            await ctx.send("You haven't voted yet!", ephemeral=True)
        else:
            await ctx.send("You do not have permission to vote on this penalty!", ephemeral=True)

async def handle_vote(ctx: interactions.ComponentContext, vote_title: str):
            """Handles a button press for a vote.""" 
            if vote_title == "remove":
                 try:
                    vote_data[ctx.message.id][get_vote_for_user(ctx.author.id)] -= 1
                    updated_embed = create_vote_embed(
                        ctx.message.embeds[0].title,
                        ctx.message.embeds[0].description,
                        ctx.message.embeds[0].fields[0].value,
                        vote_data[ctx.message.id],            
                    )
                    await ctx.message.edit(embeds=[updated_embed])
                 except Exception as e:
                    pass      
            elif ctx.message.id in vote_data:
                vote_data[ctx.message.id][vote_title] += 1
                updated_embed = create_vote_embed(
                    ctx.message.embeds[0].title,
                    ctx.message.embeds[0].description,
                    ctx.message.embeds[0].fields[0].value,
                    vote_data[ctx.message.id],            
                )
                await ctx.message.edit(embeds=[updated_embed])
                await ctx.send(f"Vote for '{vote_title}' recorded!", ephemeral=True)
            else:
                await ctx.send("This vote is not tracked.", ephemeral=True)

async def get_voters_for_vote(vote_value):
    voters = [user for user, vote in reacted_users if vote == vote_value]
    return voters

# Function to create the embed listing users who voted for each option
async def track_vote(title, description, author, votes):
    """Creates an embed with vote counts and mentions users who voted for each option."""
    embed = interactions.Embed(title=title, color=0x00FF00)
    embed.description = description
    embed.add_field(name="Requested by", value=str(author), inline=False)

    # Dictionary with the available vote types
    vote_types = ['0', '5', '10', '20']


    for vote_type in vote_types:
        voters = await get_voters_for_vote(vote_type)  # Get users who voted for this type
        if voters:
            voters_mentions = "\n".join([f"<@{user_id}>" for user_id in voters])
            embed.add_field(name=f"{vote_type} Votes", value=voters_mentions, inline=True)
        else:
            embed.add_field(name=f"{vote_type} Votes", value="No votes yet", inline=True)

    return embed


def setup(bot: interactions.Client):
    PenSubmit(bot)
