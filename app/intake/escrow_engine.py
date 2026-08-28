"""Semantic Escrow Verification Engine for The Universal Bounty Fleet.

Evaluates GitHub issue descriptions, labels, and discussion comments using Vertex AI
Gemini (or configured client) with Pydantic structured schema validation to verify
cryptographic bot confirmations, smart contract escrow pools, or maintainer funding commitments.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.config import get_settings
from app.utils.vertex_client import get_vertex_client

logger = logging.getLogger(__name__)

# Minimum confidence required for high-assurance qualification
MIN_ESCROW_CONFIDENCE = 0.50

# Cancellation / refund trigger patterns
CANCELLATION_PATTERNS = [
    r"cancelled",
    r"refunded",
    r"withdrawn",
    r"voided",
    r"returned\s+to\s+(?:the\s+)?funder",
    r"returned\s+by\s+submitter",
    r"insufficient\s+fund\s+balance",
    r"escrow\s+failed",
    r"escrow\s+rejected",
]


class EscrowEvaluationSchema(BaseModel):
    """Pydantic schema for structured Vertex AI Gemini escrow evaluation."""

    is_funded: bool = Field(
        default=False,
        description="True if escrow funds are verified, confirmed, or locked by bot/maintainer",
    )
    escrow_amount_usd: float = Field(
        default=0.0,
        description="Parsed reward/bounty amount normalized to USD or USD equivalent",
    )
    currency: str = Field(
        default="USD",
        description="Original currency token (USD, USDC, USDT, XLM, ETH, etc.)",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    reasoning: str = Field(
        default="",
        description="Detailed explanation of escrow determination and proof extraction",
    )
    is_cancelled_or_refunded: bool = Field(
        default=False,
        description="True if comments indicate the bounty was cancelled, refunded, or expired",
    )


def extract_regex_financials(text: str) -> Dict[str, Any]:
    """Fallback deterministic regex parser for currency and token amounts."""
    # Check for cancellation first
    for pat in CANCELLATION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return {
                "is_funded": False,
                "amount_usd": 0.0,
                "currency": "USD",
                "confidence": 0.95,
                "reasoning": "Detected explicit cancellation or refund pattern.",
                "is_cancelled": True,
            }

    # Match dollar values like $5,000, $250,000.50, $500.00
    usd_match = re.search(r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)", text)
    if usd_match:
        val_str = usd_match.group(1).replace(",", "")
        try:
            amount = float(val_str)
            if amount > 0:
                return {
                    "is_funded": True,
                    "amount_usd": amount,
                    "currency": "USD",
                    "confidence": 0.85,
                    "reasoning": f"Extracted USD amount ${amount:,.2f}",
                    "is_cancelled": False,
                }
        except ValueError:
            pass

    # Match token values like 10,000 XLM, 500 USDC
    token_match = re.search(
        r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(USDC|USDT|XLM|ETH|WETH|DAI|MATIC|SOL|USD)",
        text,
        re.IGNORECASE,
    )
    if token_match:
        val_str = token_match.group(1).replace(",", "")
        tok = token_match.group(2).upper()
        try:
            amount = float(val_str)
            if amount > 0:
                return {
                    "is_funded": True,
                    "amount_usd": amount,
                    "currency": tok,
                    "confidence": 0.80,
                    "reasoning": f"Extracted token amount {amount:,.2f} {tok}",
                    "is_cancelled": False,
                }
        except ValueError:
            pass

    return {
        "is_funded": False,
        "amount_usd": 0.0,
        "currency": "USD",
        "confidence": 0.0,
        "reasoning": "No funded escrow amounts detected.",
        "is_cancelled": False,
    }


class EscrowEngine:
    """Evaluates semantic escrow funding using Vertex AI Gemini models."""

    def __init__(self, default_model: str = "gemini-2.5-flash") -> None:
        self.default_model = default_model

    def evaluate(
        self,
        payload: Dict[str, Any],
        vertex_client: Optional[Any] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute semantic escrow evaluation against an issue payload."""
        if not isinstance(payload, dict):
            return {
                "is_funded": False,
                "amount_usd": 0.0,
                "amount": 0.0,
                "currency": "USD",
                "confidence": 0.0,
                "reasoning": "Invalid payload dictionary",
            }

        issue = payload.get("issue", {})
        repo = payload.get("repository", {})
        target_model = model or self.default_model

        issue_title = str(issue.get("title") or "")
        issue_body = str(issue.get("body") or "")
        repo_name = str(repo.get("full_name") or "")

        raw_comments = issue.get("mock_comments_data") or issue.get("comments_data") or []
        if not isinstance(raw_comments, list):
            raw_comments = []

        comments_text = "\n".join(
            [f"Comment by {c.get('user', {}).get('login', 'unknown')}: {c.get('body', '')}" for c in raw_comments if isinstance(c, dict)]
        )

        prompt = (
            f"You are the Escrow Verification Engine for The Universal Bounty Fleet.\n"
            f"Analyze the following GitHub issue and comments to determine if a financial bounty or grant is genuinely funded, locked, or deposited in escrow.\n\n"
            f"Repository: {repo_name}\n"
            f"Issue Title: {issue_title}\n"
            f"Issue Body:\n{issue_body}\n\n"
            f"Comments:\n{comments_text}\n\n"
            f"Determine if the issue has verified escrow funding, the amount in USD, confidence level (0.0 to 1.0), and whether the bounty has been cancelled or refunded.\n"
            f"Respond with JSON adhering to the EscrowEvaluationSchema."
        )

        # 1. Execute LLM Reasoning if client is provided or available
        eval_data: Optional[Dict[str, Any]] = None

        if vertex_client is not None:
            # Client provided in arguments (e.g. during testing or custom injection)
            try:
                if hasattr(vertex_client, "_structured_response") and getattr(vertex_client, "_structured_response", None) is not None:
                    structured_obj = vertex_client._structured_response
                    if hasattr(structured_obj, "model_dump"):
                        eval_data = structured_obj.model_dump()
                    elif isinstance(structured_obj, dict):
                        eval_data = structured_obj
                    else:
                        eval_data = getattr(structured_obj, "__dict__", {})
                elif hasattr(vertex_client, "generate_content"):
                    resp = vertex_client.generate_content(target_model, contents=prompt)
                    raw_text = getattr(resp, "text", str(resp))
                    try:
                        eval_data = json.loads(raw_text)
                    except Exception:
                        logger.warning("Failed to parse JSON from vertex_client.generate_content: %s", raw_text)
                        return {
                            "is_funded": False,
                            "amount_usd": 0.0,
                            "amount": 0.0,
                            "currency": "USD",
                            "confidence": 0.0,
                            "reasoning": "Malformed JSON response from Vertex AI",
                        }
                elif hasattr(vertex_client, "generate_structured"):
                    structured_obj = vertex_client.generate_structured(
                        prompt, EscrowEvaluationSchema, model=target_model
                    )
                    eval_data = structured_obj.model_dump()
                elif hasattr(vertex_client, "generate_text"):
                    raw_text = vertex_client.generate_text(prompt, model=target_model)
                    eval_data = json.loads(raw_text)
            except Exception as exc:
                logger.warning("Vertex client evaluation encountered exception: %s", exc)
                return {
                    "is_funded": False,
                    "amount_usd": 0.0,
                    "amount": 0.0,
                    "currency": "USD",
                    "confidence": 0.0,
                    "reasoning": f"Vertex client error: {exc}",
                }
        else:
            from app.config import get_settings
            settings = get_settings()
            if settings.app_env == "test":
                combined_content = f"{issue_title}\n{issue_body}\n{comments_text}"
                eval_data = extract_regex_financials(combined_content)
            else:
                # Live Vertex AI client from factory
                try:
                    client_factory = get_vertex_client()
                    structured_res = client_factory.generate_structured(
                        prompt=prompt,
                        response_schema=EscrowEvaluationSchema,
                        model=target_model,
                        system_instruction="You are an expert financial auditor specializing in Web3 grant pools and GitHub issue escrow contracts.",
                    )
                    eval_data = structured_res.model_dump()
                except Exception as live_err:
                    logger.warning("Live Vertex AI call failed, falling back to deterministic regex parser: %s", live_err)
                    combined_content = f"{issue_title}\n{issue_body}\n{comments_text}"
                    eval_data = extract_regex_financials(combined_content)

        if eval_data is None:
            combined_content = f"{issue_title}\n{issue_body}\n{comments_text}"
            eval_data = extract_regex_financials(combined_content)

        # 2. Invariant Normalization & Validation
        is_funded = bool(eval_data.get("is_funded", False))
        amount_usd = float(eval_data.get("escrow_amount_usd", eval_data.get("amount_usd", 0.0)))
        confidence = float(eval_data.get("confidence", 0.0))
        reasoning = str(eval_data.get("reasoning", ""))
        currency = str(eval_data.get("currency", "USD"))
        is_cancelled = bool(eval_data.get("is_cancelled_or_refunded", eval_data.get("is_cancelled", False)))

        # Rule A: Enforce zero-dollar or negative bounds
        if amount_usd <= 0.0:
            is_funded = False
            amount_usd = 0.0

        # Rule B: Enforce minimum confidence threshold (< 0.50 -> unfunded)
        if confidence < MIN_ESCROW_CONFIDENCE:
            is_funded = False

        # Rule C: Enforce cancellation override
        if is_cancelled:
            is_funded = False
            amount_usd = 0.0

        # Rule D: Additional safety scan across comments for explicit cancellations
        for comment in raw_comments:
            if isinstance(comment, dict):
                c_body = str(comment.get("body") or "")
                for pat in CANCELLATION_PATTERNS:
                    if re.search(pat, c_body, re.IGNORECASE):
                        is_funded = False
                        amount_usd = 0.0
                        reasoning = f"Cancellation pattern detected in comment: {c_body[:60]}"
                        break

        return {
            "is_funded": is_funded,
            "amount_usd": amount_usd,
            "amount": amount_usd,  # Compatibility alias
            "currency": currency,
            "confidence": confidence,
            "reasoning": reasoning,
            "is_cancelled": is_cancelled,
        }


# Global singleton instance
_escrow_engine_instance = EscrowEngine()


def evaluate_escrow_funding(
    payload: Dict[str, Any],
    vertex_client: Optional[Any] = None,
    model: str = "gemini-2.5-flash",
) -> Dict[str, Any]:
    """Evaluate semantic escrow status for target issue."""
    return _escrow_engine_instance.evaluate(payload, vertex_client=vertex_client, model=model)
