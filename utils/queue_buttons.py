from typing import Any, Dict, List

from interactions import ActionRow, Button, ButtonStyle

from utils.roster import (
    PARTY_CANCELLED,
    PARTY_MATCHED,
    PARTY_POSTED,
    PARTY_PREPARING,
    has_minimum_bagger,
    is_roster_full,
    team_queue_lobby_active,
)


def build_queue_party_buttons(party: Dict[str, Any]) -> List[ActionRow]:
    party_id = party.get("party_id")
    status = party.get("status", PARTY_PREPARING)

    if not party_id or status == PARTY_CANCELLED:
        return []

    if status == PARTY_MATCHED:
        return []

    cancel_row = ActionRow(
        Button(
            style=ButtonStyle.DANGER,
            label="Cancel Queue",
            custom_id=f"queue_cancel:{party_id}",
        ),
    )

    if status == PARTY_POSTED and not team_queue_lobby_active(party):
        return [cancel_row]

    if not team_queue_lobby_active(party):
        return []

    lineup = party.get("lineup", [])

    join_row = ActionRow(
        Button(
            style=ButtonStyle.PRIMARY,
            label="Join as Runner",
            custom_id=f"queue_join_runner:{party_id}",
            disabled=is_roster_full(lineup),
        ),
        Button(
            style=ButtonStyle.SUCCESS,
            label="Join as Bagger",
            custom_id=f"queue_join_bagger:{party_id}",
            disabled=is_roster_full(lineup),
        ),
        Button(
            style=ButtonStyle.SECONDARY,
            label="Leave Queue",
            custom_id=f"queue_leave:{party_id}",
        ),
    )

    action_row = cancel_row

    if status == PARTY_PREPARING:
        action_row = ActionRow(
            Button(
                style=ButtonStyle.SUCCESS,
                label="Post to Billboard",
                custom_id=f"queue_post:{party_id}",
                disabled=not has_minimum_bagger(lineup),
            ),
            Button(
                style=ButtonStyle.DANGER,
                label="Cancel Queue",
                custom_id=f"queue_cancel:{party_id}",
            ),
        )

    return [join_row, action_row]
