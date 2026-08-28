"""Headless Draft-to-Ready Conversion Engine.

Autonomously transitions GitHub Draft Pull Requests to "Ready for Review"
upon successful Victory Audit approval via GraphQL mutation without human intervention.
"""

import logging
from typing import Any, Optional

from app.utils.github_client import get_github_client

logger = logging.getLogger(__name__)


def convert_draft_to_ready(
    node_id: Optional[str] = None,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    pull_number: Optional[int] = None,
    github_client: Optional[Any] = None,
) -> bool:
    """Convert a Draft Pull Request to Ready for Review headlessly.

    Supports both GraphQL node ID mutations and REST/API wrappers.
    """
    client = github_client or get_github_client()

    if not node_id and not (owner and repo and pull_number):
        logger.error("convert_draft_to_ready called without valid node_id or repository/PR coordinates")
        return False

    try:
        # Check for mock client or direct mark_pull_request_ready_for_review method
        if node_id and hasattr(client, "mark_pull_request_ready_for_review"):
            return bool(client.mark_pull_request_ready_for_review(node_id))

        # Check for GitHubClient convert_draft_pr_to_ready method
        if hasattr(client, "convert_draft_pr_to_ready"):
            owner_val = owner or "unknown"
            repo_val = repo or "unknown"
            pr_num_val = pull_number or 1
            return bool(client.convert_draft_pr_to_ready(owner_val, repo_val, pr_num_val, node_id=node_id))

        logger.warning("GitHub client does not support draft-to-ready conversion")
        return False
    except Exception as exc:
        logger.error("Failed to convert Draft PR to ready: %s", exc)
        return False
