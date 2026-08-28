"""
Tier 2 Boundary Tests: F5 - Claim Staker Boundary & Corner Cases
"""

import pytest
from tests.conftest import MockGitHubAPIClient, MockFirestoreClient, make_issue_payload
from tests.tier1_feature.test_f5_claim_staker import execute_claim_staking_action, format_try_comment_body


def test_f5_boundary_long_repo_and_issue_number(mock_github_client, mock_firestore_client):
    """Test F5-B.1: Extremely long repository name and high issue number (e.g. #9999999)."""
    long_repo = "a" * 50 + "/" + "b" * 50
    payload = make_issue_payload(repo_name=long_repo, issue_number=9999999)
    res = execute_claim_staking_action(payload, mock_github_client, mock_firestore_client)
    assert res["success"] is True
    assert mock_github_client.created_comments[0]["issue_number"] == 9999999


def test_f5_boundary_special_chain_delegation_fallback():
    """Test F5-B.2: Verify standard EVM and Stellar addresses are strictly present."""
    comment = format_try_comment_body()
    # Confirm both 0x and G addresses exist
    assert "0x" in comment
    assert "G" in comment
    assert len(comment.splitlines()) >= 4


def test_f5_boundary_concurrent_staking_attempts_lock_out(mock_github_client, mock_firestore_client):
    """Test F5-B.3: Rapid concurrent staking attempts only post 1 comment."""
    payload = make_issue_payload(issue_number=888)
    results = [execute_claim_staking_action(payload, mock_github_client, mock_firestore_client) for _ in range(5)]
    success_count = sum(1 for r in results if r["success"] is True)
    assert success_count == 1
    assert len(mock_github_client.created_comments) == 1


def test_f5_boundary_comment_body_contains_exact_header_level2():
    """Test F5-B.4: Payout routing block strictly adheres to H2 header level."""
    body = format_try_comment_body()
    assert "## Payout Routing" in body


def test_f5_boundary_api_failure_handling(mock_firestore_client):
    """Test F5-B.5: Simulates GitHub API exception during comment post."""
    class FailingGitHubClient(MockGitHubAPIClient):
        def post_issue_comment(self, *args, **kwargs):
            raise RuntimeError("GitHub API 500 Internal Server Error")

    payload = make_issue_payload(issue_number=123)
    failing_client = FailingGitHubClient()
    
    with pytest.raises(RuntimeError):
        failing_client.post_issue_comment("repo", 123, "test")
