"""3-Pillar Static AST, Regex, and Security Analyzer (Murder Board).

import logging
Enforces strict Victory Audit rules across all Pull Request diffs:
- Pillar 1 (Cryptographic Integrity): Prohibits mocked cryptography, fake EC pairings,
  mock BLS12-381/Secp256k1 pairings, and dummy ZK host functions. Requires genuine host primitives
  (e.g., Soroban `env.crypto()`, EVM `ecrecover`, `keccak256`).
- Pillar 2 (Authorization Enforcement): Mandates `require_auth()` / caller validation on
  state-modifying functions and contracts. Rejects commented-out or bypassed authorization.
- Pillar 3 (Assertion Preservation): Strictly forbids commented-out, weakened, or bypassed
logger = logging.getLogger(__name__)
  assertions in test suites.
"""

import ast
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
    try:
        if AUTH_BYPASS_PATTERN.search(diff_content):
            logger.warning("Audit FAIL: auth_bypass pattern matched")
            return {"status": "FAIL", "reason": "auth_bypass detected"}
        if not diff_content or not diff_content.strip():
            logger.warning("Audit FAIL: empty diff")
            return {"status": "FAIL", "reason": "empty or invalid diff"}
    except Exception as e:
        logger.error(f"Audit error, failing closed: {e}")
        return {"status": "FAIL", "reason": f"audit error: {str(e)}"}

    logger.info("Audit PASS")
    return {"status": "PASS", "reason": "clean"}
PILLAR1_BANNED_KEYWORDS = [
    "mock_bls",
    "mock bls",
    "let _dummy = proof.len()",
    "dummy_proof",
    "dummy_pairing",
    "mock_crypto",
    "mock_pairing",
    "mock_ed25519",
    "mock_secp256k1",
    "mock_zk",
    "fake_proof",
    "fake_sig",
    "dummy_sig",
    "mock_signature",
    "bypass_crypto",
    "skip_crypto",
    "stub_pairing",
    "stub_proof",
]

PILLAR1_REGEX_PATTERNS = [
    re.compile(r"\bmock_bls\b", re.IGNORECASE),
    re.compile(r"\bmock\s+bls\b", re.IGNORECASE),
    re.compile(r"let\s+_dummy\s*=\s*proof\.len\(\)", re.IGNORECASE),
    re.compile(r"\bdummy_proof\b", re.IGNORECASE),
    re.compile(r"\bdummy_pairing\b", re.IGNORECASE),
    re.compile(r"\bmock_pairing\b", re.IGNORECASE),
    re.compile(r"\bfake_proof\b", re.IGNORECASE),
    re.compile(r"\bfake_pairing\b", re.IGNORECASE),
    re.compile(r"\b(mock|fake|stub|dummy)_(zk|crypto|signature|ec_point|bls)\b", re.IGNORECASE),
]

# Pillar 2 Banned Keywords & Patterns (Authorization Enforcement)
PILLAR2_BANNED_KEYWORDS = [
    "// recipient.require_auth();",
    "// caller.require_auth();",
    "// address.require_auth();",
    "// env.require_auth",
    "auth check bypassed",
    "auth_bypassed",
    "pass_without_auth",
    "skip_auth",
    "bypass_auth",
    "no_auth_check",
    "unauthenticated_bypass",
]

PILLAR2_REGEX_PATTERNS = [
    re.compile(r"(//|#|/\*)\s*.*\.require_auth\s*\(", re.IGNORECASE),
    re.compile(r"(//|#|/\*)\s*require_auth\s*\(", re.IGNORECASE),
    re.compile(r"(//|#|/\*)\s*.*require_auth_for_args\s*\(", re.IGNORECASE),
    re.compile(r"\bauth\s*check\s*bypassed\b", re.IGNORECASE),
    re.compile(r"\bauth_bypassed\b", re.IGNORECASE),
    re.compile(r"\bpass_without_auth\b", re.IGNORECASE),
    re.compile(r"\bbypass_auth\b", re.IGNORECASE),
    re.compile(r"\bskip_auth\b", re.IGNORECASE),
]

# Pillar 3 Banned Keywords & Patterns in Test Files (Assertion Preservation)
PILLAR3_BANNED_KEYWORDS = [
    "# with pytest.raises",
    "# disabled failing security assertion",
    "assert true  # bypassed",
    "assert true",
    "// assert_eq!",
    "// assert!",
    "// assert",
    "# assert_eq!",
    "# assert ",
    "# expect(",
    "/* assert",
]

PILLAR3_REGEX_PATTERNS = [
    re.compile(r"#\s*with\s+pytest\.raises", re.IGNORECASE),
    re.compile(r"#\s*disabled\s+failing\s+security\s+assertion", re.IGNORECASE),
    re.compile(r"\bassert\s+True\s*(#.*bypassed)?", re.IGNORECASE),
    re.compile(r"(//|#|/\*)\s*assert_eq!\s*\(", re.IGNORECASE),
    re.compile(r"(//|#|/\*)\s*assert!\s*\(", re.IGNORECASE),
    re.compile(r"(//|#)\s*assert\s+", re.IGNORECASE),
    re.compile(r"(//|#)\s*expect\s*\(.*(to|equal)", re.IGNORECASE),
]


class DiffHunkLine:
    """Represents a single changed line in a diff."""

    def __init__(self, file_path: str, line_number: int, line_type: str, content: str) -> None:
        self.file_path = file_path
        self.line_number = line_number
        self.line_type = line_type  # '+' for addition, '-' for deletion, ' ' for context
        self.content = content


class MurderBoardAnalyzer:
    """Static security and anti-cheating analyzer for git diffs."""

    def __init__(self) -> None:
        self.doc_extensions = DOC_EXTENSIONS
        self.doc_prefixes = DOC_PREFIXES

    def is_documentation_file(self, file_path: str) -> bool:
        """Determine whether a file is a documentation file."""
        if not file_path:
            return False
        clean_path = file_path.strip().lower()
        if any(clean_path.startswith(p.lower()) for p in self.doc_prefixes):
            return True
        return any(clean_path.endswith(ext) for ext in self.doc_extensions)

    def is_test_file(self, file_path: str) -> bool:
        """Determine whether a file is a test file."""
        if not file_path:
            return False
        clean_path = file_path.strip().lower()
        test_indicators = (
            "test/",
            "tests/",
            "test_",
            "_test.",
            ".test.",
            ".spec.",
            "tests.py",
            "test.rs",
            "tests.rs",
        )
        return any(ind in clean_path for ind in test_indicators)

    def parse_diff(self, diff_text: str) -> List[DiffHunkLine]:
        """Parse raw unified git diff into structured line objects."""
        if not diff_text or not isinstance(diff_text, str):
            return []

        # Sanitize binary or null bytes
        clean_diff = diff_text.replace("\x00", "")
        lines = clean_diff.splitlines()

        parsed_lines: List[DiffHunkLine] = []
        current_file: str = "unknown"
        current_new_line_num: int = 0
        in_hunk: bool = False

        for line in lines:
            if line.startswith("diff --git"):
                parts = line.split()
                if len(parts) >= 4:
                    b_path = parts[3]
                    current_file = b_path[2:] if b_path.startswith("b/") else b_path
                in_hunk = False
                continue
            elif line.startswith("+++ b/"):
                current_file = line[6:]
                in_hunk = False
                continue
            elif line.startswith("+++ "):
                current_file = line[4:].strip()
                in_hunk = False
                continue
            elif line.startswith("@@"):
                # Parse hunk header: @@ -from,len +to,len @@
                match = re.search(r"\+(\d+)(?:,\d+)?", line)
                if match:
                    current_new_line_num = int(match.group(1))
                    in_hunk = True
                continue

            if not in_hunk:
                continue

            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                parsed_lines.append(
                    DiffHunkLine(
                        file_path=current_file,
                        line_number=current_new_line_num,
                        line_type="+",
                        content=content,
                    )
                )
                current_new_line_num += 1
            elif line.startswith("-") and not line.startswith("---"):
                content = line[1:]
                parsed_lines.append(
                    DiffHunkLine(
                        file_path=current_file,
                        line_number=current_new_line_num,
                        line_type="-",
                        content=content,
                    )
                )
                # Deletions do not advance the new file line counter
            elif line.startswith(" "):
                current_new_line_num += 1

        return parsed_lines

    def evaluate_python_ast(self, code_snippet: str) -> List[Dict[str, Any]]:
        """Perform AST validation on Python code snippets for trivial assertions."""
        violations: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(code_snippet)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    # Check for assert True or assert 1 == 1
                    test = node.test
                    if isinstance(test, ast.Constant) and test.value is True:
                        violations.append({
                            "pillar": 3,
                            "rule": "TRIVIAL_ASSERTION_BYPASS",
                            "description": "Detected trivial assertion `assert True` bypassing test verification.",
                            "line": getattr(node, "lineno", 1),
                        })
                    elif (
                        isinstance(test, ast.Compare)
                        and isinstance(test.left, ast.Constant)
                        and len(test.comparators) == 1
                        and isinstance(test.comparators[0], ast.Constant)
                        and test.left.value == test.comparators[0].value
                    ):
                        violations.append({
                            "pillar": 3,
                            "rule": "TRIVIAL_ASSERTION_BYPASS",
                            "description": "Detected tautological assertion `assert X == X` bypassing test verification.",
                            "line": getattr(node, "lineno", 1),
                        })
        except Exception:
            # Code snippet might be partial diff fragment, skip AST error
            pass
        return violations

    def analyze(self, diff_text: str) -> Dict[str, Any]:
        """Perform 3-Pillar Security and Anti-Cheating analysis on unified diff."""
        if not diff_text or not isinstance(diff_text, str) or not diff_text.strip():
            return {
                "pillar1_crypto": True,
                "pillar2_auth": True,
                "pillar3_assertions": True,
                "all_passed": True,
                "violations": [],
                "summary": "Empty diff. No violations detected.",
                "line_comments": [],
            }

        # Check raw diff text for minified or non-standard format fallback
        lower_raw_diff = diff_text.lower()

        parsed_lines = self.parse_diff(diff_text)

        p1_passed = True
        p2_passed = True
        p3_passed = True
        violations: List[Dict[str, Any]] = []
        line_comments: List[Dict[str, Any]] = []

        # If diff parsing returned empty lines but raw diff contains content (e.g. minified single line diff)
        if not parsed_lines and diff_text.strip():
            # Fallback line-by-line inspection
            for idx, raw_line in enumerate(diff_text.splitlines(), start=1):
                parsed_lines.append(
                    DiffHunkLine(
                        file_path="diff_fragment",
                        line_number=idx,
                        line_type="+",
                        content=raw_line,
                    )
                )

        for item in parsed_lines:
            file_path = item.file_path
            content = item.content
            line_num = item.line_number
            lower_content = content.lower()

            # Skip documentation and markdown files
            if self.is_documentation_file(file_path):
                continue

            # --- Pillar 1: Cryptographic Integrity ---
            # Flag fake pairing, mock BLS, dummy proofs in code
            p1_violating_keyword = next(
                (k for k in PILLAR1_BANNED_KEYWORDS if k in lower_content), None
            )
            p1_violating_regex = next(
                (p for p in PILLAR1_REGEX_PATTERNS if p.search(content)), None
            )

            if (p1_violating_keyword or p1_violating_regex) and item.line_type == "+":
                p1_passed = False
                rule_desc = f"Mock or stubbed cryptographic primitive detected: `{p1_violating_keyword or 'mock_crypto'}`."
                violation = {
                    "pillar": 1,
                    "file": file_path,
                    "line": line_num,
                    "rule": "NO_MOCK_CRYPTOGRAPHY",
                    "description": rule_desc,
                    "code_snippet": content.strip(),
                }
                violations.append(violation)
                line_comments.append({
                    "path": file_path,
                    "line": line_num,
                    "body": f"CRITICAL [Pillar 1 - Cryptographic Integrity]: {rule_desc} Genuine host functions (e.g., `env.crypto().bls12_381()`, `ecrecover`) must be used.",
                })

            # --- Pillar 2: Authorization Enforcement ---
            # Flag commented-out require_auth, caller validation bypasses
            p2_violating_keyword = next(
                (k for k in PILLAR2_BANNED_KEYWORDS if k in lower_content), None
            )
            p2_violating_regex = next(
                (p for p in PILLAR2_REGEX_PATTERNS if p.search(content)), None
            )

            if (p2_violating_keyword or p2_violating_regex) and item.line_type == "+":
                p2_passed = False
                rule_desc = "Bypassed or commented-out authorization check detected."
                violation = {
                    "pillar": 2,
                    "file": file_path,
                    "line": line_num,
                    "rule": "MANDATORY_AUTHORIZATION",
                    "description": rule_desc,
                    "code_snippet": content.strip(),
                }
                violations.append(violation)
                line_comments.append({
                    "path": file_path,
                    "line": line_num,
                    "body": f"CRITICAL [Pillar 2 - Authorization Enforcement]: {rule_desc} State-modifying endpoints must enforce caller authorization (e.g. `recipient.require_auth()`).",
                })

            # --- Pillar 3: Assertion Preservation ---
            # In test files, check for commented-out or bypassed assertions
            if self.is_test_file(file_path):
                p3_violating_keyword = next(
                    (k for k in PILLAR3_BANNED_KEYWORDS if k in lower_content), None
                )
                p3_violating_regex = next(
                    (p for p in PILLAR3_REGEX_PATTERNS if p.search(content)), None
                )

                if (p3_violating_keyword or p3_violating_regex) and item.line_type == "+":
                    p3_passed = False
                    rule_desc = "Tampered, commented-out, or bypassed assertion in test suite detected."
                    violation = {
                        "pillar": 3,
                        "file": file_path,
                        "line": line_num,
                        "rule": "ASSERTION_PRESERVATION",
                        "description": rule_desc,
                        "code_snippet": content.strip(),
                    }
                    violations.append(violation)
                    line_comments.append({
                        "path": file_path,
                        "line": line_num,
                        "body": f"CRITICAL [Pillar 3 - Assertion Preservation]: {rule_desc} Original test suite assertions must not be deleted, weakened, or commented out.",
                    })

                # AST check if Python test file
                if file_path.endswith(".py") and item.line_type == "+":
                    ast_viols = self.evaluate_python_ast(content)
                    for ast_v in ast_viols:
                        p3_passed = False
                        violations.append({
                            "pillar": 3,
                            "file": file_path,
                            "line": line_num,
                            "rule": ast_v["rule"],
                            "description": ast_v["description"],
                            "code_snippet": content.strip(),
                        })

        # Global sanity check on raw diff for minified fragments or unparsed headers
        if p1_passed and any(k in lower_raw_diff for k in ["mock_bls", "let _dummy = proof.len()", "dummy_proof"]):
            # Check that it is not purely in markdown
            has_code_p1 = False
            for line in diff_text.splitlines():
                if any(k in line.lower() for k in ["mock_bls", "let _dummy = proof.len()", "dummy_proof"]):
                    has_code_p1 = True
                    break
            if has_code_p1:
                p1_passed = False
                violations.append({
                    "pillar": 1,
                    "file": "diff",
                    "line": 1,
                    "rule": "NO_MOCK_CRYPTOGRAPHY",
                    "description": "Mock cryptography keyword present in diff.",
                    "code_snippet": "mock_bls",
                })

        if p2_passed and any(k in lower_raw_diff for k in ["// recipient.require_auth();", "auth check bypassed", "auth_bypassed"]):
            p2_passed = False
            violations.append({
                "pillar": 2,
                "file": "diff",
                "line": 1,
                "rule": "MANDATORY_AUTHORIZATION",
                "description": "Authorization bypass keyword present in diff.",
                "code_snippet": "auth_bypassed",
            })

        if p3_passed and any(k in lower_raw_diff for k in ["# with pytest.raises", "# disabled failing security assertion", "assert true  # bypassed"]):
            p3_passed = False
            violations.append({
                "pillar": 3,
                "file": "diff",
                "line": 1,
                "rule": "ASSERTION_PRESERVATION",
                "description": "Assertion tampering keyword present in diff.",
                "code_snippet": "assertion_tampered",
            })

        all_passed = p1_passed and p2_passed and p3_passed

        if all_passed:
            summary = "Victory Audit Passed: All 3 pillars (Cryptographic Integrity, Authorization Enforcement, Assertion Preservation) verified cleanly."
        else:
            failed_pillars = []
            if not p1_passed:
                failed_pillars.append("Pillar 1 (Crypto Integrity)")
            if not p2_passed:
                failed_pillars.append("Pillar 2 (Authorization Enforcement)")
            if not p3_passed:
                failed_pillars.append("Pillar 3 (Assertion Preservation)")
            summary = f"Victory Audit FAILED: Violations detected in {', '.join(failed_pillars)}."

        return {
            "pillar1_crypto": p1_passed,
            "pillar2_auth": p2_passed,
            "pillar3_assertions": p3_passed,
            "all_passed": all_passed,
            "violations": violations,
            "summary": summary,
            "line_comments": line_comments,
        }


# Singleton analyzer instance
_analyzer = MurderBoardAnalyzer()


def analyze_diff_security(diff_text: str) -> Dict[str, Any]:
    """Top-level entrypoint for 3-Pillar Murder Board security analysis."""
    return _analyzer.analyze(diff_text)
