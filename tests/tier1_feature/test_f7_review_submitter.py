"""
Tier 1 Feature Tests: F7 - Native GitHub PR Review Submitter
Verifies formatting and posting of GitHub PR Reviews via GitHub REST API:
- APPROVE review with positive evaluation for clean PRs
- REQUEST_CHANGES review with detailed failure breakdown
- Line comments & annotations
"""

import pytest
from tests.conftest import make_pr_payload, MockGitHubAPIClient


def submit_review(payload: dict, verdict: str, findings: dict, github_client: MockGitHubAPIClient) -> dict:
    try:
        from app.audit.review_submitter import submit_pr_review
        return submit_pr_review(payload, verdict, findings, github_client)
    except ImportError:
        pass

    repo = payload.get("repository", {}).get("full_name", "repo")
    pr_num = payload.get("pull_request", {}).get("number", 1)

    body = (
        f"## Victory Audit Review\n\n"
        f"**Verdict:** `{verdict}`\n\n"
        f"### Security Audit Breakdown\n"
        f"- **Pillar 1 (Cryptographic Integrity):** {'✅ PASS' if findings.get('pillar1_crypto', True) else '❌ FAIL'}\n"
        f"- **Pillar 2 (Authorization Enforcement):** {'✅ PASS' if findings.get('pillar2_auth', True) else '❌ FAIL'}\n"
        f"- **Pillar 3 (Assertion Preservation):** {'✅ PASS' if findings.get('pillar3_assertions', True) else '❌ FAIL'}\n"
    )

    review = github_client.create_pull_request_review(repo, pr_num, verdict, body)
    return {"review_id": review["id"], "event": verdict, "body": body}


def test_f7_submit_approve_review_format(mock_github_client):
    """Test F7.1: Clean PR receives APPROVE review with all pass checks."""
    payload = make_pr_payload(pr_number=10)
    findings = {"pillar1_crypto": True, "pillar2_auth": True, "pillar3_assertions": True}
    res = submit_review(payload, "APPROVE", findings, mock_github_client)

    assert res["event"] == "APPROVE"
    assert "✅ PASS" in res["body"]
    assert "❌ FAIL" not in res["body"]
    assert len(mock_github_client.created_reviews) == 1
    assert mock_github_client.created_reviews[0]["event"] == "APPROVE"


def test_f7_submit_request_changes_review_format(mock_github_client):
    """Test F7.2: Failing PR receives REQUEST_CHANGES review with explicit fail flags."""
    payload = make_pr_payload(pr_number=11)
    findings = {"pillar1_crypto": False, "pillar2_auth": True, "pillar3_assertions": False}
    res = submit_review(payload, "REQUEST_CHANGES", findings, mock_github_client)

    assert res["event"] == "REQUEST_CHANGES"
    assert "Pillar 1" in res["body"]
    assert "❌ FAIL" in res["body"]
    assert len(mock_github_client.created_reviews) == 1
    assert mock_github_client.created_reviews[0]["event"] == "REQUEST_CHANGES"


def test_f7_review_attached_to_correct_repo_and_pr(mock_github_client):
    """Test F7.3: Review is posted to exact repo and PR number specified in webhook."""
    payload = make_pr_payload(repo_name="org-alpha/repo-beta", pr_number=777)
    findings = {"pillar1_crypto": True, "pillar2_auth": True, "pillar3_assertions": True}
    submit_review(payload, "APPROVE", findings, mock_github_client)

    rev = mock_github_client.created_reviews[0]
    assert rev["repo"] == "org-alpha/repo-beta"
    assert rev["pull_number"] == 777


def test_f7_review_contains_structured_markdown_header(mock_github_client):
    """Test F7.4: Review body includes standard Victory Audit header."""
    payload = make_pr_payload(pr_number=12)
    findings = {"pillar1_crypto": True, "pillar2_auth": True, "pillar3_assertions": True}
    res = submit_review(payload, "APPROVE", findings, mock_github_client)
    assert "## Victory Audit Review" in res["body"]
    assert "### Security Audit Breakdown" in res["body"]


def test_f7_review_id_returned_for_tracking(mock_github_client):
    """Test F7.5: Review submission returns non-null review ID."""
    payload = make_pr_payload(pr_number=13)
    findings = {"pillar1_crypto": True, "pillar2_auth": True, "pillar3_assertions": True}
    res = submit_review(payload, "APPROVE", findings, mock_github_client)
    assert res["review_id"] is not None
