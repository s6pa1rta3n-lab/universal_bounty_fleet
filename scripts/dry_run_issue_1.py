#!/usr/bin/env python3
"""Local dry-run of bounty issue #1 fail-closed loop (no GitHub/Cloud Run required)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Ensure test-safe settings before app import
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("USE_IN_MEMORY_FIRESTORE", "true")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret-12345")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.memory.bank import (  # noqa: E402
    RECORDING_CUE_BANNER,
    bounty_id_for_issue,
    get_memory_bank,
)
from app.utils import github_client as github_client_module  # noqa: E402
from tests.conftest import (  # noqa: E402
    AUTH_BYPASS_SOROBAN_DIFF,
    CLEAN_SOROBAN_DIFF,
    MockGitHubAPIClient,
    WEBHOOK_SECRET,
    generate_hub_signature,
    make_issue_payload,
    make_pr_payload,
)

BOUNTY_REPO = "s6pa1rta3n-lab/universal_bounty_fleet"
BOUNTY_ID = bounty_id_for_issue(BOUNTY_REPO, 1)


def post(client: TestClient, event: str, payload: dict, delivery_id: str) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "X-GitHub-Event": event,
        "X-Hub-Signature-256": generate_hub_signature(body, WEBHOOK_SECRET),
        "X-GitHub-Delivery": delivery_id,
        "Content-Type": "application/json",
    }
    resp = client.post("/webhook/github", content=body, headers=headers)
    if resp.status_code != 200:
        raise SystemExit(f"webhook {delivery_id} failed: {resp.status_code} {resp.text}")
    return resp.json()


def main() -> int:
    bank = get_memory_bank(force_in_memory=True)
    bank.clear()
    mock_github = MockGitHubAPIClient()
    github_client_module.get_github_client = lambda *args, **kwargs: mock_github
    client = TestClient(app)

    print("1) Intake /try")
    post(
        client,
        "issues",
        make_issue_payload(
            repo_name=BOUNTY_REPO,
            issue_number=1,
            title="[Bounty] Fail-closed Victory Audit on planted auth_bypass",
            body="Reward: $1,200 USDC on GrantFox. Escrow confirmed by grantfox-bot.",
            comments=[{"id": 1, "body": "GrantFox escrow locked."}],
        ),
        "dry-run-issue-1",
    )
    intake = bank.get(BOUNTY_ID)
    assert intake and intake["audit_status"] == "PENDING"
    print(f"   audit_status={intake['audit_status']} merge_allowed={intake['merge_allowed']}")

    print("2) Draft PR — planted auth_bypass")
    bypass = make_pr_payload(
        repo_name=BOUNTY_REPO,
        pr_number=1,
        title="[Bounty] planted auth_bypass — Fixes #1",
        body="Commit 1 plants the cheat.",
        diff_content=AUTH_BYPASS_SOROBAN_DIFF,
    )
    bypass["pull_request"]["mock_diff_content"] = AUTH_BYPASS_SOROBAN_DIFF
    bypass["diff_text"] = AUTH_BYPASS_SOROBAN_DIFF
    fail = post(client, "pull_request", bypass, "dry-run-pr-bypass")
    assert fail["details"]["verdict"] == "REQUEST_CHANGES"
    blocked = bank.get(BOUNTY_ID)
    assert blocked and blocked["audit_status"] == "FAIL"
    print(
        f"   verdict=REQUEST_CHANGES audit_status={blocked['audit_status']} "
        f"cheat={blocked['cheat_detected']} merge_allowed={blocked['merge_allowed']}"
    )
    latest_resp = client.get("/api/bounties/latest").json()
    banner = latest_resp["banner"]
    assert banner["title"] == RECORDING_CUE_BANNER, banner
    print(f"   console banner: {banner['title']}")

    print("3) Fix commit — bypass removed")
    fix = make_pr_payload(
        repo_name=BOUNTY_REPO,
        pr_number=1,
        title="[Bounty] planted auth_bypass — Fixes #1",
        body="Commit 2 removes the cheat.",
        diff_content=CLEAN_SOROBAN_DIFF,
        action="synchronize",
    )
    fix["pull_request"]["mock_diff_content"] = CLEAN_SOROBAN_DIFF
    fix["diff_text"] = CLEAN_SOROBAN_DIFF
    passed = post(client, "pull_request", fix, "dry-run-pr-fix")
    assert passed["details"]["verdict"] == "APPROVE"
    cleared = bank.get(BOUNTY_ID)
    assert cleared and cleared["audit_status"] == "PASS" and cleared["merge_allowed"]
    print(
        f"   verdict=APPROVE audit_status={cleared['audit_status']} "
        f"merge_allowed={cleared['merge_allowed']}"
    )

    print("DRY-RUN PASS — ready for live GitHub + Cloud Run recording.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
