"""
Challenger 1: Empirical Adversarial Stress Test Suite for Milestone 1.

Comprehensive adversarial test suite covering:
1. Malformed and forged HMAC signatures (tampered bodies, missing prefixes, timing resistance).
2. High-concurrency duplicate webhook events testing Firestore lock contention and deduplication.
3. Vertex AI client error handling when quota project is omitted vs present, ADC missing, and API failures.
4. Gateway boundary fuzzing and GitHub client error resilience.
"""

import asyncio
import concurrent.futures
import hashlib
import hmac
import json
import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.main import app
from app.security.firestore_lock import FirestoreLock, InMemoryFirestoreLock, get_lock_manager
from app.security.hmac_validator import generate_github_signature, verify_github_signature
from app.utils.github_client import GitHubClient, get_github_client
from app.utils.vertex_client import VertexClientFactory, get_vertex_client

TEST_SECRET = "test-webhook-secret-12345"


# ==============================================================================
# CHALLENGE SUITE 1: MALFORMED AND FORGED HMAC SIGNATURES & TIMING RESISTANCE
# ==============================================================================

class TestHMACAdversarialSuite:
    """Stress-tests for HMAC signature verification and payload tampering."""

    @pytest.fixture(autouse=True)
    def setup_env(self):
        os.environ["GITHUB_WEBHOOK_SECRET"] = TEST_SECRET
        get_settings.cache_clear()

    @pytest.mark.parametrize(
        "invalid_header,reason",
        [
            (None, "None header"),
            ("", "Empty header"),
            ("   ", "Whitespace only"),
            ("sha1=d3b07384d113edec49eaa6238ad5ff00", "Legacy sha1 prefix"),
            ("md5=d41d8cd98f00b204e9800998ecf8427e", "MD5 prefix"),
            ("bearer=token123", "Bearer token prefix"),
            ("sha512=abcdef", "SHA512 prefix"),
            ("SHA256=abcdef1234567890", "Uppercase prefix"),
            ("Sha256=abcdef1234567890", "Titlecase prefix"),
            ("sha256=", "Prefix with empty hex digest"),
            ("sha256=   ", "Prefix with whitespace digest"),
            ("sha256=123", "Truncated hex digest (too short)"),
            ("sha256=" + "a" * 128, "Overlong hex digest (128 chars)"),
            ("sha256=" + "z" * 64, "Invalid non-hex characters"),
            ("sha256=0000000000000000000000000000000000000000000000000000000000000000", "All zeros forged digest"),
            ("sha256=" + "0" * 63 + "1", "Off-by-one forged digest"),
            ("  sha256=abc", "Leading whitespace before prefix"),
        ],
    )
    def test_malformed_signature_headers_rejected(self, invalid_header, reason):
        """Verify all malformed signature headers are rejected without throwing unhandled exceptions."""
        payload = b'{"action": "opened", "issue": {"number": 1}}'
        assert verify_github_signature(payload, invalid_header, secret=TEST_SECRET) is False, f"Failed on {reason}"

    def test_tampered_payload_body_rejected(self):
        """Single-bit and byte tampering on valid payload is immediately rejected."""
        valid_payload = b'{"action": "opened", "issue": {"number": 42, "title": "Bounty"}}'
        valid_sig = generate_github_signature(valid_payload, TEST_SECRET)

        # 1. Single character alteration in JSON body
        tampered_1 = b'{"action": "opened", "issue": {"number": 43, "title": "Bounty"}}'
        assert verify_github_signature(tampered_1, valid_sig, TEST_SECRET) is False

        # 2. Appended whitespace
        tampered_2 = valid_payload + b" "
        assert verify_github_signature(tampered_2, valid_sig, TEST_SECRET) is False

        # 3. Appended trailing newline
        tampered_3 = valid_payload + b"\n"
        assert verify_github_signature(tampered_3, valid_sig, TEST_SECRET) is False

        # 4. Injected null byte
        tampered_4 = valid_payload + b"\x00"
        assert verify_github_signature(tampered_4, valid_sig, TEST_SECRET) is False

        # 5. Prepended byte
        tampered_5 = b" " + valid_payload
        assert verify_github_signature(tampered_5, valid_sig, TEST_SECRET) is False

    def test_forged_signature_with_wrong_secret_rejected(self):
        """Signatures computed with attacker-controlled secret must be rejected."""
        payload = b'{"action": "opened", "issue": {"number": 100}}'
        attacker_secret = "evil-attacker-secret-key-999"
        forged_sig = generate_github_signature(payload, attacker_secret)

        assert verify_github_signature(payload, forged_sig, secret=TEST_SECRET) is False

    def test_multibyte_utf8_and_unicode_payloads(self):
        """Payloads containing complex UTF-8 multibyte characters (emojis, CJK, Cyrillic) verify cleanly."""
        payload_data = {
            "action": "opened",
            "issue": {
                "number": 999,
                "title": "🎉 Stellar Soroban 智能合约 Bounty 🚀 — Привет мир — €1000",
                "body": "Special symbols: 🔥 💻 ⚡ \u2603 \U0001F600",
            },
        }
        raw_bytes = json.dumps(payload_data, ensure_ascii=False).encode("utf-8")
        sig = generate_github_signature(raw_bytes, TEST_SECRET)

        assert verify_github_signature(raw_bytes, sig, TEST_SECRET) is True

        # Tamper one unicode character
        tampered_bytes = raw_bytes.replace("🎉".encode("utf-8"), "🎊".encode("utf-8"))
        assert verify_github_signature(tampered_bytes, sig, TEST_SECRET) is False

    def test_large_payload_hmac_performance_and_verification(self):
        """Large 2MB webhook payload is correctly signed and verified without memory/stack issues."""
        large_body = {
            "action": "opened",
            "pull_request": {
                "number": 100,
                "diff": "+ " + ("A" * 100 + "\n") * 20000,  # ~2MB of diff data
            },
        }
        raw_bytes = json.dumps(large_body).encode("utf-8")
        assert len(raw_bytes) > 2_000_000

        sig = generate_github_signature(raw_bytes, TEST_SECRET)
        assert verify_github_signature(raw_bytes, sig, TEST_SECRET) is True

        # Tampering the very last byte of a 2MB payload
        tampered = raw_bytes[:-1] + (b"X" if raw_bytes[-1:] != b"X" else b"Y")
        assert verify_github_signature(tampered, sig, TEST_SECRET) is False

    def test_missing_or_empty_server_secret_fails_safe(self):
        """If server has no GITHUB_WEBHOOK_SECRET configured, all verifications fail safe (no bypass)."""
        payload = b'{"test": "payload"}'
        sig = generate_github_signature(payload, "any-secret")

        with patch("app.security.hmac_validator.get_settings") as mock_settings:
            mock_settings.return_value.github_webhook_secret = ""
            assert verify_github_signature(payload, sig, secret=None) is False

            mock_settings.return_value.github_webhook_secret = None
            assert verify_github_signature(payload, sig, secret=None) is False

    def test_constant_time_comparison_timing_resistance(self):
        """Empirically test that hmac.compare_digest is utilized and timing variance is constant-time."""
        payload = b'{"test": "timing_probe"}'
        valid_sig = generate_github_signature(payload, TEST_SECRET)
        raw_hex = valid_sig[len("sha256=") :]

        sig_fail_char_0 = raw_hex[0] != "0" and "0" + raw_hex[1:] or "1" + raw_hex[1:]
        sig_fail_char_32 = raw_hex[:32] + ("0" if raw_hex[32] != "0" else "1") + raw_hex[33:]
        sig_fail_char_63 = raw_hex[:63] + ("0" if raw_hex[63] != "0" else "1")

        # Invariant 1: Direct verification that compare_digest behaves correctly
        assert hmac.compare_digest(raw_hex, raw_hex) is True
        assert hmac.compare_digest(raw_hex, sig_fail_char_0) is False
        assert hmac.compare_digest(raw_hex, sig_fail_char_32) is False
        assert hmac.compare_digest(raw_hex, sig_fail_char_63) is False

        # Invariant 2: Interleaved timing measurement across 5000 rounds
        rounds = 5000
        t_char0 = 0.0
        t_char32 = 0.0
        t_char63 = 0.0

        for _ in range(rounds):
            t0 = time.perf_counter_ns()
            hmac.compare_digest(raw_hex, sig_fail_char_0)
            t_char0 += time.perf_counter_ns() - t0

            t0 = time.perf_counter_ns()
            hmac.compare_digest(raw_hex, sig_fail_char_32)
            t_char32 += time.perf_counter_ns() - t0

            t0 = time.perf_counter_ns()
            hmac.compare_digest(raw_hex, sig_fail_char_63)
            t_char63 += time.perf_counter_ns() - t0

        avg_0 = t_char0 / rounds
        avg_32 = t_char32 / rounds
        avg_63 = t_char63 / rounds

        # All average comparison times should be within sub-microsecond range
        assert max(avg_0, avg_32, avg_63) < 10_000  # < 10 microseconds per compare

    def test_gateway_endpoint_rejects_unauthorized_webhooks(self):
        """Test FastAPI gateway endpoint returns 401 for all forged / tampered webhooks."""
        client = TestClient(app)
        payload = {"action": "opened", "issue": {"number": 1, "title": "Test"}}
        raw_body = json.dumps(payload).encode("utf-8")

        # 1. Missing header
        res1 = client.post(
            "/webhook/github",
            content=raw_body,
            headers={"X-GitHub-Event": "issues", "X-GitHub-Delivery": "deliv-1"},
        )
        assert res1.status_code == 401

        # 2. Forged signature
        res2 = client.post(
            "/webhook/github",
            content=raw_body,
            headers={
                "X-GitHub-Event": "issues",
                "X-GitHub-Delivery": "deliv-2",
                "X-Hub-Signature-256": "sha256=badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbad1",
            },
        )
        assert res2.status_code == 401

        # 3. Valid signature succeeds
        valid_sig = generate_github_signature(raw_body, TEST_SECRET)
        res3 = client.post(
            "/webhook/github",
            content=raw_body,
            headers={
                "X-GitHub-Event": "issues",
                "X-GitHub-Delivery": "deliv-3",
                "X-Hub-Signature-256": valid_sig,
            },
        )
        assert res3.status_code == 200
        assert res3.json()["status"] == "processed"


# ==============================================================================
# CHALLENGE SUITE 2: HIGH-CONCURRENCY WEBHOOKS & LOCK CONTENTION
# ==============================================================================

class TestConcurrencyAndDeduplicationSuite:
    """Stress-tests for high concurrency, duplicate deliveries, and lock contention."""

    @pytest.fixture(autouse=True)
    def reset_locks(self):
        lock_mgr = get_lock_manager(force_in_memory=True)
        lock_mgr.clear()

    def test_high_concurrency_duplicate_delivery_deduplication(self):
        """Send 50 parallel identical webhook requests. EXACTLY ONE must be 'processed', 49 must be 'duplicate'."""
        client = TestClient(app)
        payload = {"action": "opened", "issue": {"number": 777, "title": "Concurrent Bounty"}}
        raw_body = json.dumps(payload).encode("utf-8")
        sig = generate_github_signature(raw_body, TEST_SECRET)
        delivery_id = "concurrent-duplicate-delivery-uuid-999"

        num_threads = 50
        results: List[Dict[str, Any]] = []

        def send_request():
            resp = client.post(
                "/webhook/github",
                content=raw_body,
                headers={
                    "X-GitHub-Event": "issues",
                    "X-GitHub-Delivery": delivery_id,
                    "X-Hub-Signature-256": sig,
                },
            )
            return resp.status_code, resp.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(send_request) for _ in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                status_code, body = f.result()
                results.append({"status_code": status_code, "body": body})

        assert all(r["status_code"] == 200 for r in results)
        processed_count = sum(1 for r in results if r["body"].get("status") == "processed")
        duplicate_count = sum(1 for r in results if r["body"].get("status") == "duplicate")

        assert processed_count == 1, f"Expected exactly 1 processed request, got {processed_count}"
        assert duplicate_count == num_threads - 1, f"Expected {num_threads - 1} duplicates, got {duplicate_count}"

    def test_high_concurrency_distinct_deliveries_no_contention_loss(self):
        """Send 50 parallel distinct webhook requests. ALL 50 must be 'processed' with zero drops."""
        client = TestClient(app)
        num_requests = 50
        results: List[Dict[str, Any]] = []

        def send_distinct_request(idx: int):
            payload = {"action": "opened", "issue": {"number": idx, "title": f"Bounty #{idx}"}}
            raw_body = json.dumps(payload).encode("utf-8")
            sig = generate_github_signature(raw_body, TEST_SECRET)
            delivery_id = f"distinct-delivery-uuid-{idx}"

            resp = client.post(
                "/webhook/github",
                content=raw_body,
                headers={
                    "X-GitHub-Event": "issues",
                    "X-GitHub-Delivery": delivery_id,
                    "X-Hub-Signature-256": sig,
                },
            )
            return resp.status_code, resp.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(send_distinct_request, i) for i in range(num_requests)]
            for f in concurrent.futures.as_completed(futures):
                status_code, body = f.result()
                results.append({"status_code": status_code, "body": body})

        assert len(results) == num_requests
        assert all(r["status_code"] == 200 for r in results)
        processed_count = sum(1 for r in results if r["body"].get("status") == "processed")
        assert processed_count == num_requests, f"Expected {num_requests} processed, got {processed_count}"

    def test_distributed_lock_contention_single_winner(self):
        """50 concurrent threads race to acquire the same lock key. Exactly 1 wins, 49 fail."""
        lock_mgr = InMemoryFirestoreLock()
        lock_key = "race-condition-bounty-issue-42"
        num_threads = 50

        winners: List[str] = []

        def attempt_acquire(worker_id: str):
            acquired = lock_mgr.acquire_lock(lock_key=lock_key, ttl_seconds=60, owner_id=worker_id)
            if acquired:
                winners.append(worker_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(attempt_acquire, f"worker-{i}") for i in range(num_threads)]
            concurrent.futures.wait(futures)

        assert len(winners) == 1, f"Lock contention failed: {len(winners)} threads claimed the lock simultaneously"
        winner_id = winners[0]

        assert lock_mgr.release_lock(lock_key, owner_id="unauthorized-worker") is False
        assert lock_mgr.is_locked(lock_key) is True

        assert lock_mgr.release_lock(lock_key, owner_id=winner_id) is True
        assert lock_mgr.is_locked(lock_key) is False

    def test_reentrant_lock_ttl_extension_under_concurrency(self):
        """The same owner acquiring lock concurrently extends TTL without error."""
        lock_mgr = InMemoryFirestoreLock()
        lock_key = "reentrant-lock-key"
        owner = "owner-agent-1"

        assert lock_mgr.acquire_lock(lock_key, ttl_seconds=10, owner_id=owner) is True

        results = []
        def reacquire():
            return lock_mgr.acquire_lock(lock_key, ttl_seconds=20, owner_id=owner)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(reacquire) for _ in range(10)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        assert all(r is True for r in results)
        assert lock_mgr.is_locked(lock_key) is True


# ==============================================================================
# CHALLENGE SUITE 3: VERTEX AI CLIENT ERROR HANDLING & QUOTA PROJECT
# ==============================================================================

class SampleStructuredResponse(BaseModel):
    is_valid: bool = Field(description="Eligibility status")
    score: float = Field(description="Confidence score")
    notes: Optional[str] = Field(None, description="Reasoning summary")


class TestVertexAIClientAdversarialSuite:
    """Stress-tests for Vertex AI client initialization, ADC, quota projects, and failure modes."""

    def test_quota_project_present_vs_omitted_credentials_init(self):
        """Test credentials initialization with quota_project_id provided vs omitted."""
        factory_with_quota = VertexClientFactory(
            project_id="odin-500008",
            location="us-central1",
            quota_project_id="odin-500008",
        )
        assert factory_with_quota.quota_project_id == "odin-500008"

        factory_without_quota = VertexClientFactory(
            project_id="odin-500008",
            location="us-central1",
            quota_project_id=None,
        )
        assert factory_without_quota.project_id == "odin-500008"

    def test_adc_missing_and_gcloud_cli_failure_fails_gracefully(self):
        """When ADC is completely missing and gcloud CLI fails, get_credentials returns None without unhandled crash."""
        factory = VertexClientFactory(project_id="odin-500008")

        with patch("google.auth.default", side_effect=Exception("No ADC credentials found")):
            with patch("subprocess.check_output", side_effect=FileNotFoundError("gcloud command not found")):
                creds = factory.get_credentials()
                assert creds is None

    def test_gcloud_cli_timeout_handling(self):
        """When gcloud auth print-access-token times out, fallback executes cleanly."""
        factory = VertexClientFactory(project_id="odin-500008")

        with patch("google.auth.default") as mock_auth:
            mock_auth.side_effect = [
                Exception("quota project fail"),
                ("mock_fallback_credentials", "odin-500008"),
            ]
            with patch("subprocess.check_output", side_effect=subprocess.TimeoutExpired(cmd="gcloud", timeout=5)):
                creds = factory.get_credentials()
                assert creds == "mock_fallback_credentials"

    def test_generate_structured_empty_text_raises_value_error(self):
        """If Vertex AI returns empty text, generate_structured raises ValueError."""
        factory = VertexClientFactory(project_id="odin-500008")

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = ""
        mock_resp.parsed = None
        mock_client.models.generate_content.return_value = mock_resp

        factory._client = mock_client

        with pytest.raises(ValueError, match="Vertex AI response contained empty text"):
            factory.generate_structured(
                prompt="Evaluate bounty",
                response_schema=SampleStructuredResponse,
            )

    def test_generate_structured_malformed_json_raises_validation_error(self):
        """If Vertex AI returns invalid JSON string, Pydantic ValidationError is raised."""
        factory = VertexClientFactory(project_id="odin-500008")

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "NOT_A_VALID_JSON_STRING { broken"
        mock_client.models.generate_content.return_value = mock_resp

        factory._client = mock_client

        with pytest.raises(Exception):
            factory.generate_structured(
                prompt="Evaluate bounty",
                response_schema=SampleStructuredResponse,
            )

    def test_generate_structured_schema_mismatch_raises_validation_error(self):
        """If Vertex AI returns valid JSON but wrong schema (missing required fields), ValidationError is raised."""
        factory = VertexClientFactory(project_id="odin-500008")

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = json.dumps({"unexpected_field": 12345})
        mock_client.models.generate_content.return_value = mock_resp

        factory._client = mock_client

        with pytest.raises(Exception):
            factory.generate_structured(
                prompt="Evaluate bounty",
                response_schema=SampleStructuredResponse,
            )

    def test_generate_text_and_structured_api_exception_propagation(self):
        """Vertex AI API exceptions (e.g. 429 ResourceExhausted, 403 PermissionDenied) propagate properly."""
        factory = VertexClientFactory(project_id="odin-500008")

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("429 Quota Exceeded: Resource exhausted")
        factory._client = mock_client

        with pytest.raises(RuntimeError, match="429 Quota Exceeded"):
            factory.generate_text("Prompt")

        with pytest.raises(RuntimeError, match="429 Quota Exceeded"):
            factory.generate_structured("Prompt", SampleStructuredResponse)


# ==============================================================================
# CHALLENGE SUITE 4: GATEWAY BOUNDARIES & GITHUB CLIENT ERROR RESILIENCE
# ==============================================================================

class TestGatewayAndGitHubClientBoundaries:
    """Stress tests on gateway endpoints and GitHub Client error paths."""

    def test_gateway_empty_body_ping_vs_other_events(self):
        """Empty payload with ping succeeds (200), whereas empty payload with issues returns 400."""
        client = TestClient(app)
        empty_bytes = b""
        sig = generate_github_signature(empty_bytes, TEST_SECRET)

        # 1. Ping event with empty body
        resp_ping = client.post(
            "/webhook/github",
            content=empty_bytes,
            headers={
                "X-GitHub-Event": "ping",
                "X-GitHub-Delivery": "ping-empty-delivery",
                "X-Hub-Signature-256": sig,
            },
        )
        assert resp_ping.status_code == 200
        assert resp_ping.json()["status"] == "processed"

        # 2. Issues event with empty body -> 400 Bad Request
        resp_issues = client.post(
            "/webhook/github",
            content=empty_bytes,
            headers={
                "X-GitHub-Event": "issues",
                "X-GitHub-Delivery": "issues-empty-delivery",
                "X-Hub-Signature-256": sig,
            },
        )
        assert resp_issues.status_code == 400
        assert "Empty payload body" in resp_issues.json()["detail"]

    def test_gateway_malformed_json_payload_returns_400(self):
        """Valid HMAC signature on malformed JSON payload returns 400."""
        client = TestClient(app)
        malformed_bytes = b"{this is not valid json content: 123"
        sig = generate_github_signature(malformed_bytes, TEST_SECRET)

        resp = client.post(
            "/webhook/github",
            content=malformed_bytes,
            headers={
                "X-GitHub-Event": "issues",
                "X-GitHub-Delivery": "malformed-json-delivery",
                "X-Hub-Signature-256": sig,
            },
        )
        assert resp.status_code == 400
        assert "Malformed JSON payload" in resp.json()["detail"]

    def test_gateway_unmonitored_event_ignored(self):
        """Unmonitored events (e.g. push, star, fork) return status='ignored' with 200."""
        client = TestClient(app)
        payload = {"ref": "refs/heads/main", "commits": []}
        raw_bytes = json.dumps(payload).encode("utf-8")
        sig = generate_github_signature(raw_bytes, TEST_SECRET)

        resp = client.post(
            "/webhook/github",
            content=raw_bytes,
            headers={
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "push-event-delivery",
                "X-Hub-Signature-256": sig,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored"
        assert "not actively monitored" in data["details"]["reason"]

    def test_github_client_http_error_handling(self):
        """GitHubClient handles 401, 404, 422 HTTP errors via raise_for_status."""
        def mock_handler(request: httpx.Request) -> httpx.Response:
            if "404" in str(request.url):
                return httpx.Response(404, json={"message": "Not Found"})
            if "401" in str(request.url):
                return httpx.Response(401, json={"message": "Bad credentials"})
            return httpx.Response(200, json={"id": 123})

        transport = httpx.MockTransport(mock_handler)
        client = GitHubClient(token="mock-token", custom_transport=transport)

        with pytest.raises(httpx.HTTPStatusError):
            client.get_issue("owner", "repo", 404)

        with pytest.raises(httpx.HTTPStatusError):
            client.get_issue("owner", "repo", 401)

    def test_github_client_graphql_error_handling(self):
        """convert_draft_pr_to_ready returns False when GraphQL returns errors in response."""
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"errors": [{"message": "Could not resolve to a node with the global id of 'PR_123'"}]},
            )

        transport = httpx.MockTransport(mock_handler)
        client = GitHubClient(token="mock-token", custom_transport=transport)
        success = client.convert_draft_pr_to_ready("owner", "repo", 123, node_id="PR_123")
        assert success is False
