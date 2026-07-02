from typing import Any, Dict, List, Optional

from interactions import ActionRow, Button, ButtonStyle

from utils.roster import has_minimum_bagger, is_roster_full


def build_queue_party_buttons(party: Dict[str, Any]) -> Optional[List[ActionRow]]:
    party_id = party.get("party_id")
    status = party.get("status", "preparing")
    lineup = party.get("lineup", [])

    if not party_id or status != "preparing":
        return None

    rows = [
        ActionRow(
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
        ),
        ActionRow(
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
        ),
    ]
    return rows
