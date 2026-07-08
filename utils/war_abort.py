from typing import Any, Dict, Optional

import interactions

from utils.billboard_refresh import remove_war_from_billboards
from utils.billboard_store import delete_war, find_war_across_boards
from utils.match_session_store import delete_session, get_session_by_war_id
from utils.queue_store import delete_party, get_party
from utils.war_completion_store import delete_pending, find_pending_for_war


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


async def abort_matched_war(
    bot: interactions.Client,
    board: str,
    war_a: Dict[str, Any],
    war_b: Dict[str, Any],
) -> None:
    """Tear down a matched war with no result (both captains agreed to cancel)."""
    for war in (war_a, war_b):
        pending = find_pending_for_war(war.get("war_id", ""))
        if pending:
            delete_pending(pending["completion_id"])

    session = get_session_by_war_id(war_a.get("war_id", "")) or get_session_by_war_id(
        war_b.get("war_id", "")
    )
    if session:
        await _delete_channel(bot, session.get("channel_a_id"))
        await _delete_channel(bot, session.get("channel_b_id"))
        delete_session(session["session_id"])

    for war in (war_a, war_b):
        war_id = war.get("war_id")
        if war_id:
            delete_war(board, war_id)
            await remove_war_from_billboards(bot, board, war_id)

    for war in (war_a, war_b):
        party_id = war.get("party_id")
        if not party_id:
            continue
        party = get_party(party_id)
        if party:
            await _delete_lobby_message(bot, party)
        delete_party(party_id)


def get_both_wars_from_id(war_id: str) -> Optional[tuple[str, Dict[str, Any], Dict[str, Any]]]:
    found = find_war_across_boards(war_id)
    if not found:
        return None
    board, war = found
    if war.get("status") != "matched":
        return None
    opponent_id = (war.get("matched_opponent") or {}).get("war_id")
    if not opponent_id:
        return None
    opponent_found = find_war_across_boards(opponent_id)
    if not opponent_found:
        return None
    _, opponent_war = opponent_found
    return board, war, opponent_war
