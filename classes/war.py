import uuid
from datetime import datetime
from typing import List, Dict, Any
from classes.player import Player



class War:
    """Represents a Mario Kart Wii war (match) configuration."""

    def __init__(
        self,
        war_type: str,
        team_name: str,
        gathered: bool = False,
        search_in_advance: bool = False,
        start_time: str = None,
        last_updated: str = None,
        ally_count: int = 0,
        lineup: List[Player] = None,
        war_id: str = None,
    ):
        self.war_id = war_id or str(uuid.uuid4())
        self.war_type = war_type.upper()
        self.team_name = team_name
        self.gathered = gathered
        self.search_in_advance = search_in_advance
        self.start_time = start_time or datetime.utcnow().isoformat()
        self.last_updated = datetime.utcnow().isoformat()
        self.ally_count = ally_count
        self.lineup = lineup or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "war_id": self.war_id,
            "war_type": self.war_type,
            "team_name": self.team_name,
            "gathered": self.gathered,
            "search_in_advance": self.search_in_advance,
            "start_time": self.start_time,
            "last_updated": self.last_updated,
            "ally_count": self.ally_count,
            "lineup": [p.to_dict() for p in self.lineup],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "War":
        lineup = [Player.from_dict(p) for p in data.get("lineup", [])]
        return cls(
            war_type=data.get("war_type", "RT"),
            team_name=data.get("team_name", ""),
            gathered=data.get("gathered", False),
            search_in_advance=data.get("search_in_advance", False),
            start_time=data.get("start_time"),
            ally_count=data.get("ally_count", 0),
            lineup=lineup,
            war_id=data.get("war_id"),
        )
