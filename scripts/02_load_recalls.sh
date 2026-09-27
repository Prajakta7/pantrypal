#!/usr/bin/env bash
# =============================================================================
# Load recent FDA food recalls into BigQuery, and let AlloyDB read them.
# Run in Cloud Shell from the repo root:   make recalls
# Re-run weekly to refresh (openFDA updates weekly). Takes about a minute.
# =============================================================================
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$(dirname "$0")/.."

gcloud services enable bigquery.googleapis.com bigquerystorage.googleapis.com

# --- 1. BigQuery dataset in the SAME region as AlloyDB -------------------------
bq --location="$REGION" mk --dataset --description "PantryPal: FDA food recalls" \
   "$PROJECT_ID:$BQ_DATASET" 2>/dev/null || echo "Dataset $BQ_DATASET already exists"

# --- 2. Download the last 2 years of recalls from openFDA ----------------------
python3 scripts/load_recalls.py --years 2 --out /tmp/pantrypal_recalls.ndjson

# --- 3. Replace the BigQuery table with the fresh data -------------------------
bq load --replace --source_format=NEWLINE_DELIMITED_JSON \
   "$PROJECT_ID:$BQ_DATASET.food_recalls" /tmp/pantrypal_recalls.ndjson scripts/recalls_schema.json
bq query --use_legacy_sql=false --location="$REGION" \
   "SELECT status, count(*) AS recalls, max(report_date) AS newest FROM \`$PROJECT_ID.$BQ_DATASET.food_recalls\` GROUP BY status"

# --- 4. Let AlloyDB's service agent read BigQuery (needed by bigquery_fdw) -----
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
AGENT="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-alloydb.iam.gserviceaccount.com"
for ROLE in roles/bigquery.dataViewer roles/bigquery.user roles/bigquery.readSessionUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="$AGENT" --role="$ROLE" \
    --condition=None --quiet >/dev/null
done

echo
echo "✅ Recalls loaded. Next (once): replace <YOUR_PROJECT_ID> in sql/05_bigquery_recalls.sql"
echo "   with $PROJECT_ID and run it in AlloyDB Studio."
