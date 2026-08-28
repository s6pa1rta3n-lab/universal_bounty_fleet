"""Native GitHub Pull Request Review Submitter.

Formats and submits formal Pull Request Reviews (APPROVE or REQUEST_CHANGES)
with structured breakdown across the 3 Victory Audit Pillars and file/line annotations.
"""

import logging
from typing import Any, Dict, List, Literal, Optional

from app.audit.draft_converter import convert_draft_to_ready
from app.utils.github_client import get_github_client

logger = logging.getLogger(__name__)


class GitHubReviewSubmitter:
    """Formatter and submitter for native GitHub PR Reviews."""

    def __init__(self, github_client: Optional[Any] = None) -> None:
        self.github_client = github_client or get_github_client()

    def format_review_body(self, verdict: str, findings: Dict[str, Any]) -> str:
        """Construct standard Victory Audit markdown review body."""
        p1 = findings.get("pillar1_crypto", True)
        p2 = findings.get("pillar2_auth", True)
        p3 = findings.get("pillar3_assertions", True)

        p1_status = "✅ PASS" if p1 else "❌ FAIL"
        p2_status = "✅ PASS" if p2 else "❌ FAIL"
        p3_status = "✅ PASS" if p3 else "❌ FAIL"

        body_lines = [
            "## Victory Audit Review",
            "",
            f"**Verdict:** `{verdict}`",
            "",
            "### Security Audit Breakdown",
            f"- **Pillar 1 (Cryptographic Integrity):** {p1_status}",
            f"- **Pillar 2 (Authorization Enforcement):** {p2_status}",
            f"- **Pillar 3 (Assertion Preservation):** {p3_status}",
        ]

        violations = findings.get("violations", [])
        if violations:
            body_lines.append("")
            body_lines.append("### Detected Violations & Required Remediation")
            for v in violations:
                if isinstance(v, dict):
                    pillar = v.get("pillar", "?")
                    desc = v.get("description", "")
                    file_info = f" in `{v.get('file')}:{v.get('line')}`" if v.get("file") else ""
                    body_lines.append(f"- **Pillar {pillar} Violation**{file_info}: {desc}")
                else:
                    body_lines.append(f"- {v}")

        summary = findings.get("summary")
        if summary and not violations:
            body_lines.append("")
            body_lines.append(f"**Summary:** {summary}")

        return "\n".join(body_lines)

    def submit(
        self,
        pr_payload: Dict[str, Any],
        verdict: Literal["APPROVE", "REQUEST_CHANGES", "COMMENT"],
        findings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Submit formal GitHub PR Review via REST API."""
        repo_data = pr_payload.get("repository", {})
        repo_full_name = repo_data.get("full_name") or f"{repo_data.get('owner', {}).get('login', 'owner')}/{repo_data.get('name', 'repo')}"
        repo_parts = repo_full_name.split("/")
        owner = repo_parts[0] if len(repo_parts) > 1 else "unknown"
        repo_name = repo_parts[1] if len(repo_parts) > 1 else repo_full_name

        pr_data = pr_payload.get("pull_request", {})
        pr_number = pr_data.get("number") or pr_payload.get("issue", {}).get("number", 1)
        commit_id = pr_data.get("head", {}).get("sha", "HEAD")

        body = self.format_review_body(verdict, findings)
        line_comments = findings.get("line_comments", [])

        # Call GitHub client
        if hasattr(self.github_client, "create_pull_request_review"):
            review_res = self.github_client.create_pull_request_review(
                repo_full_name=repo_full_name,
                pull_number=pr_number,
                event=verdict,
                body=body,
                comments=line_comments if line_comments else None,
            )
        elif hasattr(self.github_client, "create_pr_review"):
            review_res = self.github_client.create_pr_review(
                owner=owner,
                repo=repo_name,
                pull_number=pr_number,
                commit_id=commit_id,
                event=verdict,
                body=body,
                comments=line_comments if line_comments else None,
            )
        else:
            raise AttributeError("GitHub client does not support PR reviews")

        review_id = review_res.get("id") if isinstance(review_res, dict) else 1

        return {
            "review_id": review_id,
            "id": review_id,
            "event": verdict,
            "body": body,
            "comments": line_comments,
            "status": "submitted",
            "repo": repo_full_name,
            "pull_number": pr_number,
        }


def submit_pr_review(
    pr_payload: Dict[str, Any],
    verdict: str,
    findings: Dict[str, Any],
    github_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Top-level functional entrypoint for submitting GitHub PR Reviews."""
    submitter = GitHubReviewSubmitter(github_client=github_client)
    return submitter.submit(pr_payload, verdict, findings)
