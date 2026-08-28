#!/usr/bin/env bash
# ==============================================================================
# The Universal Bounty Fleet - Acceptance Test 4: Firestore Verification Script
# Milestone 4 / Acceptance Criterion 4
#
# Uses `gcloud firestore databases list` / `gcloud firestore databases describe`
# and an inline Python verification snippet to confirm Firestore database is
# active and accessible for read/write in project `odin-500008`.
# ==============================================================================

set -euo pipefail

# Configuration with defaults
PROJECT_ID="${GCP_PROJECT:-odin-500008}"
DATABASE_ID="${FIRESTORE_DATABASE:-(default)}"

echo "============================================================"
echo " Universal Bounty Fleet - Acceptance Test 4: Firestore"
echo " Project:  ${PROJECT_ID}"
echo " Database: ${DATABASE_ID}"
echo "============================================================"

# Step 1: Query Firestore databases list via gcloud
echo "[1/3] Querying Firestore databases in project '${PROJECT_ID}' via gcloud..."
gcloud firestore databases list --project="${PROJECT_ID}"

# Step 2: Describe the specific database instance
echo "[2/3] Describing database '${DATABASE_ID}'..."
gcloud firestore databases describe --database="${DATABASE_ID}" --project="${PROJECT_ID}" --format="yaml(name,locationId,type,state)"

# Step 3: Run live Python read/write verification test against Firestore
echo "[3/3] Executing Python Firestore read/write verification probe..."
python3 - <<EOF
import os
import sys
import time
import subprocess
from datetime import datetime, timezone

project_id = "${PROJECT_ID}"
database_id = "${DATABASE_ID}"

print(f"[PY-PROBE] Initializing Firestore Client for project='{project_id}', database='{database_id}'...")

try:
    from google.cloud import firestore
    from google.oauth2.credentials import Credentials

    # Configure credentials with quota project if running locally via gcloud
    credentials = None
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], stderr=subprocess.DEVNULL).decode().strip()
        if token:
            credentials = Credentials(token=token, quota_project_id=project_id)
            print("[PY-PROBE] Acquired gcloud OAuth token with quota_project_id.")
    except Exception as token_err:
        print(f"[PY-PROBE] Proceeding with default ADC credentials: {token_err}")

    client = firestore.Client(project=project_id, database=database_id, credentials=credentials)
    
    test_collection = "system_verification"
    test_doc_id = f"m4_acceptance_probe_{int(time.time())}"
    doc_ref = client.collection(test_collection).document(test_doc_id)

    # 1. Write Probe
    payload = {
        "service": "universal-bounty-fleet",
        "milestone": "M4",
        "acceptance_test": 4,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
        "author": "teamwork_preview_worker_m4"
    }
    print(f"[PY-PROBE] Writing test document: {test_collection}/{test_doc_id}...")
    doc_ref.set(payload)
    print("[PY-PROBE] Write successful.")

    # 2. Read Probe
    print(f"[PY-PROBE] Reading back test document...")
    snapshot = doc_ref.get()
    if not snapshot.exists:
        print("[PY-PROBE ERROR] Document does not exist after write!")
        sys.exit(1)

    data = snapshot.to_dict()
    print(f"[PY-PROBE] Retrieved data: {data}")
    assert data.get("status") == "active"
    assert data.get("milestone") == "M4"
    print("[PY-PROBE] Read verification successful.")

    # 3. Cleanup Probe
    print(f"[PY-PROBE] Cleaning up verification document...")
    doc_ref.delete()
    assert not doc_ref.get().exists
    print("[PY-PROBE] Cleanup successful. Zero residual state left in Firestore.")

    print("\n[SUCCESS] Firestore native database read/write verified end-to-end.")
except Exception as exc:
    print(f"[PY-PROBE ERROR] Firestore verification failed: {exc}", file=sys.stderr)
    sys.exit(1)
EOF

echo "============================================================"
echo " [PASSED] Acceptance Test 4: Firestore Active & Accessible"
echo " Database '${DATABASE_ID}' verified in project '${PROJECT_ID}'"
echo "============================================================"
exit 0
