"""Tier 1: Fleet Console APIs, Memory Bank persistence, fail-closed merge flag."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.memory.bank import (
    bounty_id_for_issue,
    classify_cheat,
    get_memory_bank,
    seed_demo_bounty,
)
from tests.conftest import (
    AUTH_BYPASS_SOROBAN_DIFF,
    CLEAN_SOROBAN_DIFF,
    WEBHOOK_SECRET,
    generate_hub_signature,
    make_issue_payload,
    make_pr_payload,
)

BOUNTY_REPO = "s6pa1rta3n-lab/universal_bounty_fleet"
BOUNTY_ISSUE_ID = bounty_id_for_issue(BOUNTY_REPO, 1)


def test_console_page_is_served(test_client: TestClient):
    resp = test_client.get("/console")
    assert resp.status_code == 200
    assert "Fleet Console" in resp.text
    assert "BLOCKED" in resp.text or "PENDING" in resp.text

    latest = test_client.get("/api/bounties/latest").json()["bounty"]
    assert latest["audit_status"] == "FAIL"
    assert latest["cheat_detected"] == "auth_bypass"
    assert latest["merge_allowed"] is False


def test_console_bundle_exposes_blocked_banner_copy():
    assets = Path(__file__).resolve().parents[2] / "app" / "static" / "console" / "assets"
    js_files = list(assets.glob("index-*.js"))
    assert js_files, "Fleet Console bundle missing"
    bundle = js_files[0].read_text(encoding="utf-8")
    assert "BLOCKED — MERGE DENIED" in bundle


def test_registry_lists_three_scoped_agents(test_client: TestClient):
    resp = test_client.get("/api/registry")
    assert resp.status_code == 200
    data = resp.json()
    ids = [agent["id"] for agent in data["agents"]]
    assert ids == ["intake", "executor", "auditor"]
    assert data["track"] == "Fortified Enterprise Fleet"
    assert data["policy"]["god_token"] is False
    auditor = data["agents"][2]
    assert "pull_requests:review" in auditor["tool_scope"]
    assert "contents:write" not in auditor["tool_scope"]


def test_latest_seeds_fixture_and_blocks_merge(test_client: TestClient):
    resp = test_client.get("/api/bounties/latest")
    assert resp.status_code == 200
    bounty = resp.json()["bounty"]
    assert bounty["source"] == "fixture"
    assert bounty["bounty_id"] == BOUNTY_ISSUE_ID
    assert bounty["issue_number"] == 1
    assert bounty["audit_status"] == "FAIL"
    assert bounty["merge_allowed"] is False
    assert bounty["cheat_detected"] == "auth_bypass"


def test_merge_allowed_only_when_audit_passes():
    bank = get_memory_bank(force_in_memory=True)
    bank.upsert("x#1", {"audit_status": "FAIL"})
    assert bank.get("x#1")["merge_allowed"] is False
    bank.upsert("x#1", {"audit_status": "PASS"})
    assert bank.get("x#1")["merge_allowed"] is True


def test_classify_cheat_maps_pillars():
    assert classify_cheat({"pillar1_crypto": False, "pillar2_auth": True, "pillar3_assertions": True}) == "mock_cipher"
    assert classify_cheat({"pillar1_crypto": True, "pillar2_auth": False, "pillar3_assertions": True}) == "auth_bypass"
    assert classify_cheat({"pillar1_crypto": True, "pillar2_auth": True, "pillar3_assertions": False}) == "skipped_assertion"
    assert classify_cheat({"pillar1_crypto": True, "pillar2_auth": True, "pillar3_assertions": True}) is None


def test_issue_webhook_persists_claim(test_client: TestClient):
    payload = make_issue_payload(
        title="Funded vault bounty",
        body="Reward: $500 USDC on GrantFox. Escrow confirmed by grantfox-bot.",
        issue_number=77,
        comments=[{"id": 1001, "body": "Bounty Confirmed: 500 USD locked in GrantFox escrow."}],
    )
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "X-GitHub-Event": "issues",
        "X-Hub-Signature-256": generate_hub_signature(body, WEBHOOK_SECRET),
        "X-GitHub-Delivery": "console-issue-77",
        "Content-Type": "application/json",
    }
    resp = test_client.post("/webhook/github", content=body, headers=headers)
    assert resp.status_code == 200
    stored = get_memory_bank(force_in_memory=True).get(
        bounty_id_for_issue("stellar-org/soroban-contracts", 77)
    )
    assert stored is not None
    assert stored["issue_number"] == 77


def test_pr_webhook_persists_fail_closed_audit(test_client: TestClient, mock_github_client):
    payload = make_pr_payload(
        pr_number=402,
        diff_content=AUTH_BYPASS_SOROBAN_DIFF,
        body="Fixes #402",
        title="Draft vault patch",
    )
    payload["pull_request"]["mock_diff_content"] = AUTH_BYPASS_SOROBAN_DIFF
    payload["diff_text"] = AUTH_BYPASS_SOROBAN_DIFF
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": generate_hub_signature(body, WEBHOOK_SECRET),
        "X-GitHub-Delivery": "console-pr-402",
        "Content-Type": "application/json",
    }
    resp = test_client.post("/webhook/github", content=body, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["details"]["verdict"] == "REQUEST_CHANGES"
    stored = get_memory_bank(force_in_memory=True).get(
        bounty_id_for_issue("stellar-org/soroban-contracts", 402)
    )
    assert stored is not None
    assert stored["audit_status"] == "FAIL"
    assert stored["merge_allowed"] is False
    assert stored["cheat_detected"] == "auth_bypass"
    types = [event["type"] for event in stored["events"]]
    assert "audit_fail" in types
    assert len(mock_github_client.created_reviews) == 1
    assert mock_github_client.created_reviews[0]["event"] == "REQUEST_CHANGES"
    assert "Pillar 2" in mock_github_client.created_reviews[0]["body"]


def test_seed_demo_is_idempotent():
    first = seed_demo_bounty()
    second = seed_demo_bounty()
    assert first["bounty_id"] == second["bounty_id"]
    assert len(second["events"]) == len(first["events"])


def _post_webhook(test_client: TestClient, event: str, payload: dict, delivery_id: str):
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "X-GitHub-Event": event,
        "X-Hub-Signature-256": generate_hub_signature(body, WEBHOOK_SECRET),
        "X-GitHub-Delivery": delivery_id,
        "Content-Type": "application/json",
    }
    return test_client.post("/webhook/github", content=body, headers=headers)


def test_fail_closed_auth_bypass_loop_issue_pr_fix(test_client: TestClient, mock_github_client):
    """Acceptance loop: /try intake → planted auth_bypass FAIL → fix commit PASS."""
    bank = get_memory_bank(force_in_memory=True)

    issue_payload = make_issue_payload(
        repo_name=BOUNTY_REPO,
        issue_number=1,
        title="[Bounty] Fail-closed Victory Audit on planted auth_bypass",
        body="Reward: $1,200 USDC on GrantFox. Escrow confirmed by grantfox-bot.",
        comments=[{"id": 9001, "body": "GrantFox smart-contract escrow confirmed and locked."}],
    )
    issue_resp = _post_webhook(test_client, "issues", issue_payload, "bounty-issue-1")
    assert issue_resp.status_code == 200
    after_intake = bank.get(BOUNTY_ISSUE_ID)
    assert after_intake is not None
    assert after_intake["audit_status"] == "PENDING"
    assert after_intake["merge_allowed"] is False
    assert any(event["type"] == "claimed" for event in after_intake["events"])

    bypass_payload = make_pr_payload(
        repo_name=BOUNTY_REPO,
        pr_number=1,
        title="[Bounty] planted auth_bypass — Fixes #1",
        body="First commit plants the cheat for the auditor rehearsal.",
        diff_content=AUTH_BYPASS_SOROBAN_DIFF,
    )
    bypass_payload["action"] = "opened"
    bypass_payload["pull_request"]["mock_diff_content"] = AUTH_BYPASS_SOROBAN_DIFF
    bypass_payload["diff_text"] = AUTH_BYPASS_SOROBAN_DIFF
    bypass_resp = _post_webhook(test_client, "pull_request", bypass_payload, "bounty-pr-bypass")
    assert bypass_resp.status_code == 200
    assert bypass_resp.json()["details"]["verdict"] == "REQUEST_CHANGES"
    after_fail = bank.get(BOUNTY_ISSUE_ID)
    assert after_fail is not None
    assert after_fail["audit_status"] == "FAIL"
    assert after_fail["merge_allowed"] is False
    assert after_fail["cheat_detected"] == "auth_bypass"
    assert after_fail["pr_number"] == 1
    assert any(event["type"] == "audit_fail" for event in after_fail["events"])
    assert mock_github_client.created_reviews[-1]["event"] == "REQUEST_CHANGES"

    fix_payload = make_pr_payload(
        repo_name=BOUNTY_REPO,
        pr_number=1,
        title="[Bounty] planted auth_bypass — Fixes #1",
        body="Second commit removes the bypass.",
        diff_content=CLEAN_SOROBAN_DIFF,
        action="synchronize",
        head_sha="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    )
    fix_payload["pull_request"]["mock_diff_content"] = CLEAN_SOROBAN_DIFF
    fix_payload["diff_text"] = CLEAN_SOROBAN_DIFF
    fix_resp = _post_webhook(test_client, "pull_request", fix_payload, "bounty-pr-fix")
    assert fix_resp.status_code == 200
    assert fix_resp.json()["details"]["verdict"] == "APPROVE"
    after_pass = bank.get(BOUNTY_ISSUE_ID)
    assert after_pass is not None
    assert after_pass["audit_status"] == "PASS"
    assert after_pass["merge_allowed"] is True
    assert after_pass["cheat_detected"] is None
    event_types = [event["type"] for event in after_pass["events"]]
    assert "audit_fail" in event_types
    assert "audit_pass" in event_types
    assert mock_github_client.created_reviews[-1]["event"] == "APPROVE"
    assert len(mock_github_client.draft_conversions) == 1


def test_pr_webhook_submits_review_via_github_rest_client(test_client: TestClient, monkeypatch):
    """Webhook path uses GitHubClient REST (not the lightweight mock adapter)."""
    from app.utils.github_client import GitHubClient
    from tests.test_github_client import MockTransport

    transport = MockTransport()
    rest_client = GitHubClient(token="ghp_test", custom_transport=transport)
    monkeypatch.setattr(
        "app.utils.github_client.get_github_client",
        lambda *args, **kwargs: rest_client,
    )

    payload = make_pr_payload(
        repo_name=BOUNTY_REPO,
        pr_number=1,
        title="[Bounty] REST transport — Fixes #1",
        body="Verify native review POST.",
        diff_content=AUTH_BYPASS_SOROBAN_DIFF,
    )
    payload["pull_request"]["mock_diff_content"] = AUTH_BYPASS_SOROBAN_DIFF
    payload["diff_text"] = AUTH_BYPASS_SOROBAN_DIFF
    resp = _post_webhook(test_client, "pull_request", payload, "bounty-pr-rest-transport")
    assert resp.status_code == 200
    assert resp.json()["details"]["verdict"] == "REQUEST_CHANGES"

    review_posts = [
        req
        for req in transport.recorded_requests
        if req.method == "POST" and req.url.path.endswith("/reviews")
    ]
    assert len(review_posts) == 1
    posted = json.loads(review_posts[0].content)
    assert posted["event"] == "REQUEST_CHANGES"
    assert "Pillar 2" in posted["body"]
