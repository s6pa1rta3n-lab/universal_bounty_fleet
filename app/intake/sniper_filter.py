"""5-Stage Deterministic Sniper Filter for The Universal Bounty Fleet.

Evaluates candidate GitHub issues and bounty feeds against strict qualification criteria:
- Stage 0: Metadata Integrity (valid payload structure)
- Stage 1: Banned Platforms & Repositories (Algora, Polar, twentyhq/twenty, Opire)
- Stage 2: Repository Archive & Read-Only Gate (is_archived, archived, disabled)
- Stage 3: Competitor Claims & Priority Triage (active competitor /claim comments)
- Stage 4: Subjective & Non-Technical Requirements (video pitch, zoom call, loom, etc.)
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Banned platform domains and keyword identifiers
BANNED_PLATFORMS: List[str] = [
    "algora.io",
    "api.algora.io",
    "algora",
    "polar.sh",
    "api.polar.sh",
    "polar",
    "twentyhq/twenty",
    "twentyhq",
    "opire.dev",
    "api.opire.dev",
    "opire",
]

# Prohibited subjective / non-technical keywords
SUBJECTIVE_KEYWORDS: List[str] = [
    "video pitch",
    "record a video",
    "zoom interview",
    "zoom call",
    "live zoom",
    "loom",
    "loom.com",
    "screencast",
    "pitch deck",
    "twitter thread",
    "youtube video",
    "video demo",
    "live interview",
    "figma only",
    "design only",
]

# Known fleet bot logins that should not be classified as competitors
DEFAULT_ALLOWED_BOT_LOGINS: Set[str] = {
    "bounty-fleet[bot]",
    "bounty-fleet",
    "universal-engineer",
    "universal_bounty_fleet",
    "bounty-engine",
    "universal_auditor",
}


class SniperFilterResult(BaseModel):
    """Structured result from Sniper Filter qualification evaluation."""

    qualified: bool = Field(description="True if target issue passes all 5 filter stages")
    reason: str = Field(description="Taxonomy reason code for qualification or rejection")
    stage_failed: Optional[int] = Field(None, description="Stage index (0-4) where failure occurred")
    details: Dict[str, Any] = Field(default_factory=dict, description="Contextual evaluation metadata")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class SniperFilter:
    """Deterministic multi-stage qualification filter engine."""

    def __init__(self, allowed_bot_logins: Optional[Set[str]] = None) -> None:
        self.allowed_bot_logins = allowed_bot_logins or DEFAULT_ALLOWED_BOT_LOGINS

    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute 5-stage qualification pipeline against GitHub issue payload."""
        # Stage 0: Metadata Integrity Check
        if not isinstance(payload, dict):
            return {
                "qualified": False,
                "reason": "INVALID_METADATA",
                "stage_failed": 0,
                "details": {"error": "Payload is not a dictionary"},
            }

        repo = payload.get("repository", {})
        issue = payload.get("issue", {})
        if not isinstance(repo, dict):
            repo = {}
        if not isinstance(issue, dict):
            issue = {}

        repo_full_name = str(repo.get("full_name") or repo.get("name") or "").strip().lower()
        repo_owner = str(repo.get("owner", {}).get("login") if isinstance(repo.get("owner"), dict) else "").strip().lower()
        issue_title = str(issue.get("title") or "").strip()
        issue_body = str(issue.get("body") or "").strip()
        issue_url = str(issue.get("html_url") or "").strip().lower()

        # Extract comments
        raw_comments = issue.get("mock_comments_data") or issue.get("comments_data") or []
        if not isinstance(raw_comments, list):
            raw_comments = []

        combined_text = f"{issue_title} {issue_body}".lower()
        for comment in raw_comments:
            if isinstance(comment, dict):
                c_body = str(comment.get("body") or "").lower()
                combined_text += f" {c_body}"

        # Stage 1: Banned Platforms & Repositories
        for banned in BANNED_PLATFORMS:
            # Check repository full name (e.g. twentyhq/twenty)
            if banned in repo_full_name or banned in repo_owner:
                banned_tag = banned.replace("/", "_").replace(".", "_").upper()
                return {
                    "qualified": False,
                    "reason": f"BANNED_PLATFORM_{banned_tag}",
                    "stage_failed": 1,
                    "details": {"banned_platform": banned, "match_location": "repository"},
                }

            # Check combined issue content and URL
            if banned in combined_text or banned in issue_url:
                banned_tag = banned.replace("/", "_").replace(".", "_").upper()
                return {
                    "qualified": False,
                    "reason": f"BANNED_PLATFORM_{banned_tag}",
                    "stage_failed": 1,
                    "details": {"banned_platform": banned, "match_location": "content"},
                }

        # Stage 2: Repository Archive & Read-Only Gate
        is_archived = bool(
            repo.get("is_archived", False)
            or repo.get("archived", False)
            or repo.get("disabled", False)
        )
        if is_archived:
            return {
                "qualified": False,
                "reason": "ARCHIVED_REPOSITORY",
                "stage_failed": 2,
                "details": {"repo": repo_full_name, "archived": True},
            }

        # Stage 3: Competitor Claims & Priority Triage Gate
        for comment in raw_comments:
            if not isinstance(comment, dict):
                continue
            c_body = str(comment.get("body") or "")
            c_author = ""
            user_obj = comment.get("user")
            if isinstance(user_obj, dict):
                c_author = str(user_obj.get("login") or "")
            elif isinstance(user_obj, str):
                c_author = user_obj

            # Skip if comment is from our own bot
            if c_author in self.allowed_bot_logins:
                continue

            c_body_lower = c_body.lower()
            # Detect active /claim or explicit competitor claiming statements
            if "/claim" in c_body_lower or "i am claiming" in c_body_lower or "i'd like to work on this" in c_body_lower:
                return {
                    "qualified": False,
                    "reason": "COMPETITOR_ALREADY_CLAIMED",
                    "stage_failed": 3,
                    "details": {"competitor": c_author, "comment_body": c_body[:80]},
                }

        # Stage 4: Subjective & Non-Technical Requirements Gate
        for kw in SUBJECTIVE_KEYWORDS:
            if kw in combined_text:
                return {
                    "qualified": False,
                    "reason": "SUBJECTIVE_DELIVERABLE",
                    "stage_failed": 4,
                    "details": {"keyword": kw},
                }

        # All 5 stages passed cleanly
        return {
            "qualified": True,
            "reason": "QUALIFIED_TARGET",
            "stage_failed": None,
            "details": {
                "repo": repo_full_name,
                "issue_number": issue.get("number"),
                "title": issue_title,
            },
        }


# Global singleton instance
_sniper_filter_instance = SniperFilter()


def evaluate_platform_qualification(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate candidate issue against the 5-stage Sniper Filter."""
    return _sniper_filter_instance.evaluate(payload)
