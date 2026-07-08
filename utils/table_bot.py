from typing import Any, Dict


async def sync_war_result(result: Dict[str, Any]) -> bool:
    """
    Future integration: MKW Table Bot (BadWolf) / WiimmFI.

    Uses `rxx` or per-player `team_scores` from the completed result.
    """
    sync_method = result.get("sync_method")
    if sync_method == "rxx":
        table_ref = f"RXX {result.get('rxx')}"
    elif sync_method == "player_scores":
        team_scores = result.get("team_scores") or {}
        parts = []
        for side in ("winner", "loser"):
            entry = team_scores.get(side) or {}
            name = entry.get("team_name", side)
            total = sum(p.get("score", 0) for p in entry.get("players") or [])
            pen = entry.get("penalties", 0)
            parts.append(f"{name} ({total} pts, pen {pen})")
        table_ref = " · ".join(parts)
    else:
        table_ref = "no table reference"

    print(
        "📊 Table Bot sync pending — "
        f"{result.get('winner_team_name')} beat {result.get('loser_team_name')} "
        f"by {result.get('point_margin')} pts "
        f"({result.get('board')}, {result.get('mode')}) · {table_ref}"
    )
    return False
