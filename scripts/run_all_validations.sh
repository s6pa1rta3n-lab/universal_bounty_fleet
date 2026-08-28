#!/usr/bin/env bash
# ==============================================================================
# The Universal Bounty Fleet - Master Acceptance & Validation Runner
# Milestone 4 / Milestone 5 Comprehensive E2E Test Suite
#
# Executes:
# 1. Full Pytest Suite (Tiers 1-5, Acceptance Tests 1, 2, 5)
# 2. Acceptance Test 4: Live Firestore Native Database Verification
# 3. Acceptance Test 3: Live Cloud Run Gateway Verification
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "========================================================================"
echo " The Universal Bounty Fleet - End-to-End Master Acceptance Test Suite"
echo " Working Directory: ${PROJECT_ROOT}"
echo " Timestamp:         $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "========================================================================"

FAILED_SUITES=()

# ----------------------------------------------------------------------
# 1. Run Complete Pytest Suite (Tiers 1-5 + AC 1, 2, 5)
# ----------------------------------------------------------------------
echo ""
echo ">>> [STAGE 1/3] Executing Pytest Test Suite (Tiers 1-5, AC 1, 2, 5)..."
if pytest tests/ -v; then
    echo "[STAGE 1: PASSED] Pytest test suite completed successfully."
else
    echo "[STAGE 1: FAILED] Pytest test suite encountered errors."
    FAILED_SUITES+=("pytest_suite")
fi

# ----------------------------------------------------------------------
# 2. Run Acceptance Test 4 (Firestore Live Verification)
# ----------------------------------------------------------------------
echo ""
echo ">>> [STAGE 2/3] Executing Acceptance Test 4 (Firestore Native Live Verification)..."
if bash "${SCRIPT_DIR}/verify_firestore.sh"; then
    echo "[STAGE 2: PASSED] Firestore native database verified."
else
    echo "[STAGE 2: FAILED] Firestore verification failed."
    FAILED_SUITES+=("verify_firestore")
fi

# ----------------------------------------------------------------------
# 3. Run Acceptance Test 3 (Cloud Run Live Verification)
# ----------------------------------------------------------------------
echo ""
echo ">>> [STAGE 3/3] Executing Acceptance Test 3 (Cloud Run Live Verification)..."
if bash "${SCRIPT_DIR}/verify_cloud_run.sh"; then
    echo "[STAGE 3: PASSED] Cloud Run gateway service verified."
else
    echo "[STAGE 3: FAILED] Cloud Run gateway verification failed."
    FAILED_SUITES+=("verify_cloud_run")
fi

# ----------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------
echo ""
echo "========================================================================"
if [ ${#FAILED_SUITES[@]} -eq 0 ]; then
    echo " [ALL VALIDATIONS PASSED] All test suites and acceptance criteria verified!"
    echo "========================================================================"
    exit 0
else
    echo " [VALIDATION FAILURES] The following validation suites failed:"
    for suite in "${FAILED_SUITES[@]}"; do
        echo "   - ${suite}"
    done
    echo "========================================================================"
    exit 1
fi
