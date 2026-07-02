import os
from dotenv import load_dotenv

load_dotenv(".env.local")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "temp")

PROJECT_ENV = os.getenv("PROJECT_ENVIRONMENT", "local").lower()
DEV = PROJECT_ENV == "local"

GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else 1436538029316636705
SCOPES = [GUILD_ID] if DEV else None

RT_CHANNEL_ID = int(os.getenv("RT_WAR_ID")) if os.getenv("RT_WAR_ID") else None
CT_CHANNEL_ID = int(os.getenv("CT_WAR_ID")) if os.getenv("CT_WAR_ID") else None


def track_to_type(track_type: str) -> str:
    return "ct" if track_type.upper() == "CT" else "rt"
