import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

from utils.config import DATA_DIR

WAR_RESULTS_PATH = os.path.join(DATA_DIR, "war-results.json")


def _load_all() -> Dict[str, Any]:
    if not os.path.exists(WAR_RESULTS_PATH):
        return {"results": []}
    try:
        with open(WAR_RESULTS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if "results" in data else {"results": []}
    except json.JSONDecodeError:
        return {"results": []}


def _save_all(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(WAR_RESULTS_PATH), exist_ok=True)
    with open(WAR_RESULTS_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def append_result(result: Dict[str, Any]) -> Dict[str, Any]:
    data = _load_all()
    result.setdefault("result_id", str(uuid.uuid4()))
    result.setdefault("completed_at", datetime.utcnow().isoformat())
    result.setdefault("table_bot_synced", False)
    data["results"].append(result)
    _save_all(data)
    return result


def list_results() -> List[Dict[str, Any]]:
    return _load_all()["results"]
