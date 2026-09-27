#!/usr/bin/env bash
# Shared settings for all scripts. Override by exporting before running.
export PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
export REGION="${REGION:-us-central1}"
export ALLOYDB_CLUSTER="${ALLOYDB_CLUSTER:-pantrypal-cluster}"
export ALLOYDB_INSTANCE="${ALLOYDB_INSTANCE:-pantrypal-primary}"
export DB_NAME="${DB_NAME:-pantrypal}"
export DB_USER="${DB_USER:-postgres}"
export VPC_NETWORK="${VPC_NETWORK:-default}"
export BQ_DATASET="${BQ_DATASET:-pantrypal}"
