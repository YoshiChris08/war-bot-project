import interactions
from interactions import Extension, Modal, ShortText, SlashContext, slash_command

from utils.config import SCOPES
from utils.embeds import build_profile_embed
from utils.player_links import link_manual_friend_code, resolve_friend_code, try_lounge_link
from utils.player_profile_store import get_profile
from utils.player_store import get_player
from utils.profile_view import recent_wars_for_profile, resolve_profile_team


class ProfileCommands(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @slash_command(
        name="profile",
        description="Link your Wii friend code",
        sub_cmd_name="link",
        sub_cmd_description="Link Lounge account or enter your WiimmFI FC.",
        scopes=SCOPES,
    )
    async def profile_link(self, ctx: SlashContext):
        profile, lounge_player, lounge_error = await try_lounge_link(ctx.author.id)

        if profile:
            name = profile.get("lounge_name")
            name_part = f" as **{name}**" if name else ""
            await ctx.send(
                f"Linked your **Lounge** account{name_part}.\n"
                f"**FC:** `{profile.get('friend_code')}`\n"
                "Run `/profile view` anytime to see ratings and recent form.",
                ephemeral=True,
            )
            return

        # Discord: modal must be the initial response — don't send a message first.
        if lounge_error:
            await ctx.send(
                f"Lounge lookup failed: {lounge_error}\n"
                "Fix the API key/config, then run `/profile link` again.\n"
                "Or ask an admin — manual FC linking needs a successful bot response.",
                ephemeral=True,
            )
            return

        lounge_name = None
        if lounge_player:
            lounge_name = lounge_player.get("player_name") or lounge_player.get("name")

        title = f"FC for Lounge: {lounge_name}" if lounge_name else "Link friend code"
        if len(title) > 45:
            title = "Link friend code (Lounge found)"

        modal = Modal(
            ShortText(
                label="WiimmFI friend code",
                custom_id="friend_code",
                placeholder="1234-5678-9012",
                required=True,
                max_length=14,
            ),
            title=title,
        )
        await ctx.send_modal(modal)
        m_ctx = await self.bot.wait_for_modal(modal, ctx.author)
        linked, error = await link_manual_friend_code(
            ctx.author.id,
            m_ctx.kwargs.get("friend_code", ""),
            lounge_player=lounge_player,
        )
        if error:
            await m_ctx.send(error, ephemeral=True)
            return

        if lounge_name:
            await m_ctx.send(
                f"Linked **Lounge** account **{lounge_name}** with FC `{linked.get('friend_code')}`.\n"
                "Lounge found your Discord account, but no FC was stored there — saved yours manually.\n"
                "Run `/profile view` to see your card.",
                ephemeral=True,
            )
        else:
            await m_ctx.send(
                f"Friend code saved: `{linked.get('friend_code')}`\n"
                "No Lounge account was found for your Discord ID. "
                "If you later link Discord on Lounge, run `/profile link` again.\n"
                "Run `/profile view` to see your card.",
                ephemeral=True,
            )

    @slash_command(
        name="profile",
        description="Link your Wii friend code",
        sub_cmd_name="view",
        sub_cmd_description="View your ratings, FC, team, and recent wars.",
        scopes=SCOPES,
    )
    async def profile_view(self, ctx: SlashContext):
        await ctx.defer(ephemeral=True)
        profile = get_profile(ctx.author.id)
        fc = (profile or {}).get("friend_code")
        if not fc:
            guild_id = ctx.guild.id if ctx.guild else None
            fc = await resolve_friend_code(ctx.author.id, guild_id=guild_id)
            profile = get_profile(ctx.author.id) or profile

        if not profile and not fc:
            await ctx.send(
                "No profile linked yet. Run `/profile link` first.",
                ephemeral=True,
            )
            return

        if profile and fc and not profile.get("friend_code"):
            profile = {**profile, "friend_code": fc}
        elif not profile and fc:
            profile = {"friend_code": fc, "link_source": "resolved"}

        guild_id = ctx.guild.id if ctx.guild else None
        team, team_mmr = resolve_profile_team(guild_id)
        avatar = None
        try:
            avatar = ctx.author.avatar.url if ctx.author.avatar else None
        except Exception:
            avatar = None

        embed = build_profile_embed(
            display_name=ctx.author.display_name,
            discord_id=ctx.author.id,
            avatar_url=avatar,
            profile=profile,
            player=get_player(ctx.author.id),
            team=team,
            team_mmr=team_mmr,
            recent=recent_wars_for_profile(ctx.author.id, limit=5),
        )
        await ctx.send(embeds=embed, ephemeral=True)


def setup(bot: interactions.Client):
    ProfileCommands(bot)
