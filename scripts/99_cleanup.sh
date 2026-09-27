#!/usr/bin/env bash
# Delete everything this project created, so nothing carries over into paid usage.
source "$(dirname "$0")/env.sh"
read -r -p "Delete AlloyDB cluster '$ALLOYDB_CLUSTER', the BigQuery dataset '$BQ_DATASET', the Cloud Run app and secrets? This erases your pantry data. (yes/no) " ok
[ "$ok" = "yes" ] || exit 0
gcloud run services delete pantrypal --region="$REGION" --quiet || true
gcloud alloydb clusters delete "$ALLOYDB_CLUSTER" --region="$REGION" --force --quiet || true
bq rm -r -f -d "$PROJECT_ID:$BQ_DATASET" || true
gcloud secrets delete pantrypal-db-password --quiet || true
gcloud secrets delete typesafe-jev-api-key --quiet || true
echo "Done."
