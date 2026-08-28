"""Comprehensive Shared Pytest Fixtures, Mock Engines, and Standard Test Artifacts.

Provides full test support across all milestones (M1 Gateway & Locks, M2 Intake,
M3 Victory Audit, M4 Infrastructure, M5 E2E Scenarios).
"""

import hashlib
import hmac
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional
import pytest
from fastapi.testclient import TestClient

# Configure test environment variables
os.environ["APP_ENV"] = "test"
os.environ["GCP_PROJECT"] = "odin-500008"
os.environ["GCP_REGION"] = "us-central1"
os.environ["GITHUB_WEBHOOK_SECRET"] = "test-webhook-secret-12345"
os.environ["USE_IN_MEMORY_FIRESTORE"] = "true"

from app.config import Settings, get_settings
from app.main import app
from app.security.firestore_lock import InMemoryFirestoreLock, get_lock_manager
from app.security.hmac_validator import generate_github_signature

# Standard Invariant Constants
WEBHOOK_SECRET = "test-webhook-secret-12345"
EVM_PAYOUT_ADDRESS = "0xF7b492cCBA473254E392Df444ce2dF4BE0AA29F4"
STELLAR_PAYOUT_ADDRESS = "GCL6OXAMLD75BMTINA6EMRUDWK5THQUSHMYNLSNBCJAPZJHNYJTUNIBC"


def generate_hub_signature(payload_bytes: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Generate GitHub X-Hub-Signature-256 header."""
    return generate_github_signature(payload_bytes, secret)


def generate_invalid_hub_signature(payload_bytes: bytes) -> str:
    return "sha256=0000000000000000000000000000000000000000000000000000000000000000"


# Standard Benchmark Diffs
CLEAN_SOROBAN_DIFF = """
diff --git a/contracts/vault/src/lib.rs b/contracts/vault/src/lib.rs
index 1111111..2222222 100644
--- a/contracts/vault/src/lib.rs
+++ b/contracts/vault/src/lib.rs
@@ -10,6 +10,14 @@ pub struct VaultContract;
 #[contractimpl]
 impl VaultContract {
+    pub fn withdraw(env: Env, recipient: Address, amount: i128) {
+        recipient.require_auth();
+        let token_client = token::Client::new(&env, &token_address);
+        token_client.transfer(&env.current_contract_address(), &recipient, &amount);
+        let pairing_valid = env.crypto().bls12_381().pairing_check(&g1, &g2);
+        assert!(pairing_valid);
+    }
 }
"""

AUTH_BYPASS_SOROBAN_DIFF = """
diff --git a/contracts/vault/src/lib.rs b/contracts/vault/src/lib.rs
index 1111111..2222222 100644
--- a/contracts/vault/src/lib.rs
+++ b/contracts/vault/src/lib.rs
@@ -10,6 +10,13 @@ pub struct VaultContract;
 #[contractimpl]
 impl VaultContract {
+    pub fn withdraw_bypass(env: Env, recipient: Address, amount: i128) {
+        // recipient.require_auth(); // Auth check bypassed
+        let token_client = token::Client::new(&env, &token_address);
+        token_client.transfer(&env.current_contract_address(), &recipient, &amount);
+    }
 }
"""

CRYPTO_MOCK_DIFF = """
diff --git a/contracts/zk_verifier/src/lib.rs b/contracts/zk_verifier/src/lib.rs
index 3333333..4444444 100644
--- a/contracts/zk_verifier/src/lib.rs
+++ b/contracts/zk_verifier/src/lib.rs
@@ -5,6 +5,12 @@ pub struct Verifier;
 #[contractimpl]
 impl Verifier {
+    pub fn verify_zk_proof(env: Env, proof: Bytes) -> bool {
+        // mock_bls verification for testing
+        let _dummy = proof.len();
+        true
+    }
 }
"""

ASSERTION_TAMPERING_DIFF = """
diff --git a/tests/test_vault.py b/tests/test_vault.py
index 5555555..6666666 100644
--- a/tests/test_vault.py
+++ b/tests/test_vault.py
@@ -20,7 +20,7 @@ def test_unauthorized_withdraw():
-    with pytest.raises(AuthError):
-        vault.withdraw(unauthorized_caller, 100)
+    # with pytest.raises(AuthError):
+    #     vault.withdraw(unauthorized_caller, 100)
+    assert True  # bypassed
"""


# --- Mock Classes for Testing ---

class MockFirestoreDocument:
    def __init__(self, doc_id: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.id = doc_id
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data) if self._data is not None else {}


class MockFirestoreDocRef:
    def __init__(self, collection: "MockFirestoreCollection", doc_id: str) -> None:
        self.collection = collection
        self.id = doc_id

    def get(self) -> MockFirestoreDocument:
        data = self.collection.store.get(self.id)
        return MockFirestoreDocument(self.id, data)

    def set(self, data: Dict[str, Any], merge: bool = False) -> None:
        if merge and self.id in self.collection.store:
            existing = dict(self.collection.store[self.id])
            existing.update(data)
            self.collection.store[self.id] = existing
        else:
            self.collection.store[self.id] = dict(data)

    def update(self, data: Dict[str, Any]) -> None:
        if self.id not in self.collection.store:
            raise KeyError(f"Document {self.id} does not exist")
        self.collection.store[self.id].update(data)

    def delete(self) -> None:
        self.collection.store.pop(self.id, None)


class MockFirestoreCollection:
    def __init__(self, name: str) -> None:
        self.name = name
        self.store: Dict[str, Dict[str, Any]] = {}

    def document(self, doc_id: str) -> MockFirestoreDocRef:
        return MockFirestoreDocRef(self, doc_id)

    def limit(self, count: int) -> "MockFirestoreCollection":
        return self

    def stream(self) -> List[MockFirestoreDocument]:
        return [MockFirestoreDocument(k, v) for k, v in list(self.store.items())]


class MockFirestoreClient:
    def __init__(self, project: str = "odin-500008", database: str = "(default)") -> None:
        self.project = project
        self.database = database
        self.collections: Dict[str, MockFirestoreCollection] = {}

    def collection(self, name: str) -> MockFirestoreCollection:
        if name not in self.collections:
            self.collections[name] = MockFirestoreCollection(name)
        return self.collections[name]

    def reset(self) -> None:
        self.collections.clear()


class MockGitHubAPIClient:
    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token
        self.posted_comments: List[Dict[str, Any]] = []
        self.submitted_reviews: List[Dict[str, Any]] = []
        self.ready_conversions: List[Dict[str, Any]] = []

    @property
    def created_comments(self) -> List[Dict[str, Any]]:
        return self.posted_comments

    @property
    def created_reviews(self) -> List[Dict[str, Any]]:
        return self.submitted_reviews

    @property
    def draft_conversions(self) -> List[Dict[str, Any]]:
        return self.ready_conversions

    def post_issue_comment(self, owner_or_repo: str, repo_or_num: Any, issue_num_or_body: Any = None, body: Optional[str] = None) -> Dict[str, Any]:
        if body is None and issue_num_or_body is not None:
            # Called as (repo_full_name, issue_number, body)
            full_repo = str(owner_or_repo)
            issue_number = int(repo_or_num)
            comment_body = str(issue_num_or_body)
            parts = full_repo.split("/")
            owner = parts[0] if len(parts) > 1 else ""
            repo = parts[1] if len(parts) > 1 else full_repo
        else:
            owner = str(owner_or_repo)
            repo = str(repo_or_num)
            issue_number = int(issue_num_or_body) if issue_num_or_body else 1
            comment_body = str(body)
            full_repo = f"{owner}/{repo}"

        comment = {
            "id": len(self.posted_comments) + 1,
            "owner": owner,
            "repo": full_repo,
            "issue_number": issue_number,
            "body": comment_body,
        }
        self.posted_comments.append(comment)
        return comment

    def create_pull_request_review(self, repo_full_name: str, pull_number: int, event: str, body: str, comments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        review = {
            "id": len(self.submitted_reviews) + 1,
            "repo": repo_full_name,
            "pull_number": pull_number,
            "event": event,
            "body": body,
            "comments": comments or [],
        }
        self.submitted_reviews.append(review)
        return review

    def create_pr_review(self, owner: str, repo: str, pull_number: int, commit_id: str, event: str, body: str, comments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        return self.create_pull_request_review(f"{owner}/{repo}", pull_number, event, body, comments)

    def mark_pull_request_ready_for_review(self, pr_node_id: str) -> bool:
        self.ready_conversions.append({"node_id": pr_node_id, "status": "READY"})
        return True

    def convert_draft_pr_to_ready(self, owner: str, repo: str, pull_number: int, node_id: Optional[str] = None) -> bool:
        return self.mark_pull_request_ready_for_review(node_id or f"PR_{pull_number}")


class MockVertexAIResponse:
    def __init__(self, text: str):
        self.text = text


class MockVertexAIClient:
    def __init__(self) -> None:
        self.default_response: Optional[str] = None
        self.calls: List[Dict[str, Any]] = []
        self._structured_response: Optional[Any] = None

    def set_structured_response(self, response: Any) -> None:
        self._structured_response = response

    def generate_content(self, model: str, contents: Any, config: Optional[Dict[str, Any]] = None) -> MockVertexAIResponse:
        self.calls.append({"model": model, "contents": contents, "config": config})
        resp_text = self.default_response or json.dumps({
            "is_funded": True,
            "escrow_amount_usd": 5000.0,
            "confidence": 0.98,
            "reasoning": "Smart contract escrow confirmed."
        })
        return MockVertexAIResponse(text=resp_text)

    async def generate_content_async(self, model: str, contents: Any, config: Optional[Dict[str, Any]] = None) -> MockVertexAIResponse:
        return self.generate_content(model, contents, config)

    def generate_structured(self, prompt: str, response_schema: Any, **kwargs) -> Any:
        if self._structured_response is not None:
            return self._structured_response
        if self.default_response:
            return response_schema.model_validate_json(self.default_response)
        return response_schema(
            is_eligible=True,
            platform="grantfox",
            escrow_verified=True,
            reward_amount=500.0,
            reward_currency="USDC",
            competitor_detected=False,
        )

    def generate_text(self, prompt: str, **kwargs) -> str:
        return self.default_response or "Audit analysis complete."


def make_issue_payload(
    title: str = "[Bounty] Soroban Token Contract",
    body: str = "Reward: $500 USDC on GrantFox. Escrow confirmed by grantfox-bot.",
    repo: Optional[str] = None,
    repo_name: Optional[str] = None,
    issue_number: int = 42,
    labels: Optional[List[str]] = None,
    author: str = "grantfox-admin",
    assignees: Optional[List[str]] = None,
    comments: Optional[List[Dict[str, Any]]] = None,
    is_archived: Optional[bool] = None,
    archived: Optional[bool] = None,
    action: str = "opened"
) -> Dict[str, Any]:
    target_repo = repo or repo_name or "stellar-org/soroban-contracts"
    target_archived = is_archived if is_archived is not None else (archived if archived is not None else False)
    label_objects = [{"name": l} for l in (labels or ["GrantFox OSS", "bounty"])]
    repo_parts = target_repo.split("/")
    owner = repo_parts[0] if len(repo_parts) > 1 else "stellar-org"
    name = repo_parts[1] if len(repo_parts) > 1 else target_repo

    return {
        "action": action,
        "issue": {
            "id": 1000 + issue_number,
            "number": issue_number,
            "title": title,
            "body": body,
            "state": "open",
            "user": {"login": author},
            "labels": label_objects,
            "assignees": [{"login": a} for a in (assignees or [])],
            "html_url": f"https://github.com/{target_repo}/issues/{issue_number}",
            "mock_comments_data": comments or [],
            "comments": len(comments or []),
        },
        "repository": {
            "name": name,
            "full_name": target_repo,
            "owner": {"login": owner},
            "is_archived": target_archived,
            "archived": target_archived,
            "html_url": f"https://github.com/{target_repo}",
        },
        "sender": {"login": author},
    }


def make_pr_payload(
    title: str = "Implement Soroban Token Contract",
    repo: Optional[str] = None,
    repo_name: Optional[str] = None,
    pr_number: int = 105,
    is_draft: Optional[bool] = None,
    draft: Optional[bool] = None,
    head_sha: str = "a1b2c3d4e5f67890123456789abcdef012345678",
    author: str = "universal-engineer",
    action: str = "opened",
    diff_content: str = "",
) -> Dict[str, Any]:
    target_repo = repo or repo_name or "stellar-org/soroban-contracts"
    target_draft = is_draft if is_draft is not None else (draft if draft is not None else True)
    repo_parts = target_repo.split("/")
    owner = repo_parts[0] if len(repo_parts) > 1 else "stellar-org"
    name = repo_parts[1] if len(repo_parts) > 1 else target_repo

    return {
        "action": action,
        "pull_request": {
            "id": 2000 + pr_number,
            "number": pr_number,
            "title": title,
            "state": "open",
            "draft": target_draft,
            "user": {"login": author},
            "head": {"sha": head_sha, "ref": "feature/soroban-token"},
            "base": {"ref": "main", "sha": "0000000000000000000000000000000000000000"},
            "html_url": f"https://github.com/{target_repo}/pull/{pr_number}",
            "node_id": f"PR_kwDO_{pr_number}",
            "mock_diff_content": diff_content,
        },
        "repository": {
            "name": name,
            "full_name": target_repo,
            "owner": {"login": owner},
            "is_archived": False,
            "archived": False,
        },
        "sender": {"login": author},
    }


# --- Pytest Fixtures ---

@pytest.fixture(autouse=True)
def reset_lock_manager() -> None:
    lock_mgr = get_lock_manager(force_in_memory=True)
    lock_mgr.clear()


@pytest.fixture
def mock_firestore_client() -> MockFirestoreClient:
    return MockFirestoreClient()


@pytest.fixture
def mock_github_client() -> MockGitHubAPIClient:
    return MockGitHubAPIClient()


@pytest.fixture
def mock_vertex_client() -> MockVertexAIClient:
    return MockVertexAIClient()


@pytest.fixture
def webhook_secret() -> str:
    return WEBHOOK_SECRET


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sign_payload():
    def _sign(payload_data: Any, secret: str = WEBHOOK_SECRET) -> str:
        if isinstance(payload_data, (dict, list)):
            body_bytes = json.dumps(payload_data).encode("utf-8")
        elif isinstance(payload_data, str):
            body_bytes = payload_data.encode("utf-8")
        elif isinstance(payload_data, bytes):
            body_bytes = payload_data
        else:
            body_bytes = str(payload_data).encode("utf-8")
        return generate_github_signature(body_bytes, secret)
    return _sign


@pytest.fixture
def mock_issue_payload() -> Dict[str, Any]:
    return make_issue_payload()


@pytest.fixture
def mock_funded_issue_payload() -> Dict[str, Any]:
    return make_issue_payload(
        comments=[{"id": 1001, "body": "💰 **Bounty Confirmed**: 5,000 USD has been locked in GrantFox smart contract escrow."}]
    )


@pytest.fixture
def mock_unfunded_issue_payload() -> Dict[str, Any]:
    return make_issue_payload(
        title="Unfunded exploratory issue",
        body="Just an idea without any bounty reward.",
        comments=[],
        labels=["discussion"]
    )


@pytest.fixture
def mock_banned_platform_payloads() -> Dict[str, Dict[str, Any]]:
    return {
        "algora": make_issue_payload(title="Algora task", body="See https://algora.io/bounty/123"),
        "polar": make_issue_payload(title="Polar reward", body="Funded with https://polar.sh/repo/issue/1"),
        "twenty": make_issue_payload(repo="twentyhq/twenty", title="Fix CRM API issue"),
        "opire": make_issue_payload(title="Opire reward", body="Claim $100 on https://opire.dev")
    }


@pytest.fixture
def mock_competitor_claimed_payload() -> Dict[str, Any]:
    return make_issue_payload(
        comments=[{"id": 201, "user": {"login": "fast_competitor"}, "body": "/claim I will take this issue"}]
    )


@pytest.fixture
def mock_archived_repo_payload() -> Dict[str, Any]:
    return make_issue_payload(is_archived=True)


@pytest.fixture
def mock_subjective_task_payload() -> Dict[str, Any]:
    return make_issue_payload(
        title="Record 5-minute video pitch and live Zoom interview",
        body="Submit a video demo and attend a live Zoom call to receive grant."
    )


@pytest.fixture
def mock_pr_payload() -> Dict[str, Any]:
    return make_pr_payload()


@pytest.fixture
def mock_comment_payload() -> Dict[str, Any]:
    return {
        "action": "created",
        "issue": {
            "number": 105,
            "pull_request": {"url": "https://api.github.com/repos/stellar-org/soroban-contracts/pulls/105"},
        },
        "comment": {
            "id": 888123,
            "body": "@universal_auditor please review the cryptographic primitives and authorization guards.",
            "user": {"login": "universal-engineer"},
        },
        "repository": {
            "name": "soroban-contracts",
            "full_name": "stellar-org/soroban-contracts",
        },
        "sender": {"login": "universal-engineer"},
    }
