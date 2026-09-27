#!/usr/bin/env bash
# =============================================================================
# (Optional) Store your TypeSafe AI key for Jev and let AlloyDB read it.
#   TYPESAFE_API_KEY='<key>' bash scripts/03_setup_jev_secret.sh
# Get a key at https://typesafe.ai. Check their pricing before large runs.
# Then run sql/07_jev_setup.sql in AlloyDB Studio.
# =============================================================================
set -euo pipefail
source "$(dirname "$0")/env.sh"
: "${TYPESAFE_API_KEY:?Set TYPESAFE_API_KEY}"

gcloud services enable secretmanager.googleapis.com
if gcloud secrets describe typesafe-jev-api-key >/dev/null 2>&1; then
  printf '%s' "$TYPESAFE_API_KEY" | gcloud secrets versions add typesafe-jev-api-key --data-file=-
else
  gcloud secrets create typesafe-jev-api-key --replication-policy=automatic
  printf '%s' "$TYPESAFE_API_KEY" | gcloud secrets versions add typesafe-jev-api-key --data-file=-
fi

# AlloyDB (not the app) calls Jev, so AlloyDB's service agent needs the secret
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding typesafe-jev-api-key \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-alloydb.iam.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor --quiet >/dev/null

# AlloyDB needs outbound internet to reach api.typesafe.ai
gcloud alloydb instances update "$ALLOYDB_INSTANCE" --cluster="$ALLOYDB_CLUSTER" \
  --region="$REGION" --outbound-public-ip --quiet || \
  echo "⚠️  Couldn't enable outbound public IP automatically. Enable it on the instance in the console."

echo "✅ Next: replace <YOUR_PROJECT_ID> in sql/07_jev_setup.sql with $PROJECT_ID and run it in AlloyDB Studio"
