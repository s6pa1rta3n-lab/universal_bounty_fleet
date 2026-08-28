"""The Universal Bounty Fleet - Stateless Webhook Gateway & Dispatcher Service.

Google Cloud Run FastAPI application handling incoming GitHub webhooks,
HMAC-SHA256 verification, Firestore distributed idempotency locks,
and routing to Intake Taskmaster and Victory Audit Fleet subagents.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import get_settings
from app.memory.bank import classify_cheat, get_memory_bank, seed_demo_bounty
from app.memory.registry import registry_payload
from app.security.firestore_lock import get_lock_manager
from app.security.hmac_validator import verify_github_signature

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("universal_bounty_fleet")

CONSOLE_DIR = Path(__file__).parent / "static" / "console"

app = FastAPI(
    title="The Universal Bounty Fleet - Gateway",
    description="Stateless Webhook Gateway & GEAP Multi-Agent Orchestrator",
    version="1.0.0",
)

if CONSOLE_DIR.exists():
    app.mount("/console/assets", StaticFiles(directory=CONSOLE_DIR), name="console-assets")


class WebhookResponse(BaseModel):
    """Standardized response model for webhook events."""

    status: str = Field(description="Processing status: processed, duplicate, ignored, error")
    event: str = Field(description="GitHub event type from X-GitHub-Event")
    action: Optional[str] = Field(None, description="Event action (opened, synchronize, etc.)")
    delivery_id: Optional[str] = Field(None, description="GitHub delivery UUID")
    target_agent: Optional[str] = Field(None, description="Routed subagent (intake_taskmaster, victory_auditor)")
    details: Dict[str, Any] = Field(default_factory=dict, description="Execution and routing metadata")


def _persist_intake(details: Dict[str, Any], issue: Dict[str, Any]) -> None:
    """Write Intake decisions into the Memory Bank for the Fleet Console."""
    try:
        repo = details.get("repo") or "unknown/unknown"
        issue_number = details.get("issue_number") or 0
        bounty_id = f"{repo}#{issue_number}"
        bank = get_memory_bank()
        bank.upsert(
            bounty_id,
            {
                "title": details.get("title") or issue.get("title"),
                "repo": repo,
                "issue_number": issue_number,
                "issue_url": issue.get("html_url"),
                "escrow": {
                    "verified": bool(details.get("is_funded")),
                    "amount_usd": details.get("escrow_amount") or 0.0,
                    "source": "intake",
                },
                "audit_status": "PENDING",
                "agents": {"intake": "working" if details.get("staked") else "idle"},
                "source": "live",
                "gcp": {"trace_id": details.get("comment_id") and f"intake-{details.get('comment_id')}"},
            },
        )
        if details.get("staked"):
            bank.append_event(bounty_id, "claimed", f"/try on #{issue_number}")
        elif details.get("qualified"):
            bank.append_event(bounty_id, "qualified", details.get("qualification_reason") or "qualified")
        else:
            bank.append_event(bounty_id, "rejected", details.get("qualification_reason") or "not qualified")
    except Exception as exc:
        logger.debug("Memory Bank intake persist skipped: %s", exc)


def _persist_audit(details: Dict[str, Any], pr: Dict[str, Any]) -> None:
    """Write Auditor verdicts into the Memory Bank. Merge stays blocked unless PASS."""
    try:
        repo = details.get("repo") or "unknown/unknown"
        pr_number = details.get("pr_number") or 0
        bounty_id = f"{repo}#{pr_number}"
        findings = details.get("audit_findings") or {}
        verdict = details.get("verdict") or "REQUEST_CHANGES"
        cheat = classify_cheat(findings)
        passed = verdict == "APPROVE"
        bank = get_memory_bank()
        bank.upsert(
            bounty_id,
            {
                "title": pr.get("title"),
                "repo": repo,
                "pr_number": pr_number,
                "pr_url": pr.get("html_url"),
                "audit_status": "PASS" if passed else "FAIL",
                "cheat_detected": None if passed else cheat,
                "agents": {
                    "executor": "idle" if passed else "waiting",
                    "auditor": "reviewing" if not passed else "idle",
                },
                "source": "live",
                "gcp": {"trace_id": details.get("review_id") and f"audit-{details.get('review_id')}"},
            },
        )
        if details.get("is_draft"):
            bank.append_event(bounty_id, "draft_pr", f"Draft PR #{pr_number} observed")
        if passed:
            bank.append_event(bounty_id, "audit_pass", findings.get("summary") or "Victory Audit passed")
        else:
            bank.append_event(
                bounty_id,
                "audit_fail",
                findings.get("summary") or f"REQUEST_CHANGES ({cheat or 'policy'})",
            )
    except Exception as exc:
        logger.debug("Memory Bank audit persist skipped: %s", exc)


@app.get("/", tags=["System"])
async def root() -> Dict[str, Any]:
    """Root metadata endpoint."""
    settings = get_settings()
    return {
        "name": "The Universal Bounty Fleet",
        "service": "universal-bounty-gateway",
        "version": "1.0.0",
        "status": "active",
        "project": settings.gcp_project,
        "region": settings.gcp_region,
        "track": "Fortified Enterprise Fleet",
        "console_url": "/console",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/console", tags=["Console"])
@app.get("/console/", tags=["Console"])
async def fleet_console() -> FileResponse:
    """Serve the Fleet Console used for the live judging demo."""
    index = CONSOLE_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Fleet Console is not packaged")
    return FileResponse(index)


@app.get("/api/registry", tags=["Console"])
async def api_registry() -> Dict[str, Any]:
    return registry_payload()


@app.get("/api/bounties/latest", tags=["Console"])
async def api_latest_bounty() -> Dict[str, Any]:
    bank = get_memory_bank()
    bounty = bank.latest()
    if bounty is None:
        bounty = seed_demo_bounty(bank)
    return {"bounty": bounty}


@app.get("/api/bounties", tags=["Console"])
async def api_list_bounties() -> Dict[str, Any]:
    bank = get_memory_bank()
    if not bank.list_all():
        seed_demo_bounty(bank)
    return {"bounties": bank.list_all()}


@app.get("/api/bounties/{bounty_id}", tags=["Console"])
async def api_get_bounty(bounty_id: str) -> Dict[str, Any]:
    bounty = get_memory_bank().get(bounty_id)
    if not bounty:
        raise HTTPException(status_code=404, detail=f"Unknown bounty {bounty_id}")
    return bounty


@app.get("/health", tags=["System"])
@app.get("/healthz", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """Health probe for Google Cloud Run and uptime checks."""
    return {
        "status": "healthy",
        "service": "universal-bounty-fleet",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# --- Webhook Handlers ---


async def route_issue_event(
    action: str,
    payload: Dict[str, Any],
    delivery_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Route GitHub issue webhook event to the Intake Taskmaster agent pipeline."""
    issue = payload.get("issue", {})
    repo = payload.get("repository", {})
    issue_number = issue.get("number")
    repo_full_name = repo.get("full_name", "unknown/unknown")

    logger.info(
        "Routing issue event to Intake Taskmaster: repo=%s issue=#%s action=%s",
        repo_full_name,
        issue_number,
        action,
    )

    from app.intake.sniper_filter import evaluate_platform_qualification
    from app.intake.escrow_engine import evaluate_escrow_funding
    from app.intake.claim_staker import execute_claim_staking

    # Milestone 2: Execute SniperFilter, Escrow Verification, and Intent Staking
    qual_res = evaluate_platform_qualification(payload)
    is_qualified = qual_res.get("qualified", False)
    qual_reason = qual_res.get("reason", "UNKNOWN")

    escrow_res: Dict[str, Any] = {}
    is_funded = False
    staked_res: Dict[str, Any] = {}

    if is_qualified and action in ("opened", "reopened", "labeled", "created", "synchronize", "unknown"):
        escrow_res = evaluate_escrow_funding(payload)
        is_funded = escrow_res.get("is_funded", False)
        if is_funded:
            settings = get_settings()
            if settings.github_token or settings.app_env != "test":
                try:
                    staked_res = execute_claim_staking(payload)
                except Exception as stake_err:
                    logger.debug("Could not stake intent: %s", stake_err)

    details = {
        "repo": repo_full_name,
        "issue_number": issue_number,
        "action": action,
        "title": issue.get("title"),
        "author": issue.get("user", {}).get("login"),
        "labels": [label.get("name") for label in issue.get("labels", []) if isinstance(label, dict)],
        "routed_to": "intake_taskmaster",
        "qualified": is_qualified,
        "qualification_reason": qual_reason,
        "is_funded": is_funded,
        "escrow_amount": escrow_res.get("amount_usd", 0.0),
        "staked": staked_res.get("success", False),
        "comment_id": staked_res.get("comment_id"),
    }
    _persist_intake(details, issue)
    return details


async def route_pull_request_event(
    action: str,
    payload: Dict[str, Any],
    delivery_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Route GitHub pull_request webhook event to the Victory Audit Fleet agent pipeline."""
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    pr_number = pr.get("number")
    repo_full_name = repo.get("full_name", "unknown/unknown")
    is_draft = pr.get("draft", False)
    head_sha = pr.get("head", {}).get("sha")

    logger.info(
        "Routing PR event to Victory Audit Fleet: repo=%s PR=#%s action=%s draft=%s sha=%s",
        repo_full_name,
        pr_number,
        action,
        is_draft,
        head_sha,
    )

    from app.audit.murder_board import analyze_diff_security
    from app.audit.review_submitter import submit_pr_review
    from app.audit.draft_converter import convert_draft_to_ready
    from app.utils.github_client import get_github_client

    # Obtain diff content
    diff_text = pr.get("mock_diff_content") or payload.get("diff_text") or ""
    settings = get_settings()
    if not diff_text and pr_number and settings.github_token and settings.app_env != "test":
        try:
            repo_parts = repo_full_name.split("/")
            if len(repo_parts) >= 2:
                owner, rname = repo_parts[0], repo_parts[1]
                gh_client = get_github_client()
                diff_text = gh_client.get_pr_diff(owner, rname, pr_number)
        except Exception as exc:
            logger.debug("Could not fetch remote PR diff: %s", exc)

    audit_res = analyze_diff_security(diff_text)
    is_clean = audit_res.get("pillar1_crypto", True) and audit_res.get("pillar2_auth", True) and audit_res.get("pillar3_assertions", True)
    verdict = "APPROVE" if is_clean else "REQUEST_CHANGES"

    review_res = {}
    draft_converted = False
    if action in ("opened", "synchronize", "ready_for_review", "created", "reopened", "unknown"):
        if settings.github_token or settings.app_env != "test":
            try:
                gh_client = get_github_client()
                review_res = submit_pr_review(
                    pr_payload=payload,
                    verdict=verdict,
                    findings=audit_res,
                    github_client=gh_client,
                )
                if verdict == "APPROVE" and is_draft:
                    node_id = pr.get("node_id")
                    repo_parts = repo_full_name.split("/")
                    owner = repo_parts[0] if len(repo_parts) > 1 else "unknown"
                    rname = repo_parts[1] if len(repo_parts) > 1 else repo_full_name
                    draft_converted = convert_draft_to_ready(
                        node_id=node_id,
                        owner=owner,
                        repo=rname,
                        pull_number=pr_number,
                        github_client=gh_client,
                    )
            except Exception as review_err:
                logger.debug("Could not submit PR review / convert draft: %s", review_err)

    details = {
        "repo": repo_full_name,
        "pr_number": pr_number,
        "action": action,
        "is_draft": is_draft,
        "head_sha": head_sha,
        "author": pr.get("user", {}).get("login"),
        "base_branch": pr.get("base", {}).get("ref"),
        "routed_to": "victory_auditor",
        "verdict": verdict,
        "audit_findings": audit_res,
        "review_id": review_res.get("review_id") or review_res.get("id"),
        "draft_converted": draft_converted,
    }
    _persist_audit(details, pr)
    return details


async def route_comment_event(
    action: str,
    payload: Dict[str, Any],
    delivery_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Route GitHub issue_comment webhook event for stigmergic agent coordination."""
    comment = payload.get("comment", {})
    issue = payload.get("issue", {})
    repo = payload.get("repository", {})
    comment_body = comment.get("body", "")
    is_pr = "pull_request" in issue

    target_agent = "victory_auditor" if (is_pr and "@universal_auditor" in comment_body) else "intake_taskmaster"

    logger.info(
        "Routing comment event: repo=%s issue=#%s is_pr=%s target=%s",
        repo.get("full_name"),
        issue.get("number"),
        is_pr,
        target_agent,
    )

    details: Dict[str, Any] = {
        "repo": repo.get("full_name"),
        "issue_number": issue.get("number"),
        "is_pr": is_pr,
        "comment_author": comment.get("user", {}).get("login"),
        "body_preview": comment_body[:100],
        "routed_to": target_agent,
    }

    if target_agent == "victory_auditor" and action in ("created", "opened"):
        from app.audit.murder_board import analyze_diff_security
        from app.audit.review_submitter import submit_pr_review
        from app.utils.github_client import get_github_client

        diff_text = payload.get("mock_diff_content") or ""
        findings = analyze_diff_security(diff_text)
        is_clean = findings.get("pillar1_crypto", True) and findings.get("pillar2_auth", True) and findings.get("pillar3_assertions", True)
        verdict = "APPROVE" if is_clean else "REQUEST_CHANGES"

        settings = get_settings()
        if settings.github_token or settings.app_env != "test":
            try:
                gh_client = get_github_client()
                review_res = submit_pr_review(payload, verdict, findings, github_client=gh_client)
                details["verdict"] = verdict
                details["review_id"] = review_res.get("review_id") or review_res.get("id")
            except Exception as exc:
                logger.debug("Comment-triggered audit could not submit review: %s", exc)

    return details


@app.post(
    "/webhook/github",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    tags=["Webhook"],
)
@app.post(
    "/webhook",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    tags=["Webhook"],
)
async def github_webhook_endpoint(
    request: Request,
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
) -> WebhookResponse:
    """Ingest, verify, deduplicate, and route GitHub webhooks statelessly."""
    # 1. Read raw body bytes for cryptographic HMAC verification
    raw_body = await request.body()

    # 2. Verify HMAC-SHA256 signature
    is_valid_sig = verify_github_signature(
        payload_bytes=raw_body,
        signature_header=x_hub_signature_256,
    )
    if not is_valid_sig:
        logger.warning("Rejected webhook: Invalid or missing X-Hub-Signature-256 signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Hub-Signature-256 webhook signature",
        )

    # 3. Check for empty payload
    if len(raw_body) == 0:
        event_type = x_github_event or "unknown"
        if event_type == "ping":
            return WebhookResponse(
                status="processed",
                event="ping",
                action="ping",
                delivery_id=x_github_delivery or "unknown-delivery",
                details={"zen": "Ping received with empty body", "size": 0},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty payload body",
        )

    # 4. Parse JSON payload
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as parse_err:
        logger.error("Failed to parse webhook JSON payload: %s", parse_err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {parse_err}",
        )

    event_type = x_github_event or "unknown"
    delivery_id = x_github_delivery or "unknown-delivery"
    action = payload.get("action", "unknown")

    # 5. Check & record event delivery idempotency lock via Firestore
    lock_mgr = get_lock_manager()
    is_new = lock_mgr.mark_event_processed(
        delivery_id=delivery_id,
        event_type=event_type,
        metadata={"action": action, "repo": payload.get("repository", {}).get("full_name")},
    )
    if not is_new and delivery_id != "unknown-delivery":
        logger.info("Ignoring duplicate webhook delivery: %s", delivery_id)
        return WebhookResponse(
            status="duplicate",
            event=event_type,
            action=action,
            delivery_id=delivery_id,
            details={"message": "Event already processed or in-flight (Firestore idempotency match)", "size": len(raw_body)},
        )

    # 6. Route event based on X-GitHub-Event header
    if event_type == "issues":
        details = await route_issue_event(action, payload, delivery_id)
        details["size"] = len(raw_body)
        return WebhookResponse(
            status="processed",
            event=event_type,
            action=action,
            delivery_id=delivery_id,
            target_agent="intake_taskmaster",
            details=details,
        )

    elif event_type == "pull_request":
        details = await route_pull_request_event(action, payload, delivery_id)
        details["size"] = len(raw_body)
        return WebhookResponse(
            status="processed",
            event=event_type,
            action=action,
            delivery_id=delivery_id,
            target_agent="victory_auditor",
            details=details,
        )

    elif event_type == "issue_comment":
        details = await route_comment_event(action, payload, delivery_id)
        details["size"] = len(raw_body)
        return WebhookResponse(
            status="processed",
            event=event_type,
            action=action,
            delivery_id=delivery_id,
            target_agent=details.get("routed_to", "intake_taskmaster"),
            details=details,
        )

    elif event_type == "pull_request_review":
        logger.info("Received pull_request_review event: action=%s", action)
        return WebhookResponse(
            status="processed",
            event=event_type,
            action=action,
            delivery_id=delivery_id,
            target_agent="victory_auditor",
            details={"action": action, "repo": payload.get("repository", {}).get("full_name"), "size": len(raw_body)},
        )

    elif event_type == "ping":
        logger.info("Received GitHub ping webhook")
        return WebhookResponse(
            status="processed",
            event=event_type,
            action="ping",
            delivery_id=delivery_id,
            details={"zen": payload.get("zen", "GitHub webhook active"), "size": len(raw_body)},
        )

    else:
        logger.info("Received unmonitored event type: %s", event_type)
        return WebhookResponse(
            status="ignored",
            event=event_type,
            action=action,
            delivery_id=delivery_id,
            details={"reason": f"Event type '{event_type}' not actively monitored", "size": len(raw_body)},
        )
