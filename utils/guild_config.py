import json
import os
from typing import Any, Dict, Optional

from utils.config import CT_CHANNEL_ID, DATA_DIR, RT_CHANNEL_ID

GUILD_CONFIG_PATH = os.path.join(DATA_DIR, "guild-config.json")


def _load_all() -> Dict[str, Any]:
    if not os.path.exists(GUILD_CONFIG_PATH):
        return {"guilds": {}}
    try:
        with open(GUILD_CONFIG_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if "guilds" not in data:
                return {"guilds": {}}
            return data
    except json.JSONDecodeError:
        return {"guilds": {}}


def _save_all(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(GUILD_CONFIG_PATH), exist_ok=True)
    with open(GUILD_CONFIG_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def get_guild_config(guild_id: int) -> Optional[Dict[str, Any]]:
    return _load_all()["guilds"].get(str(guild_id))


def upsert_guild_config(guild_id: int, guild_name: str, **fields) -> Dict[str, Any]:
    data = _load_all()
    key = str(guild_id)
    current = data["guilds"].get(key, {})
    current.update(fields)
    current["guild_id"] = guild_id
    current["name"] = guild_name
    data["guilds"][key] = current
    _save_all(data)
    return current


def delete_guild_config(guild_id: int) -> bool:
    data = _load_all()
    key = str(guild_id)
    if key not in data["guilds"]:
        return False
    del data["guilds"][key]
    _save_all(data)
    return True


def list_configured_billboard_channels(war_type: str) -> list[int]:
    """Return unique billboard channel IDs from guild configs."""
    channel_ids = []
    data = _load_all()
    field = "ct_channel_id" if war_type == "ct" else "rt_channel_id"
    for config in data.get("guilds", {}).values():
        channel_id = config.get(field)
        if channel_id and int(channel_id) not in channel_ids:
            channel_ids.append(int(channel_id))
    return channel_ids


def get_billboard_channel_id(guild_id: Optional[int], war_type: str) -> Optional[int]:
    if guild_id:
        config = get_guild_config(guild_id)
        if config:
            field = "ct_channel_id" if war_type.lower() == "ct" else "rt_channel_id"
            channel_id = config.get(field)
            if channel_id:
                return int(channel_id)

    return CT_CHANNEL_ID if war_type.lower() == "ct" else RT_CHANNEL_ID


def get_queue_channel_id(guild_id: int) -> Optional[int]:
    config = get_guild_config(guild_id)
    if config and config.get("queue_channel_id"):
        return int(config["queue_channel_id"])
    return None
