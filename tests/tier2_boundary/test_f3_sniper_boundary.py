"""
Tier 2 Boundary Tests: F3 - Sniper Filter Boundary & Corner Cases
"""

import pytest
from tests.conftest import make_issue_payload
from tests.tier1_feature.test_f3_sniper_filter import evaluate_sniper_qualification


def test_f3_boundary_case_insensitive_banned_platform_detection():
    """Test F3-B.1: Catches uppercase and mixed-case banned platforms (e.g. ALGORA.IO, PoLaR.Sh)."""
    payload = make_issue_payload(title="Task on ALGORA.IO and POLAR.SH")
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is False
    assert "BANNED_PLATFORM" in res["reason"]


def test_f3_boundary_subdomain_and_url_paths():
    """Test F3-B.2: Catches variations like https://app.opire.dev/ or staging.polar.sh."""
    payload = make_issue_payload(body="Claim reward at https://app.opire.dev/task/1")
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is False
    assert "BANNED_PLATFORM" in res["reason"]


def test_f3_boundary_empty_issue_body_and_title():
    """Test F3-B.3: Empty body and title without keywords passes filter safely (evaluated by escrow next)."""
    payload = make_issue_payload(title="", body="", comments=[])
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is True


def test_f3_boundary_competitor_claim_in_last_of_100_comments():
    """Test F3-B.4: Detects competitor /claim buried deep in a 100-comment thread."""
    comments = [{"id": i, "body": f"Standard discussion {i}", "user": {"login": f"user_{i}"}} for i in range(99)]
    comments.append({"id": 100, "body": "/claim I have finished the implementation", "user": {"login": "fast_competitor"}})
    
    payload = make_issue_payload(comments=comments)
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is False
    assert res["reason"] == "COMPETITOR_ALREADY_CLAIMED"


def test_f3_boundary_fleet_own_claim_not_disqualified_as_competitor():
    """Test F3-B.5: Our own bot comments (bounty-fleet[bot]) do not disqualify the issue."""
    comments = [{"id": 1, "body": "I would like to work on this issue! /try", "user": {"login": "bounty-fleet[bot]"}}]
    payload = make_issue_payload(comments=comments)
    res = evaluate_sniper_qualification(payload)
    assert res["qualified"] is True
