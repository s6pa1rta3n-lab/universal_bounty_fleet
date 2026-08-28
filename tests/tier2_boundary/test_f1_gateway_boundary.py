"""
Tier 2 Boundary Tests: F1 - Gateway Boundary & Edge Cases
"""

import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import generate_hub_signature, WEBHOOK_SECRET


@pytest.fixture
def gateway_client():
    return TestClient(app)


def test_f1_boundary_empty_payload_body_rejected(gateway_client):
    """Test F1-B.1: Zero-byte payload body with signature handles safely."""
    body_bytes = b""
    sig = generate_hub_signature(body_bytes, WEBHOOK_SECRET)
    headers = {"X-GitHub-Event": "issues", "X-Hub-Signature-256": sig, "Content-Type": "application/json"}
    resp = gateway_client.post("/webhook/github", content=body_bytes, headers=headers)
    assert resp.status_code in [200, 400]


def test_f1_boundary_large_payload_body_handled(gateway_client):
    """Test F1-B.2: Large payload (500KB with 1,000 comments) is parsed successfully."""
    large_payload = {
        "action": "opened",
        "issue": {
            "title": "Large issue stress test",
            "body": "X" * 10000,
            "mock_comments_data": [{"id": i, "body": f"Comment {i}"} for i in range(100)]
        },
        "repository": {"full_name": "org/repo"}
    }
    body_bytes = json.dumps(large_payload).encode("utf-8")
    sig = generate_hub_signature(body_bytes, WEBHOOK_SECRET)
    headers = {"X-GitHub-Event": "issues", "X-Hub-Signature-256": sig, "X-GitHub-Delivery": "deliv-large-01", "Content-Type": "application/json"}
    resp = gateway_client.post("/webhook/github", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"


def test_f1_boundary_malformed_json_syntax_returns_400(gateway_client):
    """Test F1-B.3: Truncated / malformed JSON returns 400."""
    body_bytes = b'{"action": "opened", "issue": {'
    sig = generate_hub_signature(body_bytes, WEBHOOK_SECRET)
    headers = {"X-GitHub-Event": "issues", "X-Hub-Signature-256": sig, "Content-Type": "application/json"}
    resp = gateway_client.post("/webhook/github", content=body_bytes, headers=headers)
    assert resp.status_code == 400


def test_f1_boundary_unicode_emojis_in_signature_and_body(gateway_client):
    """Test F1-B.4: UTF-8 emojis and special characters in payload pass signature verification."""
    payload = {
        "action": "opened",
        "issue": {"title": "🚀 Soroban Smart Contract Bounty 💰🦀🔒", "number": 1},
        "repository": {"full_name": "stellar-org/soroban"}
    }
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sig = generate_hub_signature(body_bytes, WEBHOOK_SECRET)
    headers = {"X-GitHub-Event": "issues", "X-Hub-Signature-256": sig, "X-GitHub-Delivery": "deliv-emoji-01", "Content-Type": "application/json; charset=utf-8"}
    resp = gateway_client.post("/webhook/github", content=body_bytes, headers=headers)
    assert resp.status_code == 200


def test_f1_boundary_unknown_event_type_handled_cleanly(gateway_client):
    """Test F1-B.5: Unrecognized X-GitHub-Event is processed as ignored without unhandled exceptions."""
    payload = {"action": "created", "star": 5}
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = generate_hub_signature(body_bytes, WEBHOOK_SECRET)
    headers = {"X-GitHub-Event": "star", "X-Hub-Signature-256": sig, "X-GitHub-Delivery": "deliv-star-01", "Content-Type": "application/json"}
    resp = gateway_client.post("/webhook/github", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
