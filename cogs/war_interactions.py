import re
from datetime import datetime
from typing import Any, Dict, Optional

import interactions
from interactions import (
    ActionRow,
    Button,
    ButtonStyle,
    ComponentContext,
    Extension,
    component_callback,
)

from classes.player import Player
from utils.billboard_store import delete_war, find_war_across_boards, upsert_war
from utils.match_posting import sync_party_lineup_from_post
from utils.queue_store import get_party, upsert_party
from utils.config import track_to_type
from utils.embeds import build_war_embed
from utils.roster import (
    SEARCH_ALLIES,
    SEARCH_OPPONENTS,
    ally_slots_remaining,
    can_seek_opponents,
    is_roster_full,
)
from utils.war_buttons import build_war_buttons


def _player_in_lineup(lineup: list, discord_id: int) -> bool:
    return any(entry.get("discord_id") == discord_id for entry in lineup)


def _touch_war(war: Dict[str, Any]) -> Dict[str, Any]:
    war["last_updated"] = datetime.utcnow().isoformat()
    war["ally_count"] = sum(1 for player in war.get("lineup", []) if player.get("ally"))
    return war


def _save_and_refresh(war_type: str, war: Dict[str, Any]) -> Dict[str, Any]:
    war = _touch_war(war)
    upsert_war(war_type, war)
    party_id = war.get("party_id")
    if party_id:
        party = get_party(party_id)
        if party:
            upsert_party(sync_party_lineup_from_post(party, war))
    return war


class WarInteractions(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    def _get_war(self, war_id: str) -> Optional[tuple[str, Dict[str, Any]]]:
        return find_war_across_boards(war_id)

    def _is_author(self, war: Dict[str, Any], user_id: int) -> bool:
        return war.get("author_discord_id") == user_id

    async def _edit_billboard_message(self, war_type: str, war: Dict[str, Any], message_id: int) -> None:
        from utils.guild_config import get_billboard_channel_id

        channel_id = get_billboard_channel_id(war.get("origin_guild_id"), war_type)
        if not channel_id:
            return

        try:
            channel = await self.bot.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
            embed = build_war_embed(war)
            components = build_war_buttons(war)
            await message.edit(embeds=embed, components=components)
        except Exception as exc:
            print(f"❌ Failed to refresh billboard message for {war.get('war_id')}: {exc}")

    @component_callback(re.compile(r"^war_join_ally:(.+)$"))
    async def join_ally_prompt(self, ctx: ComponentContext):
        war_id = ctx.custom_id.split(":", 1)[1]
        found = self._get_war(war_id)
        if not found:
            await ctx.send("This war post no longer exists.", ephemeral=True)
            return

        war_type, war = found
        if war.get("status") != "open" or war.get("search_mode") != SEARCH_ALLIES:
            await ctx.send("This war is not accepting allies right now.", ephemeral=True)
            return

        if is_roster_full(war.get("lineup", [])):
            await ctx.send("This roster is already full (5/5).", ephemeral=True)
            return

        if _player_in_lineup(war.get("lineup", []), ctx.author.id):
            await ctx.send("You are already on this roster.", ephemeral=True)
            return

        if self._is_author(war, ctx.author.id):
            await ctx.send("You cannot join your own war as an ally.", ephemeral=True)
            return

        rows = [
            ActionRow(
                Button(
                    style=ButtonStyle.PRIMARY,
                    label="Join as Runner",
                    custom_id=f"war_ally_runner:{war_id}",
                ),
                Button(
                    style=ButtonStyle.SUCCESS,
                    label="Join as Bagger",
                    custom_id=f"war_ally_bagger:{war_id}",
                ),
            )
        ]
        await ctx.send(
            f"Choose your role for **{war.get('team_name')}** ({ally_slots_remaining(war.get('lineup', []))} slot(s) left).",
            components=rows,
            ephemeral=True,
        )

    @component_callback(re.compile(r"^war_ally_(runner|bagger):(.+)$"))
    async def join_ally_confirm(self, ctx: ComponentContext):
        match = re.match(r"^war_ally_(runner|bagger):(.+)$", ctx.custom_id)
        role_key = match.group(1)
        war_id = match.group(2)

        found = self._get_war(war_id)
        if not found:
            await ctx.send("This war post no longer exists.", ephemeral=True)
            return

        war_type, war = found
        lineup = war.get("lineup", [])

        if war.get("status") != "open" or war.get("search_mode") != SEARCH_ALLIES:
            await ctx.send("This war is not accepting allies right now.", ephemeral=True)
            return

        if is_roster_full(lineup):
            await ctx.send("This roster is already full (5/5).", ephemeral=True)
            return

        if _player_in_lineup(lineup, ctx.author.id):
            await ctx.send("You are already on this roster.", ephemeral=True)
            return

        is_bagger = role_key == "bagger"
        role_name = "Bagger" if is_bagger else "Runner"
        lineup.append(
            Player(
                player=ctx.author.display_name,
                role=role_name,
                ally=True,
                bagger=is_bagger,
                discord_id=ctx.author.id,
            ).to_dict()
        )
        war["lineup"] = lineup

        if war.get("search_mode") == SEARCH_OPPONENTS and not can_seek_opponents(lineup):
            war["search_mode"] = SEARCH_ALLIES

        war = _save_and_refresh(war_type, war)
        await ctx.send(
            f"You joined **{war.get('team_name')}** as **{role_name}**.",
            ephemeral=True,
        )
        await self._edit_billboard_message(war_type, war, ctx.message.id)

    @component_callback(re.compile(r"^war_seek_opponents:(.+)$"))
    async def seek_opponents(self, ctx: ComponentContext):
        war_id = ctx.custom_id.split(":", 1)[1]
        found = self._get_war(war_id)
        if not found:
            await ctx.send("This war post no longer exists.", ephemeral=True)
            return

        war_type, war = found
        if not self._is_author(war, ctx.author.id):
            await ctx.send("Only the war author can switch to opponent search.", ephemeral=True)
            return

        if not can_seek_opponents(war.get("lineup", [])):
            await ctx.send(
                "You need a **5/5** lineup with **at least 1 bagger** before looking for opponents.",
                ephemeral=True,
            )
            return

        war["search_mode"] = SEARCH_OPPONENTS
        war = _save_and_refresh(war_type, war)
        await ctx.send("Your post is now **Looking For Opponents**.", ephemeral=True)
        await self._edit_billboard_message(war_type, war, ctx.message.id)

    @component_callback(re.compile(r"^war_seek_allies:(.+)$"))
    async def seek_allies(self, ctx: ComponentContext):
        war_id = ctx.custom_id.split(":", 1)[1]
        found = self._get_war(war_id)
        if not found:
            await ctx.send("This war post no longer exists.", ephemeral=True)
            return

        war_type, war = found
        if not self._is_author(war, ctx.author.id):
            await ctx.send("Only the war author can switch back to ally search.", ephemeral=True)
            return

        war["search_mode"] = SEARCH_ALLIES
        war = _save_and_refresh(war_type, war)
        await ctx.send("Your post is now **Looking For Allies**.", ephemeral=True)
        await self._edit_billboard_message(war_type, war, ctx.message.id)

    @component_callback(re.compile(r"^war_accept:(.+)$"))
    async def accept_war(self, ctx: ComponentContext):
        war_id = ctx.custom_id.split(":", 1)[1]
        found = self._get_war(war_id)
        if not found:
            await ctx.send("This war post no longer exists.", ephemeral=True)
            return

        target_type, target_war = found

        if target_war.get("status") != "open":
            await ctx.send("This war is no longer available.", ephemeral=True)
            return

        if target_war.get("search_mode") != SEARCH_OPPONENTS:
            await ctx.send("This team is still looking for allies, not opponents.", ephemeral=True)
            return

        if not can_seek_opponents(target_war.get("lineup", [])):
            await ctx.send("This team does not have a confirmed 5/5 lineup yet.", ephemeral=True)
            return

        if self._is_author(target_war, ctx.author.id):
            await ctx.send("You cannot accept your own war.", ephemeral=True)
            return

        from utils.billboard_store import find_war_by_author

        accepter_war = find_war_by_author(target_type, ctx.author.id)
        if not accepter_war:
            await ctx.send(
                "You need your own open war post in **Looking For Opponents** mode before accepting.",
                ephemeral=True,
            )
            return

        if accepter_war.get("search_mode") != SEARCH_OPPONENTS:
            await ctx.send("Switch your war to **Looking For Opponents** first (`Ready for Opponents` button).", ephemeral=True)
            return

        if not can_seek_opponents(accepter_war.get("lineup", [])):
            await ctx.send("Your roster must be **5/5** with at least **1 bagger** to accept.", ephemeral=True)
            return

        target_war["status"] = "matched"
        target_war["matched_opponent"] = {
            "war_id": accepter_war.get("war_id"),
            "team_name": accepter_war.get("team_name"),
            "author_discord_id": ctx.author.id,
        }

        accepter_war["status"] = "matched"
        accepter_war["matched_opponent"] = {
            "war_id": target_war.get("war_id"),
            "team_name": target_war.get("team_name"),
            "author_discord_id": target_war.get("author_discord_id"),
        }

        target_war = _save_and_refresh(target_type, target_war)
        accepter_war = _save_and_refresh(target_type, accepter_war)

        await ctx.send(
            f"You accepted **{target_war.get('team_name')}**'s war. Both posts are now matched.",
            ephemeral=True,
        )
        await self._edit_billboard_message(target_type, target_war, ctx.message.id)

    @component_callback(re.compile(r"^war_cancel:(.+)$"))
    async def cancel_war(self, ctx: ComponentContext):
        war_id = ctx.custom_id.split(":", 1)[1]
        found = self._get_war(war_id)
        if not found:
            await ctx.send("This war post no longer exists.", ephemeral=True)
            return

        war_type, war = found
        if not self._is_author(war, ctx.author.id):
            await ctx.send("Only the war author can cancel this post.", ephemeral=True)
            return

        if war.get("status") == "matched":
            opponent = war.get("matched_opponent") or {}
            opponent_id = opponent.get("war_id")
            if opponent_id:
                opponent_found = self._get_war(opponent_id)
                if opponent_found:
                    opp_type, opp_war = opponent_found
                    opp_war["status"] = "open"
                    opp_war["matched_opponent"] = None
                    _save_and_refresh(opp_type, opp_war)

        war["status"] = "cancelled"
        war["matched_opponent"] = None
        _save_and_refresh(war_type, war)
        delete_war(war_type, war_id)
        party_id = war.get("party_id")
        if party_id:
            from utils.queue_store import delete_party
            delete_party(party_id)

        try:
            await ctx.message.delete()
        except Exception:
            pass

        await ctx.send("War post cancelled.", ephemeral=True)

    @component_callback(re.compile(r"^war_delete:(.+)$"))
    async def delete_war_post(self, ctx: ComponentContext):
        war_id = ctx.custom_id.split(":", 1)[1]
        found = self._get_war(war_id)
        if not found:
            await ctx.send("This war post no longer exists.", ephemeral=True)
            return

        war_type, war = found
        if not self._is_author(war, ctx.author.id):
            await ctx.send("Only the war author can delete this post.", ephemeral=True)
            return

        if war.get("status") == "matched":
            opponent = war.get("matched_opponent") or {}
            opponent_id = opponent.get("war_id")
            if opponent_id:
                opponent_found = self._get_war(opponent_id)
                if opponent_found:
                    opp_type, opp_war = opponent_found
                    opp_war["status"] = "open"
                    opp_war["matched_opponent"] = None
                    _save_and_refresh(opp_type, opp_war)

        delete_war(war_type, war_id)
        party_id = war.get("party_id")
        if party_id:
            from utils.queue_store import delete_party
            delete_party(party_id)

        try:
            await ctx.message.delete()
        except Exception:
            pass

        await ctx.send("War post deleted.", ephemeral=True)


def setup(bot: interactions.Client):
    WarInteractions(bot)
