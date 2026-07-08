from typing import List

from interactions import ActionRow, Button, ButtonStyle


def build_war_result_report_buttons(war_id: str) -> List[ActionRow]:
    return [
        ActionRow(
            Button(
                style=ButtonStyle.SUCCESS,
                label="Complete: We Won",
                custom_id=f"war_report_win:{war_id}",
            ),
            Button(
                style=ButtonStyle.DANGER,
                label="Complete: We Lost",
                custom_id=f"war_report_loss:{war_id}",
            ),
        ),
        ActionRow(
            Button(
                style=ButtonStyle.SECONDARY,
                label="Request Cancel",
                custom_id=f"war_request_cancel:{war_id}",
            ),
        ),
    ]


def build_submit_team_scores_button(completion_id: str, war_id: str) -> List[ActionRow]:
    return [
        ActionRow(
            Button(
                style=ButtonStyle.PRIMARY,
                label="Submit Team Scores",
                custom_id=f"war_submit_scores:{completion_id}:{war_id}",
            ),
        )
    ]


def build_war_result_confirm_buttons(completion_id: str) -> List[ActionRow]:
    return [
        ActionRow(
            Button(
                style=ButtonStyle.SUCCESS,
                label="Confirm Result",
                custom_id=f"war_confirm_result:{completion_id}",
            ),
            Button(
                style=ButtonStyle.DANGER,
                label="Dispute",
                custom_id=f"war_dispute_result:{completion_id}",
            ),
        )
    ]


def build_cancel_confirm_buttons(request_id: str) -> List[ActionRow]:
    return [
        ActionRow(
            Button(
                style=ButtonStyle.DANGER,
                label="Approve Cancel",
                custom_id=f"war_approve_cancel:{request_id}",
            ),
            Button(
                style=ButtonStyle.SECONDARY,
                label="Decline Cancel",
                custom_id=f"war_decline_cancel:{request_id}",
            ),
        )
    ]
