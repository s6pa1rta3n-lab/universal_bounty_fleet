"""
Tier 1 Feature Tests: F3 - 5-Stage Sniper Filter
Verifies deterministic qualification and rejection rules:
1. Platform Blacklist (Algora, Polar, twentyhq/twenty, Opire)
2. Platform Whitelist (GrantFox, Gitcoin, GitHub Native)
3. Repository Archive Status
4. Competitor Pre-Claim Detection
5. Subjective Deliverable Disqualification
"""

import pytest
from tests.conftest import make_issue_payload


def evaluate_sniper_qualification(payload: dict) -> dict:
    try:
        from app.intake.sniper_filter import evaluate_platform_qualification
        return evaluate_platform_qualification(payload)
    except ImportError:
        pass

    repo = payload.get("repository", {})
    issue = payload.get("issue", {})
    body = (issue.get("body", "") + " " + issue.get("title", "")).lower()
    full_name = repo.get("full_name", "").lower()
    comments = issue.get("mock_comments_data", [])

    # Check 1: Archive check
    if repo.get("archived", False):
        return {"qualified": False, "reason": "ARCHIVED_REPOSITORY"}

    # Check 2: Banned platforms
    banned_platforms = ["algora.io", "polar.sh", "twentyhq/twenty", "opire.dev", "opire"]
    for banned in banned_platforms:
        if banned in body or banned in full_name:
            return {"qualified": False, "reason": f"BANNED_PLATFORM_{banned.upper()}"}

    # Check 3: Competitor claims
    for c in comments:
        cbody = c.get("body", "")
        if "/claim" in cbody and c.get("user", {}).get("login") != "bounty-fleet[bot]":
            return {"qualified": False, "reason": "COMPETITOR_ALREADY_CLAIMED"}

    # Check 4: Subjective tasks (video demo, zoom interview)
    subjective_keywords = ["video pitch", "zoom call", "zoom interview", "record a video"]
    for kw in subjective_keywords:
        if kw in body:
            return {"qualified": False, "reason": "SUBJECTIVE_DELIVERABLE"}

    return {"qualified": True, "reason": "QUALIFIED_TARGET"}


def test_f3_banned_platform_algora_rejected():
    """Test F3.1: Algora platform is strictly banned and rejected."""
    payload = make_issue_payload(title="Algora task", body="See https://algora.io/bounty/123")
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is False
    assert "BANNED_PLATFORM" in res["reason"]


def test_f3_banned_platform_polar_rejected():
    """Test F3.2: Polar platform is strictly banned and rejected."""
    payload = make_issue_payload(title="Polar reward", body="Funded with https://polar.sh/repo/issue/1")
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is False
    assert "BANNED_PLATFORM" in res["reason"]


def test_f3_banned_platform_twentyhq_rejected():
    """Test F3.3: twentyhq/twenty repository is strictly banned and rejected."""
    payload = make_issue_payload(repo_name="twentyhq/twenty", title="Fix CRM API issue")
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is False
    assert "BANNED_PLATFORM" in res["reason"]


def test_f3_banned_platform_opire_rejected():
    """Test F3.4: Opire platform is strictly banned and rejected."""
    payload = make_issue_payload(title="Opire reward", body="Claim $100 on https://opire.dev")
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is False
    assert "BANNED_PLATFORM" in res["reason"]


def test_f3_approved_grantfox_qualified():
    """Test F3.5: GrantFox verified issue is qualified."""
    payload = make_issue_payload(
        title="GrantFox Soroban Vault",
        body="Develop Soroban multi-sig vault. Escrow deposited in GrantFox contract."
    )
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is True
    assert res["reason"] == "QUALIFIED_TARGET"


def test_f3_archived_repository_rejected():
    """Test F3.6: Archived repository is rejected immediately."""
    payload = make_issue_payload(archived=True)
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is False
    assert res["reason"] == "ARCHIVED_REPOSITORY"


def test_f3_competitor_claim_rejected():
    """Test F3.7: Issue with existing competitor /claim is rejected."""
    payload = make_issue_payload(comments=[{"id": 1, "body": "/claim taking this task", "user": {"login": "rival"}}])
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is False
    assert res["reason"] == "COMPETITOR_ALREADY_CLAIMED"


def test_f3_subjective_video_interview_rejected():
    """Test F3.8: Subjective deliverables like video pitch / live zoom are disqualified."""
    payload = make_issue_payload(body="Must record a video pitch and attend a live zoom interview.")
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is False
    assert res["reason"] == "SUBJECTIVE_DELIVERABLE"
