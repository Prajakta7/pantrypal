#!/usr/bin/env bash
# =============================================================================
# Create an AlloyDB cluster with AlloyDB AI enabled (your own project).
# Run in Cloud Shell:  DB_PASSWORD='<choose one>' bash scripts/01_create_alloydb.sh
#
# Uses the AlloyDB 30-day free trial by default. Delete it when you're done:
#    bash scripts/99_cleanup.sh
# Using a Google Skills AlloyDB lab instead? Skip this script (see README).
# =============================================================================
set -euo pipefail
source "$(dirname "$0")/env.sh"
: "${DB_PASSWORD:?Set DB_PASSWORD first}"

# --- APIs --------------------------------------------------------------------
gcloud services enable alloydb.googleapis.com compute.googleapis.com \
  servicenetworking.googleapis.com aiplatform.googleapis.com \
  discoveryengine.googleapis.com storage.googleapis.com

# --- Private services access (AlloyDB lives on a private range in your VPC) ---
gcloud compute addresses describe alloydb-range --global >/dev/null 2>&1 || \
  gcloud compute addresses create alloydb-range --global --purpose=VPC_PEERING \
    --prefix-length=16 --network="$VPC_NETWORK"
gcloud services vpc-peerings connect --service=servicenetworking.googleapis.com \
  --ranges=alloydb-range --network="$VPC_NETWORK" || true   # ok if it already exists

# --- Cluster + primary instance ----------------------------------------------
# Free trial by default: 30 days at no cost (8 vCPU primary). Set ALLOYDB_TRIAL=false
# for a regular paid cluster with a smaller 2 vCPU instance.
if [ "${ALLOYDB_TRIAL:-true}" = "true" ]; then
  SUBSCRIPTION=(--subscription-type=TRIAL); CPUS=8
  echo "Creating a 30-day FREE TRIAL cluster. Upgrade or delete it before the trial ends."
else
  SUBSCRIPTION=(--subscription-type=STANDARD); CPUS=2
fi

gcloud alloydb clusters create "$ALLOYDB_CLUSTER" \
  --region="$REGION" --network="$VPC_NETWORK" --password="$DB_PASSWORD" \
  "${SUBSCRIPTION[@]}"

# Flags turn on AlloyDB AI: model calls, faster embeddings, AI functions, ScaNN.
# Public IP lets Cloud Run connect through the AlloyDB connector (TLS + IAM);
# no authorized networks are opened. Outbound public IP lets AlloyDB call
# external model APIs such as TypeSafe AI's Jev (optional feature).
# alloydb.iam_authentication lets AlloyDB read BigQuery tables (bigquery_fdw).
gcloud alloydb instances create "$ALLOYDB_INSTANCE" \
  --cluster="$ALLOYDB_CLUSTER" --region="$REGION" \
  --instance-type=PRIMARY --cpu-count="$CPUS" \
  --assign-inbound-public-ip=ASSIGN_IPV4 \
  --outbound-public-ip \
  --database-flags="google_ml_integration.enable_model_support=on,google_ml_integration.enable_faster_embedding_generation=on,google_ml_integration.enable_preview_ai_functions=on,google_ml_integration.enable_ai_query_engine=on,google_ml_integration.enable_ai_function_acceleration=on,scann.enable_preview_features=on,alloydb.iam_authentication=on"

# --- Let AlloyDB call Gemini Enterprise Agent Platform models and the ranker ---
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
AGENT="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-alloydb.iam.gserviceaccount.com"
for ROLE in roles/aiplatform.user roles/discoveryengine.viewer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="$AGENT" --role="$ROLE" \
    --condition=None --quiet >/dev/null
done

echo "✅ AlloyDB ready. Next: AlloyDB Studio → CREATE DATABASE $DB_NAME; then run sql/01_schema.sql"
