"""Tier 1: Fleet Console APIs, Memory Bank persistence, fail-closed merge flag."""

import json

from fastapi.testclient import TestClient

from app.memory.bank import classify_cheat, get_memory_bank, seed_demo_bounty
from tests.conftest import (
    AUTH_BYPASS_SOROBAN_DIFF,
    WEBHOOK_SECRET,
    generate_hub_signature,
    make_issue_payload,
    make_pr_payload,
)


def test_console_page_is_served(test_client: TestClient):
    resp = test_client.get("/console")
    assert resp.status_code == 200
    assert "Fleet Console" in resp.text
    assert "BLOCKED" in resp.text or "PENDING" in resp.text


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
    stored = get_memory_bank(force_in_memory=True).get("stellar-org/soroban-contracts#77")
    assert stored is not None
    assert stored["issue_number"] == 77


def test_pr_webhook_persists_fail_closed_audit(test_client: TestClient):
    payload = make_pr_payload(pr_number=402, diff_content=AUTH_BYPASS_SOROBAN_DIFF)
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
    stored = get_memory_bank(force_in_memory=True).get("stellar-org/soroban-contracts#402")
    assert stored is not None
    assert stored["audit_status"] == "FAIL"
    assert stored["merge_allowed"] is False
    assert stored["cheat_detected"] == "auth_bypass"
    types = [event["type"] for event in stored["events"]]
    assert "audit_fail" in types


def test_seed_demo_is_idempotent():
    first = seed_demo_bounty()
    second = seed_demo_bounty()
    assert first["bounty_id"] == second["bounty_id"]
    assert len(second["events"]) == len(first["events"])
