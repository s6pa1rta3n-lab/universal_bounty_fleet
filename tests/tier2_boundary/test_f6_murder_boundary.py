"""
Tier 2 Boundary Tests: F6 - Murder Board Analyzer Boundary & Corner Cases
"""

import pytest
from tests.tier1_feature.test_f6_murder_board import analyze_diff


def test_f6_boundary_empty_diff():
    """Test F6-B.1: Empty diff with no changes is treated as clean / pass."""
    findings = analyze_diff("")
    assert findings["all_passed"] is True


def test_f6_boundary_markdown_documentation_diff():
    """Test F6-B.2: Documentation and markdown diffs pass security checks."""
    doc_diff = """
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,3 +1,4 @@
 # Documentation
+Explaining require_auth() and cryptographic verification.
"""
    findings = analyze_diff(doc_diff)
    assert findings["all_passed"] is True


def test_f6_boundary_obfuscated_auth_comment():
    """Test F6-B.3: Catches variations of commented-out require_auth."""
    obfuscated_diff = """
diff --git a/contract.rs b/contract.rs
--- a/contract.rs
+++ b/contract.rs
@@ -10,3 +10,3 @@
-    recipient.require_auth();
+    // recipient.require_auth();
"""
    findings = analyze_diff(obfuscated_diff)
    assert findings["pillar2_auth"] is False


def test_f6_boundary_one_violation_in_multi_file_diff():
    """Test F6-B.4: A single violation in a 10-file clean diff fails the entire audit."""
    clean_part = "\n".join([f"diff --git a/file_{i}.rs b/file_{i}.rs\n+ fn ok_{i}() {{}}" for i in range(10)])
    bad_part = "\ndiff --git a/bad.rs b/bad.rs\n+ // recipient.require_auth();"
    findings = analyze_diff(clean_part + bad_part)
    assert findings["pillar2_auth"] is False
    assert findings["all_passed"] is False


def test_f6_boundary_minified_single_line_diff():
    """Test F6-B.5: Minified single line containing mock_bls fails Pillar 1."""
    minified = "diff --git a/dist.js b/dist.js\n+ function test(){let mock_bls=true;return mock_bls;}"
    findings = analyze_diff(minified)
    assert findings["pillar1_crypto"] is False
