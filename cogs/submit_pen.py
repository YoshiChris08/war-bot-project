import os
import re
import interactions
from dotenv import load_dotenv
from interactions import (
    Extension,
    SlashContext,
    slash_command,
    slash_option,
    OptionType,
    SlashCommandChoice,
    ComponentContext,
    Button,
    ButtonStyle,
    component_callback,
    Embed,
)

load_dotenv(".env.local")

# NEEDS TO BE CHANGED FOR REF ROLES
global_ping_role = [
    907468726146854973,
    1153207371976409109,
    888289090695479357,
    888289675490504754,
]

penchoices = [
    SlashCommandChoice(name="Scrim", value="scrim"),
    SlashCommandChoice(name="Match", value="gsc_match"),
]


class PenaltyVote:
    OPTIONS = ["0", "5", "10", "20"]

    def __init__(self, message_id, title, description, author):
        self.message_id = message_id
        self.title = title
        self.description = description
        self.author = author
        self.counts = {opt: 0 for opt in self.OPTIONS}
        self.user_votes = {}  # user_id -> vote

    def add_vote(self, user_id, vote):
        if user_id in self.user_votes:
            return False
        self.user_votes[user_id] = vote
        self.counts[vote] += 1
        return True

    def remove_vote(self, user_id):
        if user_id not in self.user_votes:
            return False
        vote = self.user_votes.pop(user_id)
        self.counts[vote] -= 1
        return True

    def build_embed(self):
        embed = Embed(
            title=self.title,
            description=self.description,
            color=0x00FF00,
        )
        embed.add_field(name="Submitted by", value=self.author, inline=False)
        for opt, count in self.counts.items():
            embed.add_field(name=f"{opt} Votes", value=str(count), inline=True)
        return embed

    def build_summary_embed(self):
        embed = Embed(title="Penalty Vote Summary", color=0x00FF00)
        for opt in self.OPTIONS:
            voters = [
                f"<@{uid}>" for uid, v in self.user_votes.items() if v == opt
            ]
            embed.add_field(
                name=f"{opt} Votes",
                value="\n".join(voters) if voters else "No votes",
                inline=True,
            )
        return embed


class VoteManager:
    def __init__(self):
        self.votes = {}

    def create(self, message_id, title, description, author):
        self.votes[message_id] = PenaltyVote(message_id, title, description, author)

    def get(self, message_id):
        return self.votes.get(message_id)


vote_manager = VoteManager()


class PenSubmit(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @slash_command(
        name="submit_pen",
        description="Pings GSC Referees with a provided possible Penalty",
    )
    @slash_option(
        name="type",
        description="Match Type",
        required=True,
        opt_type=OptionType.STRING,
        choices=penchoices,
    )
    @slash_option(
        name="title",
        description="Match Header (e.g., Cy v RS - RS Pen)",
        required=True,
        opt_type=OptionType.STRING,
    )
    @slash_option(
        name="attachment",
        description="Attach a link to the pen (can be a GIF or Video Link)",
        required=True,
        opt_type=OptionType.STRING,
    )
    async def submitpen(
        self, ctx: SlashContext, type: str, title: str, attachment: str
    ):
        await ctx.defer(ephemeral=True)

        # Allowed servers ***NEEDS TO BE CHANGED TO ALLOW SUBMISSIONS FROM ANY SERVER AND ROUTE TO GSC OR ONLY ALLOW SUBMISSIONS IN GSC***
        allowed_guilds = [814572061510729758, 888071905184198736]
        if ctx.guild_id not in allowed_guilds:
            await ctx.send("You are not allowed to use this command!", ephemeral=True)
            return

        # Server-specific config (NEEDS TO BE ROUTED TO GSC / ANY OFFICIAL HUBS REFS SEE, CHANGE THESE VALUES)
        if ctx.guild_id == 814572061510729758:
            ping_role = 1153207371976409109
            spec_channel_id = 1323062737076621384 if type == "scrim" else 814572061510729761
        elif ctx.guild_id == 888071905184198736:
            ping_role = 907468726146854973
            spec_channel_id = 907079860856455209 if type == "scrim" else 951530514689429544

        channel = await self.bot.fetch_channel(spec_channel_id)

        buttons = [
            Button(style=ButtonStyle.PRIMARY, label=opt, custom_id=f"vote_button_{opt}")
            for opt in PenaltyVote.OPTIONS
        ] + [Button(style=ButtonStyle.RED, label="Remove Vote", custom_id="remove_button")]

        message = await channel.send(content=f"<@&{ping_role}>", components=buttons)

        vote_manager.create(message.id, title, f"Download: {attachment}", ctx.author.mention)
        await message.edit(embeds=[vote_manager.get(message.id).build_embed()])
        await channel.send(attachment)
        await ctx.send("Penalty submitted successfully!", ephemeral=True)

    # ======================
    # BUTTON HANDLERS
    # ======================
    @component_callback(re.compile(r"vote_button_(\d+)"))
    async def vote_handler(self, ctx: ComponentContext):
        vote = ctx.custom_id.split("_")[-1]

        if not any(role.id in global_ping_role for role in ctx.author.roles):
            await ctx.send("You do not have permission to vote.", ephemeral=True)
            return

        penalty = vote_manager.get(ctx.message.id)
        if not penalty:
            await ctx.send("Vote no longer exists.", ephemeral=True)
            return

        if not penalty.add_vote(ctx.author.id, vote):
            await ctx.send("You already voted. Use **Remove Vote** first.", ephemeral=True)
            return

        await ctx.message.edit(embeds=[penalty.build_embed()])
        await ctx.send(f"Vote `{vote}` recorded.", ephemeral=True)

    @component_callback("remove_button")
    async def remove_vote(self, ctx: ComponentContext):
        penalty = vote_manager.get(ctx.message.id)

        if not penalty:
            await ctx.send("Vote no longer exists.", ephemeral=True)
            return

        if not penalty.remove_vote(ctx.author.id):
            await ctx.send("You haven't voted yet.", ephemeral=True)
            return

        await ctx.message.edit(embeds=[penalty.build_embed()])
        await ctx.send("Your vote has been removed.", ephemeral=True)


    # ======================
    # Penalty Votes Checker ***MAY NEED TO BE REMOVED, DONT KNOW IF IT CAN GO IN THIS COG***
    # ======================
    @slash_command(
        name="pen_votes",
        description="Checks who voted on the most recent GSC penalty!",
    )
    async def pen_votes(self, ctx: SlashContext):
        if not any(role.id in global_ping_role for role in ctx.author.roles):
            await ctx.send("You do not have permission to execute this!", ephemeral=True)
            return

        if not vote_manager.votes:
            await ctx.send("No active penalty votes found.", ephemeral=True)
            return

        penalty = list(vote_manager.votes.values())[-1]
        await ctx.send(embeds=[penalty.build_summary_embed()])


def setup(bot: interactions.Client):
    PenSubmit(bot)
