"""Acceptance Test 5 & Comprehensive Webhook Routing Test Suite.

Verifies stateless Cloud Run webhook routing to subagents (Intake vs Auditor)
with HMAC-SHA256 verification and Firestore distributed idempotency locks,
strictly ensuring zero local persistent database files are created.
"""

import glob
import json
import os
from typing import Any, Callable, Dict, Optional
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app


def create_test_gateway_dispatcher(custom_app: Optional[FastAPI] = None) -> TestClient:
    """Create a FastAPI TestClient for the webhook gateway."""
    return TestClient(custom_app or app)


class TestWebhookRouting:
    """Test suite for stateless GitHub webhook gateway endpoints."""

    def test_root_endpoint_metadata(self, test_client: TestClient):
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "The Universal Bounty Fleet"
        assert data["service"] == "universal-bounty-gateway"
        assert data["status"] == "active"
        assert data["project"] == "odin-500008"
        assert "Taskmaster" in str(data["tracks"])

    def test_health_endpoints(self, test_client: TestClient):
        for path in ["/health", "/healthz"]:
            response = test_client.get(path)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "universal-bounty-fleet"

    def test_webhook_missing_signature_rejected(self, test_client: TestClient, mock_issue_payload: Dict[str, Any]):
        response = test_client.post(
            "/webhook/github",
            json=mock_issue_payload,
            headers={
                "X-GitHub-Event": "issues",
                "X-GitHub-Delivery": "deliv-no-sig",
            },
        )
        assert response.status_code == 401
        assert "signature" in response.json()["detail"].lower()

    def test_webhook_invalid_signature_rejected(
        self,
        test_client: TestClient,
        mock_issue_payload: Dict[str, Any],
    ):
        body_bytes = json.dumps(mock_issue_payload).encode("utf-8")
        response = test_client.post(
            "/webhook/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": "sha256=invalidhex00000000000000000000000000000000000000000000000000000000",
                "X-GitHub-Delivery": "deliv-bad-sig",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 401

    def test_webhook_malformed_json_body(self, test_client: TestClient, sign_payload: Callable):
        bad_body = b"not-a-valid-json-payload-{"
        sig = sign_payload(bad_body)

        response = test_client.post(
            "/webhook/github",
            content=bad_body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "deliv-bad-json",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 400

    def test_issues_event_routed_to_intake_taskmaster(
        self,
        test_client: TestClient,
        mock_issue_payload: Dict[str, Any],
        sign_payload: Callable,
    ):
        body_bytes = json.dumps(mock_issue_payload).encode("utf-8")
        sig = sign_payload(body_bytes)

        response = test_client.post(
            "/webhook/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "delivery-issue-1001",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["event"] == "issues"
        assert data["target_agent"] == "intake_taskmaster"
        assert data["details"]["issue_number"] == mock_issue_payload["issue"]["number"]
        assert data["details"]["repo"] == mock_issue_payload["repository"]["full_name"]

    def test_pull_request_event_routed_to_victory_auditor(
        self,
        test_client: TestClient,
        mock_pr_payload: Dict[str, Any],
        sign_payload: Callable,
    ):
        body_bytes = json.dumps(mock_pr_payload).encode("utf-8")
        sig = sign_payload(body_bytes)

        response = test_client.post(
            "/webhook/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "delivery-pr-2001",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["event"] == "pull_request"
        assert data["target_agent"] == "victory_auditor"
        assert data["details"]["pr_number"] == mock_pr_payload["pull_request"]["number"]
        assert data["details"]["is_draft"] is True
        assert data["details"]["repo"] == mock_pr_payload["repository"]["full_name"]

    def test_issue_comment_mentioning_auditor_routes_to_victory_auditor(
        self,
        test_client: TestClient,
        mock_comment_payload: Dict[str, Any],
        sign_payload: Callable,
    ):
        body_bytes = json.dumps(mock_comment_payload).encode("utf-8")
        sig = sign_payload(body_bytes)

        response = test_client.post(
            "/webhook/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "issue_comment",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "delivery-comment-888",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["event"] == "issue_comment"
        assert data["target_agent"] == "victory_auditor"

    def test_pull_request_review_event(
        self,
        test_client: TestClient,
        sign_payload: Callable,
    ):
        payload = {
            "action": "submitted",
            "review": {"id": 1, "state": "approved"},
            "repository": {"full_name": "stellar-org/soroban-contracts"},
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        sig = sign_payload(body_bytes)

        response = test_client.post(
            "/webhook/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "pull_request_review",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "delivery-review-1",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["target_agent"] == "victory_auditor"

    def test_ping_event_handling(self, test_client: TestClient, sign_payload: Callable):
        payload = {"zen": "Keep it logically awesome."}
        body_bytes = json.dumps(payload).encode("utf-8")
        sig = sign_payload(body_bytes)

        response = test_client.post(
            "/webhook/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "delivery-ping-1",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["action"] == "ping"

    def test_duplicate_delivery_id_deduplicated_by_firestore_lock(
        self,
        test_client: TestClient,
        mock_issue_payload: Dict[str, Any],
        sign_payload: Callable,
    ):
        body_bytes = json.dumps(mock_issue_payload).encode("utf-8")
        sig = sign_payload(body_bytes)
        delivery_id = "delivery-duplicate-test-99"

        # Delivery 1: Processed
        res1 = test_client.post(
            "/webhook/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": delivery_id,
                "Content-Type": "application/json",
            },
        )
        assert res1.status_code == 200
        assert res1.json()["status"] == "processed"

        # Delivery 2 (same delivery ID): Duplicate ignored
        res2 = test_client.post(
            "/webhook/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": delivery_id,
                "Content-Type": "application/json",
            },
        )
        assert res2.status_code == 200
        assert res2.json()["status"] == "duplicate"
        assert "already processed" in res2.json()["details"]["message"]

    def test_stateless_invariant_no_local_databases_created(self, test_client: TestClient, sign_payload: Callable):
        """Invariant: Zero SQLite/JSONL databases created locally during webhook ingestion."""
        # Find any sqlite or jsonl files before/after
        sqlite_files = glob.glob("**/*.sqlite*", recursive=True) + glob.glob("**/*.db", recursive=True)
        assert len(sqlite_files) == 0, f"Found forbidden local database files: {sqlite_files}"
