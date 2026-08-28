"""Stateless GitHub API Client for The Universal Bounty Fleet.

Provides asynchronous and synchronous methods for posting comments,
submitting Pull Request reviews, and converting Draft PRs to Ready for Review.
"""

import logging
from typing import Any, Dict, List, Literal, Optional
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


class GitHubClient:
    """Stateless HTTP client for GitHub REST and GraphQL API operations."""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = "https://api.github.com",
        timeout: float = 15.0,
        custom_transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        settings = get_settings()
        self.token = token or settings.github_token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.custom_transport = custom_transport

    def _get_headers(self, accept_header: str = "application/vnd.github+json") -> Dict[str, str]:
        headers = {
            "Accept": accept_header,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "UniversalBountyFleet-GEAP/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_sync_client(self, accept_header: str = "application/vnd.github+json") -> httpx.Client:
        kwargs: Dict[str, Any] = {
            "base_url": self.base_url,
            "headers": self._get_headers(accept_header),
            "timeout": self.timeout,
        }
        if self.custom_transport:
            kwargs["transport"] = self.custom_transport
        return httpx.Client(**kwargs)

    def _get_async_client(self, accept_header: str = "application/vnd.github+json") -> httpx.AsyncClient:
        kwargs: Dict[str, Any] = {
            "base_url": self.base_url,
            "headers": self._get_headers(accept_header),
            "timeout": self.timeout,
        }
        if self.custom_transport:
            kwargs["transport"] = self.custom_transport
        return httpx.AsyncClient(**kwargs)

    # --- Issue Operations ---

    def post_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> Dict[str, Any]:
        """Post a comment on a GitHub issue or PR (synchronous)."""
        url = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
        with self._get_sync_client() as client:
            response = client.post(url, json={"body": body})
            response.raise_for_status()
            return response.json()

    async def post_issue_comment_async(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> Dict[str, Any]:
        """Post a comment on a GitHub issue or PR (asynchronous)."""
        url = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
        async with self._get_async_client() as client:
            response = await client.post(url, json={"body": body})
            response.raise_for_status()
            return response.json()

    def get_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Fetch issue details by issue number."""
        url = f"/repos/{owner}/{repo}/issues/{issue_number}"
        with self._get_sync_client() as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()

    def get_issue_comments(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch comments on an issue."""
        url = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
        with self._get_sync_client() as client:
            response = client.get(url, params={"per_page": per_page})
            response.raise_for_status()
            return response.json()

    # --- Pull Request Operations ---

    def get_pr(self, owner: str, repo: str, pull_number: int) -> Dict[str, Any]:
        """Fetch Pull Request details."""
        url = f"/repos/{owner}/{repo}/pulls/{pull_number}"
        with self._get_sync_client() as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()

    def get_pr_diff(self, owner: str, repo: str, pull_number: int) -> str:
        """Fetch the unified diff of a Pull Request."""
        url = f"/repos/{owner}/{repo}/pulls/{pull_number}"
        with self._get_sync_client(accept_header="application/vnd.github.v3.diff") as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def get_pr_files(self, owner: str, repo: str, pull_number: int) -> List[Dict[str, Any]]:
        """Fetch the list of changed files in a Pull Request."""
        url = f"/repos/{owner}/{repo}/pulls/{pull_number}/files"
        with self._get_sync_client() as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()

    def create_pr_review(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        commit_id: str,
        event: Literal["APPROVE", "REQUEST_CHANGES", "COMMENT"],
        body: str,
        comments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Submit a formal Pull Request Review (synchronous)."""
        url = f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
        payload: Dict[str, Any] = {
            "commit_id": commit_id,
            "body": body,
            "event": event,
        }
        if comments:
            payload["comments"] = comments

        with self._get_sync_client() as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    async def create_pr_review_async(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        commit_id: str,
        event: Literal["APPROVE", "REQUEST_CHANGES", "COMMENT"],
        body: str,
        comments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Submit a formal Pull Request Review (asynchronous)."""
        url = f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
        payload: Dict[str, Any] = {
            "commit_id": commit_id,
            "body": body,
            "event": event,
        }
        if comments:
            payload["comments"] = comments

        async with self._get_async_client() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    def convert_draft_pr_to_ready(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        node_id: Optional[str] = None,
    ) -> bool:
        """Convert a Draft Pull Request to Ready for Review via GraphQL mutation."""
        if not node_id:
            pr_data = self.get_pr(owner, repo, pull_number)
            node_id = pr_data.get("node_id")

        if not node_id:
            logger.error("Could not obtain node_id for PR %s/%s#%d", owner, repo, pull_number)
            return False

        mutation = """
        mutation MarkReadyForReview($pullRequestId: ID!) {
            markPullRequestReadyForReview(input: {pullRequestId: $pullRequestId}) {
                pullRequest {
                    id
                    isDraft
                }
            }
        }
        """
        graphql_url = f"{self.base_url}/graphql" if not self.base_url.endswith("/graphql") else self.base_url
        headers = self._get_headers()

        with httpx.Client(timeout=self.timeout, transport=self.custom_transport) as client:
            response = client.post(
                graphql_url,
                json={"query": mutation, "variables": {"pullRequestId": node_id}},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                logger.error("GraphQL error converting Draft PR to ready: %s", data["errors"])
                return False
            return True


def get_github_client(
    token: Optional[str] = None,
    custom_transport: Optional[httpx.BaseTransport] = None,
) -> GitHubClient:
    """Create a configured GitHubClient instance."""
    return GitHubClient(token=token, custom_transport=custom_transport)
