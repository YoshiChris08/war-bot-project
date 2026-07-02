from typing import Any, Dict, Optional, Tuple

from utils.billboard_store import upsert_war
from utils.config import track_to_type
from utils.match_posting import create_match_post_from_party
from utils.queue_store import upsert_party
from utils.roster import has_minimum_bagger, resolve_search_mode, status_label

from classes.queue_party import PARTY_POSTED


def post_party_to_billboard(party: Dict[str, Any], looking_for: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    lineup = party.get("lineup", [])
    if not has_minimum_bagger(lineup):
        return None, "You need **at least 1 bagger** before posting."

    search_mode = resolve_search_mode(looking_for, lineup)
    if search_mode is None:
        return None, (
            "**Looking For Opponents** requires **5/5** with **≥1 bagger**. "
            "Post as **Looking For Allies** or add teammates first."
        )

    war_type = track_to_type(party.get("war_type", "RT"))
    post = create_match_post_from_party(party, search_mode)
    upsert_war(war_type, post)

    party["status"] = PARTY_POSTED
    party["match_post_id"] = post["war_id"]
    party["search_mode"] = search_mode
    upsert_party(party)

    label = status_label(search_mode, "open", lineup)
    return post, f"Posted to hub billboard as **{label}**."
