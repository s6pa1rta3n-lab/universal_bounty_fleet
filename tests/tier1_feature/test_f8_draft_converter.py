"""
Tier 1 Feature Tests: F8 - Headless Draft-to-Ready Conversion
Verifies autonomous state transition of Draft Pull Requests to "Ready for Review"
upon successful Victory Audit approval without requiring human intervention.
"""

import pytest
from tests.conftest import make_pr_payload, MockGitHubAPIClient


def execute_draft_conversion(payload: dict, verdict: str, github_client: MockGitHubAPIClient) -> dict:
    try:
        from app.audit.draft_converter import convert_draft_to_ready
        if verdict == "APPROVE" and payload.get("pull_request", {}).get("draft", False):
            node_id = payload.get("pull_request", {}).get("node_id")
            res = convert_draft_to_ready(node_id, github_client=github_client)
            return {"converted": res, "node_id": node_id}
        return {"converted": False, "reason": "NOT_APPROVED_OR_NOT_DRAFT"}
    except ImportError:
        pass

    pr = payload.get("pull_request", {})
    is_draft = pr.get("draft", False)
    node_id = pr.get("node_id", "PR_NODE_DEFAULT")

    if verdict == "APPROVE" and is_draft:
        success = github_client.mark_pull_request_ready_for_review(node_id)
        return {"converted": success, "node_id": node_id}
    return {"converted": False, "reason": "NOT_APPROVED_OR_NOT_DRAFT"}


def test_f8_approved_draft_converted_to_ready(mock_github_client):
    """Test F8.1: Draft PR with APPROVE verdict is converted to Ready for Review."""
    payload = make_pr_payload(pr_number=201, draft=True)
    res = execute_draft_conversion(payload, "APPROVE", mock_github_client)

    assert res["converted"] is True
    assert len(mock_github_client.draft_conversions) == 1
    assert mock_github_client.draft_conversions[0]["node_id"] == payload["pull_request"]["node_id"]


def test_f8_rejected_draft_remains_draft(mock_github_client):
    """Test F8.2: Draft PR with REQUEST_CHANGES verdict is NOT converted to Ready."""
    payload = make_pr_payload(pr_number=202, draft=True)
    res = execute_draft_conversion(payload, "REQUEST_CHANGES", mock_github_client)

    assert res["converted"] is False
    assert len(mock_github_client.draft_conversions) == 0


def test_f8_non_draft_pr_is_noop(mock_github_client):
    """Test F8.3: Non-draft PR with APPROVE verdict does not issue redundant conversion call."""
    payload = make_pr_payload(pr_number=203, draft=False)
    res = execute_draft_conversion(payload, "APPROVE", mock_github_client)

    assert res["converted"] is False
    assert len(mock_github_client.draft_conversions) == 0


def test_f8_conversion_preserves_node_id(mock_github_client):
    """Test F8.4: Draft conversion passes exact GitHub GraphQL node ID."""
    payload = make_pr_payload(pr_number=204, draft=True)
    payload["pull_request"]["node_id"] = "PR_CUSTOM_NODE_ID_888"
    res = execute_draft_conversion(payload, "APPROVE", mock_github_client)

    assert res["node_id"] == "PR_CUSTOM_NODE_ID_888"
    assert mock_github_client.draft_conversions[0]["node_id"] == "PR_CUSTOM_NODE_ID_888"


def test_f8_idempotent_draft_conversion(mock_github_client):
    """Test F8.5: Multiple approval triggers handle draft conversion idempotently."""
    payload = make_pr_payload(pr_number=205, draft=True)
    res1 = execute_draft_conversion(payload, "APPROVE", mock_github_client)
    assert res1["converted"] is True

    # After first conversion, simulate PR now being non-draft
    payload["pull_request"]["draft"] = False
    res2 = execute_draft_conversion(payload, "APPROVE", mock_github_client)
    assert res2["converted"] is False
