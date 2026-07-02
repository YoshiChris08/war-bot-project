import uuid
from datetime import datetime
from typing import Any, Dict


class Team:
    """Registered MKWii team tied to a Discord server."""

    def __init__(
        self,
        guild_id: int,
        name: str,
        team_id: str = None,
        registered_at: str = None,
    ):
        self.team_id = team_id or str(uuid.uuid4())
        self.guild_id = guild_id
        self.name = name
        self.registered_at = registered_at or datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "guild_id": self.guild_id,
            "name": self.name,
            "registered_at": self.registered_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Team":
        return cls(
            team_id=data.get("team_id"),
            guild_id=data.get("guild_id"),
            name=data.get("name", ""),
            registered_at=data.get("registered_at"),
        )
