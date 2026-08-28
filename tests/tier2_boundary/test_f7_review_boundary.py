"""
Tier 2 Boundary Tests: F7 - PR Review Submitter Boundary & Corner Cases
"""

import pytest
from tests.conftest import make_pr_payload, MockGitHubAPIClient
from tests.tier1_feature.test_f7_review_submitter import submit_review


def test_f7_boundary_large_review_body(mock_github_client):
    """Test F7-B.1: Review with extensive line comments and diagnostic logs."""
    payload = make_pr_payload(pr_number=501)
    findings = {
        "pillar1_crypto": False,
        "pillar2_auth": False,
        "pillar3_assertions": False,
        "details": "A" * 10000
    }
    res = submit_review(payload, "REQUEST_CHANGES", findings, mock_github_client)
    assert res["event"] == "REQUEST_CHANGES"
    assert len(mock_github_client.created_reviews) == 1


def test_f7_boundary_special_unicode_in_review_body(mock_github_client):
    """Test F7-B.2: Special symbols (🛡️, ❌, ⚠️, 🔒, 🦀) render properly."""
    payload = make_pr_payload(pr_number=502)
    findings = {"pillar1_crypto": True, "pillar2_auth": True, "pillar3_assertions": True}
    res = submit_review(payload, "APPROVE", findings, mock_github_client)
    assert "✅ PASS" in res["body"]


def test_f7_boundary_high_pr_number(mock_github_client):
    """Test F7-B.3: High PR number (e.g. #999999) handled cleanly."""
    payload = make_pr_payload(pr_number=999999)
    res = submit_review(payload, "APPROVE", {"pillar1_crypto": True}, mock_github_client)
    assert mock_github_client.created_reviews[0]["pull_number"] == 999999


def test_f7_boundary_sequential_reviews_on_same_pr(mock_github_client):
    """Test F7-B.4: Multiple revisions on the same PR submit distinct reviews."""
    payload = make_pr_payload(pr_number=504)
    # First revision failed
    submit_review(payload, "REQUEST_CHANGES", {"pillar2_auth": False}, mock_github_client)
    # Second revision passed
    submit_review(payload, "APPROVE", {"pillar2_auth": True}, mock_github_client)
    
    assert len(mock_github_client.created_reviews) == 2
    assert mock_github_client.created_reviews[0]["event"] == "REQUEST_CHANGES"
    assert mock_github_client.created_reviews[1]["event"] == "APPROVE"


def test_f7_boundary_empty_findings_dict_defaults_safely(mock_github_client):
    """Test F7-B.5: Empty findings dictionary defaults safely to pass without crash."""
    payload = make_pr_payload(pr_number=505)
    res = submit_review(payload, "APPROVE", {}, mock_github_client)
    assert res["event"] == "APPROVE"
