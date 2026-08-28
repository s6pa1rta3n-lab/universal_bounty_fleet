#!/usr/bin/env bash
# ==============================================================================
# The Universal Bounty Fleet - GEAP Cloud Run Deployment Script
# Milestone 4: Infrastructure & Deployment Automation
#
# Enables required GCP services and deploys the bounty-fleet-gateway service
# to Google Cloud Run in us-central1 for project odin-500008.
# ==============================================================================

set -euo pipefail

# Configuration with defaults
PROJECT_ID="${GCP_PROJECT:-odin-500008}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-bounty-fleet-gateway}"
VERTEX_LOCATION="${VERTEX_AI_LOCATION:-us-central1}"
ENVIRONMENT="${APP_ENV:-production}"
SOURCE_DIR="${1:-.}"

echo "============================================================"
echo " Universal Bounty Fleet: Cloud Run Gateway Deployment"
echo " Project:     ${PROJECT_ID}"
echo " Region:      ${REGION}"
echo " Service:     ${SERVICE_NAME}"
echo " Environment: ${ENVIRONMENT}"
echo " Vertex Loc:  ${VERTEX_LOCATION}"
echo " Source Dir:  ${SOURCE_DIR}"
echo "============================================================"

# Step 1: Enable required GCP services
echo "[1/3] Enabling required Google Cloud APIs (Cloud Run, Firestore, Cloud Build)..."
gcloud services enable run.googleapis.com firestore.googleapis.com cloudbuild.googleapis.com --project="${PROJECT_ID}"

# Step 2: Deploy service to Cloud Run from source
echo "[2/3] Building container and deploying service '${SERVICE_NAME}' to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --source "${SOURCE_DIR}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --allow-unauthenticated \
    --quiet \
    --set-env-vars "GCP_PROJECT=${PROJECT_ID},GCP_REGION=${REGION},VERTEX_AI_LOCATION=${VERTEX_LOCATION},APP_ENV=${ENVIRONMENT}"

# Step 3: Retrieve and display deployed service URL
echo "[3/3] Retrieving service URL and status..."
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)" 2>/dev/null || echo "")

if [ -n "${SERVICE_URL}" ]; then
    echo "============================================================"
    echo " Deployment Succeeded!"
    echo " Service URL: ${SERVICE_URL}"
    echo " Health Check: ${SERVICE_URL}/healthz"
    echo " Webhook URL:  ${SERVICE_URL}/webhook/github"
    echo "============================================================"
else
    echo "[WARNING] Service deployed but URL could not be automatically resolved."
fi

exit 0
