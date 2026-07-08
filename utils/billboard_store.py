import json
import os
from typing import Any, Dict, List, Optional

from utils.boards import ALL_BOARD_KEYS, board_key as make_board_key
from utils.config import DATA_DIR

BILLBOARD_DIR = os.path.join(DATA_DIR, "billboard-data")


def billboard_path(board: str) -> str:
    return os.path.join(BILLBOARD_DIR, f"{board}-billboard.json")


def _legacy_path(board: str) -> Optional[str]:
    """Migrate old rt-billboard.json → rt-ranked-billboard.json."""
    if board == "rt-ranked":
        legacy = os.path.join(BILLBOARD_DIR, "rt-billboard.json")
        return legacy if os.path.exists(legacy) else None
    if board == "ct-ranked":
        legacy = os.path.join(BILLBOARD_DIR, "ct-billboard.json")
        return legacy if os.path.exists(legacy) else None
    return None


def load_wars(board: str) -> List[Dict[str, Any]]:
    path = billboard_path(board)
    if not os.path.exists(path):
        legacy = _legacy_path(board)
        if legacy:
            path = legacy
        else:
            return []

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        print(f"⚠️ {board} billboard JSON is corrupted.")
        return []
    except Exception as exc:
        print(f"❌ Failed to load {board} billboard: {exc}")
        return []


def save_wars(board: str, wars: List[Dict[str, Any]]) -> None:
    path = billboard_path(board)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(wars, handle, indent=2, ensure_ascii=False)


def find_war(board: str, war_id: str) -> Optional[Dict[str, Any]]:
    for war in load_wars(board):
        if war.get("war_id") == war_id:
            return war
    return None


def find_war_by_author(board: str, author_discord_id: int) -> Optional[Dict[str, Any]]:
    for war in load_wars(board):
        if war.get("author_discord_id") == author_discord_id and war.get("status", "open") == "open":
            return war
    return None


def upsert_war(board: str, war: Dict[str, Any]) -> None:
    wars = load_wars(board)
    war_id = war.get("war_id")
    updated = False
    for index, existing in enumerate(wars):
        if existing.get("war_id") == war_id:
            wars[index] = war
            updated = True
            break
    if not updated:
        wars.append(war)
    save_wars(board, wars)


def delete_war(board: str, war_id: str) -> bool:
    wars = load_wars(board)
    new_wars = [war for war in wars if war.get("war_id") != war_id]
    if len(new_wars) == len(wars):
        return False
    save_wars(board, new_wars)
    return True


def find_post_by_party_id(party_id: str) -> Optional[tuple[str, Dict[str, Any]]]:
    for board in ALL_BOARD_KEYS:
        for war in load_wars(board):
            if war.get("party_id") == party_id:
                return board, war
    return None


def find_war_across_boards(war_id: str) -> Optional[tuple[str, Dict[str, Any]]]:
    for board in ALL_BOARD_KEYS:
        war = find_war(board, war_id)
        if war:
            return board, war
    return None


def board_for_war(war_type: str, mode: str) -> str:
    return make_board_key(war_type, mode)
