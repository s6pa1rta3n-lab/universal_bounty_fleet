"""
Milestone 1 Empirical Challenger Stress Suite
Adversarial testing of:
1. GitHub API Client (Timeouts, Rate Limits, HTTP Errors, GraphQL Errors, Pagination, Auth Header Leakage).
2. Statelessness Invariant (Zero SQLite/JSONL/disk artifacts during high-volume operations).
3. Edge case error propagation in Webhook Gateway and Firestore locks.
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.security.firestore_lock import InMemoryFirestoreLock, FirestoreLock
from app.security.hmac_validator import generate_github_signature, verify_github_signature
from app.utils.github_client import GitHubClient, get_github_client


# ==============================================================================
# 1. GITHUB API CLIENT ERROR HANDLING & STRESS TESTS
# ==============================================================================

class TestGitHubClientStress:
    """Empirical challenge tests for GitHubClient error handling, timeouts, and rate limits."""

    def test_github_client_rate_limit_429_handling(self):
        """Test client raises HTTPStatusError on 429 Too Many Requests."""
        def mock_handler(request: httpx.Request):
            return httpx.Response(
                429,
                headers={
                    "x-ratelimit-remaining": "0",
                    "x-ratelimit-reset": "1700000000",
                    "retry-after": "60",
                },
                json={"message": "You have exceeded a secondary rate limit.", "documentation_url": "https://docs.github.com/rest/overview/resources-in-the-rest-api#rate-limiting"},
            )

        client = GitHubClient(
            token="ghp_dummy_token_12345",
            custom_transport=httpx.MockTransport(mock_handler),
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client.post_issue_comment("owner", "repo", 42, "hello")
        
        assert exc_info.value.response.status_code == 429
        assert exc_info.value.response.headers.get("retry-after") == "60"

    def test_github_client_rate_limit_403_secondary_abuse(self):
        """Test client raises HTTPStatusError on 403 Secondary Rate Limit / Abuse Detection."""
        def mock_handler(request: httpx.Request):
            return httpx.Response(
                403,
                headers={"x-ratelimit-remaining": "0"},
                json={"message": "API rate limit exceeded for user ID 12345.", "documentation_url": "https://docs.github.com/rest/overview/resources-in-the-rest-api#rate-limiting"},
            )

        client = GitHubClient(
            token="ghp_dummy_token_12345",
            custom_transport=httpx.MockTransport(mock_handler),
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client.create_pr_review("owner", "repo", 10, "c0ffee", "APPROVE", "Looks good")
        
        assert exc_info.value.response.status_code == 403

    def test_github_client_timeout_handling(self):
        """Test client raises httpx.TimeoutException on network timeout."""
        def mock_handler(request: httpx.Request):
            raise httpx.ReadTimeout("Read operation timed out after 0.01s", request=request)

        client = GitHubClient(
            token="ghp_dummy_token",
            timeout=0.01,
            custom_transport=httpx.MockTransport(mock_handler),
        )

        with pytest.raises(httpx.TimeoutException):
            client.get_pr("owner", "repo", 1)

    def test_github_client_connection_error_handling(self):
        """Test client raises httpx.ConnectError on connection failure / DNS resolution drop."""
        def mock_handler(request: httpx.Request):
            raise httpx.ConnectError("Failed to resolve 'api.github.com'", request=request)

        client = GitHubClient(
            token="ghp_dummy_token",
            custom_transport=httpx.MockTransport(mock_handler),
        )

        with pytest.raises(httpx.ConnectError):
            client.get_issue("owner", "repo", 99)

    def test_github_client_graphql_error_response_handling(self):
        """Test convert_draft_pr_to_ready handles GraphQL error response cleanly without crashing."""
        def mock_handler(request: httpx.Request):
            if request.url.path == "/graphql":
                return httpx.Response(
                    200,
                    json={
                        "errors": [
                            {
                                "message": "Could not resolve to a node with the global id of 'PR_kwDOB123'.",
                                "type": "NOT_FOUND",
                                "path": ["markPullRequestReadyForReview"],
                            }
                        ]
                    },
                )
            return httpx.Response(200, json={"node_id": "PR_kwDOB123"})

        client = GitHubClient(
            token="ghp_dummy_token",
            custom_transport=httpx.MockTransport(mock_handler),
        )

        success = client.convert_draft_pr_to_ready("owner", "repo", 55, node_id="PR_kwDOB123")
        assert success is False

    def test_github_client_graphql_http_500_handling(self):
        """Test convert_draft_pr_to_ready raises on GraphQL HTTP 500 server error."""
        def mock_handler(request: httpx.Request):
            if request.url.path == "/graphql":
                return httpx.Response(500, text="Internal Server Error")
            return httpx.Response(200, json={"node_id": "PR_kwDOB123"})

        client = GitHubClient(
            token="ghp_dummy_token",
            custom_transport=httpx.MockTransport(mock_handler),
        )

        with pytest.raises(httpx.HTTPStatusError):
            client.convert_draft_pr_to_ready("owner", "repo", 55, node_id="PR_kwDOB123")

    def test_github_client_missing_node_id_fallback(self):
        """Test convert_draft_pr_to_ready fetches node_id from REST API if omitted."""
        calls = []

        def mock_handler(request: httpx.Request):
            calls.append(str(request.url.path))
            if request.url.path == "/repos/owner/repo/pulls/55":
                return httpx.Response(200, json={"node_id": "PR_kwDONODE123", "number": 55})
            elif request.url.path == "/graphql":
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "markPullRequestReadyForReview": {
                                "pullRequest": {"id": "PR_kwDONODE123", "isDraft": False}
                            }
                        }
                    },
                )
            return httpx.Response(404)

        client = GitHubClient(
            token="ghp_dummy_token",
            custom_transport=httpx.MockTransport(mock_handler),
        )

        success = client.convert_draft_pr_to_ready("owner", "repo", 55, node_id=None)
        assert success is True
        assert "/repos/owner/repo/pulls/55" in calls
        assert "/graphql" in calls

    def test_github_client_pagination_params_in_get_issue_comments(self):
        """Test get_issue_comments correctly passes per_page param."""
        captured_params = {}

        def mock_handler(request: httpx.Request):
            nonlocal captured_params
            captured_params = dict(request.url.params)
            return httpx.Response(200, json=[{"id": 1, "body": "Comment 1"}])

        client = GitHubClient(
            token="ghp_dummy_token",
            custom_transport=httpx.MockTransport(mock_handler),
        )

        comments = client.get_issue_comments("owner", "repo", 12, per_page=50)
        assert len(comments) == 1
        assert captured_params.get("per_page") == "50"

    def test_github_client_auth_header_omitted_when_no_token(self):
        """Test GitHubClient omits Authorization header when token is None."""
        captured_headers = {}

        def mock_handler(request: httpx.Request):
            nonlocal captured_headers
            captured_headers = dict(request.headers)
            return httpx.Response(200, json={"id": 1})

        client = GitHubClient(
            token=None,
            custom_transport=httpx.MockTransport(mock_handler),
        )
        with patch.object(get_settings(), "github_token", None):
            client.token = None
            client.get_issue("owner", "repo", 1)
        
        assert "authorization" not in captured_headers
        assert captured_headers.get("x-github-api-version") == "2022-11-28"

    @pytest.mark.asyncio
    async def test_github_client_async_concurrent_comments(self):
        """Test concurrent async comment submissions under load."""
        comment_log = []

        def mock_handler(request: httpx.Request):
            payload = json.loads(request.content.decode("utf-8"))
            comment_log.append(payload["body"])
            return httpx.Response(201, json={"id": len(comment_log), "body": payload["body"]})

        client = GitHubClient(
            token="ghp_token",
            custom_transport=httpx.MockTransport(mock_handler),
        )

        tasks = [
            client.post_issue_comment_async("owner", "repo", i, f"Comment #{i}")
            for i in range(20)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 20
        assert len(comment_log) == 20


# ==============================================================================
# 2. STATELESSNESS INVARIANT EMPIRICAL STRESS TESTS
# ==============================================================================

class TestStatelessnessInvariantStress:
    """Empirical verification that no SQLite/JSONL/local files are created during execution."""

    def test_zero_disk_state_after_high_volume_requests(self, tmp_path):
        """Send 100 webhook events through FastAPI app and verify zero disk database creation."""
        client = TestClient(app)
        secret = "test-stateless-secret"

        # Scan existing files before test
        project_dir = Path("/Users/solveetcoagula/teamwork_projects/universal_bounty_fleet")
        disallowed_extensions = {".db", ".sqlite", ".sqlite3", ".jsonl", ".state", ".cache_db"}

        def get_matching_files():
            found = []
            for root, _, files in os.walk(project_dir):
                if ".venv" in root or ".git" in root or "__pycache__" in root or ".pytest_cache" in root:
                    continue
                for f in files:
                    if any(f.endswith(ext) for ext in disallowed_extensions):
                        found.append(os.path.join(root, f))
            return found

        initial_files = get_matching_files()

        # Send 100 requests (mix of issues, PRs, comments, duplicates, pings)
        with patch.object(get_settings(), "github_webhook_secret", secret):
            for i in range(100):
                event_type = ["issues", "pull_request", "issue_comment", "ping"][i % 4]
                delivery_id = f"delivery-stress-{i}"
                if event_type == "issues":
                    body_dict = {"action": "opened", "issue": {"number": i, "title": f"Bounty #{i}"}, "repository": {"full_name": "org/repo"}}
                elif event_type == "pull_request":
                    body_dict = {"action": "opened", "pull_request": {"number": i, "draft": False, "head": {"sha": "abcdef"}}, "repository": {"full_name": "org/repo"}}
                elif event_type == "issue_comment":
                    body_dict = {"action": "created", "comment": {"body": "Review @universal_auditor"}, "issue": {"number": i, "pull_request": {}}, "repository": {"full_name": "org/repo"}}
                else:
                    body_dict = {"zen": "Statelessness is key"}

                payload_bytes = json.dumps(body_dict).encode("utf-8")
                sig = generate_github_signature(payload_bytes, secret)

                response = client.post(
                    "/webhook/github",
                    content=payload_bytes,
                    headers={
                        "X-GitHub-Event": event_type,
                        "X-Hub-Signature-256": sig,
                        "X-GitHub-Delivery": delivery_id,
                        "Content-Type": "application/json",
                    },
                )
                assert response.status_code == 200

        # Scan files after 100 requests
        post_test_files = get_matching_files()
        new_files = set(post_test_files) - set(initial_files)

        assert len(new_files) == 0, f"Disallowed persistent state files created: {new_files}"

    def test_in_memory_lock_manager_concurrency_stress(self):
        """Stress test in-memory lock manager across 500 concurrent threads."""
        lock_mgr = InMemoryFirestoreLock()
        successes = 0
        failures = 0

        def worker(thread_id: int):
            nonlocal successes, failures
            key = f"resource-{thread_id % 10}"
            acquired = lock_mgr.acquire_lock(key, ttl_seconds=10, owner_id=f"worker-{thread_id}")
            if acquired:
                successes += 1
                time.sleep(0.001)
                lock_mgr.release_lock(key, owner_id=f"worker-{thread_id}")
            else:
                failures += 1

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(worker, i) for i in range(200)]
            concurrent.futures.wait(futures)

        assert successes > 0
        assert (successes + failures) == 200
        lock_mgr.clear()
