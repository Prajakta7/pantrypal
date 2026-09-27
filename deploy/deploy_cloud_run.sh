#!/usr/bin/env bash
# =============================================================================
# Deploy PantryPal to Cloud Run.
#   DB_PASSWORD='<db password>' bash deploy/deploy_cloud_run.sh
# In a lab VPC with PSC, also set: ALLOYDB_IP_TYPE=PSC VPC_NETWORK=<vpc> VPC_SUBNET=<subnet>
# =============================================================================
set -euo pipefail
source "$(dirname "$0")/../scripts/env.sh"
: "${DB_PASSWORD:?Set DB_PASSWORD first}"
SERVICE="pantrypal"
SA_NAME="pantrypal-sa"
SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
IP_TYPE="${ALLOYDB_IP_TYPE:-PUBLIC}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com aiplatform.googleapis.com

# --- Password → Secret Manager -------------------------------------------------
if gcloud secrets describe pantrypal-db-password >/dev/null 2>&1; then
  printf '%s' "$DB_PASSWORD" | gcloud secrets versions add pantrypal-db-password --data-file=-
else
  printf '%s' "$DB_PASSWORD" | gcloud secrets create pantrypal-db-password --data-file=-
fi

# --- Least-privilege identity for the app ------------------------------------
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --display-name="PantryPal"
for ROLE in roles/alloydb.client roles/serviceusage.serviceUsageConsumer \
            roles/secretmanager.secretAccessor roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" \
    --role="$ROLE" --condition=None --quiet >/dev/null
done

# --- Optional Direct VPC egress (needed for PRIVATE / PSC connections) --------
NET_FLAGS=()
if [ -n "${VPC_SUBNET:-}" ]; then
  NET_FLAGS=(--network "$VPC_NETWORK" --subnet "$VPC_SUBNET")
fi

gcloud run deploy "$SERVICE" \
  --source "$(dirname "$0")/.." \
  --region "$REGION" \
  --service-account "$SA" \
  "${NET_FLAGS[@]}" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,ALLOYDB_REGION=$REGION,ALLOYDB_CLUSTER=$ALLOYDB_CLUSTER,ALLOYDB_INSTANCE=$ALLOYDB_INSTANCE,ALLOYDB_IP_TYPE=$IP_TYPE,DB_NAME=$DB_NAME,DB_USER=$DB_USER,GEMINI_MODEL=$GEMINI_MODEL" \
  --set-secrets "DB_PASSWORD=pantrypal-db-password:latest" \
  --no-allow-unauthenticated \
  --memory 1Gi \
  --quiet

echo
echo "Open it:  gcloud run services proxy $SERVICE --region $REGION --port 8080"
echo "Then Web Preview → Preview on port 8080"
