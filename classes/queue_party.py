import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from classes.player import Player

PARTY_PREPARING = "preparing"
PARTY_POSTED = "posted"
PARTY_MATCHED = "matched"
PARTY_CANCELLED = "cancelled"

MODE_CASUAL = "casual"


class QueueParty:
    """Party formed in a team server before a hub billboard post."""

    def __init__(
        self,
        team_id: str,
        guild_id: int,
        team_name: str,
        war_type: str,
        captain_discord_id: int,
        search_time: str = "ASAP",
        mode: str = MODE_CASUAL,
        status: str = PARTY_PREPARING,
        lineup: List[Player] = None,
        party_id: str = None,
        invite_code: str = None,
        lobby_channel_id: int = None,
        lobby_message_id: int = None,
        match_post_id: str = None,
        search_mode: str = "allies",
        last_updated: str = None,
    ):
        self.party_id = party_id or str(uuid.uuid4())
        self.team_id = team_id
        self.guild_id = guild_id
        self.team_name = team_name
        self.war_type = war_type.upper()
        self.captain_discord_id = captain_discord_id
        self.search_time = search_time
        self.mode = mode
        self.status = status
        self.lineup = lineup or []
        self.invite_code = invite_code or secrets.token_urlsafe(6)
        self.lobby_channel_id = lobby_channel_id
        self.lobby_message_id = lobby_message_id
        self.match_post_id = match_post_id
        self.search_mode = search_mode
        self.last_updated = last_updated or datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "party_id": self.party_id,
            "team_id": self.team_id,
            "guild_id": self.guild_id,
            "team_name": self.team_name,
            "war_type": self.war_type,
            "captain_discord_id": self.captain_discord_id,
            "search_time": self.search_time,
            "mode": self.mode,
            "status": self.status,
            "lineup": [player.to_dict() for player in self.lineup],
            "invite_code": self.invite_code,
            "lobby_channel_id": self.lobby_channel_id,
            "lobby_message_id": self.lobby_message_id,
            "match_post_id": self.match_post_id,
            "search_mode": self.search_mode,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueParty":
        lineup = [Player.from_dict(player) for player in data.get("lineup", [])]
        return cls(
            party_id=data.get("party_id"),
            team_id=data.get("team_id"),
            guild_id=data.get("guild_id"),
            team_name=data.get("team_name", ""),
            war_type=data.get("war_type", "RT"),
            captain_discord_id=data.get("captain_discord_id"),
            search_time=data.get("search_time", "ASAP"),
            mode=data.get("mode", MODE_CASUAL),
            status=data.get("status", PARTY_PREPARING),
            lineup=lineup,
            invite_code=data.get("invite_code"),
            lobby_channel_id=data.get("lobby_channel_id"),
            lobby_message_id=data.get("lobby_message_id"),
            match_post_id=data.get("match_post_id"),
            search_mode=data.get("search_mode", "allies"),
            last_updated=data.get("last_updated"),
        )
