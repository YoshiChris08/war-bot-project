from typing import Dict, Any

class Player:
    """Represents a single player in a war lineup."""

    def __init__(self, player: str, role: str, ally: bool = False, bagger: bool = False):
        self.player = player
        self.role = role
        self.ally = ally
        self.bagger = bagger

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player": self.player,
            "role": self.role,
            "ally": self.ally,
            "bagger": self.bagger,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Player":
        return cls(
            player=data.get("player"),
            role=data.get("role"),
            ally=data.get("ally", False),
            bagger=data.get("bagger", False),  
        )
