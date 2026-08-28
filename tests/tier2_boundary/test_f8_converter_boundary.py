"""
Tier 2 Boundary Tests: F8 - Draft Converter Boundary & Corner Cases
"""

import pytest
from tests.conftest import make_pr_payload, MockGitHubAPIClient
from tests.tier1_feature.test_f8_draft_converter import execute_draft_conversion


def test_f8_boundary_already_ready_pr_is_noop(mock_github_client):
    """Test F8-B.1: PR with draft=False does not trigger conversion API call."""
    payload = make_pr_payload(pr_number=601, draft=False)
    res = execute_draft_conversion(payload, "APPROVE", mock_github_client)
    assert res["converted"] is False
    assert len(mock_github_client.draft_conversions) == 0


def test_f8_boundary_missing_draft_field_defaults_to_false(mock_github_client):
    """Test F8-B.2: Payload missing draft field defaults to draft=False (noop)."""
    payload = make_pr_payload(pr_number=602)
    payload["pull_request"].pop("draft", None)
    res = execute_draft_conversion(payload, "APPROVE", mock_github_client)
    assert res["converted"] is False


def test_f8_boundary_request_changes_never_converts_draft(mock_github_client):
    """Test F8-B.3: Even if draft=True, REQUEST_CHANGES strictly forbids conversion."""
    payload = make_pr_payload(pr_number=603, draft=True)
    res = execute_draft_conversion(payload, "REQUEST_CHANGES", mock_github_client)
    assert res["converted"] is False
    assert len(mock_github_client.draft_conversions) == 0


def test_f8_boundary_special_node_id_encoding(mock_github_client):
    """Test F8-B.4: GraphQL base64 node IDs with special chars (=, _, -) handled cleanly."""
    special_node_id = "PR_kwDOAbc123==__--"
    payload = make_pr_payload(pr_number=604, draft=True)
    payload["pull_request"]["node_id"] = special_node_id
    res = execute_draft_conversion(payload, "APPROVE", mock_github_client)
    assert res["converted"] is True
    assert mock_github_client.draft_conversions[0]["node_id"] == special_node_id


def test_f8_boundary_multiple_draft_prs_converted_independently(mock_github_client):
    """Test F8-B.5: Multiple PRs in parallel convert their respective node IDs."""
    p1 = make_pr_payload(pr_number=605, draft=True)
    p1["pull_request"]["node_id"] = "NODE_1"
    p2 = make_pr_payload(pr_number=606, draft=True)
    p2["pull_request"]["node_id"] = "NODE_2"

    execute_draft_conversion(p1, "APPROVE", mock_github_client)
    execute_draft_conversion(p2, "APPROVE", mock_github_client)

    assert len(mock_github_client.draft_conversions) == 2
    assert mock_github_client.draft_conversions[0]["node_id"] == "NODE_1"
    assert mock_github_client.draft_conversions[1]["node_id"] == "NODE_2"
