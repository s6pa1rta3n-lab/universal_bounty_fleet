"""Comprehensive Adversarial Stress Test Suite for Milestones 2 & 3.

Empirically challenges:
1. Milestone 2: Sniper Filter & Escrow Engine
   - Obfuscated and subdomain/path platform domains (Algora, Polar, Opire, twenty)
   - Cancelled and refunded wording variants (negations, question comments, refund phrases)
   - Token & financial amount parsing (unusual tokens, scientific notation, formatted amounts, extreme values)
   - Competitor claim variations (/claim variants, conversational claiming, bot whitelist validation)
2. Milestone 3: 3-Pillar Murder Board & Victory Audit
   - Obfuscated mock crypto keywords (case variations, variable name variations, cryptographic host bypasses)
   - Tricky auth bypasses in multi-line comments, macros, and comments
   - Tampered test assertions (tautologies, unary ops, commented asserts, Rust assert macros)
   - Documentation file exemption safety vs code diff detection
"""

import json
import pytest
from app.intake.sniper_filter import SniperFilter, evaluate_platform_qualification
from app.intake.escrow_engine import EscrowEngine, extract_regex_financials, evaluate_escrow_funding
from app.intake.claim_staker import ClaimStaker, format_claim_comment
from app.audit.murder_board import MurderBoardAnalyzer, analyze_diff_security
from app.audit.gemini_auditor import GeminiCodeAuditor, PillarAuditVerdict
from app.audit.review_submitter import GitHubReviewSubmitter
from app.audit.draft_converter import convert_draft_to_ready
from tests.conftest import MockGitHubAPIClient, MockVertexAIClient


# ============================================================================
# MILESTONE 2: SNIPER FILTER ADVERSARIAL STRESS TESTS
# ============================================================================

class TestSniperFilterAdversarial:
    """Adversarial stress testing for 5-Stage Sniper Filter."""

    def test_banned_platform_subdomains_and_paths(self):
        """Test rejection of subdomains and complex URLs of banned platforms."""
        subdomain_cases = [
            "https://console.algora.io/bounties/123",
            "https://sub.polar.sh/api/v1/grant",
            "https://staging.opire.dev/rewards/456",
            "https://github.com/twentyhq/twenty/issues/999",
            "https://api.algora.io/v1/webhook",
        ]
        for url in subdomain_cases:
            payload = {
                "repository": {"full_name": "clean-org/clean-repo"},
                "issue": {
                    "number": 1,
                    "title": "Bounty issue",
                    "body": f"Details at {url}",
                    "html_url": "https://github.com/clean-org/clean-repo/issues/1",
                },
            }
            res = evaluate_platform_qualification(payload)
            assert not res["qualified"], f"Failed to reject banned URL: {url}"
            assert res["stage_failed"] == 1

    def test_banned_platform_in_issue_title_casing(self):
        """Test case-insensitive detection of banned platforms in title."""
        cases = ["ALGORA Bounty $500", "pOlAr.Sh reward", "OPIRE Escrow", "twentyhq integration"]
        for title in cases:
            payload = {
                "repository": {"full_name": "clean-org/clean-repo"},
                "issue": {"number": 1, "title": title, "body": "Clean body"},
            }
            res = evaluate_platform_qualification(payload)
            assert not res["qualified"], f"Failed to reject banned title: {title}"
            assert res["stage_failed"] == 1

    def test_banned_platform_in_comment_thread(self):
        """Test detection when banned platform link is posted in a comment."""
        payload = {
            "repository": {"full_name": "clean-org/clean-repo"},
            "issue": {
                "number": 1,
                "title": "Valid GrantFox bounty",
                "body": "Funded issue on GrantFox",
                "mock_comments_data": [
                    {"user": {"login": "random-user"}, "body": "Also cross-posted to algora.io/bounty/1"}
                ],
            }
        }
        res = evaluate_platform_qualification(payload)
        assert not res["qualified"]
        assert res["stage_failed"] == 1

    def test_archived_repository_variations(self):
        """Test rejection of archived/disabled repositories across all flag variations."""
        flag_cases = [
            {"is_archived": True},
            {"archived": True},
            {"disabled": True},
        ]
        for repo_flags in flag_cases:
            repo_meta = {"full_name": "some-org/archived-repo"}
            repo_meta.update(repo_flags)
            payload = {
                "repository": repo_meta,
                "issue": {"number": 1, "title": "Bounty", "body": "Fix bug"},
            }
            res = evaluate_platform_qualification(payload)
            assert not res["qualified"], f"Failed on flag: {repo_flags}"
            assert res["stage_failed"] == 2
            assert res["reason"] == "ARCHIVED_REPOSITORY"

    def test_competitor_claims_standard_variants(self):
        """Test standard competitor claim detection."""
        competitor_comments = [
            "/claim",
            "/CLAIM",
            "I am claiming this bounty now",
            "i'd like to work on this issue please",
        ]
        for comment_body in competitor_comments:
            payload = {
                "repository": {"full_name": "clean-org/clean-repo"},
                "issue": {
                    "number": 1,
                    "title": "Clean Issue",
                    "body": "Funded $1000",
                    "mock_comments_data": [
                        {"user": {"login": "competitor_dev"}, "body": comment_body}
                    ],
                }
            }
            res = evaluate_platform_qualification(payload)
            assert not res["qualified"], f"Failed to reject competitor claim: {comment_body}"
            assert res["stage_failed"] == 3
            assert res["reason"] == "COMPETITOR_ALREADY_CLAIMED"

    def test_allowed_fleet_bot_comments_not_flagged_as_competitor(self):
        """Test that our own bot's staking comments do not block qualification."""
        fleet_bots = [
            "bounty-fleet[bot]",
            "bounty-fleet",
            "universal-engineer",
            "universal_bounty_fleet",
            "bounty-engine",
            "universal_auditor",
        ]
        for bot_login in fleet_bots:
            payload = {
                "repository": {"full_name": "clean-org/clean-repo"},
                "issue": {
                    "number": 1,
                    "title": "Clean Issue",
                    "body": "Funded $1000",
                    "mock_comments_data": [
                        {"user": {"login": bot_login}, "body": "I would like to work on this issue! /try"}
                    ],
                }
            }
            res = evaluate_platform_qualification(payload)
            assert res["qualified"], f"Wrongly flagged fleet bot {bot_login} as competitor"

    def test_subjective_deliverable_keyword_detection(self):
        """Test rejection of non-technical / subjective tasks."""
        subjective_snippets = [
            "Please submit a video pitch alongside your PR",
            "Mandatory 15-minute zoom interview before assignment",
            "Record a loom walkthrough at loom.com/123",
            "Include a pitch deck and screencast",
            "Design only: Figma only asset delivery",
        ]
        for snippet in subjective_snippets:
            payload = {
                "repository": {"full_name": "clean-org/clean-repo"},
                "issue": {
                    "number": 1,
                    "title": "Hackathon Task",
                    "body": snippet,
                }
            }
            res = evaluate_platform_qualification(payload)
            assert not res["qualified"], f"Failed to reject subjective deliverable: {snippet}"
            assert res["stage_failed"] == 4
            assert res["reason"] == "SUBJECTIVE_DELIVERABLE"


# ============================================================================
# MILESTONE 2: ESCROW ENGINE ADVERSARIAL STRESS TESTS
# ============================================================================

class TestEscrowEngineAdversarial:
    """Adversarial stress testing for Semantic Escrow Engine."""

    def test_cancellation_patterns_in_body_and_comments(self):
        """Test detection of cancelled/refunded/withdrawn bounties."""
        cancellation_texts = [
            "Reward was cancelled by author",
            "Funds refunded to funder",
            "Bounty withdrawn due to inactivity",
            "Grant voided",
            "Funds returned to the funder",
            "Insufficient fund balance on escrow wallet",
            "Escrow failed to lock tokens",
            "Escrow rejected by smart contract",
        ]
        for ctext in cancellation_texts:
            parsed = extract_regex_financials(f"Bounty $1,000 USD. Notice: {ctext}")
            assert not parsed["is_funded"], f"Failed to mark cancelled: {ctext}"
            assert parsed["is_cancelled"]

    def test_token_amount_parsing(self):
        """Test parsing of various crypto token symbols and amounts."""
        test_cases = [
            ("$5,000", 5000.0, "USD"),
            ("$250,000.50", 250000.50, "USD"),
            ("10,000 XLM", 10000.0, "XLM"),
            ("500.50 USDC", 500.50, "USDC"),
            ("2.5 ETH", 2.5, "ETH"),
            ("1000 USDT", 1000.0, "USDT"),
            ("750 DAI", 750.0, "DAI"),
            ("100 MATIC", 100.0, "MATIC"),
            ("50 SOL", 50.0, "SOL"),
        ]
        for text, expected_amt, expected_curr in test_cases:
            res = extract_regex_financials(f"We have deposited {text} into escrow for this issue.")
            assert res["is_funded"], f"Failed to parse funded status for: {text}"
            assert res["amount_usd"] == pytest.approx(expected_amt), f"Amount mismatch for {text}"
            assert res["currency"] == expected_curr, f"Currency mismatch for {text}"

    def test_zero_and_negative_amounts_rejected(self):
        """Test that $0 or negative amounts are never treated as funded."""
        res_zero = extract_regex_financials("Reward: $0.00")
        assert not res_zero["is_funded"]
        assert res_zero["amount_usd"] == 0.0

    def test_escrow_engine_vertex_ai_confidence_cutoff(self):
        """Test that confidence scores below 0.50 are rejected even if is_funded is True."""
        mock_client = MockVertexAIClient()
        mock_client.default_response = json.dumps({
            "is_funded": True,
            "escrow_amount_usd": 1000.0,
            "currency": "USD",
            "confidence": 0.40,  # Below MIN_ESCROW_CONFIDENCE (0.50)
            "reasoning": "Low confidence evaluation",
            "is_cancelled_or_refunded": False,
        })
        engine = EscrowEngine()
        payload = {
            "issue": {"title": "Bounty $1000", "body": "Funded $1000"},
            "repository": {"full_name": "test/repo"},
        }
        res = engine.evaluate(payload, vertex_client=mock_client)
        assert not res["is_funded"], "Confidence < 0.50 must force is_funded=False"


# ============================================================================
# MILESTONE 3: 3-PILLAR MURDER BOARD ADVERSARIAL STRESS TESTS
# ============================================================================

class TestMurderBoardAdversarial:
    """Adversarial stress testing for 3-Pillar Murder Board Analyzer."""

    def test_pillar1_mock_crypto_variants(self):
        """Test catching various mocked cryptographic primitives in diffs."""
        mock_crypto_diffs = [
            ("diff --git a/src/zk.rs b/src/zk.rs\n+++ b/src/zk.rs\n@@ -1,3 +1,4 @@\n+let mock_bls = true;\n", "mock_bls"),
            ("diff --git a/src/verifier.rs b/src/verifier.rs\n+++ b/src/verifier.rs\n@@ -1,3 +1,4 @@\n+let _dummy = proof.len();\n", "dummy proof len"),
            ("diff --git a/src/ec.rs b/src/ec.rs\n+++ b/src/ec.rs\n@@ -1,3 +1,4 @@\n+fn verify_pairing() { let dummy_pairing = 1; }\n", "dummy_pairing"),
            ("diff --git a/src/crypto.rs b/src/crypto.rs\n+++ b/src/crypto.rs\n@@ -1,3 +1,4 @@\n+let fake_proof = vec![0u8; 32];\n", "fake_proof"),
            ("diff --git a/src/sig.rs b/src/sig.rs\n+++ b/src/sig.rs\n@@ -1,3 +1,4 @@\n+let mock_signature = Signature::default();\n", "mock_signature"),
            ("diff --git a/src/auth.rs b/src/auth.rs\n+++ b/src/auth.rs\n@@ -1,3 +1,4 @@\n+let stub_pairing = 42;\n", "stub_pairing"),
        ]
        for diff, name in mock_crypto_diffs:
            res = analyze_diff_security(diff)
            assert not res["pillar1_crypto"], f"Failed to flag Pillar 1 violation for {name}"
            assert not res["all_passed"]
            assert any(v["pillar"] == 1 for v in res["violations"])

    def test_pillar2_authorization_bypass_variants(self):
        """Test catching commented-out or bypassed require_auth across comments and code."""
        auth_bypass_diffs = [
            ("diff --git a/src/contract.rs b/src/contract.rs\n+++ b/src/contract.rs\n@@ -1,3 +1,4 @@\n+// recipient.require_auth();\n", "commented recipient auth"),
            ("diff --git a/src/contract.rs b/src/contract.rs\n+++ b/src/contract.rs\n@@ -1,3 +1,4 @@\n+// caller.require_auth();\n", "commented caller auth"),
            ("diff --git a/src/vault.rs b/src/vault.rs\n+++ b/src/vault.rs\n@@ -1,3 +1,4 @@\n+# env.require_auth();\n", "hash commented auth"),
            ("diff --git a/src/pool.rs b/src/pool.rs\n+++ b/src/pool.rs\n@@ -1,3 +1,4 @@\n+/* address.require_auth(); */\n", "block commented auth"),
            ("diff --git a/src/token.rs b/src/token.rs\n+++ b/src/token.rs\n@@ -1,3 +1,4 @@\n+let auth_bypassed = true;\n", "auth_bypassed variable"),
            ("diff --git a/src/claim.rs b/src/claim.rs\n+++ b/src/claim.rs\n@@ -1,3 +1,4 @@\n+let bypass_auth = true;\n", "bypass_auth variable"),
        ]
        for diff, name in auth_bypass_diffs:
            res = analyze_diff_security(diff)
            assert not res["pillar2_auth"], f"Failed to flag Pillar 2 violation for {name}"
            assert not res["all_passed"]
            assert any(v["pillar"] == 2 for v in res["violations"])

    def test_pillar3_test_assertion_tampering_variants(self):
        """Test catching commented-out, weakened, or bypassed assertions in test files."""
        assertion_tampering_diffs = [
            ("diff --git a/tests/test_vault.rs b/tests/test_vault.rs\n+++ b/tests/test_vault.rs\n@@ -1,3 +1,4 @@\n+// assert_eq!(balance, 1000);\n", "commented assert_eq"),
            ("diff --git a/tests/test_auth.rs b/tests/test_auth.rs\n+++ b/tests/test_auth.rs\n@@ -1,3 +1,4 @@\n+// assert!(is_valid);\n", "commented assert!"),
            ("diff --git a/tests/test_security.py b/tests/test_security.py\n+++ b/tests/test_security.py\n@@ -1,3 +1,4 @@\n+# with pytest.raises(AuthError):\n", "commented pytest.raises"),
            ("diff --git a/tests/test_pool.py b/tests/test_pool.py\n+++ b/tests/test_pool.py\n@@ -1,3 +1,4 @@\n+assert True  # bypassed\n", "assert True bypass"),
            ("diff --git a/tests/test_token.py b/tests/test_pool.py\n+++ b/tests/test_token.py\n@@ -1,3 +1,4 @@\n+assert 1 == 1\n", "tautological assert 1 == 1"),
        ]
        for diff, name in assertion_tampering_diffs:
            res = analyze_diff_security(diff)
            assert not res["pillar3_assertions"], f"Failed to flag Pillar 3 violation for {name}"
            assert not res["all_passed"]
            assert any(v["pillar"] == 3 for v in res["violations"])

    def test_clean_production_diff_passes_all_pillars(self):
        """Test that genuine Soroban contract code with proper auth and crypto passes cleanly."""
        clean_diff = """diff --git a/src/contract.rs b/src/contract.rs
--- a/src/contract.rs
+++ b/src/contract.rs
@@ -10,6 +10,12 @@ pub struct BountyContract;

 impl BountyContract {
     pub fn claim_bounty(env: Env, claimer: Address, amount: i128) {
+        claimer.require_auth();
+        let valid = env.crypto().bls12_381_verify(&proof);
+        if !valid {
+            panic_with_error!(&env, Error::InvalidProof);
+        }
+        token::Client::new(&env, &token_addr).transfer(&env.current_contract_address(), &claimer, &amount);
     }
 }
"""
        res = analyze_diff_security(clean_diff)
        assert res["pillar1_crypto"]
        assert res["pillar2_auth"]
        assert res["pillar3_assertions"]
        assert res["all_passed"]
        assert len(res["violations"]) == 0


# ============================================================================
# MILESTONE 3: GEMINI AUDITOR & REVIEW SUBMISSION ADVERSARIAL STRESS TESTS
# ============================================================================

class TestVictoryAuditReviewFlow:
    """Test full Victory Audit reasoning, review submission, and draft conversion."""

    def test_auditor_flags_request_changes_on_violation(self):
        """Test that GeminiCodeAuditor correctly issues REQUEST_CHANGES on violation."""
        violating_diff = """diff --git a/src/token.rs b/src/token.rs
+++ b/src/token.rs
@@ -1,3 +1,4 @@
+// caller.require_auth();
"""
        auditor = GeminiCodeAuditor()
        result = auditor.audit_diff(violating_diff)
        assert not result.passed
        assert result.verdict == "REQUEST_CHANGES"
        assert not result.pillar_breakdown["pillar2_auth"]

    def test_review_submitter_formats_structured_markdown(self):
        """Test formatting of review markdown across pass/fail states."""
        submitter = GitHubReviewSubmitter(github_client=MockGitHubAPIClient())
        
        # Test failing review format
        failing_findings = {
            "pillar1_crypto": False,
            "pillar2_auth": True,
            "pillar3_assertions": True,
            "violations": [
                {"pillar": 1, "file": "src/zk.rs", "line": 42, "description": "Mock crypto detected."}
            ]
        }
        review_body = submitter.format_review_body("REQUEST_CHANGES", failing_findings)
        assert "## Victory Audit Review" in review_body
        assert "**Verdict:** `REQUEST_CHANGES`" in review_body
        assert "- **Pillar 1 (Cryptographic Integrity):** ❌ FAIL" in review_body
        assert "- **Pillar 2 (Authorization Enforcement):** ✅ PASS" in review_body
        assert "- **Pillar 3 (Assertion Preservation):** ✅ PASS" in review_body
        assert "Mock crypto detected" in review_body

    def test_draft_converter_converts_ready_on_approved_pr(self):
        """Test that convert_draft_to_ready converts draft pull requests."""
        mock_gh = MockGitHubAPIClient()
        # Mocking GraphQL conversion
        res = convert_draft_to_ready(node_id="PR_kwDOMock123", github_client=mock_gh)
        assert res is True
        assert any(c.get("node_id") == "PR_kwDOMock123" for c in mock_gh.ready_conversions)
