"""
Tier 1 Feature Tests: F1 - Stateless Webhook Gateway
Verifies HMAC-SHA256 signature verification, event discrimination,
health endpoint, and routing contracts on /webhook/github.
"""

import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import (
    generate_hub_signature,
    generate_invalid_hub_signature,
    make_issue_payload,
    make_pr_payload,
    WEBHOOK_SECRET
)


@pytest.fixture
def gateway_client():
    return TestClient(app)


def test_f1_health_endpoint_returns_ok(gateway_client):
    """Test F1.1: GET /health returns 200 OK and healthy status."""
    resp = gateway_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_f1_root_endpoint_returns_gateway_info(gateway_client):
    """Test F1.2: GET / returns 200 OK and gateway info."""
    resp = gateway_client.get("/")
    assert resp.status_code == 200
    assert "Universal Bounty Fleet" in resp.json()["name"]


def test_f1_valid_hmac_signature_passes(gateway_client):
    """Test F1.3: POST /webhook/github with valid HMAC-SHA256 signature returns 200."""
    payload = {"zen": "Testing is discipline.", "action": "ping"}
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = generate_hub_signature(body_bytes, WEBHOOK_SECRET)

    headers = {
        "X-GitHub-Event": "ping",
        "X-Hub-Signature-256": sig,
        "X-GitHub-Delivery": "deliv-001",
        "Content-Type": "application/json"
    }
    resp = gateway_client.post("/webhook/github", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"


def test_f1_invalid_hmac_signature_rejected(gateway_client):
    """Test F1.4: POST /webhook/github with invalid HMAC-SHA256 returns 401."""
    payload = {"action": "opened"}
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "X-GitHub-Event": "issues",
        "X-Hub-Signature-256": "sha256=invalid_hash_value_here",
        "X-GitHub-Delivery": "deliv-002",
        "Content-Type": "application/json"
    }
    resp = gateway_client.post("/webhook/github", content=body_bytes, headers=headers)
    assert resp.status_code == 401


def test_f1_missing_signature_header_rejected(gateway_client):
    """Test F1.5: POST /webhook/github without X-Hub-Signature-256 returns 401."""
    payload = {"action": "opened"}
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "X-GitHub-Event": "issues",
        "X-GitHub-Delivery": "deliv-003",
        "Content-Type": "application/json"
    }
    resp = gateway_client.post("/webhook/github", content=body_bytes, headers=headers)
    assert resp.status_code == 401


def test_f1_event_routing_contract(gateway_client):
    """Test F1.6: POST /webhook/github routes issues event to intake_taskmaster."""
    payload = make_issue_payload(issue_number=123)
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = generate_hub_signature(body_bytes, WEBHOOK_SECRET)
    headers = {
        "X-GitHub-Event": "issues",
        "X-Hub-Signature-256": sig,
        "X-GitHub-Delivery": "deliv-004-route",
        "Content-Type": "application/json"
    }
    resp = gateway_client.post("/webhook/github", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["target_agent"] == "intake_taskmaster"
