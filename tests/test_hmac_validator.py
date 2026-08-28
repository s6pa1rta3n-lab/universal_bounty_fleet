"""Unit tests for GitHub Webhook HMAC-SHA256 Signature Validator."""

import hashlib
import hmac
import pytest
from app.security.hmac_validator import generate_github_signature, verify_github_signature


class TestHMACValidator:
    """Test suite for verify_github_signature and generate_github_signature."""

    def test_valid_signature_matches(self, webhook_secret: str):
        payload = b'{"action":"opened","issue":{"number":1}}'
        sig = generate_github_signature(payload, webhook_secret)

        assert verify_github_signature(payload, sig, webhook_secret) is True

    def test_invalid_signature_fails(self, webhook_secret: str):
        payload = b'{"action":"opened","issue":{"number":1}}'
        bad_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

        assert verify_github_signature(payload, bad_sig, webhook_secret) is False

    def test_tampered_payload_fails(self, webhook_secret: str):
        payload_orig = b'{"action":"opened","issue":{"number":1}}'
        payload_tampered = b'{"action":"opened","issue":{"number":2}}'
        sig = generate_github_signature(payload_orig, webhook_secret)

        assert verify_github_signature(payload_tampered, sig, webhook_secret) is False

    def test_missing_signature_header_fails(self, webhook_secret: str):
        payload = b'{"action":"ping"}'

        assert verify_github_signature(payload, None, webhook_secret) is False
        assert verify_github_signature(payload, "", webhook_secret) is False

    def test_malformed_signature_prefix_fails(self, webhook_secret: str):
        payload = b'{"action":"ping"}'
        raw_mac = hmac.new(webhook_secret.encode(), payload, hashlib.sha256).hexdigest()

        # Missing "sha256=" prefix
        assert verify_github_signature(payload, raw_mac, webhook_secret) is False
        # Wrong prefix
        assert verify_github_signature(payload, f"sha1={raw_mac}", webhook_secret) is False
        assert verify_github_signature(payload, f"md5={raw_mac}", webhook_secret) is False

    def test_empty_hex_digest_fails(self, webhook_secret: str):
        payload = b'{"action":"ping"}'
        assert verify_github_signature(payload, "sha256=", webhook_secret) is False
        assert verify_github_signature(payload, "sha256=   ", webhook_secret) is False

    def test_wrong_secret_fails(self):
        payload = b'{"action":"opened"}'
        sig = generate_github_signature(payload, "secret-A")

        assert verify_github_signature(payload, sig, "secret-B") is False

    def test_empty_payload_verification(self, webhook_secret: str):
        payload = b""
        sig = generate_github_signature(payload, webhook_secret)

        assert verify_github_signature(payload, sig, webhook_secret) is True

    def test_unicode_payload_verification(self, webhook_secret: str):
        payload = '{"title":"🚀 Bounty on Stellar ⚡️","amount":"1000 XLM"}'.encode("utf-8")
        sig = generate_github_signature(payload, webhook_secret)

        assert verify_github_signature(payload, sig, webhook_secret) is True

    def test_non_string_signature_header_handled_gracefully(self, webhook_secret: str):
        payload = b'{"action":"ping"}'
        # Pass non-string types
        assert verify_github_signature(payload, 12345, webhook_secret) is False  # type: ignore
        assert verify_github_signature(payload, ["sha256=abc"], webhook_secret) is False  # type: ignore
