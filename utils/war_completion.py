from typing import Any, Dict, Optional, Tuple

import interactions

from utils.billboard_refresh import remove_war_from_billboards
from utils.billboard_store import delete_war, find_war_across_boards
from utils.match_session_store import delete_session, get_session_by_channel, get_session_by_war_id
from utils.mmr import apply_ranked_war_mmr
from utils.queue_store import delete_party, get_party
from utils.table_bot import sync_war_result
from utils.war_results_store import append_result
from classes.queue_party import MODE_RANKED


async def _delete_channel(bot: interactions.Client, channel_id: Optional[int]) -> None:
    if not channel_id:
        return
    try:
        channel = await bot.fetch_channel(channel_id)
        if channel:
            await channel.delete()
    except Exception as exc:
        print(f"❌ Failed to delete channel {channel_id}: {exc}")


async def _delete_lobby_message(bot: interactions.Client, party: Dict[str, Any]) -> None:
    channel_id = party.get("lobby_channel_id")
    message_id = party.get("lobby_message_id")
    if not channel_id or not message_id:
        return
    try:
        channel = await bot.fetch_channel(channel_id)
        message = await channel.fetch_message(message_id)
        await message.delete()
    except Exception:
        pass


def _opponent_war(war: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    opponent = war.get("matched_opponent") or {}
    opponent_id = opponent.get("war_id")
    if not opponent_id:
        return None
    return find_war_across_boards(opponent_id)


async def finalize_war_completion(
    bot: interactions.Client,
    board: str,
    winner_war: Dict[str, Any],
    loser_war: Dict[str, Any],
    point_margin: int,
    table_reference: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record result, update MMR (ranked), clean up queues/billboards/channels."""
    mode = winner_war.get("mode", MODE_RANKED)
    winner_lineup = winner_war.get("lineup", [])
    loser_lineup = loser_war.get("lineup", [])

    mmr_delta = 0
    per_player: Dict[str, int] = {}
    if mode == MODE_RANKED:
        mmr_delta, per_player = apply_ranked_war_mmr(winner_lineup, loser_lineup, point_margin)

    table_reference = table_reference or {}
    result = append_result(
        {
            "board": board,
            "mode": mode,
            "war_type": winner_war.get("war_type", "RT"),
            "winner_war_id": winner_war.get("war_id"),
            "loser_war_id": loser_war.get("war_id"),
            "winner_team_name": winner_war.get("team_name"),
            "loser_team_name": loser_war.get("team_name"),
            "winner_guild_id": winner_war.get("origin_guild_id"),
            "loser_guild_id": loser_war.get("origin_guild_id"),
            "point_margin": point_margin,
            "winner_lineup": winner_lineup,
            "loser_lineup": loser_lineup,
            "team_mmr_delta": mmr_delta,
            "player_mmr_deltas": per_player,
            "sync_method": table_reference.get("sync_method"),
            "rxx": table_reference.get("rxx"),
            "team_scores": table_reference.get("team_scores"),
        }
    )

    synced = await sync_war_result(result)
    if synced:
        result["table_bot_synced"] = True

    session = get_session_by_war_id(winner_war.get("war_id", ""))
    if session:
        await _delete_channel(bot, session.get("channel_a_id"))
        await _delete_channel(bot, session.get("channel_b_id"))
        delete_session(session["session_id"])

    for war in (winner_war, loser_war):
        war_id = war.get("war_id")
        if war_id:
            delete_war(board, war_id)
            await remove_war_from_billboards(bot, board, war_id)

    for war in (winner_war, loser_war):
        party_id = war.get("party_id")
        if not party_id:
            continue
        party = get_party(party_id)
        if party:
            await _delete_lobby_message(bot, party)
        delete_party(party_id)

    return result


async def notify_teams_for_score_collection(
    bot: interactions.Client,
    pending: Dict[str, Any],
    reporter_war: Dict[str, Any],
    opponent_war: Dict[str, Any],
    winner_name: str,
    session: Dict[str, Any],
) -> None:
    from utils.wiimmfi import build_score_entry_instructions

    header = (
        f"**{pending['reporter_team_name']}** started match completion "
        f"(winner: **{winner_name}**, margin: `{pending['point_margin']}`).\n"
        "Each **captain** runs `/queue submit-scores` in this channel.\n\n"
    )

    for war in (reporter_war, opponent_war):
        guild_id = war.get("origin_guild_id")
        channel_id = None
        if session.get("guild_a_id") == guild_id:
            channel_id = session.get("channel_a_id")
        elif session.get("guild_b_id") == guild_id:
            channel_id = session.get("channel_b_id")
        if not channel_id:
            continue
        try:
            channel = await bot.fetch_channel(channel_id)
            await channel.send(
                f"<@{war.get('author_discord_id')}> — {header}"
                f"{build_score_entry_instructions(war.get('lineup', []))}"
            )
        except Exception as exc:
            print(f"❌ Failed to request scores in war channel {channel_id}: {exc}")


def _war_channel_for_guild(session: Dict[str, Any], guild_id: int) -> Optional[int]:
    if session.get("guild_a_id") == guild_id:
        return session.get("channel_a_id")
    if session.get("guild_b_id") == guild_id:
        return session.get("channel_b_id")
    return None


async def notify_teams_for_confirmation(
    bot: interactions.Client,
    pending: Dict[str, Any],
    winner_name: str,
    loser_name: str,
) -> None:
    from utils.wiimmfi import format_scores_for_confirmation, format_table_reference_summary

    session = get_session_by_war_id(pending.get("reporter_war_id", ""))
    if not session:
        session = get_session_by_war_id(pending.get("opponent_war_id", ""))
    if not session:
        return

    table_line = format_table_reference_summary(pending)
    scores_block = ""
    if pending.get("sync_method") == "player_scores":
        scores_block = "\n" + format_scores_for_confirmation(
            {"sync_method": "player_scores", "team_scores": pending.get("team_scores")}
        )

    body = (
        f"**{pending['reporter_team_name']}** reported a result:\n"
        f"**Winner:** {winner_name}\n"
        f"**Loser:** {loser_name}\n"
        f"**Margin:** `{pending['point_margin']}` points\n"
        f"{table_line}"
        f"{scores_block}\n\n"
        "Both captains must run `/queue confirm` in their war channel.\n"
        "Dispute: `/queue dispute`"
    )

    for captain_id, guild_id in (
        (pending.get("reporter_captain_id"), pending.get("reporter_guild_id")),
        (pending.get("opponent_captain_id"), pending.get("opponent_guild_id")),
    ):
        if not captain_id or not guild_id:
            continue
        channel_id = _war_channel_for_guild(session, guild_id)
        if not channel_id:
            continue
        try:
            channel = await bot.fetch_channel(channel_id)
            await channel.send(content=f"<@{captain_id}> — {body}")
        except Exception as exc:
            print(f"❌ Failed to notify captain {captain_id} in war channel {channel_id}: {exc}")


async def notify_opponent_confirmation(
    bot: interactions.Client,
    pending: Dict[str, Any],
    winner_name: str,
    loser_name: str,
) -> None:
    """Notify both war channels that a result is ready for confirmation."""
    await notify_teams_for_confirmation(bot, pending, winner_name, loser_name)
