"""Billboard board keys: {rt|ct}-{ranked|casual}."""

from classes.queue_party import MODE_CASUAL, MODE_RANKED

ALL_BOARD_KEYS = ("rt-ranked", "rt-casual", "ct-ranked", "ct-casual")


def board_key(war_type: str, mode: str) -> str:
    track = "ct" if str(war_type).upper() == "CT" else "rt"
    ladder = MODE_CASUAL if mode == MODE_CASUAL else MODE_RANKED
    return f"{track}-{ladder}"


def parse_board_key(key: str) -> tuple[str, str]:
    """Return (war_type 'RT'|'CT', mode 'ranked'|'casual')."""
    parts = key.lower().split("-", 1)
    if len(parts) != 2:
        return "RT", MODE_RANKED
    track, ladder = parts
    return ("CT" if track == "ct" else "RT", ladder if ladder in (MODE_CASUAL, MODE_RANKED) else MODE_RANKED)


def board_label(board_key: str) -> str:
    war_type, mode = parse_board_key(board_key)
    return f"{war_type} · {mode.title()}"


board_for_war = board_key
