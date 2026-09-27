-- =============================================================================
-- 5. Read FDA recalls from BigQuery, live, inside AlloyDB (zero-ETL)
-- Run AFTER `make recalls` has loaded the BigQuery table.
-- Replace <YOUR_PROJECT_ID> below, then run in AlloyDB Studio (db: pantrypal).
--
-- The bigquery_fdw extension is in Preview. A foreign table stores no data:
-- each query is sent to BigQuery, with WHERE filters, COUNT/SUM/GROUP BY and
-- LIMIT pushed down so BigQuery does the heavy lifting.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS bigquery_fdw;

CREATE SERVER IF NOT EXISTS bigquery_server FOREIGN DATA WRAPPER bigquery_fdw;

-- The app connects as 'postgres'. Add a mapping for any other database user you use.
CREATE USER MAPPING IF NOT EXISTS FOR postgres SERVER bigquery_server;

CREATE FOREIGN TABLE IF NOT EXISTS food_recalls (
    recall_number          varchar,
    report_date            varchar,   -- YYYY-MM-DD text, so it compares and sorts correctly
    recall_initiation_date varchar,
    status                 varchar,   -- Ongoing, Completed, Terminated
    classification         varchar,   -- Class I (most serious), II, III
    recalling_firm         varchar,
    product_description    varchar,
    reason_for_recall      varchar,
    distribution_pattern   varchar,
    code_info              varchar,   -- lot numbers and dates to compare with your package
    state                  varchar
) SERVER bigquery_server OPTIONS (
    project '<YOUR_PROJECT_ID>',
    dataset 'pantrypal',
    table   'food_recalls'
);

-- --- Try it ----------------------------------------------------------------------

-- Counted in BigQuery (aggregate pushdown)
SELECT classification, count(*) AS ongoing_recalls
FROM food_recalls
WHERE status = 'Ongoing'
GROUP BY classification
ORDER BY classification;

-- The most recent recalls
SELECT report_date, classification, left(product_description, 80) AS product, left(reason_for_recall, 60) AS reason
FROM food_recalls
ORDER BY report_date DESC
LIMIT 10;

-- A federated join: your AlloyDB pantry against BigQuery recalls, in one query.
-- (The app does smarter word matching in Python; this shows the idea in SQL.)
SELECT p.name AS pantry_item, r.report_date, r.classification, left(r.product_description, 90) AS recalled_product
FROM pantry_items p
JOIN food_recalls r ON r.product_description ILIKE '%' || p.name || '%'
WHERE p.used_on IS NULL
  AND r.status = 'Ongoing'
  AND r.report_date >= to_char(current_date - 365, 'YYYY-MM-DD')
ORDER BY r.report_date DESC
LIMIT 20;
