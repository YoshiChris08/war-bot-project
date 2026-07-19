"""Match completion/cancel logic for `/war` in war comm channels."""

from typing import Optional

import interactions
from interactions import Modal, ParagraphText, ShortText

from utils.billboard_store import find_war_across_boards
from utils.match_session_store import get_session_by_channel
from utils.war_abort import abort_matched_war
from utils.war_cancel_store import (
    create_cancel_request,
    delete_cancel_request,
    find_cancel_for_war,
    get_cancel_request,
)
from utils.war_completion import (
    finalize_war_completion,
    notify_opponent_confirmation,
    notify_teams_for_score_collection,
)
from utils.rxx_scoring import build_scores_from_rxx, validate_rxx_margin
from utils.war_completion_store import (
    both_captains_confirmed,
    clear_team_scores,
    create_pending_collecting_scores,
    delete_pending,
    find_pending_for_war,
    get_pending,
    mark_pending_confirmation,
    record_captain_confirmation,
    upsert_team_scores,
)
from utils.wiimmfi import (
    build_score_entry_instructions,
    build_table_reference_from_scores,
    build_team_score_entry,
    normalize_rxx,
    parse_score_line,
    validate_reported_margin,
)


def _parse_margin(raw: str) -> tuple[int | None, Optional[str]]:
    text = (raw or "").strip()
    if not text.isdigit():
        return None, "Point margin must be a whole number (e.g. `15`)."
    margin = int(text)
    if margin < 1:
        return None, "Point margin must be at least **1**."
    return margin, None


def require_match_channel(ctx) -> tuple[dict, dict] | tuple[None, str]:
    session = get_session_by_channel(ctx.channel_id)
    if not session:
        return None, "This command only works in your **`war-vs-*`** match channel."
    return session, ""


def war_for_guild(session: dict, guild_id: int) -> Optional[dict]:
    if session.get("guild_a_id") == guild_id:
        war_id = session.get("war_a_id")
    elif session.get("guild_b_id") == guild_id:
        war_id = session.get("war_b_id")
    else:
        return None
    if not war_id:
        return None
    found = find_war_across_boards(war_id)
    return found[1] if found else None


def opponent_war(board: str, war: dict) -> Optional[dict]:
    opponent_id = (war.get("matched_opponent") or {}).get("war_id")
    if not opponent_id:
        return None
    found = find_war_across_boards(opponent_id)
    if not found:
        return None
    opp_board, opp_war = found
    if opp_board != board:
        return None
    return opp_war


async def send_to_guild_war_channel(bot, session: dict, guild_id: int, content: str) -> None:
    channel_id = None
    if session.get("guild_a_id") == guild_id:
        channel_id = session.get("channel_a_id")
    elif session.get("guild_b_id") == guild_id:
        channel_id = session.get("channel_b_id")
    if not channel_id:
        return
    try:
        channel = await bot.fetch_channel(channel_id)
        await channel.send(content)
    except Exception as exc:
        print(f"❌ Failed to send to war channel {channel_id}: {exc}")


async def maybe_finish_score_collection(bot, pending: dict, session: dict) -> bool:
    scores = pending.get("team_scores") or {}
    needed = {pending["reporter_war_id"], pending["opponent_war_id"]}
    if not needed.issubset(scores.keys()):
        return False

    winner_found = find_war_across_boards(pending["winner_war_id"])
    if not winner_found:
        return False
    board, winner_war = winner_found
    loser_id = (
        pending["opponent_war_id"]
        if pending["winner_war_id"] == pending["reporter_war_id"]
        else pending["reporter_war_id"]
    )
    loser_found = find_war_across_boards(loser_id)
    if not loser_found:
        return False
    _, loser_war = loser_found

    winner_entry = scores[winner_war["war_id"]]
    loser_entry = scores[loser_war["war_id"]]
    ok, margin_error = validate_reported_margin(
        winner_entry, loser_entry, int(pending["point_margin"])
    )
    if not ok:
        clear_team_scores(pending["completion_id"])
        notice = (
            f"⚠️ **Score margin mismatch** — {margin_error}\n"
            "Both captains must `/war scores` again with corrected values."
        )
        for guild_id in (pending.get("reporter_guild_id"), pending.get("opponent_guild_id")):
            await send_to_guild_war_channel(bot, session, guild_id, notice)
        return False

    table_ref = build_table_reference_from_scores(winner_entry, loser_entry)
    pending = mark_pending_confirmation(pending["completion_id"], table_ref)
    if not pending:
        return False

    await notify_opponent_confirmation(
        bot, pending, winner_war.get("team_name"), loser_war.get("team_name")
    )
    return True


async def handle_complete(
    bot,
    ctx,
    reporter_won: bool,
) -> None:
    session, error = require_match_channel(ctx)
    if error:
        await ctx.send(error, ephemeral=True)
        return

    war = war_for_guild(session, ctx.guild_id)
    if not war or war.get("status") != "matched":
        await ctx.send("No active matched war for this channel.", ephemeral=True)
        return
    if war.get("author_discord_id") != ctx.author.id:
        await ctx.send("Only your team's **captain** can complete the match.", ephemeral=True)
        return

    found = find_war_across_boards(war["war_id"])
    if not found:
        await ctx.send("War post not found.", ephemeral=True)
        return
    board, war = found

    if find_pending_for_war(war["war_id"]):
        await ctx.send("A completion is already in progress for this match.", ephemeral=True)
        return
    if find_cancel_for_war(war["war_id"]):
        await ctx.send("A cancel request is pending for this match.", ephemeral=True)
        return

    opp = opponent_war(board, war)
    if not opp:
        await ctx.send("Could not find opponent war.", ephemeral=True)
        return

    modal = Modal(
        ShortText(
            label="Points won by",
            custom_id="margin",
            placeholder="e.g. 15",
            required=True,
            max_length=4,
        ),
        ShortText(
            label="RXX room code",
            custom_id="rxx",
            placeholder="r12345",
            required=True,
            max_length=8,
        ),
        title="Complete match",
    )
    await ctx.send_modal(modal)
    m_ctx = await bot.wait_for_modal(modal, ctx.author)

    margin, margin_error = _parse_margin(m_ctx.kwargs.get("margin", ""))
    if margin_error:
        await m_ctx.send(margin_error, ephemeral=True)
        return

    winner_war = war if reporter_won else opp
    loser_war = opp if reporter_won else war
    rxx = normalize_rxx(m_ctx.kwargs.get("rxx", ""))
    if not rxx:
        await m_ctx.send("A valid **RXX** room code is required (e.g. `r12345`).", ephemeral=True)
        return

    table_ref, rxx_error = await build_scores_from_rxx(rxx, winner_war, loser_war, margin)
    if table_ref:
        pending = create_pending_collecting_scores(
            board,
            war,
            opp,
            winner_war["war_id"],
            margin,
            ctx.author.id,
            session.get("session_id"),
            rxx=rxx,
        )
        pending = mark_pending_confirmation(pending["completion_id"], table_ref)
        if not pending:
            await m_ctx.send("Could not save completion.", ephemeral=True)
            return
        await notify_opponent_confirmation(
            bot, pending, winner_war.get("team_name"), loser_war.get("team_name")
        )
        await m_ctx.send(
            f"Scores loaded from **`{rxx}`** — both captains must `/war confirm`.\n"
            f"**Winner:** {winner_war.get('team_name')} · **Margin:** `{margin}`",
            ephemeral=True,
        )
        return

    pending = create_pending_collecting_scores(
        board,
        war,
        opp,
        winner_war["war_id"],
        margin,
        ctx.author.id,
        session.get("session_id"),
        rxx=rxx,
        manual_fallback=True,
        fallback_reason=rxx_error,
    )
    fallback_note = (
        f"⚠️ Could not load scores from **`{rxx}`** — {rxx_error}\n"
        "**Manual fallback:** each captain must `/war scores` in their war channel."
    )
    for guild_id in (pending.get("reporter_guild_id"), pending.get("opponent_guild_id")):
        await send_to_guild_war_channel(bot, session, guild_id, fallback_note)
    await m_ctx.send(
        f"RXX lookup failed — manual score entry required.\n{fallback_note}",
        ephemeral=True,
    )


async def handle_submit_scores(bot, ctx) -> None:
    session, error = require_match_channel(ctx)
    if error:
        await ctx.send(error, ephemeral=True)
        return

    war = war_for_guild(session, ctx.guild_id)
    if not war:
        await ctx.send("War not found for this channel.", ephemeral=True)
        return
    if war.get("author_discord_id") != ctx.author.id:
        await ctx.send("Only your team's **captain** can submit scores.", ephemeral=True)
        return

    pending = find_pending_for_war(war["war_id"])
    if not pending or pending.get("status") != "collecting_scores":
        await ctx.send("This match is not waiting for score submissions.", ephemeral=True)
        return

    if not pending.get("manual_fallback"):
        await ctx.send(
            "Scores are loaded from the **RXX** room automatically. "
            "`/war scores` is only available when RXX lookup failed.",
            ephemeral=True,
        )
        return

    if (pending.get("team_scores") or {}).get(war["war_id"]):
        await ctx.send("Your team already submitted scores.", ephemeral=True)
        return

    instructions = build_score_entry_instructions(war.get("lineup", []))
    modal = Modal(
        ParagraphText(
            label="Scores (space separated)",
            custom_id="score_line",
            placeholder="79 81 100 91 4 -5",
            required=True,
        ),
        title=f"{war.get('team_name', 'Team')[:40]} scores",
    )
    await ctx.send_modal(modal)
    m_ctx = await bot.wait_for_modal(modal, ctx.author)

    parsed, parse_error = parse_score_line(m_ctx.kwargs.get("score_line", ""), war.get("lineup", []))
    if parse_error:
        await m_ctx.send(f"{parse_error}\n\n{instructions}", ephemeral=True)
        return

    pending = upsert_team_scores(
        pending["completion_id"], war["war_id"], build_team_score_entry(war, parsed)
    )
    if not pending:
        await m_ctx.send("Submission window closed.", ephemeral=True)
        return

    pen = parsed.get("penalties", 0)
    pen_note = f" · Penalties: `{pen}`" if pen else ""
    await m_ctx.send(f"Scores saved{pen_note}.", ephemeral=True)

    await maybe_finish_score_collection(bot, pending, session)


async def handle_confirm(bot, ctx) -> None:
    session, error = require_match_channel(ctx)
    if error:
        await ctx.send(error, ephemeral=True)
        return

    war = war_for_guild(session, ctx.guild_id)
    if not war:
        await ctx.send("War not found.", ephemeral=True)
        return

    pending = find_pending_for_war(war["war_id"])
    if not pending or pending.get("status") != "pending_confirmation":
        await ctx.send("Nothing to confirm for this match.", ephemeral=True)
        return

    captain_ids = {pending.get("reporter_captain_id"), pending.get("opponent_captain_id")}
    if ctx.author.id not in captain_ids:
        await ctx.send("Only a **team captain** can confirm.", ephemeral=True)
        return

    if ctx.author.id in (pending.get("confirmed_by") or []):
        await ctx.send("You already confirmed this result.", ephemeral=True)
        return

    pending = record_captain_confirmation(pending["completion_id"], ctx.author.id)
    if not pending:
        await ctx.send("Confirmation window closed.", ephemeral=True)
        return

    if not both_captains_confirmed(pending):
        other_id = (
            pending["opponent_captain_id"]
            if ctx.author.id == pending.get("reporter_captain_id")
            else pending["reporter_captain_id"]
        )
        await ctx.send(
            "Your confirmation was recorded. Waiting for the other captain to `/war confirm`.",
            ephemeral=True,
        )
        for guild_id in (pending.get("reporter_guild_id"), pending.get("opponent_guild_id")):
            await send_to_guild_war_channel(
                bot,
                session,
                guild_id,
                f"<@{other_id}> — Your opponent confirmed the result. Run `/war confirm` to finalize.",
            )
        return

    board = pending["board"]
    winner_found = find_war_across_boards(pending["winner_war_id"])
    if not winner_found:
        delete_pending(pending["completion_id"])
        await ctx.send("War data missing.", ephemeral=True)
        return
    _, winner_war = winner_found

    loser_id = (
        pending["opponent_war_id"]
        if pending["winner_war_id"] == pending["reporter_war_id"]
        else pending["reporter_war_id"]
    )
    loser_found = find_war_across_boards(loser_id)
    if not loser_found:
        delete_pending(pending["completion_id"])
        await ctx.send("Opponent war missing.", ephemeral=True)
        return
    _, loser_war = loser_found

    table_ref = {
        "sync_method": pending.get("sync_method"),
        "rxx": pending.get("rxx"),
        "team_scores": pending.get("team_scores"),
    }

    if pending.get("sync_method") == "player_scores":
        team_scores = pending.get("team_scores") or {}
        winner_entry = team_scores.get("winner") or {}
        loser_entry = team_scores.get("loser") or {}
        ok, margin_error = validate_reported_margin(
            winner_entry, loser_entry, int(pending["point_margin"])
        )
        if not ok:
            delete_pending(pending["completion_id"])
            await ctx.send(f"Cannot finalize: {margin_error}", ephemeral=True)
            for guild_id in (pending.get("reporter_guild_id"), pending.get("opponent_guild_id")):
                await send_to_guild_war_channel(
                    bot,
                    session,
                    guild_id,
                    f"⚠️ Result blocked — {margin_error} Use `/war complete` to resubmit.",
                )
            return

    if pending.get("sync_method") == "rxx" and pending.get("rxx"):
        ok, rxx_error = await validate_rxx_margin(
            pending["rxx"],
            int(pending["point_margin"]),
            winner_war,
            loser_war,
        )
        if not ok and rxx_error:
            delete_pending(pending["completion_id"])
            await ctx.send(f"Cannot finalize: {rxx_error}", ephemeral=True)
            for guild_id in (pending.get("reporter_guild_id"), pending.get("opponent_guild_id")):
                await send_to_guild_war_channel(
                    bot,
                    session,
                    guild_id,
                    f"⚠️ RXX margin mismatch — {rxx_error} Use `/war complete` to resubmit.",
                )
            return

    result = await finalize_war_completion(
        bot, board, winner_war, loser_war, int(pending["point_margin"]), table_ref
    )
    delete_pending(pending["completion_id"])

    mmr_note = ""
    if pending.get("mode") == "ranked" and result.get("team_mmr_delta"):
        mmr_note = f" MMR ±`{result['team_mmr_delta']}` per core roster player."

    summary = (
        f"**War complete** — **{result.get('winner_team_name')}** beat "
        f"**{result.get('loser_team_name')}** by **{pending['point_margin']}** pts.{mmr_note}"
    )
    await ctx.send(summary, ephemeral=True)
    for guild_id in (pending.get("reporter_guild_id"), pending.get("opponent_guild_id")):
        await send_to_guild_war_channel(bot, session, guild_id, summary)


async def handle_dispute(bot, ctx) -> None:
    session, error = require_match_channel(ctx)
    if error:
        await ctx.send(error, ephemeral=True)
        return

    war = war_for_guild(session, ctx.guild_id)
    if not war:
        return

    pending = find_pending_for_war(war["war_id"])
    if not pending or pending.get("status") != "pending_confirmation":
        await ctx.send("Nothing to dispute.", ephemeral=True)
        return

    captain_ids = {pending.get("reporter_captain_id"), pending.get("opponent_captain_id")}
    if ctx.author.id not in captain_ids:
        await ctx.send("Only a **team captain** can dispute.", ephemeral=True)
        return

    delete_pending(pending["completion_id"])
    await ctx.send("Result disputed.", ephemeral=True)
    for guild_id in (pending.get("reporter_guild_id"), pending.get("opponent_guild_id")):
        await send_to_guild_war_channel(
            bot,
            session,
            guild_id,
            f"**{war.get('team_name')}** disputed the result. "
            "Captain: `/war complete` to resubmit.",
        )


async def handle_match_cancel(bot, ctx) -> None:
    session, error = require_match_channel(ctx)
    if error:
        await ctx.send(error, ephemeral=True)
        return

    war = war_for_guild(session, ctx.guild_id)
    if not war or war.get("status") != "matched":
        await ctx.send("No matched war in this channel.", ephemeral=True)
        return
    if war.get("author_discord_id") != ctx.author.id:
        await ctx.send("Only your team's **captain** can request cancel.", ephemeral=True)
        return

    found = find_war_across_boards(war["war_id"])
    if not found:
        await ctx.send("War not found.", ephemeral=True)
        return
    board, war = found

    if find_pending_for_war(war["war_id"]):
        await ctx.send("Finish or dispute the completion first.", ephemeral=True)
        return
    if find_cancel_for_war(war["war_id"]):
        await ctx.send("A cancel request is already pending.", ephemeral=True)
        return

    opp = opponent_war(board, war)
    if not opp:
        await ctx.send("Opponent not found.", ephemeral=True)
        return

    request = create_cancel_request(board, war, opp, ctx.author.id)
    await send_to_guild_war_channel(
        bot,
        session,
        opp.get("origin_guild_id"),
        (
            f"<@{opp.get('author_discord_id')}> — **{war.get('team_name')}** wants to cancel this match.\n"
            "Approve: `/war approve-cancel` · Decline: `/war decline-cancel`"
        ),
    )
    await ctx.send("Cancel request sent to the other team's war channel.", ephemeral=True)


async def handle_approve_cancel(bot, ctx) -> None:
    session, error = require_match_channel(ctx)
    if error:
        await ctx.send(error, ephemeral=True)
        return

    war = war_for_guild(session, ctx.guild_id)
    if not war:
        return

    request = find_cancel_for_war(war["war_id"])
    if not request or request.get("status") != "pending":
        await ctx.send("No cancel request to approve.", ephemeral=True)
        return
    if ctx.author.id != request.get("opponent_captain_id"):
        await ctx.send("Only the **opponent captain** can approve.", ephemeral=True)
        return

    board = request["board"]
    w1 = find_war_across_boards(request["requester_war_id"])
    w2 = find_war_across_boards(request["opponent_war_id"])
    if not w1 or not w2:
        delete_cancel_request(request["request_id"])
        await ctx.send("War data missing.", ephemeral=True)
        return

    await abort_matched_war(bot, board, w1[1], w2[1])
    delete_cancel_request(request["request_id"])

    summary = "**Match cancelled** — no result recorded."
    await ctx.send(summary, ephemeral=True)
    for guild_id in (request.get("requester_guild_id"), request.get("opponent_guild_id")):
        await send_to_guild_war_channel(bot, session, guild_id, summary)


async def handle_decline_cancel(bot, ctx) -> None:
    session, error = require_match_channel(ctx)
    if error:
        await ctx.send(error, ephemeral=True)
        return

    war = war_for_guild(session, ctx.guild_id)
    if not war:
        return

    request = find_cancel_for_war(war["war_id"])
    if not request or request.get("status") != "pending":
        await ctx.send("No cancel request to decline.", ephemeral=True)
        return
    if ctx.author.id != request.get("opponent_captain_id"):
        await ctx.send("Only the **opponent captain** can decline.", ephemeral=True)
        return

    delete_cancel_request(request["request_id"])
    await ctx.send("Cancel request declined.", ephemeral=True)
    await send_to_guild_war_channel(
        bot,
        session,
        request.get("requester_guild_id"),
        f"**{request.get('opponent_team_name')}** declined your cancel request.",
    )
