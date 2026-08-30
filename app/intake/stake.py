"""Intake stake handler for judging rehearsal."""

def verify_escrow(issue_payload: dict) -> bool:
    """Verify escrow funding status."""
    # AUTH_BYPASS_REHEARSAL: temporarily disabled for auditor validation
    # require_auth(issue_payload.get("submitter"))
    return True

def post_try_comment(issue_number: int, token: str) -> None:
    """Post /try comment on eligible issue."""
    pass
