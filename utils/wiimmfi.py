import re
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_RUNNER_SLOTS = 4


def normalize_rxx(raw: str) -> Optional[str]:
    text = (raw or "").strip().lower()
    if not text:
        return None
    if text.startswith("r"):
        text = text[1:]
    if not text.isdigit() or not (4 <= len(text) <= 6):
        return None
    return f"r{text}"


def parse_score_token(raw: str) -> Tuple[Optional[int], Optional[str]]:
    text = (raw or "").strip()
    if not text:
        return None, "Empty score value."
    if text.lstrip("-").isdigit():
        return int(text), None
    return None, f"Invalid number: `{raw}`"


def sort_lineup_for_scores(lineup: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    runners = [
        player
        for player in lineup or []
        if not (player.get("bagger") or player.get("role") == "Bagger")
    ]
    baggers = [
        player
        for player in lineup or []
        if player.get("bagger") or player.get("role") == "Bagger"
    ]
    return runners + baggers


def score_entry_order_labels(lineup: List[Dict[str, Any]]) -> List[str]:
    """Human labels for the expected score order (players then penalties)."""
    ordered = sort_lineup_for_scores(lineup)
    labels: List[str] = []
    runner_num = 1
    for player in ordered:
        name = player.get("player", "Unknown")
        if player.get("bagger") or player.get("role") == "Bagger":
            labels.append(f"Bagger ({name})")
        else:
            labels.append(f"Player {runner_num} ({name})")
            runner_num += 1
    labels.append("Penalties")
    return labels


def build_score_entry_instructions(lineup: List[Dict[str, Any]]) -> str:
    labels = score_entry_order_labels(lineup)
    player_labels = labels[:-1]
    example_values = ["79", "81", "100", "91", "4", "-5"]
    while len(example_values) < len(labels):
        example_values.insert(-1, "0")
    example = " ".join(example_values[: len(labels)])
    order_line = " → ".join(player_labels) + " → **Penalties**"
    return (
        f"Enter scores **space-separated** in this order:\n"
        f"{order_line}\n\n"
        f"Example: `{example}`\n"
        "*Penalties optional — omit the last value if there are none (assumed `0`).*"
    )


def parse_score_line(
    raw: str,
    lineup: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    ordered = sort_lineup_for_scores(lineup)
    if not ordered:
        return None, "This team has no players on the lineup."

    tokens = [part for part in re.split(r"\s+", (raw or "").strip()) if part]
    player_count = len(ordered)

    if len(tokens) == player_count:
        penalties = 0
        score_tokens = tokens
    elif len(tokens) == player_count + 1:
        score_tokens = tokens[:-1]
        penalty, error = parse_score_token(tokens[-1])
        if error:
            return None, f"Invalid penalties value: {error}"
        penalties = penalty
    else:
        labels = score_entry_order_labels(lineup)
        return None, (
            f"Expected **{player_count}** player scores"
            f"{' + optional penalties' if player_count else ''} "
            f"({' '.join(labels)}), but got **{len(tokens)}** value(s)."
        )

    players: List[Dict[str, Any]] = []
    for index, player in enumerate(ordered):
        score, error = parse_score_token(score_tokens[index])
        if error:
            name = player.get("player", "player")
            return None, f"Invalid score for **{name}**: {error}"
        players.append(
            {
                "player": player.get("player"),
                "role": player.get("role"),
                "bagger": bool(player.get("bagger") or player.get("role") == "Bagger"),
                "discord_id": player.get("discord_id"),
                "ally": bool(player.get("ally")),
                "score": score,
            }
        )

    return {
        "players": players,
        "penalties": penalties,
    }, None


def build_team_score_entry(war: Dict[str, Any], parsed: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "war_id": war.get("war_id"),
        "team_name": war.get("team_name"),
        "players": parsed.get("players", []),
        "penalties": parsed.get("penalties", 0),
    }


def build_table_reference_from_rxx(rxx: str) -> Dict[str, Any]:
    return {
        "sync_method": "rxx",
        "rxx": rxx,
        "team_scores": None,
    }


def build_table_reference_from_scores(
    winner_entry: Dict[str, Any],
    loser_entry: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "sync_method": "player_scores",
        "rxx": None,
        "team_scores": {
            "winner": winner_entry,
            "loser": loser_entry,
        },
    }


def format_table_reference_summary(table_ref: Dict[str, Any]) -> str:
    if table_ref.get("sync_method") == "rxx":
        return f"**Table:** `{table_ref.get('rxx')}`"
    team_scores = table_ref.get("team_scores") or {}
    parts = []
    for side in ("winner", "loser"):
        entry = team_scores.get(side) or {}
        if entry.get("team_name"):
            parts.append(entry["team_name"])
    return f"**Scores:** both teams submitted ({' vs '.join(parts) if parts else 'complete'})"


def format_scores_for_confirmation(table_ref: Dict[str, Any]) -> str:
    if table_ref.get("sync_method") == "rxx":
        return f"**Table RXX:** `{table_ref.get('rxx')}`"

    lines: List[str] = ["**Player scores:**"]
    team_scores = table_ref.get("team_scores") or {}
    for side in ("winner", "loser"):
        entry = team_scores.get(side) or {}
        team_name = entry.get("team_name", side.title())
        lines.append(f"\n**{team_name}**")
        for player in entry.get("players") or []:
            role = "Bagger" if player.get("bagger") else "Runner"
            lines.append(f"> {player.get('player', '?')} ({role}): `{player.get('score', 0)}`")
        penalties = entry.get("penalties", 0)
        if penalties:
            lines.append(f"> Penalties: `{penalties}`")
    return "\n".join(lines)
