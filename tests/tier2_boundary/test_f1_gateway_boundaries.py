"""Tier 2 Boundary Tests: Feature 1 - Webhook Gateway Boundary & Edge Cases."""

import json
from typing import Callable
import pytest
from fastapi.testclient import TestClient


class TestFeature1GatewayBoundaries:
    """Tier 2: >= 5 boundary and corner-case tests for Webhook Gateway."""

    def test_f1_t2_01_empty_payload_with_valid_sig(self, test_client: TestClient, sign_payload: Callable):
        empty_body = b""
        sig = sign_payload(empty_body)
        res = test_client.post(
            "/webhook/github",
            content=empty_body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "t2-f1-empty-01",
            },
        )
        assert res.status_code == 200

    def test_f1_t2_02_large_payload_handling(self, test_client: TestClient, sign_payload: Callable):
        # 500 KB large simulated payload
        large_body = json.dumps({"action": "opened", "issue": {"number": 1, "large_blob": "X" * 500_000}}).encode(
            "utf-8"
        )
        sig = sign_payload(large_body)
        res = test_client.post(
            "/webhook/github",
            content=large_body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "t2-f1-large-01",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 200

    def test_f1_t2_03_missing_delivery_header_generates_fallback(
        self,
        test_client: TestClient,
        sign_payload: Callable,
    ):
        body = json.dumps({"action": "opened", "issue": {"number": 5}}).encode("utf-8")
        sig = sign_payload(body)
        res = test_client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 200
        assert res.json()["delivery_id"] == "unknown-delivery"

    def test_f1_t2_04_missing_event_header_defaults_unknown(
        self,
        test_client: TestClient,
        sign_payload: Callable,
    ):
        body = json.dumps({"action": "custom"}).encode("utf-8")
        sig = sign_payload(body)
        res = test_client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "t2-f1-no-event-01",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 200
        assert res.json()["status"] == "ignored"
        assert res.json()["event"] == "unknown"

    def test_f1_t2_05_special_characters_in_headers(self, test_client: TestClient, sign_payload: Callable):
        body = json.dumps({"action": "opened", "issue": {"number": 99}}).encode("utf-8")
        sig = sign_payload(body)
        res = test_client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "uuid-special-12345-abc-XYZ_#$%",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 200
        assert res.json()["delivery_id"] == "uuid-special-12345-abc-XYZ_#$%"
