import interactions
from interactions import Extension, SlashContext, slash_command

from utils.colors import COLORS
from utils.config import SCOPES


def _embed(title: str, description: str) -> interactions.Embed:
    return interactions.Embed(title=title, description=description, color=COLORS["default"])


HELP_TOPICS = {
    "queue": _embed(
        "Help · /queue",
        "**Team-server commands** (captain + teammates):\n\n"
        "• `/profile link` — link Lounge account or Wii friend code (required to join lineups)\n"
        "• `/profile view` — ratings (RT/CT × runner/bagger), FC, team, last 5 wars\n"
        "• `/queue start` — opens a form; creates a lobby in **#team-queue**\n"
        "• Teammates join with lobby buttons (runner / bagger)\n"
        "• `/queue post` — captain posts to the hub billboard (needs ≥1 bagger)\n"
        "• `/queue status` — your lobby + hub post summary\n"
        "• `/queue cancel` — captain removes the team queue\n\n"
        "**Notes**\n"
        "• Ranked is default; type `casual` in the start form for casual\n"
        "• You can only be on **one** active lineup at a time\n"
        "• At **5/5** with a bagger, posts auto-switch to Looking For Opponents",
    ),
    "war": _embed(
        "Help · /war",
        "**Match channel only** (`war-vs-*`):\n\n"
        "• `/war complete` — captain reports won/lost + margin + **RXX** (required)\n"
        "• Scores load from the WiimmFI room via Lounge API when RXX lookup succeeds\n"
        "• Linked FCs are checked against live WiimmFI when available — mismatches block auto-score\n"
        "• `/war scores` — **fallback only** if RXX lookup fails (each captain submits)\n"
        "• `/war confirm` — **both** captains must confirm the result\n"
        "• `/war dispute` — either captain rejects the report\n"
        "• `/war cancel` — request abort; opponent uses `/war approve-cancel`\n"
        "• `/war decline-cancel` — opponent declines abort\n\n"
        "**Score line format** (manual fallback)\n"
        "`p1 p2 p3 p4 bagger [penalties]` — space separated, penalties optional\n\n"
        "Everyone on the roster needs `/profile link` so their FC can be matched in the room.",
    ),
    "billboard": _embed(
        "Help · Hub billboard",
        "Hub channels: `rt-ranked-wars`, `ct-ranked-wars`, `rt-casual-wars`, `ct-casual-wars`\n\n"
        "• **Join as Ally** — fill a team looking for allies (5/5 max)\n"
        "• **Request Match** — challenge a 5/5 team looking for opponents\n"
        "• Defending captain **Accept** / **Decline** in their team queue\n"
        "• `/war-view` — view your team's hub post",
    ),
    "setup": _embed(
        "Help · Setup",
        "**One-time per server (admin):**\n\n"
        "• `/team` — register this Discord as your MKWii team\n"
        "• `/setup` → **Create category** — RT/CT ranked+casual boards + team queue + how-to-use\n"
        "• Or `/setup` → **Link …** for each board (RT/CT × ranked/casual) + team queue\n\n"
        "• `/queue-status` — quick view of your lobby",
    ),
}


class HelpCommands(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @slash_command(
        name="help",
        description="War Bot guides",
        sub_cmd_name="queue",
        sub_cmd_description="Team queue commands",
        scopes=SCOPES,
    )
    async def help_queue(self, ctx: SlashContext):
        await ctx.send(embeds=HELP_TOPICS["queue"], ephemeral=True)

    @slash_command(
        name="help",
        description="War Bot guides",
        sub_cmd_name="war",
        sub_cmd_description="Match channel commands",
        scopes=SCOPES,
    )
    async def help_war(self, ctx: SlashContext):
        await ctx.send(embeds=HELP_TOPICS["war"], ephemeral=True)

    @slash_command(
        name="help",
        description="War Bot guides",
        sub_cmd_name="billboard",
        sub_cmd_description="Hub billboard flow",
        scopes=SCOPES,
    )
    async def help_billboard(self, ctx: SlashContext):
        await ctx.send(embeds=HELP_TOPICS["billboard"], ephemeral=True)

    @slash_command(
        name="help",
        description="War Bot guides",
        sub_cmd_name="setup",
        sub_cmd_description="Server setup",
        scopes=SCOPES,
    )
    async def help_setup(self, ctx: SlashContext):
        await ctx.send(embeds=HELP_TOPICS["setup"], ephemeral=True)


def setup(bot: interactions.Client):
    HelpCommands(bot)
