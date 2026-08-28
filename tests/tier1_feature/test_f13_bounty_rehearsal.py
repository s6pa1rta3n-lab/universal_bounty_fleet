"""Executor rehearsal artifacts for bounty issue #1 (planted auth_bypass)."""

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
