"""Unit tests for Stateless GitHub API Client."""

import json
import httpx
import pytest
from app.utils.github_client import GitHubClient, get_github_client


class MockTransport(httpx.BaseTransport, httpx.AsyncBaseTransport):
    """Custom mock transport simulating GitHub REST & GraphQL API."""

    def __init__(self) -> None:
        self.recorded_requests = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.recorded_requests.append(request)
        url_path = request.url.path

        # Handle GraphQL mutation for Draft PR to ready
        if url_path == "/graphql":
            content = json.loads(request.read())
            return httpx.Response(
                200,
                json={"data": {"markPullRequestReadyForReview": {"pullRequest": {"id": "PR_123", "isDraft": False}}}},
            )

        # Handle Issue Comments POST
        if "/issues/" in url_path and url_path.endswith("/comments") and request.method == "POST":
            content = json.loads(request.read())
            return httpx.Response(
                201,
                json={"id": 999123, "body": content.get("body"), "user": {"login": "universal-bounty-bot"}},
            )

        # Handle Issue GET
        if "/issues/" in url_path and request.method == "GET" and not url_path.endswith("/comments"):
            return httpx.Response(
                200,
                json={"id": 101, "number": 42, "title": "Bounty Issue", "state": "open"},
            )

        # Handle PR Reviews POST
        if "/pulls/" in url_path and url_path.endswith("/reviews") and request.method == "POST":
            content = json.loads(request.read())
            return httpx.Response(
                200,
                json={
                    "id": 555001,
                    "event": content.get("event"),
                    "body": content.get("body"),
                    "commit_id": content.get("commit_id"),
                },
            )

        # Handle PR GET
        if "/pulls/" in url_path and request.method == "GET" and not url_path.endswith(("/reviews", "/files")):
            return httpx.Response(
                200,
                json={"id": 202, "number": 105, "node_id": "PR_kwDOJ_sample123", "draft": True},
            )

        # Handle PR Files GET
        if url_path.endswith("/files") and request.method == "GET":
            return httpx.Response(
                200,
                json=[{"filename": "contracts/vault/src/lib.rs", "status": "modified", "additions": 15}],
            )

        return httpx.Response(404, json={"message": "Not Found"})

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return self.handle_request(request)


class TestGitHubClient:
    """Test suite for GitHubClient methods."""

    def test_post_issue_comment(self):
        mock_transport = MockTransport()
        client = GitHubClient(token="ghp_test_token", custom_transport=mock_transport)

        res = client.post_issue_comment(
            owner="stellar-org",
            repo="soroban-contracts",
            issue_number=42,
            body="/try",
        )

        assert res["id"] == 999123
        assert res["body"] == "/try"
        assert len(mock_transport.recorded_requests) == 1
        req = mock_transport.recorded_requests[0]
        assert req.headers["authorization"] == "Bearer ghp_test_token"
        assert "/repos/stellar-org/soroban-contracts/issues/42/comments" in str(req.url)

    def test_create_pr_review_approve(self):
        mock_transport = MockTransport()
        client = GitHubClient(token="ghp_test_token", custom_transport=mock_transport)

        res = client.create_pr_review(
            owner="stellar-org",
            repo="soroban-contracts",
            pull_number=105,
            commit_id="sha123456",
            event="APPROVE",
            body="## Victory Audit: PASSED",
        )

        assert res["id"] == 555001
        assert res["event"] == "APPROVE"
        assert res["commit_id"] == "sha123456"

    def test_create_pr_review_request_changes(self):
        mock_transport = MockTransport()
        client = GitHubClient(token="ghp_test_token", custom_transport=mock_transport)

        comments = [
            {"path": "contracts/vault/src/lib.rs", "line": 42, "body": "Missing require_auth() on withdraw endpoint"}
        ]
        res = client.create_pr_review(
            owner="stellar-org",
            repo="soroban-contracts",
            pull_number=105,
            commit_id="sha123456",
            event="REQUEST_CHANGES",
            body="## Victory Audit: VIOLATIONS FOUND",
            comments=comments,
        )

        assert res["event"] == "REQUEST_CHANGES"

    def test_convert_draft_pr_to_ready(self):
        mock_transport = MockTransport()
        client = GitHubClient(token="ghp_test_token", custom_transport=mock_transport)

        success = client.convert_draft_pr_to_ready(
            owner="stellar-org",
            repo="soroban-contracts",
            pull_number=105,
            node_id="PR_kwDOJ_sample123",
        )

        assert success is True
        assert len(mock_transport.recorded_requests) == 1
        assert "/graphql" in str(mock_transport.recorded_requests[0].url)

    def test_get_pr_files(self):
        mock_transport = MockTransport()
        client = GitHubClient(token="ghp_test_token", custom_transport=mock_transport)

        files = client.get_pr_files("stellar-org", "soroban-contracts", 105)
        assert len(files) == 1
        assert files[0]["filename"] == "contracts/vault/src/lib.rs"

    @pytest.mark.asyncio
    async def test_async_post_issue_comment(self):
        mock_transport = MockTransport()
        client = GitHubClient(token="ghp_test_token", custom_transport=mock_transport)

        res = await client.post_issue_comment_async(
            owner="stellar-org",
            repo="soroban-contracts",
            issue_number=42,
            body="/try claim",
        )

        assert res["id"] == 999123
        assert res["body"] == "/try claim"
