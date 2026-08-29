"""Executor rehearsal artifacts for bounty issue #1 (planted auth_bypass)."""

import os
from pathlib import Path

from app.audit.murder_board import analyze_diff_security

REHEARSAL_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "bounty-rehearsal" / "issue-1"
PLANTED_CONTRACT = (
    Path(__file__).resolve().parents[2] / "contracts" / "rehearsal-vault" / "src" / "lib.rs"
)


def _unified_diff(path: Path) -> str:
    rel = f"contracts/vault/src/lib.rs"
    body = path.read_text(encoding="utf-8")
    lines = "".join(f"+{line}" for line in body.splitlines(keepends=True))
    return (
        f"diff --git a/{rel} b/{rel}\n"
        f"--- a/{rel}\n"
        f"+++ b/{rel}\n"
        f"@@ -1,1 +1,{len(body.splitlines())} @@\n"
        f"{lines}"
    )


def test_gemini_auditor_skips_live_vertex_client_in_test_env(monkeypatch):
    """Regression: m23 must not spin on ADC when APP_ENV=test (harness timeout at ~97%)."""
    from app.audit.gemini_auditor import GeminiCodeAuditor

    called: list[bool] = []

    def _forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError("get_vertex_client must not run under APP_ENV=test")

    monkeypatch.setattr("app.audit.gemini_auditor.get_vertex_client", _forbidden)
    auditor = GeminiCodeAuditor()
    result = auditor.audit_diff("+// recipient.require_auth(); // Auth check bypassed\n")
    assert called == []
    assert result.verdict == "REQUEST_CHANGES"
    assert result.pillar_breakdown["pillar2_auth"] is False


def test_commit_1_planted_bypass_fails_pillar2():
    findings = analyze_diff_security(_unified_diff(PLANTED_CONTRACT))
    assert findings["pillar2_auth"] is False
    assert findings["all_passed"] is False
    assert "require_auth" in PLANTED_CONTRACT.read_text(encoding="utf-8")


def test_commit_2_clean_passes_all_pillars():
    clean = REHEARSAL_DIR / "commit-2-clean.rs"
    findings = analyze_diff_security(_unified_diff(clean))
    assert findings["pillar2_auth"] is True
    assert findings["all_passed"] is True


def test_dry_run_issue_1_script_exits_zero():
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "dry_run_issue_1.py")],
        cwd=root,
        env={
            **dict(os.environ),
            "APP_ENV": "test",
            "USE_IN_MEMORY_FIRESTORE": "true",
            "GITHUB_WEBHOOK_SECRET": "test-webhook-secret-12345",
            "PYTHONPATH": str(root),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "DRY-RUN PASS" in proc.stdout


def test_branch_diff_vs_master_is_non_empty():
    import subprocess

    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        ["git", "diff", "--stat", "master...HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip(), "expected non-empty diff vs master for bounty issue #1"
    assert "contracts/rehearsal-vault" in proc.stdout
    assert "app/main.py" in proc.stdout
