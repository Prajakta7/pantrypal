.RECIPEPREFIX = >
SHELL := /bin/bash
.PHONY: install test run alloydb recalls deploy open jev-secret cleanup

install:     ## Create .venv and install dependencies
> python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

test:        ## Run unit tests (no cloud needed)
> .venv/bin/python -m pytest -q

run:         ## Run locally using .env
> set -a && . ./.env && set +a && .venv/bin/uvicorn app.main:app --reload --port 8080

alloydb:     ## Create the AlloyDB free trial cluster (needs DB_PASSWORD)
> bash scripts/01_create_alloydb.sh

recalls:     ## Load the past year of FDA food recalls into BigQuery (re-run weekly)
> bash scripts/02_load_recalls.sh

deploy:      ## Deploy to Cloud Run (needs DB_PASSWORD)
> bash deploy/deploy_cloud_run.sh

open:        ## Open your private app on localhost:8080
> source scripts/env.sh && gcloud run services proxy pantrypal --region $$REGION --port 8080

jev-secret:  ## (Optional) Store a TypeSafe AI key for Jev diet labels
> bash scripts/03_setup_jev_secret.sh

cleanup:     ## Delete cloud resources (erases your data)
> bash scripts/99_cleanup.sh
