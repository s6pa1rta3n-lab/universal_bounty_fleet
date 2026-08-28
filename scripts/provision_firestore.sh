#!/usr/bin/env bash
# ==============================================================================
# The Universal Bounty Fleet - GEAP Firestore Provisioning Script
# Milestone 4: Infrastructure & Deployment Automation
#
# Provisions Google Cloud Firestore in Native Mode for project odin-500008
# in location nam5 (or configured region), with idempotency check.
# ==============================================================================

set -euo pipefail

# Configuration with defaults
PROJECT_ID="${GCP_PROJECT:-odin-500008}"
LOCATION="${FIRESTORE_LOCATION:-nam5}"
DATABASE_ID="${FIRESTORE_DATABASE:-(default)}"
DATABASE_TYPE="firestore-native"

echo "============================================================"
echo " Universal Bounty Fleet: Firestore Provisioning"
echo " Project:  ${PROJECT_ID}"
echo " Location: ${LOCATION}"
echo " Database: ${DATABASE_ID}"
echo " Type:     ${DATABASE_TYPE}"
echo "============================================================"

# Step 1: Ensure Firestore API is enabled
echo "[1/3] Verifying firestore.googleapis.com API enablement..."
gcloud services enable firestore.googleapis.com --project="${PROJECT_ID}"

# Step 2: Check if the Firestore database already exists
echo "[2/3] Checking if database '${DATABASE_ID}' already exists in project '${PROJECT_ID}'..."
EXISTING_DBS=$(gcloud firestore databases list --project="${PROJECT_ID}" --format="value(name)" 2>/dev/null || true)

DB_FOUND=false
if [ -n "${EXISTING_DBS}" ]; then
    while IFS= read -r db_name; do
        if [[ "${db_name}" == *"${DATABASE_ID}"* ]] || [[ "${db_name}" == *"/databases/(default)"* && "${DATABASE_ID}" == "(default)" ]]; then
            DB_FOUND=true
            break
        fi
    done <<< "${EXISTING_DBS}"
fi

if [ "${DB_FOUND}" = true ]; then
    echo "[INFO] Firestore database '${DATABASE_ID}' already exists in project '${PROJECT_ID}'."
    echo "[INFO] Retrieving database metadata..."
    gcloud firestore databases describe --database="${DATABASE_ID}" --project="${PROJECT_ID}" --format="yaml(name,locationId,type,state)" 2>/dev/null || true
else
    echo "[3/3] Creating Firestore native mode database '${DATABASE_ID}' in location '${LOCATION}'..."
    if [ "${DATABASE_ID}" = "(default)" ]; then
        gcloud firestore databases create \
            --location="${LOCATION}" \
            --project="${PROJECT_ID}" \
            --type="${DATABASE_TYPE}"
    else
        gcloud firestore databases create \
            --database="${DATABASE_ID}" \
            --location="${LOCATION}" \
            --project="${PROJECT_ID}" \
            --type="${DATABASE_TYPE}"
    fi
    echo "[SUCCESS] Firestore native mode database provisioned successfully."
fi

echo "============================================================"
echo " Firestore Provisioning Complete: ${PROJECT_ID} / ${DATABASE_ID}"
echo "============================================================"
exit 0
