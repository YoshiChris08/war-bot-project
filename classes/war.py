import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from classes.player import Player


class War:
    """Public hub billboard post (MatchPost) created from a QueueParty."""

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
        search_mode: str = "allies",
        status: str = "open",
        author_discord_id: int = None,
        origin_guild_id: int = None,
        matched_opponent: Optional[Dict[str, Any]] = None,
        party_id: str = None,
    ):
        self.war_id = war_id or str(uuid.uuid4())
        self.war_type = war_type.upper()
        self.team_name = team_name
        self.gathered = gathered
        self.search_in_advance = search_in_advance
        self.start_time = start_time or datetime.utcnow().isoformat()
        self.last_updated = last_updated or datetime.utcnow().isoformat()
        self.ally_count = ally_count
        self.lineup = lineup or []
        self.search_mode = search_mode
        self.status = status
        self.author_discord_id = author_discord_id
        self.origin_guild_id = origin_guild_id
        self.matched_opponent = matched_opponent
        self.party_id = party_id

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
            "search_mode": self.search_mode,
            "status": self.status,
            "author_discord_id": self.author_discord_id,
            "origin_guild_id": self.origin_guild_id,
            "matched_opponent": self.matched_opponent,
            "party_id": self.party_id,
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
            last_updated=data.get("last_updated"),
            ally_count=data.get("ally_count", 0),
            lineup=lineup,
            war_id=data.get("war_id"),
            search_mode=data.get("search_mode", "allies"),
            status=data.get("status", "open"),
            author_discord_id=data.get("author_discord_id"),
            origin_guild_id=data.get("origin_guild_id"),
            matched_opponent=data.get("matched_opponent"),
            party_id=data.get("party_id"),
        )
