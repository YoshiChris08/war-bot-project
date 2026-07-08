import os
from dotenv import load_dotenv

load_dotenv(".env.local")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "temp")

PROJECT_ENV = os.getenv("PROJECT_ENVIRONMENT", "local").lower()
DEV = PROJECT_ENV == "local"


def _parse_int_list(raw: str) -> list[int]:
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return ids


def _parse_guild_ids() -> list[int]:
    """DEV slash commands register to these guilds (instant). Comma-separate for multiple servers."""
    for env_name in ("GUILD_IDS", "GUILD_ID"):
        raw = os.getenv(env_name)
        if raw:
            ids = _parse_int_list(raw)
            if ids:
                return ids

    return [1436538029316636705]


GUILD_IDS = _parse_guild_ids()
GUILD_ID = GUILD_IDS[0]
SCOPES = GUILD_IDS if DEV else None

RT_CHANNEL_ID = int(os.getenv("RT_WAR_ID")) if os.getenv("RT_WAR_ID") else None
CT_CHANNEL_ID = int(os.getenv("CT_WAR_ID")) if os.getenv("CT_WAR_ID") else None


def track_to_type(track_type: str) -> str:
    return "ct" if track_type.upper() == "CT" else "rt"
