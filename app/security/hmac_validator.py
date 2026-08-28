"""GitHub Webhook HMAC-SHA256 Signature Validator.

Provides timing-attack resistant verification of X-Hub-Signature-256 headers.
"""

import hashlib
import hmac
import logging
from typing import Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


def generate_github_signature(payload_bytes: bytes, secret: str) -> str:
    """Generate a GitHub-compatible X-Hub-Signature-256 header value.

    Args:
        payload_bytes: The raw byte content of the webhook payload.
        secret: The HMAC secret key.

    Returns:
        Formatted signature string: "sha256=<hex_digest>".
    """
    mac = hmac.new(
        secret.encode("utf-8") if isinstance(secret, str) else secret,
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    )
    return f"sha256={mac.hexdigest()}"


def verify_github_signature(
    payload_bytes: bytes,
    signature_header: Optional[str],
    secret: Optional[str] = None,
) -> bool:
    """Verify GitHub X-Hub-Signature-256 HMAC against the raw request payload.

    Args:
        payload_bytes: Raw HTTP request body bytes.
        signature_header: The value of the X-Hub-Signature-256 header.
        secret: The shared webhook secret. If not provided, falls back to config.

    Returns:
        True if signature is valid and authentic, False otherwise.
    """
    if not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header")
        return False

    if not isinstance(signature_header, str):
        logger.warning("Invalid signature header type: %s", type(signature_header))
        return False

    if not signature_header.startswith("sha256="):
        logger.warning("Signature header does not use sha256 prefix: %s", signature_header[:10])
        return False

    provided_signature = signature_header[len("sha256=") :].strip()
    if not provided_signature:
        logger.warning("Empty hex digest in signature header")
        return False

    if secret is None:
        secret = get_settings().github_webhook_secret

    if not secret:
        logger.error("No GITHUB_WEBHOOK_SECRET configured; cannot verify signature")
        return False

    try:
        secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
        mac = hmac.new(secret_bytes, msg=payload_bytes, digestmod=hashlib.sha256)
        expected_signature = mac.hexdigest()

        # Constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(expected_signature, provided_signature)
        if not is_valid:
            logger.warning("HMAC signature mismatch for payload (%d bytes)", len(payload_bytes))
        return is_valid
    except Exception as exc:
        logger.error("Error verifying HMAC signature: %s", exc)
        return False
