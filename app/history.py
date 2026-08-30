"""Packaged overseer history served to the Fleet Console."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

HISTORY_PATH = Path(__file__).parent / "data" / "overseer.json"


@lru_cache(maxsize=1)
def overseer_payload() -> Dict[str, Any]:
    if not HISTORY_PATH.exists():
        return {
            "meta": {"rule": "Overseer history is not packaged."},
            "sprint": {"opened": 0, "waiting": 0, "merged": 0, "closed": 0, "days": [], "repos": [], "prs": []},
            "claims": [],
            "archive": [],
        }
    return json.loads(HISTORY_PATH.read_text())
