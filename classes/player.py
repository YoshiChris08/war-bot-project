from typing import Dict, Any, Optional

class Player:
    """Represents a single player in a war lineup."""

    def __init__(
        self,
        player: str,
        role: str,
        ally: bool = False,
        bagger: bool = False,
        discord_id: Optional[int] = None,
    ):
        self.player = player
        self.role = role
        self.ally = ally
        self.bagger = bagger
        self.discord_id = discord_id

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "player": self.player,
            "role": self.role,
            "ally": self.ally,
            "bagger": self.bagger,
        }
        if self.discord_id is not None:
            data["discord_id"] = self.discord_id
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Player":
        return cls(
            player=data.get("player"),
            role=data.get("role"),
            ally=data.get("ally", False),
            bagger=data.get("bagger", False),
            discord_id=data.get("discord_id"),
        )
