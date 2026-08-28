"""
Tier 3: Cross-Feature Combinations & Integration Tests (12 Tests)
Verifies multi-module interactions across Gateway, Firestore Locks,
Sniper Filter, Escrow Engine, Claim Staker, Murder Board, Review Submitter, and Draft Converter.
"""

import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import (
    generate_hub_signature,
    make_issue_payload,
    make_pr_payload,
    EVM_PAYOUT_ADDRESS,
    STELLAR_PAYOUT_ADDRESS,
    CLEAN_SOROBAN_DIFF,
    AUTH_BYPASS_SOROBAN_DIFF,
    CRYPTO_MOCK_DIFF,
    WEBHOOK_SECRET,
    MockFirestoreClient,
    MockGitHubAPIClient,
    MockVertexAIClient
)
from tests.test_intake_service import run_intake_pipeline
from tests.test_victory_audit import run_audit_pipeline


@pytest.fixture
def client():
    return TestClient(app)


def test_combo_1_gateway_hmac_and_firestore_idempotency(client):
    """Combination 1: Gateway + HMAC + Firestore Idempotency prevents duplicate webhook execution."""
    payload = make_issue_payload(issue_number=101)
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = generate_hub_signature(body_bytes, WEBHOOK_SECRET)
    headers = {
        "X-GitHub-Event": "issues",
        "X-Hub-Signature-256": sig,
        "X-GitHub-Delivery": "delivery-c1-combo",
        "Content-Type": "application/json"
    }

    # First attempt: processed
    r1 = client.post("/webhook/github", content=body_bytes, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "processed"

    # Replay attempt: caught by idempotency
    r2 = client.post("/webhook/github", content=body_bytes, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"


def test_combo_2_sniper_filter_drops_banned_platform_before_escrow_call(mock_github_client, mock_vertex_client, mock_firestore_client):
    """Combination 2: Banned platform (Algora) is dropped by Sniper Filter before any Vertex AI tokens are spent."""
    payload = make_issue_payload(title="Algora bounty", body="See https://algora.io/task/1")
    res = run_intake_pipeline(payload, mock_github_client, mock_vertex_client, mock_firestore_client)

    assert res["qualified"] is False
    assert res["staked"] is False
    assert len(mock_vertex_client.calls) == 0  # No LLM tokens consumed!
    assert len(mock_github_client.created_comments) == 0


def test_combo_3_sniper_filter_and_escrow_and_claim_staking_happy_path(mock_github_client, mock_vertex_client, mock_firestore_client):
    """Combination 3: Qualified GrantFox issue passes filter + escrow -> triggers /try comment with payout block."""
    payload = make_issue_payload(issue_number=303)
    res = run_intake_pipeline(payload, mock_github_client, mock_vertex_client, mock_firestore_client)

    assert res["qualified"] is True
    assert res["staked"] is True
    assert len(mock_github_client.created_comments) == 1

    comment = mock_github_client.created_comments[0]
    assert "/try" in comment["body"]
    assert EVM_PAYOUT_ADDRESS in comment["body"]
    assert STELLAR_PAYOUT_ADDRESS in comment["body"]


def test_combo_4_pr_webhook_triggers_murder_board_and_submits_request_changes(mock_github_client, mock_vertex_client):
    """Combination 4: PR webhook containing auth bypass triggers Murder Board -> submits REQUEST_CHANGES review."""
    payload = make_pr_payload(pr_number=404, draft=True)
    res = run_audit_pipeline(payload, AUTH_BYPASS_SOROBAN_DIFF, mock_github_client, mock_vertex_client)

    assert res["verdict"] == "REQUEST_CHANGES"
    assert res["findings"]["pillar2_auth"] is False
    assert res["draft_converted"] is False
    assert len(mock_github_client.created_reviews) == 1
    assert mock_github_client.created_reviews[0]["event"] == "REQUEST_CHANGES"


def test_combo_5_clean_pr_triggers_approve_and_draft_to_ready_conversion(mock_github_client, mock_vertex_client):
    """Combination 5: Clean PR passes all 3 pillars -> submits APPROVE review -> converts Draft PR to Ready."""
    payload = make_pr_payload(pr_number=505, draft=True)
    res = run_audit_pipeline(payload, CLEAN_SOROBAN_DIFF, mock_github_client, mock_vertex_client)

    assert res["verdict"] == "APPROVE"
    assert res["draft_converted"] is True
    assert len(mock_github_client.created_reviews) == 1
    assert mock_github_client.created_reviews[0]["event"] == "APPROVE"
    assert len(mock_github_client.draft_conversions) == 1
    assert mock_github_client.draft_conversions[0]["status"] == "READY"


def test_combo_6_escrow_engine_failure_blocks_claim_staker(mock_github_client, mock_vertex_client, mock_firestore_client):
    """Combination 6: Unfunded or failed escrow check halts pipeline before claim staking."""
    payload = make_issue_payload(comments=[{"id": 1, "body": "No funds available"}])
    mock_vertex_client.default_response = json.dumps({
        "is_funded": False,
        "escrow_amount_usd": 0.0,
        "confidence": 0.99,
        "reasoning": "Unfunded issue."
    })
    res = run_intake_pipeline(payload, mock_github_client, mock_vertex_client, mock_firestore_client)

    assert res["qualified"] is False
    assert res["staked"] is False
    assert len(mock_github_client.created_comments) == 0


def test_combo_7_duplicate_webhook_prevents_double_claim_staking(mock_github_client, mock_vertex_client, mock_firestore_client):
    """Combination 7: Replaying the same issue intake event does not create a second /try comment."""
    payload = make_issue_payload(issue_number=707)
    res1 = run_intake_pipeline(payload, mock_github_client, mock_vertex_client, mock_firestore_client)
    assert res1["staked"] is True
    assert len(mock_github_client.created_comments) == 1

    # Second intake attempt on same issue
    res2 = run_intake_pipeline(payload, mock_github_client, mock_vertex_client, mock_firestore_client)
    assert len(mock_github_client.created_comments) == 1


def test_combo_8_multi_pillar_failure_composite_review(mock_github_client, mock_vertex_client):
    """Combination 8: PR with both auth bypass AND crypto mock fails multiple pillars and records both in review body."""
    combined_diff = AUTH_BYPASS_SOROBAN_DIFF + "\n" + CRYPTO_MOCK_DIFF
    payload = make_pr_payload(pr_number=808, draft=True)
    res = run_audit_pipeline(payload, combined_diff, mock_github_client, mock_vertex_client)

    assert res["verdict"] == "REQUEST_CHANGES"
    assert res["findings"]["pillar1_crypto"] is False
    assert res["findings"]["pillar2_auth"] is False
    assert "Pillar 1" in mock_github_client.created_reviews[0]["body"]
    assert "Pillar 2" in mock_github_client.created_reviews[0]["body"]


def test_combo_9_competitor_claim_blocks_staking_even_if_escrow_funded(mock_github_client, mock_vertex_client, mock_firestore_client):
    """Combination 9: $10,000 funded escrow is rejected because a competitor commented /claim."""
    payload = make_issue_payload(
        issue_number=909,
        comments=[
            {"id": 1, "body": "GrantFox: $10,000 escrow deposited", "user": {"login": "grantfox-bot"}},
            {"id": 2, "body": "/claim taking this task now", "user": {"login": "competitor"}}
        ]
    )
    res = run_intake_pipeline(payload, mock_github_client, mock_vertex_client, mock_firestore_client)
    assert res["qualified"] is False
    assert res["staked"] is False
    assert len(mock_github_client.created_comments) == 0


def test_combo_10_gateway_routes_pull_request_synchronize_event(client):
    """Combination 10: Gateway dispatches pull_request 'synchronize' event (new commit pushed) to Victory Audit."""
    payload = make_pr_payload(pr_number=1010, action="synchronize")
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = generate_hub_signature(body_bytes, WEBHOOK_SECRET)
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": sig,
        "X-GitHub-Delivery": "deliv-sync-10",
        "Content-Type": "application/json"
    }

    resp = client.post("/webhook/github", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["target_agent"] == "victory_auditor"


def test_combo_11_archived_repo_fails_before_escrow_or_staking(mock_github_client, mock_vertex_client, mock_firestore_client):
    """Combination 11: Issue in archived repo is blocked at Sniper Filter stage."""
    payload = make_issue_payload(archived=True)
    res = run_intake_pipeline(payload, mock_github_client, mock_vertex_client, mock_firestore_client)
    assert res["qualified"] is False
    assert len(mock_vertex_client.calls) == 0
    assert len(mock_github_client.created_comments) == 0


def test_combo_12_headless_draft_conversion_skipped_on_non_draft_pr(mock_github_client, mock_vertex_client):
    """Combination 12: Clean PR that is already non-draft gets APPROVE review but skips redundant ready mutation."""
    payload = make_pr_payload(pr_number=1212, draft=False)
    res = run_audit_pipeline(payload, CLEAN_SOROBAN_DIFF, mock_github_client, mock_vertex_client)
    assert res["verdict"] == "APPROVE"
    assert len(mock_github_client.draft_conversions) == 0
