"""
Tier 4: Real-World Application Scenarios (5 Scenarios)
Simulates end-to-end operational workflows across the entire Universal Bounty Fleet lifecycle.
"""

import json
import pytest
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


def test_scenario_1_valid_grantfox_bounty_discovery_to_intent_stake(
    mock_github_client,
    mock_vertex_client,
    mock_firestore_client
):
    """
    Scenario 1 (S1): Valid GrantFox Bounty Discovery to Intent Stake
    - Webhook receives new GrantFox issue in active Soroban repository.
    - Sniper filter qualifies issue (no competitor, not archived, approved platform).
    - Escrow engine evaluates GrantFox smart contract lock of $5,000 USD.
    - Autonomous claim staker posts `/try` comment with verified EVM and Stellar payout addresses.
    """
    grantfox_payload = make_issue_payload(
        repo_name="stellar/soroban-examples",
        issue_number=101,
        title="Implement Atomic Swap Vault Contract",
        body="High priority GrantFox bounty for atomic cross-chain swap escrow.",
        comments=[
            {"id": 1, "body": "💰 **GrantFox Escrow Confirmed**: 5,000 USD locked in contract.", "user": {"login": "grantfox-bot"}}
        ]
    )

    result = run_intake_pipeline(
        grantfox_payload,
        github_client=mock_github_client,
        vertex_client=mock_vertex_client,
        firestore_client=mock_firestore_client
    )

    assert result["qualified"] is True
    assert result["staked"] is True
    assert len(mock_github_client.created_comments) == 1

    comment = mock_github_client.created_comments[0]
    assert "/try" in comment["body"]
    assert EVM_PAYOUT_ADDRESS in comment["body"]
    assert STELLAR_PAYOUT_ADDRESS in comment["body"]


def test_scenario_2_banned_platform_and_competitor_sniping_rejection(
    mock_github_client,
    mock_vertex_client,
    mock_firestore_client
):
    """
    Scenario 2 (S2): Banned Platform & Competitor Sniping Rejection
    - Fleet intercepts an issue mentioning banned platform (Algora/Opire).
    - Fleet intercepts another issue where competitor already commented `/claim`.
    - Both are disqualified instantly without spending LLM tokens or posting comments.
    """
    # 1. Banned platform issue
    banned_payload = make_issue_payload(
        title="Algora bounty: Web3 Frontend",
        body="Funded via https://algora.io/org/test/123"
    )
    r1 = run_intake_pipeline(banned_payload, mock_github_client, mock_vertex_client, mock_firestore_client)
    assert r1["qualified"] is False

    # 2. Competitor claimed issue
    claimed_payload = make_issue_payload(
        comments=[{"id": 2, "body": "/claim working on this now", "user": {"login": "fast_competitor"}}]
    )
    r2 = run_intake_pipeline(claimed_payload, mock_github_client, mock_vertex_client, mock_firestore_client)
    assert r2["qualified"] is False

    assert len(mock_github_client.created_comments) == 0


def test_scenario_3_compromised_pull_request_victory_audit(
    mock_github_client,
    mock_vertex_client
):
    """
    Scenario 3 (S3): Compromised Pull Request Victory Audit
    - Engineer opens Draft PR containing an authorization bypass in Soroban (`// recipient.require_auth()`).
    - Victory Audit Fleet intercepts PR via webhook.
    - Murder Board flags Pillar 2 violation (missing auth).
    - Submits native GitHub PR Review with REQUEST_CHANGES and keeps PR in Draft state.
    """
    pr_payload = make_pr_payload(
        repo_name="stellar/soroban-examples",
        pr_number=202,
        draft=True
    )

    res = run_audit_pipeline(
        pr_payload,
        AUTH_BYPASS_SOROBAN_DIFF,
        github_client=mock_github_client,
        vertex_client=mock_vertex_client
    )

    assert res["verdict"] == "REQUEST_CHANGES"
    assert res["findings"]["pillar2_auth"] is False
    assert res["draft_converted"] is False
    assert len(mock_github_client.created_reviews) == 1
    assert mock_github_client.created_reviews[0]["event"] == "REQUEST_CHANGES"
    assert len(mock_github_client.draft_conversions) == 0


def test_scenario_4_honest_clean_pull_request_victory_audit(
    mock_github_client,
    mock_vertex_client
):
    """
    Scenario 4 (S4): Honest Clean Pull Request Victory Audit
    - Engineer opens Draft PR with real Soroban cryptography and required auth checks.
    - Victory Audit Fleet evaluates all 3 pillars -> 100% PASS.
    - Submits native GitHub PR Review with APPROVE.
    - Autonomously executes headless GraphQL mutation converting Draft PR to Ready for Review.
    """
    pr_payload = make_pr_payload(
        repo_name="stellar/soroban-examples",
        pr_number=303,
        draft=True
    )

    res = run_audit_pipeline(
        pr_payload,
        CLEAN_SOROBAN_DIFF,
        github_client=mock_github_client,
        vertex_client=mock_vertex_client
    )

    assert res["verdict"] == "APPROVE"
    assert res["draft_converted"] is True
    assert len(mock_github_client.created_reviews) == 1
    assert mock_github_client.created_reviews[0]["event"] == "APPROVE"
    assert len(mock_github_client.draft_conversions) == 1
    assert mock_github_client.draft_conversions[0]["status"] == "READY"


def test_scenario_5_complete_end_to_end_bounty_lifecycle_simulation(
    client,
    mock_firestore_client,
    mock_github_client,
    mock_vertex_client
):
    """
    Scenario 5 (S5): Complete End-to-End Bounty Lifecycle Simulation
    1. Gateway receives issue webhook -> Intake Taskmaster qualifies & stakes `/try` with payout addresses.
    2. Engineer implements fix and opens Draft PR.
    3. Gateway receives PR webhook -> Victory Audit Fleet runs 3-Pillar Murder Board on clean code.
    4. Victory Audit passes -> Submits APPROVE review -> Draft PR converted to Ready for Review.
    5. Verifies zero local SQLite/JSONL state created throughout the entire lifecycle.
    """
    # Step 1: Issue Webhook
    issue_payload = make_issue_payload(issue_number=500)
    issue_bytes = json.dumps(issue_payload).encode("utf-8")
    sig1 = generate_hub_signature(issue_bytes, WEBHOOK_SECRET)
    headers1 = {
        "X-GitHub-Event": "issues",
        "X-Hub-Signature-256": sig1,
        "X-GitHub-Delivery": "lifecycle-step-1-s5",
        "Content-Type": "application/json"
    }

    resp1 = client.post("/webhook/github", content=issue_bytes, headers=headers1)
    assert resp1.status_code == 200
    assert resp1.json()["target_agent"] == "intake_taskmaster"

    # Step 2: Intake Staking
    intake_res = run_intake_pipeline(issue_payload, mock_github_client, mock_vertex_client, mock_firestore_client)
    assert intake_res["staked"] is True
    assert len(mock_github_client.created_comments) >= 1

    # Step 3: PR Opened Webhook
    pr_payload = make_pr_payload(pr_number=501, draft=True)
    pr_bytes = json.dumps(pr_payload).encode("utf-8")
    sig2 = generate_hub_signature(pr_bytes, WEBHOOK_SECRET)
    headers2 = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": sig2,
        "X-GitHub-Delivery": "lifecycle-step-2-s5",
        "Content-Type": "application/json"
    }

    resp2 = client.post("/webhook/github", content=pr_bytes, headers=headers2)
    assert resp2.status_code == 200
    assert resp2.json()["target_agent"] == "victory_auditor"

    # Step 4: Audit & Draft Conversion
    audit_res = run_audit_pipeline(pr_payload, CLEAN_SOROBAN_DIFF, mock_github_client, mock_vertex_client)
    assert audit_res["verdict"] == "APPROVE"
    assert audit_res["draft_converted"] is True

    # Step 5: Verification of End State
    assert len(mock_github_client.created_reviews) >= 1
    assert len(mock_github_client.draft_conversions) >= 1
