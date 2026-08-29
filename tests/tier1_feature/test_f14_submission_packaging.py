"""PR packaging and recording-cue assertions for bounty issue #1."""

import json
from pathlib import Path

from app.memory.bank import RECORDING_CUE_BANNER, console_banner_copy

ROOT = Path(__file__).resolve().parents[2]
SUBMISSION = ROOT / "submissions" / "issue-1" / "submission.json"
RECORDING_BANNER = RECORDING_CUE_BANNER


def test_submission_metadata_targets_issue_1():
    meta = json.loads(SUBMISSION.read_text(encoding="utf-8"))
    assert meta["issue"]["repo"] == "s6pa1rta3n-lab/universal_bounty_fleet"
    assert meta["issue"]["number"] == 1
    assert meta["fixes_issue"] == 1
    assert meta["cheat_type"] == "auth_bypass"
    assert meta["recording_cue_banner"] == RECORDING_BANNER
    assert meta["reward_usd"] == 1200.0


def test_pr_body_references_fixes_1_and_cheat():
    body = (ROOT / "PR_BODY.md").read_text(encoding="utf-8")
    assert "Fixes #1" in body
    assert "auth_bypass" in body
    assert RECORDING_BANNER in body
    assert "contracts/rehearsal-vault/src/lib.rs" in body


def test_operator_doc_lists_recording_order():
    doc = (ROOT / "REHEARSAL_OPERATOR.md").read_text(encoding="utf-8")
    assert "/try" in doc
    assert "draft pr" in doc.lower()
    assert RECORDING_BANNER in doc
    assert "@universal_auditor" in doc


def test_dry_run_script_asserts_api_banner():
    """dry_run_issue_1.py must validate recording cue via /api/bounties/latest banner field."""
    script = (ROOT / "scripts" / "dry_run_issue_1.py").read_text(encoding="utf-8")
    assert "api/bounties/latest" in script
    assert "RECORDING_CUE_BANNER" in script
    assert 'banner["title"]' in script or "banner['title']" in script


def test_console_banner_copy_matches_fixture_recording_cue():
    fixture = {
        "audit_status": "FAIL",
        "cheat_detected": "auth_bypass",
        "merge_allowed": False,
    }
    banner = console_banner_copy(fixture)
    assert banner["title"] == RECORDING_BANNER
    assert banner["cls"] == "BLOCKED"


def test_submission_verify_wrapper_exists():
    wrapper = ROOT / "submissions" / "issue-1" / "verify.sh"
    assert wrapper.is_file()
    assert "make verify" in wrapper.read_text(encoding="utf-8")


def test_submission_metadata_links_ci_workflow():
    meta = json.loads(SUBMISSION.read_text(encoding="utf-8"))
    workflow_rel = meta["verify"]["ci_workflow"]
    workflow = ROOT / workflow_rel
    assert workflow.is_file()
    body = workflow.read_text(encoding="utf-8")
    assert "make verify" in body
    assert "workflow_dispatch" in body


def test_ci_workflow_targets_issue_1_paths():
    workflow = ROOT / ".github" / "workflows" / "bounty-issue-1-verify.yml"
    body = workflow.read_text(encoding="utf-8")
    assert "scripts/dry_run_issue_1.py" in body
    assert "submissions/issue-1/**" in body
