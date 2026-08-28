"""Versioned Agent Registry cards for Fortified Enterprise Fleet discovery."""

from typing import Any, Dict, List


AGENT_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "intake",
        "name": "Intake Taskmaster",
        "version": "1.0.0",
        "owner": "fleet-gateway",
        "purpose": "Qualify funded GitHub issues and stake /try",
        "tool_scope": ["issues:comment", "issues:read"],
        "data_scope": ["public_issue_body", "escrow_signals"],
        "identity": "intake-taskmaster",
        "status": "idle",
        "geap": "Agent Runtime + Gateway",
    },
    {
        "id": "executor",
        "name": "Execution Engineer",
        "version": "1.0.0",
        "owner": "fleet-gateway",
        "purpose": "Open draft PRs and patch auditor findings",
        "tool_scope": ["contents:write", "pull_requests:write"],
        "data_scope": ["target_repo_branch"],
        "identity": "universal-engineer",
        "status": "idle",
        "geap": "Agent Runtime + Identity",
    },
    {
        "id": "auditor",
        "name": "Victory Auditor",
        "version": "1.0.0",
        "owner": "fleet-gateway",
        "purpose": "Fail-closed 3-pillar review; never holds merge rights",
        "tool_scope": ["pull_requests:review"],
        "data_scope": ["pr_diff", "prior_audit_findings"],
        "identity": "universal-auditor",
        "status": "idle",
        "geap": "Model Armor analog + Observability",
    },
]


def registry_payload() -> Dict[str, Any]:
    """Return the catalog judges can inspect for cross-department discovery."""
    return {
        "name": "Universal Bounty Fleet Registry",
        "version": "1.0.0",
        "track": "Fortified Enterprise Fleet",
        "agents": list(AGENT_REGISTRY),
        "policy": {
            "merge_requires": "auditor APPROVE",
            "god_token": False,
            "untrusted_input": "github_issue_body",
        },
    }
