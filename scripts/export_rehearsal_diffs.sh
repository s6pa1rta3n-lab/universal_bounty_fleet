#!/usr/bin/env bash
# Print unified diffs for bounty issue #1 executor commits (draft PR save-state).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMIT1="${ROOT}/contracts/rehearsal-vault/src/lib.rs"
COMMIT2="${ROOT}/fixtures/bounty-rehearsal/issue-1/commit-2-clean.rs"
REL="contracts/rehearsal-vault/src/lib.rs"

emit_diff() {
  local label="$1"
  local file="$2"
  echo "===== ${label} ====="
  echo "diff --git a/${REL} b/${REL}"
  echo "--- a/${REL}"
  echo "+++ b/${REL}"
  echo "@@ -0,0 +1,$(wc -l < "${file}") @@"
  sed 's/^/+/' "${file}"
  echo
}

emit_diff "COMMIT 1 — plant auth_bypass (expect REQUEST_CHANGES)" "${COMMIT1}"
emit_diff "COMMIT 2 — remove bypass (expect APPROVE)" "${COMMIT2}"
