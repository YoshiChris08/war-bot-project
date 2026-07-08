from typing import Any, Dict, List, Optional

ROSTER_SIZE = 5
MIN_BAGGERS = 1

SEARCH_ALLIES = "allies"
SEARCH_OPPONENTS = "opponents"

PARTY_PREPARING = "preparing"
PARTY_POSTED = "posted"
PARTY_MATCHED = "matched"
PARTY_CANCELLED = "cancelled"

BAGGER_ICON = "🛍️"  # Discord :shopping_bags:
RUNNER_ICON = "🏃"


def lineup_size(lineup: List[Dict[str, Any]]) -> int:
    return len(lineup or [])


def count_baggers(lineup: List[Dict[str, Any]]) -> int:
    return sum(1 for player in lineup or [] if player.get("bagger") or player.get("role") == "Bagger")


def has_minimum_bagger(lineup: List[Dict[str, Any]]) -> bool:
    return count_baggers(lineup) >= MIN_BAGGERS


def is_roster_full(lineup: List[Dict[str, Any]]) -> bool:
    return lineup_size(lineup) >= ROSTER_SIZE


def ally_slots_remaining(lineup: List[Dict[str, Any]]) -> int:
    return max(0, ROSTER_SIZE - lineup_size(lineup))


def can_seek_opponents(lineup: List[Dict[str, Any]]) -> bool:
    return is_roster_full(lineup) and has_minimum_bagger(lineup)


def reconcile_search_mode(search_mode: str, lineup: List[Dict[str, Any]]) -> str:
    """Promote to opponent search at 5/5+bagger; demote if roster drops below."""
    mode = search_mode or SEARCH_ALLIES
    if mode == SEARCH_ALLIES and can_seek_opponents(lineup):
        return SEARCH_OPPONENTS
    if mode == SEARCH_OPPONENTS and not can_seek_opponents(lineup):
        return SEARCH_ALLIES
    return mode


def team_queue_lobby_active(party: Dict[str, Any]) -> bool:
    """
    Team-server queue buttons stay usable while forming a roster, including after
    posting to the hub billboard in allies mode.
    """
    status = party.get("status", PARTY_PREPARING)
    lineup = party.get("lineup", [])

    if status == PARTY_PREPARING:
        return True
    if status == PARTY_POSTED and party.get("search_mode", SEARCH_ALLIES) == SEARCH_ALLIES:
        return not is_roster_full(lineup)
    return False


def resolve_search_mode(requested: Optional[str], lineup: List[Dict[str, Any]]) -> Optional[str]:
    """
    Return the effective search mode, or None if opponents was requested but roster is not ready.
    """
    mode = (requested or SEARCH_ALLIES).lower()
    if mode == SEARCH_OPPONENTS and not can_seek_opponents(lineup):
        return None
    if mode not in (SEARCH_ALLIES, SEARCH_OPPONENTS):
        return SEARCH_ALLIES
    return mode


def party_status_label(status: str) -> str:
    labels = {
        "preparing": "Team Queue — forming roster",
        "posted": "On hub billboard",
        "matched": "Matched — awaiting gather",
        "cancelled": "Cancelled",
    }
    return labels.get(status, status)


def status_label(search_mode: str, status: str, lineup: List[Dict[str, Any]]) -> str:
    if status == "matched":
        return "Matched — awaiting gather"
    if status == "cancelled":
        return "Cancelled"
    if search_mode == SEARCH_OPPONENTS and can_seek_opponents(lineup):
        return "Looking For Opponents"
    return "Looking For Allies"


def format_lineup_entry(player: Dict[str, Any]) -> str:
    role_icon = BAGGER_ICON if player.get("bagger") or player.get("role") == "Bagger" else RUNNER_ICON
    ally_tag = " *(ally)*" if player.get("ally") else ""
    name = player.get("player", "Unknown")
    role = player.get("role", "Runner")
    return f"> {role_icon} **{name}** — {role}{ally_tag}"


def format_lineup(lineup: List[Dict[str, Any]]) -> str:
    if not lineup:
        return "> No players yet."
    return "\n".join(format_lineup_entry(player) for player in lineup)


def roster_summary(lineup: List[Dict[str, Any]]) -> str:
    size = lineup_size(lineup)
    baggers = count_baggers(lineup)
    allies = sum(1 for player in lineup if player.get("ally"))
    slots = ally_slots_remaining(lineup)
    bagger_ok = "✅" if has_minimum_bagger(lineup) else "❌"
    return (
        f"**Roster:** `{size}/{ROSTER_SIZE}` · "
        f"**Baggers:** `{baggers}` {bagger_ok} · "
        f"**Ally slots:** `{slots}` · "
        f"**Allies joined:** `{allies}`"
    )
