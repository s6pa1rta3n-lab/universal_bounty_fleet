"""Intake Taskmaster & Escrow Engine Module for The Universal Bounty Fleet.

Includes:
- 5-Stage Sniper Filter (sniper_filter.py)
- Semantic Escrow Verification Engine (escrow_engine.py)
- Autonomous Intent Staker (claim_staker.py)
"""

from typing import Any, Dict, Optional

from app.intake.sniper_filter import (
    SniperFilter,
    SniperFilterResult,
    evaluate_platform_qualification,
)
from app.intake.escrow_engine import (
    EscrowEngine,
    EscrowEvaluationSchema,
    evaluate_escrow_funding,
)
from app.intake.claim_staker import (
    ClaimStaker,
    execute_claim_staking,
    format_claim_comment,
)


class IntakePipeline:
    """End-to-end Intake Taskmaster pipeline coordinator."""

    def __init__(
        self,
        sniper_filter: Optional[SniperFilter] = None,
        escrow_engine: Optional[EscrowEngine] = None,
        claim_staker: Optional[ClaimStaker] = None,
    ) -> None:
        self.sniper_filter = sniper_filter or SniperFilter()
        self.escrow_engine = escrow_engine or EscrowEngine()
        self.claim_staker = claim_staker or ClaimStaker()

    def process_issue(
        self,
        payload: Dict[str, Any],
        github_client: Optional[Any] = None,
        vertex_client: Optional[Any] = None,
        firestore_client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute full intake pipeline: Sniper Filter -> Escrow Verification -> Intent Staking."""
        # 1. Sniper Filter Qualification Gate
        qual_res = self.sniper_filter.evaluate(payload)
        if not qual_res.get("qualified", False):
            return {
                "qualified": False,
                "staked": False,
                "reason": qual_res.get("reason"),
                "stage_failed": qual_res.get("stage_failed"),
                "details": qual_res.get("details", {}),
            }

        # 2. Semantic Escrow Funding Gate
        escrow_res = self.escrow_engine.evaluate(payload, vertex_client=vertex_client)
        if not escrow_res.get("is_funded", False):
            return {
                "qualified": False,
                "staked": False,
                "reason": "Escrow unfunded",
                "escrow_amount": escrow_res.get("amount_usd", 0.0),
                "escrow_reasoning": escrow_res.get("reasoning"),
            }

        # 3. Autonomous Intent Staking Gate
        staked_res = self.claim_staker.stake_intent(
            payload=payload,
            github_client=github_client,
            firestore_client=firestore_client,
        )

        return {
            "qualified": True,
            "staked": staked_res.get("success", False),
            "comment_id": staked_res.get("comment_id"),
            "amount": escrow_res.get("amount", escrow_res.get("amount_usd", 0.0)),
            "amount_usd": escrow_res.get("amount_usd", 0.0),
            "reason": staked_res.get("reason") if not staked_res.get("success") else None,
            "repo": staked_res.get("repo"),
            "issue_number": staked_res.get("issue_number"),
        }


# Global pipeline instance
_intake_pipeline_instance = IntakePipeline()


def run_intake_pipeline(
    payload: Dict[str, Any],
    github_client: Optional[Any] = None,
    vertex_client: Optional[Any] = None,
    firestore_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Execute end-to-end intake processing on GitHub issue payload."""
    return _intake_pipeline_instance.process_issue(
        payload=payload,
        github_client=github_client,
        vertex_client=vertex_client,
        firestore_client=firestore_client,
    )


__all__ = [
    "SniperFilter",
    "SniperFilterResult",
    "evaluate_platform_qualification",
    "EscrowEngine",
    "EscrowEvaluationSchema",
    "evaluate_escrow_funding",
    "ClaimStaker",
    "execute_claim_staking",
    "format_claim_comment",
    "IntakePipeline",
    "run_intake_pipeline",
]
