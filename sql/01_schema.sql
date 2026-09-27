-- =============================================================================
-- 1. Tables and AI extensions
-- AlloyDB Studio: first run  CREATE DATABASE pantrypal;  (connected to 'postgres'),
-- then reconnect to database 'pantrypal' and run this file.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS google_ml_integration CASCADE;  -- ai.embedding(), ai.if()
CREATE EXTENSION IF NOT EXISTS vector;                         -- vector type, <=> operator

-- What's in your kitchen
CREATE TABLE IF NOT EXISTS pantry_items (
    item_id     bigserial PRIMARY KEY,
    name        text NOT NULL,
    brand       text,                         -- optional; makes recall checks more precise
    category    text NOT NULL DEFAULT 'Other'
                CHECK (category IN ('Produce', 'Dairy & eggs', 'Meat & fish', 'Grains & bread',
                                    'Dals & lentils', 'Spices & masalas', 'Canned & jarred', 'Frozen',
                                    'Dry fruits & seeds', 'Snacks', 'Condiments', 'Other')),
    quantity    numeric,
    unit        text,
    expires_on  date,
    added_on    date NOT NULL DEFAULT current_date,
    used_on     date,                         -- set when used up; NULL = still in the pantry
    source      text DEFAULT 'app'            -- 'app' = yours, 'demo' = optional demo pantry
);
CREATE INDEX IF NOT EXISTS pantry_active_idx ON pantry_items (expires_on) WHERE used_on IS NULL;

-- Recipe collection, searchable by meaning (embedding) and keyword (tsvector)
CREATE TABLE IF NOT EXISTS recipes (
    recipe_id    bigserial PRIMARY KEY,
    title        text NOT NULL UNIQUE,
    cuisine      text,
    minutes      integer NOT NULL CHECK (minutes > 0),
    servings     integer DEFAULT 2,
    ingredients  text[] NOT NULL,             -- plain names, used to match your pantry
    steps        text NOT NULL,
    -- Diet labels: hand-checked for starter recipes, AI-tagged for recipes you add
    vegetarian       boolean,             -- no meat, fish or eggs
    eggetarian       boolean,             -- vegetarian, eggs allowed
    non_veg          boolean,             -- eggs and chicken allowed, no other meat or fish
    gluten_free      boolean,
    dairy_free       boolean,
    nut_free         boolean,
    tagged_by    text,                        -- 'starter', 'gemini' (ai.if) or 'jev'
    source       text DEFAULT 'starter',      -- 'starter' or 'app'
    search_text  text,                        -- what gets embedded and keyword-indexed
    search_tsv   tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(search_text, ''))) STORED,
    embedding    vector(768)                  -- filled automatically (03_auto_embeddings.sql)
);
CREATE INDEX IF NOT EXISTS recipes_tsv_idx ON recipes USING GIN (search_tsv);

-- Your saved diet: every recipe suggestion follows it (one row)
CREATE TABLE IF NOT EXISTS preferences (
    id          smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    diets       text[] NOT NULL DEFAULT '{}',   -- e.g. {vegetarian} or {eggetarian,nut_free}
    avoid       text[] NOT NULL DEFAULT '{}',   -- ingredients you skip, e.g. {mushroom,coconut}
    updated_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO preferences (id) VALUES (1) ON CONFLICT DO NOTHING;
