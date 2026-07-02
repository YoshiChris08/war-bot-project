from typing import Any, Dict, List, Optional

from interactions import ActionRow, Button, ButtonStyle

from utils.roster import (
    SEARCH_ALLIES,
    SEARCH_OPPONENTS,
    ally_slots_remaining,
    can_seek_opponents,
    is_roster_full,
)


def build_war_buttons(war: Dict[str, Any]) -> Optional[List[ActionRow]]:
    war_id = war.get("war_id")
    status = war.get("status", "open")
    search_mode = war.get("search_mode", SEARCH_ALLIES)
    lineup = war.get("lineup", [])

    if not war_id or status != "open":
        if status == "matched":
            return [
                ActionRow(
                    Button(
                        style=ButtonStyle.SECONDARY,
                        label="Matched",
                        custom_id=f"war_matched:{war_id}",
                        disabled=True,
                    )
                )
            ]
        return None

    rows: List[ActionRow] = []

    if search_mode == SEARCH_ALLIES:
        join_disabled = is_roster_full(lineup)
        rows.append(
            ActionRow(
                Button(
                    style=ButtonStyle.PRIMARY,
                    label="Join as Ally",
                    custom_id=f"war_join_ally:{war_id}",
                    disabled=join_disabled,
                ),
                Button(
                    style=ButtonStyle.SUCCESS,
                    label="Ready for Opponents",
                    custom_id=f"war_seek_opponents:{war_id}",
                    disabled=not can_seek_opponents(lineup),
                ),
            )
        )
    else:
        rows.append(
            ActionRow(
                Button(
                    style=ButtonStyle.SUCCESS,
                    label="Accept War",
                    custom_id=f"war_accept:{war_id}",
                    disabled=not can_seek_opponents(lineup),
                ),
                Button(
                    style=ButtonStyle.SECONDARY,
                    label="Back to Allies",
                    custom_id=f"war_seek_allies:{war_id}",
                ),
            )
        )

    rows.append(
        ActionRow(
            Button(
                style=ButtonStyle.DANGER,
                label="Cancel",
                custom_id=f"war_cancel:{war_id}",
            ),
            Button(
                style=ButtonStyle.SECONDARY,
                label="Delete Post",
                custom_id=f"war_delete:{war_id}",
            ),
        )
    )

    return rows
